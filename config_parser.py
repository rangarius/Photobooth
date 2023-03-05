from __future__ import annotations
import base64
import configparser 
import os
import logging  # logging functions
from photoCard_new import PhotoCard, PictureOnCard

logger = logging.getLogger(__name__)
REAL_PATH = os.path.dirname(os.path.realpath(__file__))


class TemplateParser: 

    def __init__(self, path) -> None:
        self.template_path = path
        self.ini_path = os.path.join(path, "card.ini");
        self.layout = [PhotoCard(), PhotoCard()]
        self.cardconfig = configparser.ConfigParser()
        self.readCardConfiguration()

    def parseData(self, data):
        if data["id"] is not None:
            id = int(data["id"])
            card = self.layout[id-1]
            if "new_image" in data:
                image_basecode = data["new_image"]
                with open(os.path.join(self.template_path, "picture"+str(id)+".png"), "wb") as fh:
                    con_basecode = image_basecode.split(',')[1]
                    img_str_encoded = str.encode(con_basecode)
                    image_data = base64.urlsafe_b64decode(img_str_encoded)
                    fh.write(image_data)

            if data["picCount"] is not None:
                card.picCount = int(data["picCount"])
            if data["layoutInForeground"] is not None:
                card.layoutInForeground = bool(data["layoutInForeground"])
            card.cardFileName = str("picture" + data["id"]+".png")

            if data["pictures"] is not None:
                pictures = data["pictures"]
                for i in range(0, len(pictures)):
                    pic_data = pictures[i]
                    picture = card.pictures[i]
                    if picture is None:
                        picture = PictureOnCard()
                    
                    picture.resizeX = int(pic_data["resizeX"])
                    picture.resizeY = int(pic_data["resizeY"])
                    picture.rotate = int(pic_data["rotate"])
                    picture.posX = int(pic_data["posX"])
                    picture.posY = int(pic_data["posY"])

                    card.pictures[i] = picture


    def writeCardConfig(self):
        for i in range(0,2):
            id = i + 1
            layout_str = "Layout"+str(id)
            card = self.layout[i]

            if not self.cardconfig.has_section(layout_str):
                self.cardconfig.add_section(layout_str)

            self.cardconfig.set(layout_str, "piccount", str(card.picCount))
            self.cardconfig.set(layout_str, "layout_in_foreground", str(card.layoutInForeground))
            self.cardconfig.set(layout_str, "cardtemplate", "picture"+str(id)+".png")
            pictures = card.pictures

            for i in range(0, len(pictures)):
                picture = pictures[i]
                pic_id = i + 1
                self.cardconfig.set(layout_str, "resize_image_x_"+str(pic_id), str(picture.resizeX))
                self.cardconfig.set(layout_str, "resize_image_y_"+str(pic_id), str(picture.resizeY))
                self.cardconfig.set(layout_str, "position_image_x_"+str(pic_id), str(picture.posX))
                self.cardconfig.set(layout_str, "position_image_y_"+str(pic_id), str(picture.posY))
                self.cardconfig.set(layout_str, "rotate_image_"+str(pic_id), str(picture.rotate))

        with open(self.ini_path, 'w') as configfile:    # save
            self.cardconfig.write(configfile, True)

    def readCardConfiguration(self) -> list[PhotoCard]:
        logger.debug("Read card Config File")
        
        self.cardconfig.sections()

        if self.ini_path is not None:
            logger.debug("start reading")
            self.cardconfig.read(self.ini_path)

            for l in range(0, 2):
                layout_str = "Layout"+str(l+1)
                # layout 1 configuration
                self.layout[l].picCount = int(self.cardconfig.get(layout_str, "piccount", fallback="0"))
                self.layout[l].cardFileName = os.path.join(self.template_path,
                "picture"+str(l+1)+".png")

                self.layout[l].layoutInForeground = self.cardconfig.getboolean(layout_str, "layout_in_foreground", fallback=False)
                # manipulation of photos for Layout 1
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

        logger.debug(self.layout[l].__json__)
        return self.layout

class Config:
    sections = ["Debug", "Paths", "InOut", "Resolution", "Camera"]
    debug: True
    printPicEnable: True
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
    camera_awb_mode = "auto"
    camera_awb_gains_red = 1.6
    camera_awb_gains_blue = 1.6
    camera_iso = 0
    base_path = os.path.dirname(os.path.realpath(__file__))
    screen_turnOnPrinter = "ScreenTurnOnPrinter.png"
    screen_logo = "ScreenLogo.png"
    screen_choose_layout = "ScreenChooseLayout.png"
    screen_countdown_0 ="ScreenCountdown0.png"
    screen_countdown_1 = "ScreenCountdown1.png"
    screen_countdown_2 =  "ScreenCountdown2.png"
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
    camera_awb_mode = "auto"
    screen_photo = []
    
    for i in range(0, 9):
        screen_photo.append("ScreenPhoto" + str(i + 1) + ".png")

    
    def __json__(self):
        return {
            "debug": self.debug,
            "printPicsEnable": self.printPicsEnable,
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
            "camera_awb_gains_red": self.camera_awb_gains_red,
            "camera_awb_gains_blue": self.camera_awb_gains_blue,
            "camera_iso": self.camera_iso,
            "base_path": self.base_path
        }


