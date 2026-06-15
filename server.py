import io
import os
import json
import base64
import threading
import zipfile
from functools import wraps

from json import JSONEncoder
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, jsonify, Response, session
from werkzeug.utils import secure_filename
from config_parser import TemplateParser, ConfigParser, PROJECTS_PATH, BRANDING_PATH, BRANDABLE_SCREENS, BRANDABLE_SCREEN_MAP
import logging
from datetime import datetime
import secrets
from pathlib import Path
from flask_cors import CORS


class ConfigEncoder(JSONEncoder):
    def default(self, o):
        try:
            return o.__json__()
        except Exception:
            return o.__dict__


REAL_PATH = os.path.dirname(os.path.realpath(__file__))


class WebServer(Flask):
    photobooth = None
    configParser = None
    templateParser = None
    logging = None

    def setup_photobooth(self, photobooth, logging):
        self.photobooth = photobooth
        self.logging = logging

        logging.debug("Setting Up Config Parser")
        try:
            self.configParser = self.photobooth.configParser
        except Exception:
            logging.debug("Got a local config object")
            self.configParser = ConfigParser(logging)
        else:
            logging.debug("Got a photobooth config object")

        logging.debug("Setting Up Template Parser")
        try:
            self.templateParser = self.photobooth.layoutParser
        except Exception:
            logging.debug("Got a local layout object")
            self.templateParser = TemplateParser(self.configParser.config.templates_file_path)
            self.templateParser.readCardConfiguration()
        else:
            logging.debug("Got a photobooth layout object")


app = WebServer(__name__, template_folder='web_templates')
CORS(app)

SECRET_FILE_PATH = Path(".flask_secret")
try:
    with SECRET_FILE_PATH.open("r") as secret_file:
        app.secret_key = secret_file.read()
        app.config['SECRET_KEY'] = app.secret_key
except FileNotFoundError:
    with SECRET_FILE_PATH.open("w") as secret_file:
        app.secret_key = secrets.token_hex(32)
        secret_file.write(app.secret_key)
        app.config['SECRET_KEY'] = app.secret_key


# ---------------------------------------------------------------------------
# Auth + Project unlock
# ---------------------------------------------------------------------------

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        cfg = app.configParser.config if app.configParser else None
        if cfg and cfg.webserver_user and cfg.webserver_password:
            auth = request.authorization
            if not auth or auth.username != cfg.webserver_user or auth.password != cfg.webserver_password:
                return Response(
                    'Authentication required',
                    401,
                    {'WWW-Authenticate': 'Basic realm="Photobooth"'}
                )
        return f(*args, **kwargs)
    return decorated


def _project_unlocked(name):
    if not app.configParser:
        return True
    if not app.configParser.project_has_password(name):
        return True
    return name in session.get('unlocked_projects', [])


