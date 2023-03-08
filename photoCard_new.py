from wand.image import Image as image  # image manipulation lib


"""
Class containing the single Photos
"""

class PictureOnCard:

    # init method
    def __init__(self, pictureNumber):
        self.resizeX = 800  # defaults
        self.resizeY = 600  # defaults
        self.rotate = 0
        self.posX = 0
        self.posY = 0
        self.fileNamePrefix = ""
        self.pictureNumber = pictureNumber
        self.image = ""
        self.color = ""

    def __json__(self):
        return {
            "resizeX": self.resizeX,
            "resizeY": self.resizeY,
            "rotate": self.rotate,
            "posX": self.posX,
            "posY": self.posY,
            "pictureNumber": self.pictureNumber
        }


    def __getFileName(self):
        return self.fileNamePrefix + '_' + str(self.pictureNumber) + '.jpg'

    def __setFileName(self):
        pass

    fileName = property(__getFileName, __setFileName)


    # string return method
    def __str__(self):
        return "Picture: " + str(self.fileName) + " size: " + str(self.resizeX) + " / " + str(self.resizeY) + \
               " rot: " + str(self.rotate) + " pos: " + str(self.posX) + " / " + str(self.posY) + " - color " + str(self.color)

    # process the image
    def ProcessImage(self):
        self.img.resize(self.resizeX, self.resizeY)
        self.img.rotate(self.rotate)

    # Load the image from the saved filename
    def LoadImage(self):
        self.img = image(filename=self.fileName)


"""
class containing the photo card
"""


class PhotoCard:

    # init method
    def __init__(self):
        self.sizeX = 1868  # default for Canon Selphy printer
        self.sizeY = 1261  # default for Canon Selphy printer
        self.cardTemplate = ""
        self.cardFileName = ""
        self.__picCount = 0
        self.__fileNamePrefix = ""
        self.pictures: list[PictureOnCard] =  []  # list for single pictures on card
        self.cardImage = ""
        self.layoutInForeground = False

    def __json__(self):
        return {
            "sizeX": self.sizeX,
            "sizeY": self.sizeY,
            "picCount": self.__picCount,
            "pictures": self.pictures,
            "cardImage": self.cardImage,
            "layoutInForeground": self.layoutInForeground
        }

    @property
    def picCount(self):
        return self.__picCount

    @picCount.setter
    def picCount(self, piccount):
        # if piccount is different to current, clear photoobject list and create a new list
        if piccount != self.__picCount:
            self.pictures.clear()

            # create a new list of photoobjects
            for i in range(1, piccount + 1):
                self.pictures.append(PictureOnCard(i))

        self.__picCount = piccount



    def __getFileNamePrefix(self):
        return self.__fileNamePrefix

    def __setFileNamePrefix(self, name):
        self.__fileNamePrefix = name
        self.cardFileName = self.fileNamePrefix + '_card' + '.jpg'
        for x in self.__pictures:
            x.fileNamePrefix = name

    fileNamePrefix = property(__getFileNamePrefix, __setFileNamePrefix)


    # reload the card background image
    def loadImageTemplate(self):
        self.cardImage = image(filename=self.cardTemplate).clone()

    # create an empty card, if template is in foreground
    def createEmptyCard(self):
        self.cardImage = image(width=self.sizeX, height=self.sizeY)

    # create the card
    def processCard(self):
        #if layout in foreground, the template is overlaied at last
        if self.layoutInForeground:
            self.createEmptyCard()

        else:
            self.loadImageTemplate()

        # composite all photos to card
        for i in range(0, self.picCount):
            self.cardImage.composite(self.pictures[i].img, self.pictures[i].posX,
                                       self.pictures[i].posY)

        # if Layout is in foreground, overlay it last
        if self.layoutInForeground:
            self.cardImage.composite(image(filename=self.cardTemplate).clone(), 0, 0)

        self.cardImage.resize(int(1868), int(1261))

    # # string return method
    # def __str__(self):
    #     return str(self.piccount) + " photos on Template: " + str(self.templateFileName) + " save as: " + str(
    #         self.cardFileName)
