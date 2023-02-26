from PIL import Image  # image manipulation for Overlay
from wand.image import Image as image  # image manipulation lib


"""
Class containing the single Photos
"""

class PictureOnCard:

    # init method
    def __init__(self, pictureNumber):
        self.__resizeX = 800  # defaults
        self.__resizeY = 600  # defaults
        self.__rotate = 0
        self.__posX = 0
        self.__posY = 0
        self.__fileNamePrefix = ""
        self.__pictureNumber = pictureNumber
        self.__image = ""
        self.__color = ""

    # list of getter and setter
    def __getResizeX(self):
        return self.__resizeX

    def __setResizeX(self, x):
        self.__resizeX = x

    resizeX = property(__getResizeX, __setResizeX)

    def __getResizeY(self):
        return self.__resizeY

    def __setResizeY(self, y):
        self.__resizeY = y

    resizeY = property(__getResizeY, __setResizeY)

    def __getRotate(self):
        return self.__rotate

    def __setRotate(self, y):
        self.__rotate = y

    rotate = property(__getRotate, __setRotate)

    def __getPosX(self):
        return self.__posX

    def __setPosX(self, x):
        self.__posX = x

    posX = property(__getPosX, __setPosX)

    def __getPosY(self):
        return self.__posY

    def __setPosY(self, y):
        self.__posY = y

    posY = property(__getPosY, __setPosY)

    def __getFileNamePrefix(self):
        return self.__fileNamePrefix

    def __setFileNamePrefix(self, name):
        self.__fileNamePrefix = name

    fileNamePrefix = property(__getFileNamePrefix, __setFileNamePrefix)

    def __getPictureNumber(self):
        return self.__pictureNumber

    def __setPictureNumber(self, number):
        self.__pictureNumber = number

    pictureNumber = property(__getPictureNumber, __setPictureNumber)

    def __getFileName(self):
        return self.__fileNamePrefix + '_' + str(self.__pictureNumber) + '.jpg'

    def __setFileName(self):
        pass

    fileName = property(__getFileName, __setFileName)

    def __getImage(self):
        return self.__image

    def __setImage(self, img):
        self.__image = img

    img = property(__getImage, __setImage)

    def __getColor(self):
        return self.__color

    def __setColor(self, color):
        self.__color = color

    color = property(__getColor, __setColor)

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
        self.__sizeX = 1868  # default for Canon Selphy printer
        self.__sizeY = 1261  # default for Canon Selphy printer
        self.__cardTemplate = ""
        self.__cardFileName = ""
        self.__picCount = 0
        self.__fileNamePrefix = ""
        self.__pictures = []  # list for single pictures on card
        self.__cardImage = ""
        self.__layoutInForeground = False

    # list of getter and setter
    def __getSizeX(self):
        return self.__sizeX

    def __setSizeX(self, x):
        self.__sizeX = x

    sizeX = property(__getSizeX, __setSizeX)

    def __getSizeY(self):
        return self.__sizeY

    def __setSizeY(self, y):
        self.__sizeY = y

    sizeY = property(__getSizeY, __setSizeY)

    def __getPicCount(self):
        return self.__picCount

    def __setPicCount(self, piccount):
        # if piccount is different to current, clear photoobject list and create a new list
        if piccount != self.__picCount:
            self.__pictures.clear()

            # create a new list of photoobjects
            for i in range(1, piccount + 1):
                self.__pictures.append(PictureOnCard(i))

        self.__picCount = piccount

    piccount = property(__getPicCount, __setPicCount)

    def __getLayoutInForeground(self):
        return self.__layoutInForeground

    def __setLayoutInForeground(self, foreground):
        self.__layoutInForeground = foreground

    layoutInForeground = property(__getLayoutInForeground, __setLayoutInForeground)

    def __getCardTemplate(self):
        return self.__cardTemplate

    def __setCardTemplate(self, name):
        self.__cardTemplate = name

    templateFileName = property(__getCardTemplate, __setCardTemplate)

    def __getFileNamePrefix(self):
        return self.__fileNamePrefix

    def __setFileNamePrefix(self, name):
        self.__fileNamePrefix = name
        self.cardFileName = self.fileNamePrefix + '_card' + '.jpg'
        for x in self.__pictures:
            x.fileNamePrefix = name

    fileNamePrefix = property(__getFileNamePrefix, __setFileNamePrefix)

    def __getCardFileName(self):
        return self.__cardFileName

    def __setCardFileName(self, name):
        self.__cardFileName = name

    cardFileName = property(__getCardFileName, __setCardFileName)

    def __getPicture(self):
        return self.__pictures

    def __setPicture(self):
        pass

    picture = property(__getPicture, __setPicture)

    def __getCardImage(self):
        return self.__cardImage

    def __setCardImage(self):
        pass

    cardImage = property(__getCardImage, __setCardImage)

    # reload the card background image
    def loadImageTemplate(self):
        self.__cardImage = image(filename=self.templateFileName).clone()

    # create an empty card, if template is in foreground
    def createEmptyCard(self):
        self.__cardImage = image(width=self.sizeX, height=self.sizeY)

    # create the card
    def processCard(self):
        #if layout in foreground, the template is overlaied at last
        if self.layoutInForeground:
            self.createEmptyCard()

        else:
            self.loadImageTemplate()

        # composite all photos to card
        for i in range(0, self.piccount):
            self.__cardImage.composite(self.picture[i].img, self.picture[i].posX,
                                       self.picture[i].posY)

        # if Layout is in foreground, overlay it last
        if self.layoutInForeground:
            self.__cardImage.composite(image(filename=self.templateFileName).clone(), 0, 0)

        self.__cardImage.resize(int(1868), int(1261))

    # string return method
    def __str__(self):
        return str(self.piccount) + " photos on Template: " + str(self.templateFileName) + " save as: " + str(
            self.cardFileName)