class ConfigParser: 
    logging = None

    def __init__(self, logging) -> None:
        self.logging = logging
        self.configParser = configparser.ConfigParser()
        self.configParser.read(os.path.join(REAL_PATH, 'config.ini'))
        self.config = Config()
        self.readConfiguration()

    def readConfiguration(self) -> Config:
        logging.debug("Read Config File")

        if self.configParser.getboolean("Debug", "debug", fallback=True) == True:
            self.config.debug = self.configParser.getboolean("Debug", "debug", fallback=True)
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.WARNING)

        self.config.printPicsEnable = self.configParser.getboolean("Debug", "print", fallback=True)

        if self.config.printPicsEnable == False:
            logging.debug("Printing pics disabled")

        self.config.photo_abs_file_path = os.path.join(REAL_PATH, self.configParser.get("Paths", "photo_path", fallback="Photos/"))
        self.config.screens_abs_file_path = os.path.join(REAL_PATH,
                                                  self.configParser.get("Paths", "screen_path", fallback="Screens/"))
        self.config.templates_file_path = os.path.join(REAL_PATH,
                                                  self.configParser.get("Paths", "template_path", fallback="Tempates/"))
        self.config.pin_button_left = int(self.configParser.get("InOut", "pin_button_left", fallback="23"))
        self.config.pin_button_right = int(self.configParser.get("InOut", "pin_button_right", fallback="24"))
        self.config.photo_w = int(self.configParser.get("Resolution", "photo_w", fallback="3280"))
        self.config.photo_h = int(self.configParser.get("Resolution", "photo_h", fallback="2464"))
        self.config.screen_w = int(self.configParser.get("Resolution", "screen_w", fallback="1024"))
        self.config.screen_h = int(self.configParser.get("Resolution", "screen_h", fallback="600"))
        self.config.flip_screen_h = self.configParser.getboolean("Resolution", "flip_screen_h", fallback=False)
        self.config.flip_screen_v = self.configParser.getboolean("Resolution", "flip_screen_v", fallback=False)
        self.config.screen_turnOnPrinter = os.path.join(self.config.screens_abs_file_path,
                                                 self.configParser.get("Screens", "screen_turn_on_printer",
                                                                 fallback="ScreenTurnOnPrinter.png"))
        self.config.screen_logo = os.path.join(self.config.screens_abs_file_path,
                                        self.configParser.get("Screens", "screen_logo", fallback="ScreenLogo.png"))
        self.config.screen_choose_layout = os.path.join(self.config.screens_abs_file_path,
                                                 self.configParser.get("Screens", "screen_Choose_Layout",
                                                                 fallback="ScreenChooseLayout.png"))
        self.config.screen_countdown_0 = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_countdown_0",
                                                               fallback="ScreenCountdown0.png"))
        self.config.screen_countdown_1 = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_countdown_1",
                                                               fallback="ScreenCountdown1.png"))
        self.config.screen_countdown_2 = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_countdown_2",
                                                               fallback="ScreenCountdown2.png"))
        self.config.screen_countdown_3 = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_countdown_3",
                                                               fallback="ScreenCountdown3.png"))
        self.config.screen_countdown_4 = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_countdown_4",
                                                               fallback="ScreenCountdown4.png"))
        self.config.screen_countdown_5 = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_countdown_5",
                                                               fallback="ScreenCountdown5.png"))
        self.config.screen_black = os.path.join(self.config.screens_abs_file_path,
                                         self.configParser.get("Screens", "screen_black",
                                                         fallback="ScreenBlack.png"))
        self.config.screen_again_next = os.path.join(self.config.screens_abs_file_path,
                                              self.configParser.get("Screens", "screen_again_next",
                                                              fallback="ScreenAgainNext.png"))
        self.config.screen_wait = os.path.join(self.config.screens_abs_file_path,
                                        self.configParser.get("Screens", "screen_wait",
                                                        fallback="ScreenWait.png"))
        self.config.screen_print = os.path.join(self.config.screens_abs_file_path,
                                         self.configParser.get("Screens", "screen_print",
                                                         fallback="ScreenPrint.png"))
        self.config.screen_print_again = os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_print_again",
                                                               fallback="ScreenPrintagain.png"))
        self.config.screen_change_ink = os.path.join(self.config.screens_abs_file_path,
                                              self.configParser.get("Screens", "screen_change_ink",
                                                              fallback="ScreenChangeInk.png"))
        self.config.screen_change_paper = os.path.join(self.config.screens_abs_file_path,
                                                self.configParser.get("Screens", "screen_change_paper",
                                                                fallback="ScreenChangePaper.png"))
        self.config.camera_awb_mode = self.configParser.get("Camera", "camera_awb_mode", fallback="auto")
        self.config.camera_awb_gains_red = float(self.configParser.get("Camera", "camera_awb_gains_red", fallback="1.6"))
        self.config.camera_awb_gains_blue = float(self.configParser.get("Camera", "camera_awb_gains_blue", fallback="1.6"))

        self.config.camera_iso = int(self.configParser.get("Camera", "camera_iso", fallback="0"))

        self.config.screen_photo = []
        
        for i in range(0, 9):
            self.config.screen_photo.append(os.path.join(self.config.screens_abs_file_path,
                                               self.configParser.get("Screens", "screen_photo_" + str(i + 1),
                                                               fallback="ScreenPhoto" + str(i + 1) + ".png")))
        return self.config

    def parseData(self, data):
        if data is not None:
            if data["photo_path"] is not None:
                self.config.photo_abs_file_path = os.path.join(REAL_PATH, str(data["photo_path"]))
            if data["screen_path"] is not None:
                self.config.screens_abs_file_path = os.path.join(REAL_PATH, str(data["screen_path"]))
            if data["tempates_path"] is not None:
                self.config.templates_file_path = os.path.join(REAL_PATH, str(data["template_path"]))
            
            if data["photo_w"] is not None:
                self.config.photo_w = int(data["photo_w"])
            if data["photo_h"] is not None:
                self.config.photo_h = int(data["photo_h"])
            if data["screen_w"] is not None:
                self.config.screen_w = int(data["screen_w"])
            if data["screen_h"] is not None:
                self.config.screen_h = int(data["screen_h"])
            if data["flip_screen_h"] is not None:
                self.config.flip_screen_h = bool(data["flip_screen_h"])
            if data["flip_screen_v"] is not None:
                self.config.flip_screen_v = bool(data["flip_screen_v"])

            if data["camera_awb_mode"] is not None:
                self.config.camera_awb_mode = str(data["camera_awb_mode"])
            if data["camera_awb_gains"] is not None:
                self.config.camera_awb_gains_red = float(data["camera_awb_gains"][0])
                self.config.camera_awb_gains_blue = float(data["camera_awb_gains"][1])

            if data["camera_iso"] is not None:
                self.config.camera_iso = int([data["camera_iso"]])

    def writeConfig(self):
        #
        for i in range(0, len(self.config.sections)):
            if not self.configParser.has_section(self.config.sections[i]):
                self.configParser.add_section(self.config.sections[i])

        self.configParser.set("Debug", "print", str(self.config.debug))
 
        self.configParser.set("Paths", "photo_path", self.config.photo_abs_file_path[len(REAL_PATH):])
        self.configParser.set("Paths", "screen_path", self.config.screens_abs_file_path[len(REAL_PATH):])
        self.configParser.set("Paths", "templates_path", self.config.templates_file_path[len(REAL_PATH):])

        self.configParser.set("InOut", "pin_button_left", str(self.config.pin_button_left))
        self.configParser.set("InOut", "pin_button_right", str(self.config.pin_button_right))

        self.configParser.set("Resolution", "photo_w", str(self.config.photo_w))
        self.configParser.set("Resolution", "photo_h", str(self.config.photo_h))
        self.configParser.set("Resolution", "screen_w", str(self.config.screen_w))
        self.configParser.set("Resolution", "screen_h", str(self.config.screen_h))
        self.configParser.set("Resolution", "flip_screen_h", str(self.config.flip_screen_h))
        self.configParser.set("Resolution", "flip_screen_v", str(self.config.flip_screen_v))

        self.configParser.set("Camera", "camera_awb_mode,", str(self.config.camera_awb_mode))
        self.configParser.set("Camera", "camera_awb_gains_red", str(self.config.camera_awb_gains_red))
        self.configParser.set("Camera", "camera_awb_gains_blue", str(self.config.camera_awb_gains_blue))

        self.configParser.set("Camera", "camera_iso,", str(self.config.camera_iso))

        with open(self.path, 'w') as configfile:    # save
            self.configParser.write(configfile, True)
        
    