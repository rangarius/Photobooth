from __future__ import annotations

import configparser 
import os
import logging  # logging functions
from photoCard import PhotoCard, PictureOnCard

logger = logging.getLogger(__name__)
REAL_PATH = os.path.dirname(os.path.realpath(__file__))


class TemplateParser: 

    def __init__(self, path) -> None:
        self.path = path;
        self.layout = [PhotoCard(), PhotoCard()]

    def writeCardConfig(self, data):
        layout_str = "Layout"+data["id"]
        if not self.cardconfig.has_section(layout_str):
            self.cardconfig.add_section(layout_str)

        self.cardconfig.set(layout_str, "piccount", str(data["piccount"]))
        self.cardconfig.set(layout_str, "layout_in_foreground", str(data["layoutInForeground"]))
        self.cardconfig.set(layout_str, "cardtemplate", "picture"+data["id"]+".png")
        
        pictures = data["pictures"]
        for i in range(0, len(pictures)):
            value = pictures[i]
            self.cardconfig.set(layout_str, "resize_image_x_"+str(i+1), str(value["resizeX"]))
            self.cardconfig.set(layout_str, "resize_image_y_"+str(i+1), str(value["resizeY"]))
            self.cardconfig.set(layout_str, "position_image_x_"+str(i+1), str(value["posX"]))
            self.cardconfig.set(layout_str, "position_image_y_"+str(i+1), str(value["posY"]))
            self.cardconfig.set(layout_str, "rotate_image_"+str(i+1), str(value["rotate"]))

        with open(self.path, 'w') as configfile:    # save
            self.cardconfig.write(configfile, True)
        
        self.readCardConfiguration()

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

        logger.debug(self.layout[l])

class ConfigParser: 
    logging = None

    def __init__(self, logging) -> None:
        self.logging = logging

    def readConfiguration(self) -> ConfigParser:

        logging.debug("Read Config File")
        self.config = configparser.ConfigParser()
        self.config.sections()
        self.config.read(os.path.join(REAL_PATH, 'config.ini'))

        if self.config.getboolean("Debug", "debug", fallback=True) == True:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.WARNING)

        self.printPicsEnable = self.config.getboolean("Debug", "print", fallback=True)

        if self.printPicsEnable == False:
            logging.debug("Printing pics disabled")

        self.photo_abs_file_path = os.path.join(REAL_PATH, self.config.get("Paths", "photo_path", fallback="Photos/"))
        self.screens_abs_file_path = os.path.join(REAL_PATH,
                                                  self.config.get("Paths", "screen_path", fallback="Screens/"))
        self.templates_file_path = os.path.join(REAL_PATH,
                                                  self.config.get("Paths", "templates_path", fallback="Tempates/"))
        self.pin_button_left = int(self.config.get("InOut", "pin_button_left", fallback="23"))
        self.pin_button_right = int(self.config.get("InOut", "pin_button_right", fallback="24"))
        self.photo_w = int(self.config.get("Resolution", "photo_w", fallback="3280"))
        self.photo_h = int(self.config.get("Resolution", "photo_h", fallback="2464"))
        self.screen_w = int(self.config.get("Resolution", "screen_w", fallback="1024"))
        self.screen_h = int(self.config.get("Resolution", "screen_h", fallback="600"))
        self.flip_screen_h = self.config.getboolean("Resolution", "flip_screen_h", fallback=False)
        self.flip_screen_v = self.config.getboolean("Resolution", "flip_screen_v", fallback=False)
        self.screen_turnOnPrinter = os.path.join(self.screens_abs_file_path,
                                                 self.config.get("Screens", "screen_turn_on_printer",
                                                                 fallback="ScreenTurnOnPrinter.png"))
        self.screen_logo = os.path.join(self.screens_abs_file_path,
                                        self.config.get("Screens", "screen_logo", fallback="ScreenLogo.png"))
        self.screen_choose_layout = os.path.join(self.screens_abs_file_path,
                                                 self.config.get("Screens", "screen_Choose_Layout",
                                                                 fallback="ScreenChooseLayout.png"))
        self.screen_countdown_0 = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_countdown_0",
                                                               fallback="ScreenCountdown0.png"))
        self.screen_countdown_1 = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_countdown_1",
                                                               fallback="ScreenCountdown1.png"))
        self.screen_countdown_2 = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_countdown_2",
                                                               fallback="ScreenCountdown2.png"))
        self.screen_countdown_3 = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_countdown_3",
                                                               fallback="ScreenCountdown3.png"))
        self.screen_countdown_4 = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_countdown_4",
                                                               fallback="ScreenCountdown4.png"))
        self.screen_countdown_5 = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_countdown_5",
                                                               fallback="ScreenCountdown5.png"))
        self.screen_black = os.path.join(self.screens_abs_file_path,
                                         self.config.get("Screens", "screen_black",
                                                         fallback="ScreenBlack.png"))
        self.screen_again_next = os.path.join(self.screens_abs_file_path,
                                              self.config.get("Screens", "screen_again_next",
                                                              fallback="ScreenAgainNext.png"))
        self.screen_wait = os.path.join(self.screens_abs_file_path,
                                        self.config.get("Screens", "screen_wait",
                                                        fallback="ScreenWait.png"))
        self.screen_print = os.path.join(self.screens_abs_file_path,
                                         self.config.get("Screens", "screen_print",
                                                         fallback="ScreenPrint.png"))
        self.screen_print_again = os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_print_again",
                                                               fallback="ScreenPrintagain.png"))
        self.screen_change_ink = os.path.join(self.screens_abs_file_path,
                                              self.config.get("Screens", "screen_change_ink",
                                                              fallback="ScreenChangeInk.png"))
        self.screen_change_paper = os.path.join(self.screens_abs_file_path,
                                                self.config.get("Screens", "screen_change_paper",
                                                                fallback="ScreenChangePaper.png"))


        self.screen_photo = []
        
        for i in range(0, 9):
            self.screen_photo.append(os.path.join(self.screens_abs_file_path,
                                               self.config.get("Screens", "screen_photo_" + str(i + 1),
                                                               fallback="ScreenPhoto" + str(i + 1) + ".png")))


    