def requires_active_project_unlock(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if app.configParser:
            active = app.configParser.config.active_project
            if not _project_unlocked(active):
                return redirect(url_for('ui_project_unlock',
                                        name=active, next=request.path))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def _inject_project_context():
    active = "Default"
    locked = False
    active_branding = "Default"
    if app.configParser:
        active = app.configParser.config.active_project
        locked = app.configParser.project_has_password(active)
        active_branding = app.configParser.config.active_branding
    return dict(active_project=active, active_project_locked=locked, active_branding=active_branding)


def _do_select_project(name):
    """Switch active project. Uses photobooth.switch_project() when real hardware is present,
    falls back to direct configParser/templateParser calls for standalone mode."""
    if app.photobooth and hasattr(app.photobooth, 'camera') and app.photobooth.camera:
        try:
            app.photobooth.switch_project(name)
            return
        except Exception as e:
            logging.warning(f"switch_project error: {e}")
    # Standalone or fallback: update config and templateParser directly
    app.configParser.set_active_project(name)
    if app.templateParser:
        app.templateParser.set_path(app.configParser.config.templates_file_path)


# ---------------------------------------------------------------------------
# JSON API — config
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def iamabox():
    return jsonify({"photobox": "true"})


@app.route('/config', methods=['GET', 'POST'])
def api_config():
    if request.method == "GET":
        config = app.configParser.config
        return json.dumps(config, indent=4, cls=ConfigEncoder)
    elif request.method == "POST":
        data = request.get_json()
        app.configParser.parseData(data)
        config = app.configParser.config
        return json.dumps(config, indent=4, cls=ConfigEncoder)


@app.route("/config/save", methods=["GET"])
def api_save_config():
    app.configParser.writeConfig()
    return jsonify({"msg": "saved"})


# ---------------------------------------------------------------------------
# JSON API — layouts
# ---------------------------------------------------------------------------

@app.route('/projects', methods=['GET'])
def api_list_projects():
    projects = app.configParser.list_projects() if app.configParser else []
    active = app.configParser.config.active_project if app.configParser else "Default"
    return jsonify({"projects": projects, "active": active})


@app.route('/project/select', methods=['POST'])
@requires_auth
def api_project_select():
    name = (request.get_json() or {}).get("name", "")
    if not name or name not in (app.configParser.list_projects() if app.configParser else []):
        return jsonify({"msg": "not found"}), 404
    if not _project_unlocked(name):
        return jsonify({"msg": "locked"}), 403
    _do_select_project(name)
    return jsonify({"msg": "activated", "project": name})


@app.route('/layouts', methods=['GET'])
@requires_active_project_unlock
def api_list_layouts():
    layouts = app.templateParser.layout
    return json.dumps(layouts, indent=4, cls=ConfigEncoder)


@app.route("/layout/save", methods=["GET"])
@requires_active_project_unlock
def api_save_layout():
    app.templateParser.writeCardConfig()
    if app.photobooth:
        try:
            app.photobooth.to_PowerOn()
        except Exception:
            pass
    return jsonify({"msg": "success"})


@app.route("/layout/edit/<id>", methods=["POST"])
@requires_active_project_unlock
def api_edit_layout(id):
    data = request.get_json()
    app.templateParser.parseData(data)
    if app.photobooth:
        try:
            app.photobooth.to_PowerOn()
        except Exception:
            pass
    return jsonify({"msg": "success"})


# ---------------------------------------------------------------------------
# JSON API — camera live apply
# ---------------------------------------------------------------------------

@app.route("/camera/apply", methods=["POST"])
@requires_auth
@requires_active_project_unlock
def api_camera_apply():
    data = request.get_json() or {}
    app.configParser.parseData(data)
    cfg = app.configParser.config

    if app.photobooth and hasattr(app.photobooth, 'camera') and app.photobooth.camera:
        try:
            app.photobooth.camera.apply_settings(
                iso=cfg.camera_iso,
                awb_mode=cfg.camera_awb_mode,
                exposure_mode=cfg.camera_exposure_mode,
                shutterspeed=cfg.camera_shutterspeed,
                aperture=cfg.camera_aperture,
                flip_h=cfg.flip_screen_h,
                flip_v=cfg.flip_screen_v,
            )
            return jsonify({"msg": "applied"})
        except Exception as e:
            return jsonify({"msg": "error", "detail": str(e)}), 500
    return jsonify({"msg": "no camera available"})


# ---------------------------------------------------------------------------
# JSON API — status
# ---------------------------------------------------------------------------

@app.route("/status", methods=["GET"])
def api_status():
    state = "unknown"
    if app.photobooth:
        try:
            state = app.photobooth.state
        except Exception:
            pass
    cfg = app.configParser.config if app.configParser else None
    return jsonify({
        "state": state,
        "photo_resolution": f"{cfg.photo_w}x{cfg.photo_h}" if cfg else "?",
        "screen_resolution": f"{cfg.screen_w}x{cfg.screen_h}" if cfg else "?",
        "print_enabled": cfg.printPicsEnable if cfg else False,
        "debug": cfg.debug if cfg else False,
    })


# ---------------------------------------------------------------------------
# JSON API — button simulation (for testing without physical buttons)
# ---------------------------------------------------------------------------

@app.route("/button/<int:num>", methods=["POST"])
def api_button(num):
    if not app.photobooth:
        return jsonify({"msg": "no photobooth"}), 503
    try:
        if num == 1:
            app.photobooth.Button1pressed(None)
        elif num == 2:
            app.photobooth.Button2pressed(None)
        else:
            return jsonify({"msg": "invalid button"}), 400
        return jsonify({"msg": f"button {num} pressed", "state": app.photobooth.state})
    except Exception as e:
        return jsonify({"msg": "error", "detail": str(e)}), 500


# ---------------------------------------------------------------------------
# JSON API — images
# ---------------------------------------------------------------------------

@app.route("/systemImage/<name>", methods=["GET"])
def api_get_system_image(name):
    return send_from_directory(app.configParser.config.screens_abs_file_path, name)


@app.route("/upload/systemImage", methods=["POST"])
@requires_auth
def api_upload_system_image():
    data = request.get_json()
    if data and data.get("name") and data.get("image_data"):
        dest = os.path.join(app.configParser.config.screens_abs_file_path, data["name"] + ".png")
        with open(dest, "wb") as fh:
            con_basecode = data["image_data"].split(",")[1]
            fh.write(base64.urlsafe_b64decode(str.encode(con_basecode)))
        if app.photobooth:
            try:
                app.photobooth.to_PowerOn()
            except Exception:
                pass
        return jsonify({"msg": "uploaded"})
    return jsonify({"msg": "missing fields"}), 400


@app.route("/photo/<name>", methods=["GET"])
@requires_auth
@requires_active_project_unlock
def api_get_photo(name):
    return send_from_directory(app.configParser.config.photo_abs_file_path, name)


@app.route("/photo/<name>/delete", methods=["POST"])
@requires_auth
@requires_active_project_unlock
def api_delete_photo(name):
    photo_dir = app.configParser.config.photo_abs_file_path
    filepath = os.path.realpath(os.path.join(photo_dir, os.path.basename(name)))
    if not filepath.startswith(os.path.realpath(photo_dir)):
        return jsonify({"msg": "invalid path"}), 400
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"msg": "deleted"})
    return jsonify({"msg": "not found"}), 404


