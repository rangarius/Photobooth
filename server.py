import os
import json
import base64
from functools import wraps

from json import JSONEncoder
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash, jsonify, Response
from werkzeug.utils import secure_filename
from config_parser import TemplateParser, ConfigParser
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
# Auth
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

@app.route('/layouts', methods=['GET'])
def api_list_layouts():
    layouts = app.templateParser.layout
    return json.dumps(layouts, indent=4, cls=ConfigEncoder)


@app.route("/layout/save", methods=["GET"])
def api_save_layout():
    app.templateParser.writeCardConfig()
    if app.photobooth:
        try:
            app.photobooth.to_PowerOn()
        except Exception:
            pass
    return jsonify({"msg": "success"})


@app.route("/layout/edit/<id>", methods=["POST"])
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
def api_camera_apply():
    data = request.get_json() or {}
    app.configParser.parseData(data)
    cfg = app.configParser.config

    if app.photobooth and hasattr(app.photobooth, 'camera') and app.photobooth.camera:
        try:
            cam = app.photobooth.camera
            cam.iso = cfg.camera_iso
            cam.awb_mode = cfg.camera_awb_mode
            if cfg.camera_awb_mode == 'off':
                cam.awb_gains = (cfg.camera_awb_gains_red, cfg.camera_awb_gains_blue)
            cam.hflip = cfg.flip_screen_h
            cam.vflip = cfg.flip_screen_v
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
def api_get_photo(name):
    return send_from_directory(app.configParser.config.photo_abs_file_path, name)


@app.route("/photos", methods=["GET"])
@requires_auth
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

@app.route('/restart', methods=['GET'])
@requires_auth
def api_restart_photobooth():
    if app.photobooth:
        try:
            app.photobooth.on_enter_PowerOn()
        except Exception:
            pass
    return jsonify({"msg": "restarting"})


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
def ui_camera():
    cfg = app.configParser.config
    awb_modes = ["auto", "sunlight", "cloudy", "shade", "tungsten", "fluorescent", "flash", "horizon", "off"]
    msg = request.args.get("msg")
    return render_template("camera.html", cfg=cfg, awb_modes=awb_modes, msg=msg)


@app.route("/ui/camera/save", methods=["POST"])
@requires_auth
def ui_camera_save():
    data = {
        "camera_awb_mode": request.form.get("camera_awb_mode"),
        "camera_awb_gains_red": request.form.get("camera_awb_gains_red"),
        "camera_awb_gains_blue": request.form.get("camera_awb_gains_blue"),
        "camera_iso": request.form.get("camera_iso"),
        "flip_screen_h": "on" if request.form.get("flip_screen_h") else "false",
        "flip_screen_v": "on" if request.form.get("flip_screen_v") else "false",
    }
    app.configParser.parseData(data)
    app.configParser.writeConfig()
    return redirect(url_for("ui_camera", msg="saved"))


@app.route("/ui/layouts", methods=["GET"])
@requires_auth
def ui_layouts():
    layouts = app.templateParser.layout
    msg = request.args.get("msg")
    return render_template("layouts.html", layouts=layouts, msg=msg)


@app.route("/ui/layouts/editor/<int:layout_id>", methods=["GET"])
@requires_auth
def ui_layout_editor(layout_id):
    if layout_id < 1 or layout_id > len(app.templateParser.layout):
        return redirect(url_for("ui_layouts"))
    layout = app.templateParser.layout[layout_id - 1]
    return render_template("layout_editor.html", layout=layout, layout_id=layout_id)


@app.route("/ui/layouts/save/<int:layout_id>", methods=["POST"])
@requires_auth
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
# Uploads / static helpers
# ---------------------------------------------------------------------------

@app.route('/uploads/<name>')
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
