from __future__ import annotations
import base64
import configparser
import os
import shutil
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from photoCard_new import PhotoCard, PictureOnCard

logger = logging.getLogger(__name__)
REAL_PATH = os.path.dirname(os.path.realpath(__file__))
PROJECTS_PATH = os.path.join(REAL_PATH, "Projects")


class TemplateParser:

    def __init__(self, path) -> None:
        self.template_path = path
        self.ini_path = os.path.join(path, "card.ini")
        self.layout = [PhotoCard(), PhotoCard()]
        self.cardconfig = configparser.ConfigParser()

    def set_path(self, new_path):
        """Switch to a different project directory and reload layouts."""
        self.template_path = new_path
        self.ini_path = os.path.join(new_path, "card.ini")
        self.layout = [PhotoCard(), PhotoCard()]
        self.cardconfig = configparser.ConfigParser()
        self.readCardConfiguration()

    def parseData(self, data):
        if data.get("id") is not None:
            id = int(data["id"])
            card = self.layout[id-1]
            if "new_image" in data:
                image_basecode = data["new_image"]
                new_filename = "picture" + str(id) + ".png"
                with open(os.path.join(self.template_path, new_filename), "wb") as fh:
                    con_basecode = image_basecode.split(',')[1]
                    img_str_encoded = str.encode(con_basecode)
                    image_data = base64.urlsafe_b64decode(img_str_encoded)
                    fh.write(image_data)
                card.cardFileName = new_filename

            if data.get("picCount") is not None:
                card.picCount = int(data["picCount"])
            if data.get("layoutInForeground") is not None:
                card.layoutInForeground = data["layoutInForeground"] in (True, "True", "true", "on", "1")

            if data.get("pictures") is not None:
                pictures = data["pictures"]
                for i in range(0, len(pictures)):
                    pic_data = pictures[i]
                    if i >= len(card.pictures):
                        card.pictures.append(PictureOnCard(i))
                    picture = card.pictures[i]
                    picture.resizeX = int(pic_data["resizeX"])
                    picture.resizeY = int(pic_data["resizeY"])
                    picture.rotate = int(pic_data["rotate"])
                    picture.posX = int(pic_data["posX"])
                    picture.posY = int(pic_data["posY"])
                    picture.color = str(pic_data.get("color", "color"))
                    card.pictures[i] = picture
            self.writeCardConfig()

    def writeCardConfig(self):
        for i in range(0, 2):
            id = i + 1
            layout_str = "Layout"+str(id)
            card = self.layout[i]

            if not self.cardconfig.has_section(layout_str):
                self.cardconfig.add_section(layout_str)

            self.cardconfig.set(layout_str, "piccount", str(card.picCount))
            self.cardconfig.set(layout_str, "layout_in_foreground", str(card.layoutInForeground))
            self.cardconfig.set(layout_str, "cardtemplate", card.cardFileName or "picture"+str(id)+".png")
            pictures = card.pictures

            for j in range(0, len(pictures)):
                picture = pictures[j]
                pic_id = j + 1
                self.cardconfig.set(layout_str, "resize_image_x_"+str(pic_id), str(picture.resizeX))
                self.cardconfig.set(layout_str, "resize_image_y_"+str(pic_id), str(picture.resizeY))
                self.cardconfig.set(layout_str, "position_image_x_"+str(pic_id), str(picture.posX))
                self.cardconfig.set(layout_str, "position_image_y_"+str(pic_id), str(picture.posY))
                self.cardconfig.set(layout_str, "rotate_image_"+str(pic_id), str(picture.rotate))
                self.cardconfig.set(layout_str, "color_image_"+str(pic_id), str(picture.color))

        os.makedirs(self.template_path, exist_ok=True)
        with open(self.ini_path, 'w') as configfile:
            self.cardconfig.write(configfile, True)

    def readCardConfiguration(self):
        logger.debug("Read card Config File")
        self.cardconfig.sections()

        if self.ini_path is not None:
            self.cardconfig.read(self.ini_path)

            for l in range(0, 2):
                layout_str = "Layout"+str(l+1)
                self.layout[l].picCount = int(self.cardconfig.get(layout_str, "piccount", fallback="0"))
                card_tpl = self.cardconfig.get(layout_str, "cardtemplate", fallback="picture"+str(l+1)+".png")
                self.layout[l].cardFileName = card_tpl
                self.layout[l].cardTemplate = os.path.join(self.template_path, card_tpl)

                self.layout[l].layoutInForeground = self.cardconfig.getboolean(layout_str, "layout_in_foreground", fallback=False)
                self.layout[l].pictures = []
                for i in range(0, self.layout[l].picCount):
                    self.layout[l].pictures.append(PictureOnCard(i))
                    self.layout[l].pictures[i].resizeX = int(
                        self.cardconfig.get(layout_str, "resize_image_x_" + str(i + 1), fallback="0"))
                    self.layout[l].pictures[i].resizeY = int(
                        self.cardconfig.get(layout_str, "resize_image_y_" + str(i + 1), fallback="0"))
                    self.layout[l].pictures[i].rotate = int(
                        self.cardconfig.get(layout_str, "rotate_image_" + str(i + 1), fallback="0"))
                    self.layout[l].pictures[i].posX = int(
                        self.cardconfig.get(layout_str, "position_image_x_" + str(i + 1), fallback="0"))
                    self.layout[l].pictures[i].posY = int(
                        self.cardconfig.get(layout_str, "position_image_y_" + str(i + 1), fallback="0"))
                    self.layout[l].pictures[i].color = self.cardconfig.get(layout_str, "color_image_" + str(i + 1), fallback="color")

                    logger.debug(self.layout[l].pictures[i])
        return self.layout


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