@app.route("/photos", methods=["GET"])
@requires_auth
@requires_active_project_unlock
def api_list_photos():
    photo_dir = app.configParser.config.photo_abs_file_path
    files = []
    if os.path.exists(photo_dir):
        files = sorted(
            [f for f in os.listdir(photo_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))],
            reverse=True
        )
    return jsonify(files)


# ---------------------------------------------------------------------------
# JSON API — photobooth control
# ---------------------------------------------------------------------------

def _do_restart():
    try:
        app.photobooth.to_PowerOn()
    except Exception as e:
        logging.warning(f"Restart error: {e}")

@app.route('/restart', methods=['GET'])
@requires_auth
def api_restart_photobooth():
    if app.photobooth:
        threading.Thread(target=_do_restart, daemon=True).start()
    return jsonify({"msg": "Restarting…"})


# ---------------------------------------------------------------------------
# UI routes
# ---------------------------------------------------------------------------

@app.route("/ui", methods=["GET"])
@app.route("/ui/", methods=["GET"])
@requires_auth
def ui_index():
    state = "offline"
    if app.photobooth:
        try:
            state = app.photobooth.state
        except Exception:
            pass
    cfg = app.configParser.config
    return render_template("index.html", state=state, cfg=cfg)


@app.route("/ui/config", methods=["GET"])
@requires_auth
def ui_config():
    cfg = app.configParser.config
    msg = request.args.get("msg")
    return render_template("config.html", cfg=cfg, msg=msg)


@app.route("/ui/config/save", methods=["POST"])
@requires_auth
def ui_config_save():
    data = {
        "photo_w": request.form.get("photo_w"),
        "photo_h": request.form.get("photo_h"),
        "screen_w": request.form.get("screen_w"),
        "screen_h": request.form.get("screen_h"),
        "flip_screen_h": "on" if request.form.get("flip_screen_h") else "false",
        "flip_screen_v": "on" if request.form.get("flip_screen_v") else "false",
        "pin_button_left": request.form.get("pin_button_left"),
        "pin_button_right": request.form.get("pin_button_right"),
        "debug": "on" if request.form.get("debug") else "false",
        "printPicsEnable": "on" if request.form.get("printPicsEnable") else "false",
        "webserver_user": request.form.get("webserver_user", ""),
        "webserver_password": request.form.get("webserver_password", ""),
    }
    app.configParser.parseData(data)
    app.configParser.writeConfig()
    return redirect(url_for("ui_config", msg="saved"))


