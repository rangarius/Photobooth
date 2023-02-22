import configparser 
import os
import logging  # logging functions
logger = logging.getLogger(__name__)

class CardLayout:
    def __init__(self):
        self.piccount = 0
        self.pictures = []
        self.layoutInForeground = False

class Picture:
    def __init__(self):
        self.resizeX = 0
        self.resizeY = 0
        self.rotate = 0
        self.posX = 0
        self.posY = 0
    

class TemplateParser: 

    def __init__(self, path) -> None:
        self.path = path;
        self.layout = [CardLayout(), CardLayout()]

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
                    self.layout[l].pictures.append(Picture())
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