class Config:
    sections = ["Debug", "Paths", "InOut", "Resolution", "Project", "WebServer"]
    debug = True
    printPicsEnable = True
    active_project = "Default"
    photo_abs_file_path = ""
    screens_abs_file_path = ""
    templates_file_path = ""
    pin_button_left = 23
    pin_button_right = 24
    photo_w = 3280
    photo_h = 2464
    screen_w = 1024
    screen_h = 600
    flip_screen_h = False
    flip_screen_v = False
    camera_exposure_mode = "P"
    camera_awb_mode = "Auto"
    camera_iso = "Auto"
    camera_shutterspeed = "auto"
    camera_aperture = "auto"
    webserver_user = ""
    webserver_password = ""
    base_path = os.path.dirname(os.path.realpath(__file__))
    screen_turnOnPrinter = "ScreenTurnOnPrinter.png"
    screen_logo = "ScreenLogo.png"
    screen_choose_layout = "ScreenChooseLayout.png"
    screen_countdown_0 = "ScreenCountdown0.png"
    screen_countdown_1 = "ScreenCountdown1.png"
    screen_countdown_2 = "ScreenCountdown2.png"
    screen_countdown_3 = "ScreenCountdown3.png"
    screen_countdown_4 = "ScreenCountdown4.png"
    screen_countdown_5 = "ScreenCountdown5.png"
    screen_black = "ScreenBlack.png"
    screen_again_next = "ScreenAgainNext.png"
    screen_wait = "ScreenWait.png"
    screen_print = "ScreenPrint.png"
    screen_print_again = "ScreenPrintagain.png"
    screen_change_ink = "ScreenChangeInk.png"
    screen_change_paper = "ScreenChangePaper.png"
    screen_photo = []

    for i in range(0, 9):
        screen_photo.append("ScreenPhoto" + str(i + 1) + ".png")

    def __json__(self):
        return {
            "debug": self.debug,
            "printPicsEnable": self.printPicsEnable,
            "active_project": self.active_project,
            "photo_abs_file_path": self.photo_abs_file_path,
            "screens_abs_file_path": self.screens_abs_file_path,
            "templates_file_path": self.templates_file_path,
            "pin_button_left": self.pin_button_left,
            "pin_button_right": self.pin_button_right,
            "photo_w": self.photo_w,
            "photo_h": self.photo_h,
            "screen_w": self.screen_w,
            "screen_h": self.screen_h,
            "flip_screen_h": self.flip_screen_h,
            "flip_screen_v": self.flip_screen_v,
            "camera_awb_mode": self.camera_awb_mode,
            "camera_iso": self.camera_iso,
            "camera_exposure_mode": self.camera_exposure_mode,
            "camera_shutterspeed": self.camera_shutterspeed,
            "camera_aperture": self.camera_aperture,
            "webserver_user": self.webserver_user,
            "base_path": self.base_path,
        }


# ---------------------------------------------------------------------------
# ConfigParser
# ---------------------------------------------------------------------------