@app.route("/ui/camera", methods=["GET"])
@requires_auth
@requires_active_project_unlock
def ui_camera():
    cfg = app.configParser.config
    wb_modes = ["Auto", "Daylight", "Shadow", "Cloudy", "Tungsten", "Fluorescent", "Flash", "Manual"]
    exposure_modes = ["P", "Tv", "Av", "Manual", "Auto"]
    shutter_speeds = [
        "bulb",
        "30", "25", "20", "15", "13", "10.3", "8", "6.3", "5", "4", "3.2", "2.5", "2", "1.6", "1.3", "1",
        "0.8", "0.6", "0.5", "0.4", "0.3",
        "1/4", "1/5", "1/6", "1/8", "1/10", "1/13", "1/15", "1/20", "1/25", "1/30",
        "1/40", "1/50", "1/60", "1/80", "1/100", "1/125", "1/160", "1/200", "1/250",
        "1/320", "1/400", "1/500", "1/640", "1/800", "1/1000", "1/1250", "1/1600",
        "1/2000", "1/2500", "1/3200", "1/4000",
    ]
    apertures = ["5", "5.6", "6.3", "7.1", "8", "9", "10", "11", "13", "14", "16", "18", "20", "22", "25"]
    iso_values = ["Auto", "100", "125", "160", "200", "250", "320", "400", "500", "640",
                  "800", "1000", "1250", "1600", "3200", "6400", "12800", "25600"]
    msg = request.args.get("msg")
    return render_template("camera.html", cfg=cfg, wb_modes=wb_modes,
                           exposure_modes=exposure_modes, shutter_speeds=shutter_speeds,
                           apertures=apertures, iso_values=iso_values, msg=msg)


@app.route("/ui/camera/save", methods=["POST"])
@requires_auth
@requires_active_project_unlock
def ui_camera_save():
    data = {
        "camera_exposure_mode": request.form.get("camera_exposure_mode"),
        "camera_awb_mode": request.form.get("camera_awb_mode"),
        "camera_iso": request.form.get("camera_iso"),
        "camera_shutterspeed": request.form.get("camera_shutterspeed"),
        "camera_aperture": request.form.get("camera_aperture"),
        "flip_screen_h": "on" if request.form.get("flip_screen_h") else "false",
        "flip_screen_v": "on" if request.form.get("flip_screen_v") else "false",
    }
    app.configParser.parseData(data)
    # Camera settings go into project.ini, not config.ini
    app.configParser.write_project_camera()
    # Global settings (flips) still into config.ini
    app.configParser.writeConfig()
    return redirect(url_for("ui_camera", msg="saved"))


@app.route("/ui/layouts", methods=["GET"])
@requires_auth
@requires_active_project_unlock
def ui_layouts():
    layouts = app.templateParser.layout
    msg = request.args.get("msg")
    return render_template("layouts.html", layouts=layouts, msg=msg)


@app.route("/ui/layouts/editor/<int:layout_id>", methods=["GET"])
@requires_auth
@requires_active_project_unlock
def ui_layout_editor(layout_id):
    if layout_id < 1 or layout_id > len(app.templateParser.layout):
        return redirect(url_for("ui_layouts"))
    layout = app.templateParser.layout[layout_id - 1]
    return render_template("layout_editor.html", layout=layout, layout_id=layout_id)


@app.route("/ui/layouts/save/<int:layout_id>", methods=["POST"])
@requires_auth
@requires_active_project_unlock
def ui_layouts_save(layout_id):
    pic_count = int(request.form.get("picCount", 1))
    layout_in_fg = bool(request.form.get("layoutInForeground"))

    pictures = []
    for i in range(pic_count):
        pictures.append({
            "resizeX": request.form.get(f"pic_{i}_resizeX", 800),
            "resizeY": request.form.get(f"pic_{i}_resizeY", 600),
            "posX": request.form.get(f"pic_{i}_posX", 0),
            "posY": request.form.get(f"pic_{i}_posY", 0),
            "rotate": request.form.get(f"pic_{i}_rotate", 0),
            "color": request.form.get(f"pic_{i}_color", "color"),
        })

    data = {
        "id": str(layout_id),
        "picCount": pic_count,
        "layoutInForeground": layout_in_fg,
        "pictures": pictures,
    }

    # Handle template image upload
    template_file = request.files.get("template_image")
    if template_file and template_file.filename:
        raw = template_file.read()
        b64 = base64.b64encode(raw).decode()
        ext = template_file.content_type or "image/png"
        data["new_image"] = f"data:{ext};base64,{b64}"

    app.templateParser.parseData(data)
    if app.photobooth:
        try:
            app.photobooth.to_PowerOn()
        except Exception:
            pass
    return redirect(url_for("ui_layouts", msg="saved"))


