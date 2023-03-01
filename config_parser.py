from __future__ import annotations

import configparser 
import os
import logging  # logging functions
from photoCard_new import PhotoCard, PictureOnCard

logger = logging.getLogger(__name__)
REAL_PATH = os.path.dirname(os.path.realpath(__file__))




class TemplateParser: 

    def __init__(self, path) -> None:
        self.path = path;
        self.layout = [PhotoCard(), PhotoCard()]
        self.readCardConfiguration()

    def parseData(self, data):
        if data["id"] is not None:
            id = int(data["id"])
            card = self.layout[id-1]

            if data["piccount"] is not None:
                card.piccount = int(data["piccount"])
            if data["layout_in_foreground"] is not None:
                card.layoutInForeground = bool(data["layout_in_foreground"])
            if data["cardtemplate"] is not None:
                card.templateFileName = str("picture" + data["id"]+".png")

            if data["pictures"] is not None:
                pictures = data["pictures"]
                for i in range(0, len(pictures)):
                    pic_data = pictures[i]
                    picture = card.pictures[i]
                    if picture is None:
                        picture = PictureOnCard()
                    
                    picture.resizeX = int(pic_data["resize_image_x"])
                    picture.resizeY = int(pic_data["resize_image_y"])
                    picture.rotate = int(pic_data["rotate_image"])
                    picture.posX = int(pic_data["position_image_x"])
                    picture.posY = int(pic_data["position_image_y"])

                    card.pictures[i] = picture


    def writeCardConfig(self):
        for i in range(0,2):
            id = i + 1
            layout_str = "Layout"+id
            card = self.layout[i]

            if not self.cardconfig.has_section(layout_str):
                self.cardconfig.add_section(layout_str)

            self.cardconfig.set(layout_str, "piccount", str(card.piccount))
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

        with open(self.path, 'w') as configfile:    # save
            self.cardconfig.write(configfile, True)

    def readCardConfiguration(self):
        logger.debug("Read card Config File")
        self.cardconfig = configparser.ConfigParser()
        self.cardconfig.sections()

        if self.path is not None:
            logger.debug("start reading")
            self.cardconfig.read(self.path)

            for l in range(0, 2):
                layout_str = "Layout"+str(l+1)
                # layout 1 configuration
                self.layout[l].piccount = int(self.cardconfig.get(layout_str, "piccount", fallback="0"))
                self.layout[l].templateFileName = os.path.join(os.path.split(self.path)[0],
                "picture"+str(l+1)+".png")

                self.layout[l].layoutInForeground = self.cardconfig.getboolean(layout_str, "layout_in_foreground", fallback=False)
                # manipulation of photos for Layout 1
                self.layout[l].pictures = []
                for i in range(0, self.layout[l].piccount):
                    self.layout[l].pictures.append(PictureOnCard())
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

class Config:
    sections = ["Debug", "Paths", "InOut", "Resolution", "Camera"]
    debug: True
    print: True
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
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.WARNING)

        self.printPicsEnable = self.configParser.getboolean("Debug", "print", fallback=True)

        if self.printPicsEnable == False:
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
            if not self.cardconfig.has_section(self.config.sections[i]):
                self.cardconfig.add_section(self.config.sections[i])
 
        self.cardconfig.set("Paths", "photo_path", self.config.photo_abs_file_path[len(REAL_PATH):])
        self.cardconfig.set("Paths", "screen_path", self.config.screens_abs_file_path[len(REAL_PATH):])
        self.cardconfig.set("Paths", "templates_path", self.config.templates_file_path[len(REAL_PATH):])

        self.cardconfig.set("InOut", "pin_button_left", str(self.config.pin_button_left))
        self.cardconfig.set("InOut", "pin_button_right", str(self.config.pin_button_right))

        self.cardconfig.set("Resolution", "photo_w", str(self.config.photo_w))
        self.cardconfig.set("Resolution", "photo_h", str(self.config.photo_h))
        self.cardconfig.set("Resolution", "screen_w", str(self.config.screen_w))
        self.cardconfig.set("Resolution", "screen_h", str(self.config.screen_h))
        self.cardconfig.set("Resolution", "flip_screen_h", str(self.config.flip_screen_h))
        self.cardconfig.set("Resolution", "flip_screen_v", str(self.config.flip_screen_v))

        self.cardconfig.set("Camera", "camera_awb_mode,", str(self.config.camera_awb_mode))
        self.cardconfig.set("Camera", "camera_awb_gains_red", str(self.config.camera_awb_gains_red))
        self.cardconfig.set("Camera", "camera_awb_gains_blue", str(self.config.camera_awb_gains_blue))

        self.cardconfig.set("Camera", "camera_iso,", str(self.config.camera_iso))

        with open(self.path, 'w') as configfile:    # save
            self.cardconfig.write(configfile, True)
        
    