class ConfigParser:
    logging = None

    def __init__(self, logging) -> None:
        self.logging = logging
        self.path = os.path.join(REAL_PATH, 'config.ini')
        self.configParser = configparser.ConfigParser()
        self.configParser.read(self.path)
        self.config = Config()
        self.ensure_default_project()
        self.readConfiguration()

    # ── Project filesystem helpers ─────────────────────────────────────────

    def project_dir(self, name=None):
        return os.path.join(PROJECTS_PATH, name or self.config.active_project)

    def _project_ini_path(self, name=None):
        return os.path.join(self.project_dir(name), "project.ini")

    def list_projects(self):
        if not os.path.isdir(PROJECTS_PATH):
            return []
        return sorted([
            n for n in os.listdir(PROJECTS_PATH)
            if os.path.isdir(os.path.join(PROJECTS_PATH, n))
        ])

    def ensure_default_project(self):
        """Bootstrap: create Projects/Default/ from Templates/Default/ on first run."""
        os.makedirs(PROJECTS_PATH, exist_ok=True)
        default_dir = os.path.join(PROJECTS_PATH, "Default")
        if not os.path.isdir(default_dir):
            os.makedirs(default_dir)
            os.makedirs(os.path.join(default_dir, "Photos"), exist_ok=True)

            # Migrate from Templates/Default/ if present
            old_src = os.path.join(REAL_PATH, "Templates", "Default")
            if os.path.isdir(old_src):
                for fname in os.listdir(old_src):
                    src = os.path.join(old_src, fname)
                    if os.path.isfile(src) and fname.lower().endswith(('.ini', '.png', '.jpg')):
                        shutil.copy2(src, os.path.join(default_dir, fname))

            # Migrate old [Camera] values from config.ini into project.ini
            old_cam = configparser.ConfigParser()
            old_cam.read(self.path)
            self._write_project_ini_camera(default_dir, {
                'camera_exposure_mode': old_cam.get('Camera', 'camera_exposure_mode', fallback='P'),
                'camera_awb_mode': old_cam.get('Camera', 'camera_awb_mode', fallback='Auto'),
                'camera_iso': old_cam.get('Camera', 'camera_iso', fallback='Auto'),
                'camera_shutterspeed': old_cam.get('Camera', 'camera_shutterspeed', fallback='auto'),
                'camera_aperture': old_cam.get('Camera', 'camera_aperture', fallback='auto'),
            })

        # Ensure Photos/ subdir for every existing project
        for name in self.list_projects():
            os.makedirs(os.path.join(PROJECTS_PATH, name, "Photos"), exist_ok=True)

    def create_project(self, name):
        proj_dir = os.path.join(PROJECTS_PATH, name)
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(os.path.join(proj_dir, "Photos"), exist_ok=True)

        # Write empty card.ini (2 layouts, 0 pictures)
        tp = TemplateParser(proj_dir)
        tp.writeCardConfig()

        # Write project.ini with current camera defaults
        self._write_project_ini_camera(proj_dir, {
            'camera_exposure_mode': self.config.camera_exposure_mode,
            'camera_awb_mode': self.config.camera_awb_mode,
            'camera_iso': self.config.camera_iso,
            'camera_shutterspeed': self.config.camera_shutterspeed,
            'camera_aperture': self.config.camera_aperture,
        })

    def delete_project(self, name):
        if name == self.config.active_project:
            raise ValueError("Cannot delete the active project")
        proj_dir = os.path.join(PROJECTS_PATH, name)
        if os.path.isdir(proj_dir):
            shutil.rmtree(proj_dir)

    def set_active_project(self, name):
        self.config.active_project = name
        self.writeConfig()
        self.readConfiguration()

    # ── Project camera (project.ini [Camera]) ─────────────────────────────

    def _write_project_ini_camera(self, proj_dir, camera_dict):
        """Write [Camera] to project.ini, preserving other sections (e.g. [Security])."""
        path = os.path.join(proj_dir, "project.ini")
        cfg = configparser.ConfigParser()
        cfg.read(path)
        if not cfg.has_section("Camera"):
            cfg.add_section("Camera")
        for k, v in camera_dict.items():
            cfg.set("Camera", k, str(v))
        with open(path, "w") as f:
            cfg.write(f)

    def _read_project_camera(self, proj_dir):
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(proj_dir, "project.ini"))
        self.config.camera_exposure_mode = cfg.get("Camera", "camera_exposure_mode", fallback="P")
        self.config.camera_awb_mode = cfg.get("Camera", "camera_awb_mode", fallback="Auto")
        self.config.camera_iso = cfg.get("Camera", "camera_iso", fallback="Auto")
        self.config.camera_shutterspeed = cfg.get("Camera", "camera_shutterspeed", fallback="auto")
        self.config.camera_aperture = cfg.get("Camera", "camera_aperture", fallback="auto")

    def write_project_camera(self, proj_dir=None):
        """Persist current camera config values to project.ini of the active project."""
        self._write_project_ini_camera(proj_dir or self.project_dir(), {
            'camera_exposure_mode': self.config.camera_exposure_mode,
            'camera_awb_mode': self.config.camera_awb_mode,
            'camera_iso': self.config.camera_iso,
            'camera_shutterspeed': self.config.camera_shutterspeed,
            'camera_aperture': self.config.camera_aperture,
        })

    # ── Project password (project.ini [Security]) ─────────────────────────

    def project_has_password(self, name):
        cfg = configparser.ConfigParser()
        cfg.read(self._project_ini_path(name))
        return bool(cfg.get("Security", "password_hash", fallback=""))

    def set_project_password(self, name, password):
        path = self._project_ini_path(name)
        cfg = configparser.ConfigParser()
        cfg.read(path)
        if password:
            if not cfg.has_section("Security"):
                cfg.add_section("Security")
            cfg.set("Security", "password_hash", generate_password_hash(password))
        else:
            if cfg.has_section("Security"):
                cfg.remove_section("Security")
        with open(path, "w") as f:
            cfg.write(f)

    def check_project_password(self, name, password):
        cfg = configparser.ConfigParser()
        cfg.read(self._project_ini_path(name))
        stored = cfg.get("Security", "password_hash", fallback="")
        if not stored:
            return True
        return check_password_hash(stored, password)

    # ── Main config read/write ─────────────────────────────────────────────

    def readConfiguration(self):
        logging.debug("Read Config File")

        if self.configParser.getboolean("Debug", "debug", fallback=True):
            self.config.debug = True
            logging.basicConfig(level=logging.DEBUG)
        else:
            self.config.debug = False
            logging.basicConfig(level=logging.WARNING)

        self.config.printPicsEnable = self.configParser.getboolean("Debug", "print", fallback=True)

        self.config.screens_abs_file_path = os.path.join(REAL_PATH,
            self.configParser.get("Paths", "screen_path", fallback="Screens/"))

        self.config.pin_button_left = int(self.configParser.get("InOut", "pin_button_left", fallback="23"))
        self.config.pin_button_right = int(self.configParser.get("InOut", "pin_button_right", fallback="24"))

        self.config.photo_w = int(self.configParser.get("Resolution", "photo_w", fallback="3280"))
        self.config.photo_h = int(self.configParser.get("Resolution", "photo_h", fallback="2464"))
        self.config.screen_w = int(self.configParser.get("Resolution", "screen_w", fallback="1024"))
        self.config.screen_h = int(self.configParser.get("Resolution", "screen_h", fallback="600"))
        self.config.flip_screen_h = self.configParser.getboolean("Resolution", "flip_screen_h", fallback=False)
        self.config.flip_screen_v = self.configParser.getboolean("Resolution", "flip_screen_v", fallback=False)

        self.config.screen_turnOnPrinter = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_turn_on_printer", fallback="ScreenTurnOnPrinter.png"))
        self.config.screen_logo = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_logo", fallback="ScreenLogo.png"))
        self.config.screen_choose_layout = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_Choose_Layout", fallback="ScreenChooseLayout.png"))
        self.config.screen_countdown_0 = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_countdown_0", fallback="ScreenCountdown0.png"))
        self.config.screen_countdown_1 = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_countdown_1", fallback="ScreenCountdown1.png"))
        self.config.screen_countdown_2 = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_countdown_2", fallback="ScreenCountdown2.png"))
        self.config.screen_countdown_3 = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_countdown_3", fallback="ScreenCountdown3.png"))
        self.config.screen_countdown_4 = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_countdown_4", fallback="ScreenCountdown4.png"))
        self.config.screen_countdown_5 = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_countdown_5", fallback="ScreenCountdown5.png"))
        self.config.screen_black = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_black", fallback="ScreenBlack.png"))
        self.config.screen_again_next = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_again_next", fallback="ScreenAgainNext.png"))
        self.config.screen_wait = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_wait", fallback="ScreenWait.png"))
        self.config.screen_print = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_print", fallback="ScreenPrint.png"))
        self.config.screen_print_again = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_print_again", fallback="ScreenPrintagain.png"))
        self.config.screen_change_ink = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_change_ink", fallback="ScreenChangeInk.png"))
        self.config.screen_change_paper = os.path.join(self.config.screens_abs_file_path,
            self.configParser.get("Screens", "screen_change_paper", fallback="ScreenChangePaper.png"))

        self.config.screen_photo = []
        for i in range(0, 9):
            self.config.screen_photo.append(os.path.join(self.config.screens_abs_file_path,
                self.configParser.get("Screens", "screen_photo_" + str(i + 1),
                    fallback="ScreenPhoto" + str(i + 1) + ".png")))

        self.config.webserver_user = self.configParser.get("WebServer", "webserver_user", fallback="")
        self.config.webserver_password = self.configParser.get("WebServer", "webserver_password", fallback="")

        # Active project → derive paths
        active = self.configParser.get("Project", "active", fallback="Default")
        self.config.active_project = active
        proj_dir = os.path.join(PROJECTS_PATH, active)
        self.config.templates_file_path = proj_dir
        self.config.photo_abs_file_path = os.path.join(proj_dir, "Photos")

        # Camera settings from project.ini
        self._read_project_camera(proj_dir)

        return self.config

    def parseData(self, data):
        if data is None:
            return
        if data.get("photo_w") is not None:
            self.config.photo_w = int(data["photo_w"])
        if data.get("photo_h") is not None:
            self.config.photo_h = int(data["photo_h"])
        if data.get("screen_w") is not None:
            self.config.screen_w = int(data["screen_w"])
        if data.get("screen_h") is not None:
            self.config.screen_h = int(data["screen_h"])
        if data.get("flip_screen_h") is not None:
            self.config.flip_screen_h = data["flip_screen_h"] in (True, "True", "true", "on", "1")
        if data.get("flip_screen_v") is not None:
            self.config.flip_screen_v = data["flip_screen_v"] in (True, "True", "true", "on", "1")
        if data.get("pin_button_left") is not None:
            self.config.pin_button_left = int(data["pin_button_left"])
        if data.get("pin_button_right") is not None:
            self.config.pin_button_right = int(data["pin_button_right"])
        if data.get("debug") is not None:
            self.config.debug = data["debug"] in (True, "True", "true", "on", "1")
        if data.get("printPicsEnable") is not None:
            self.config.printPicsEnable = data["printPicsEnable"] in (True, "True", "true", "on", "1")
        if data.get("camera_exposure_mode") is not None:
            self.config.camera_exposure_mode = str(data["camera_exposure_mode"])
        if data.get("camera_awb_mode") is not None:
            self.config.camera_awb_mode = str(data["camera_awb_mode"])
        if data.get("camera_iso") is not None:
            self.config.camera_iso = str(data["camera_iso"])
        if data.get("camera_shutterspeed") is not None:
            self.config.camera_shutterspeed = str(data["camera_shutterspeed"])
        if data.get("camera_aperture") is not None:
            self.config.camera_aperture = str(data["camera_aperture"])
        if data.get("webserver_user") is not None:
            self.config.webserver_user = str(data["webserver_user"])
        if data.get("webserver_password") is not None and data["webserver_password"] != "":
            self.config.webserver_password = str(data["webserver_password"])

    def writeConfig(self):
        for section in self.config.sections:
            if not self.configParser.has_section(section):
                self.configParser.add_section(section)

        self.configParser.set("Debug", "debug", str(self.config.debug))
        self.configParser.set("Debug", "print", str(self.config.printPicsEnable))

        self.configParser.set("Paths", "screen_path",
            self.config.screens_abs_file_path[len(REAL_PATH):].lstrip("/"))

        self.configParser.set("InOut", "pin_button_left", str(self.config.pin_button_left))
        self.configParser.set("InOut", "pin_button_right", str(self.config.pin_button_right))

        self.configParser.set("Resolution", "photo_w", str(self.config.photo_w))
        self.configParser.set("Resolution", "photo_h", str(self.config.photo_h))
        self.configParser.set("Resolution", "screen_w", str(self.config.screen_w))
        self.configParser.set("Resolution", "screen_h", str(self.config.screen_h))
        self.configParser.set("Resolution", "flip_screen_h", str(self.config.flip_screen_h))
        self.configParser.set("Resolution", "flip_screen_v", str(self.config.flip_screen_v))

        self.configParser.set("Project", "active", str(self.config.active_project))

        self.configParser.set("WebServer", "webserver_user", str(self.config.webserver_user))
        self.configParser.set("WebServer", "webserver_password", str(self.config.webserver_password))

        with open(self.path, 'w') as configfile:
            self.configParser.write(configfile, True)