@app.route("/ui/screens", methods=["GET"])
@requires_auth
def ui_screens():
    screens_dir = app.configParser.config.screens_abs_file_path
    screens = []
    if os.path.exists(screens_dir):
        screens = sorted([f for f in os.listdir(screens_dir) if f.lower().endswith('.png')])
    msg = request.args.get("msg")
    return render_template("screens.html", screens=screens, msg=msg)


@app.route("/ui/screens/upload", methods=["POST"])
@requires_auth
def ui_screens_upload():
    screen_name = request.form.get("screen_name", "").strip()
    screen_file = request.files.get("screen_file")
    if not screen_name or not screen_file or not screen_file.filename:
        return redirect(url_for("ui_screens", msg="error_missing"))

    # Strip extension from name if provided, always save as .png
    base = os.path.splitext(secure_filename(screen_name))[0]
    dest = os.path.join(app.configParser.config.screens_abs_file_path, base + ".png")
    screen_file.save(dest)

    if app.photobooth:
        try:
            app.photobooth.to_PowerOn()
        except Exception:
            pass
    return redirect(url_for("ui_screens", msg="uploaded"))


@app.route("/ui/photos", methods=["GET"])
@requires_auth
@requires_active_project_unlock
def ui_photos():
    photo_dir = app.configParser.config.photo_abs_file_path
    photos = []
    if os.path.exists(photo_dir):
        photos = sorted(
            [f for f in os.listdir(photo_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))],
            reverse=True
        )
    msg = request.args.get("msg")
    return render_template("photos.html", photos=photos, msg=msg)


# ---------------------------------------------------------------------------
# UI — Projects
# ---------------------------------------------------------------------------

@app.route("/ui/projects", methods=["GET"])
@requires_auth
def ui_projects():
    active = app.configParser.config.active_project
    projects = []
    for name in app.configParser.list_projects():
        photo_dir = os.path.join(PROJECTS_PATH, name, "Photos")
        count = 0
        if os.path.isdir(photo_dir):
            count = len([f for f in os.listdir(photo_dir)
                         if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        projects.append({
            "name": name,
            "active": name == active,
            "has_password": app.configParser.project_has_password(name),
            "unlocked": _project_unlocked(name),
            "photo_count": count,
            "branding": app.configParser.get_project_branding(name),
        })
    brandings = app.configParser.list_brandings()
    msg = request.args.get("msg")
    return render_template("projects.html", projects=projects, brandings=brandings, msg=msg)


@app.route("/ui/projects/select", methods=["POST"])
@requires_auth
def ui_project_select():
    name = request.form.get("name", "").strip()
    if not name or name not in app.configParser.list_projects():
        return redirect(url_for("ui_projects", msg="not_found"))
    if not _project_unlocked(name):
        return redirect(url_for("ui_project_unlock", name=name,
                                next=url_for("ui_project_select_do", name=name)))
    _do_select_project(name)
    return redirect(url_for("ui_projects", msg="activated"))


@app.route("/ui/projects/select/<name>", methods=["GET"])
@requires_auth
def ui_project_select_do(name):
    """GET target after unlock — activates the project."""
    if not name or name not in app.configParser.list_projects():
        return redirect(url_for("ui_projects", msg="not_found"))
    _do_select_project(name)
    return redirect(url_for("ui_projects", msg="activated"))


@app.route("/ui/projects/create", methods=["POST"])
@requires_auth
def ui_project_create():
    raw = request.form.get("name", "").strip()
    name = secure_filename(raw)
    if not name:
        return redirect(url_for("ui_projects", msg="invalid_name"))
    if name in app.configParser.list_projects():
        return redirect(url_for("ui_projects", msg="exists"))
    app.configParser.create_project(name)
    return redirect(url_for("ui_projects", msg="created"))


@app.route("/ui/projects/<name>/password", methods=["POST"])
@requires_auth
def ui_project_password(name):
    if name not in app.configParser.list_projects():
        return redirect(url_for("ui_projects", msg="not_found"))
    password = request.form.get("password", "")
    app.configParser.set_project_password(name, password)
    return redirect(url_for("ui_projects", msg="password_set"))


@app.route("/ui/projects/<name>/delete", methods=["POST"])
@requires_auth
def ui_project_delete(name):
    if name == app.configParser.config.active_project:
        return redirect(url_for("ui_projects", msg="delete_active"))
    if app.configParser.project_has_password(name) and not _project_unlocked(name):
        return redirect(url_for("ui_project_unlock", name=name, next=request.path))
    try:
        app.configParser.delete_project(name)
    except Exception as e:
        logging.warning(f"delete_project error: {e}")
    return redirect(url_for("ui_projects", msg="deleted"))


@app.route("/ui/projects/unlock", methods=["GET", "POST"])
@requires_auth
def ui_project_unlock():
    name = request.args.get("name") or request.form.get("name", "")
    next_url = request.args.get("next") or request.form.get("next", url_for("ui_projects"))
    error = None

    if request.method == "POST":
        password = request.form.get("password", "")
        if app.configParser.check_project_password(name, password):
            unlocked = session.get("unlocked_projects", [])
            if name not in unlocked:
                unlocked.append(name)
            session["unlocked_projects"] = unlocked
            return redirect(next_url)
        error = "Falsches Passwort"

    return render_template("unlock.html", name=name, next=next_url, error=error)


@app.route("/ui/projects/<name>/branding", methods=["POST"])
@requires_auth
def ui_project_set_branding(name):
    branding = request.form.get("branding", "Default")
    app.configParser.set_project_branding(name, branding)
    if name == app.configParser.config.active_project and app.photobooth:
        try:
            app.photobooth.to_PowerOn()
        except Exception:
            pass
    return redirect(url_for("ui_projects", msg="branding_set"))


# ---------------------------------------------------------------------------
# UI — Brandings
# ---------------------------------------------------------------------------

@app.route('/ui/brandings')
@requires_auth
def ui_brandings():
    brandings = app.configParser.list_brandings()
    branding_info = []
    for name in brandings:
        d = os.path.join(BRANDING_PATH, name)
        count = len([f for f in os.listdir(d) if f.lower().endswith('.png')]) if os.path.isdir(d) else 0
        branding_info.append({"name": name, "count": count})
    return render_template('brandings.html', brandings=branding_info, msg=request.args.get('msg'))


@app.route('/ui/brandings/create', methods=['POST'])
@requires_auth
def ui_brandings_create():
    name = secure_filename(request.form.get('name', '').strip())
    if not name:
        return redirect(url_for('ui_brandings', msg='invalid_name'))
    try:
        app.configParser.create_branding(name)
    except Exception:
        return redirect(url_for('ui_brandings', msg='error'))
    return redirect(url_for('ui_branding_detail', name=name))


@app.route('/ui/brandings/<name>/delete', methods=['POST'])
@requires_auth
def ui_brandings_delete(name):
    try:
        app.configParser.delete_branding(name)
    except ValueError:
        return redirect(url_for('ui_brandings', msg='delete_default'))
    return redirect(url_for('ui_brandings', msg='deleted'))


@app.route('/ui/brandings/<name>')
@requires_auth
def ui_branding_detail(name):
    if not os.path.isdir(os.path.join(BRANDING_PATH, name)):
        return redirect(url_for('ui_brandings'))
    screens = []
    for key, fname, label in BRANDABLE_SCREENS:
        custom_path = os.path.join(BRANDING_PATH, name, fname)
        has_custom = os.path.isfile(custom_path) and os.path.getsize(custom_path) > 0
        screens.append({'key': key, 'filename': fname, 'label': label, 'has_custom': has_custom})
    return render_template('branding_detail.html', branding_name=name, screens=screens,
                           msg=request.args.get('msg'))


@app.route('/ui/brandings/<name>/upload/<screen_key>', methods=['POST'])
@requires_auth
def ui_branding_upload(name, screen_key):
    if screen_key not in BRANDABLE_SCREEN_MAP:
        return redirect(url_for('ui_branding_detail', name=name, msg='invalid_key'))
    fname, _ = BRANDABLE_SCREEN_MAP[screen_key]
    f = request.files.get('image')
    if not f or not f.filename:
        return redirect(url_for('ui_branding_detail', name=name, msg='no_file'))
    dest = os.path.join(BRANDING_PATH, name, fname)
    f.save(dest)
    if app.configParser.config.active_branding == name:
        app.configParser.readConfiguration()
    return redirect(url_for('ui_branding_detail', name=name, msg='uploaded'))


@app.route('/ui/brandings/<name>/reset/<screen_key>', methods=['POST'])
@requires_auth
def ui_branding_reset(name, screen_key):
    if name == 'Default':
        return redirect(url_for('ui_branding_detail', name=name))
    if screen_key not in BRANDABLE_SCREEN_MAP:
        return redirect(url_for('ui_branding_detail', name=name))
    fname, _ = BRANDABLE_SCREEN_MAP[screen_key]
    path = os.path.join(BRANDING_PATH, name, fname)
    if os.path.isfile(path):
        os.remove(path)
    if app.configParser.config.active_branding == name:
        app.configParser.readConfiguration()
    return redirect(url_for('ui_branding_detail', name=name, msg='reset'))


@app.route('/branding/<pkg>/<filename>')
@requires_auth
def serve_branding_asset(pkg, filename):
    candidate = os.path.join(BRANDING_PATH, pkg, filename)
    if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
        return send_from_directory(os.path.join(BRANDING_PATH, pkg), filename)
    default = os.path.join(BRANDING_PATH, 'Default', filename)
    if os.path.isfile(default):
        return send_from_directory(os.path.join(BRANDING_PATH, 'Default'), filename)
    return '', 404


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ZIP downloads
# ---------------------------------------------------------------------------

@app.route('/ui/photos/download')
@requires_active_project_unlock
def ui_photos_download():
    photo_dir = app.configParser.config.photo_abs_file_path
    project = app.configParser.config.active_project
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.isdir(photo_dir):
            for fname in sorted(os.listdir(photo_dir)):
                if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    zf.write(os.path.join(photo_dir, fname), fname)
    buf.seek(0)
    return Response(
        buf,
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="photos_{project}.zip"'},
    )


@app.route('/ui/brandings/<name>/download')
@requires_auth
def ui_branding_download(name):
    branding_dir = os.path.join(BRANDING_PATH, name)
    if not os.path.isdir(branding_dir):
        return redirect(url_for('ui_brandings'))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(branding_dir)):
            if fname.lower().endswith('.png'):
                zf.write(os.path.join(branding_dir, fname), fname)
    buf.seek(0)
    return Response(
        buf,
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="branding_{name}.zip"'},
    )


# ---------------------------------------------------------------------------
# Uploads / static helpers
# ---------------------------------------------------------------------------

@app.route('/uploads/<name>')
@requires_active_project_unlock
def download_file(name):
    return send_from_directory(app.configParser.config.templates_file_path, name)


# ---------------------------------------------------------------------------
# Mock for standalone dev
# ---------------------------------------------------------------------------

class Photobooth:
    state = "Start"

    def __init__(self):
        pass

    def to_PowerOn(self):
        pass

    def to_Start(self):
        pass

    def on_enter_PowerOn(self):
        pass

    def switch_project(self, name):
        pass


# ---------------------------------------------------------------------------
# Standalone entry point (no RPi hardware)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_filename = str(datetime.now()).split('.')[0].replace(' ', '_').replace(':', '-')
    loggingfolder = REAL_PATH + "/Log/"

    if not os.path.exists(loggingfolder):
        os.mkdir(loggingfolder)

    logging.basicConfig(
        format='%(asctime)s-%(module)s-%(funcName)s:%(lineno)d - %(message)s',
        level=logging.DEBUG,
        filename=loggingfolder + "webserver_" + log_filename + ".log"
    )

    try:
        app.setup_photobooth(Photobooth(), logging)
        app.run("0.0.0.0", 4010, debug=True)

    except KeyboardInterrupt:
        logging.debug("keyboard interrupt")

    except Exception as exception:
        logging.critical("unexpected error: " + str(exception))
        logging.exception(exception)

    finally:
        logging.debug("logfile closed")
