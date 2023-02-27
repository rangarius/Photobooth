#!/usr/bin/python3
## import sys
import os
import pyudev
import psutil
from PIL import Image  # image manipulation for Overlay
import time  # timing
import picamera  # camera driver
import shutil  # file io access like copy
from datetime import datetime  # datetime routine
import RPi.GPIO as GPIO  # gpio access
import subprocess  # call external scripts
from transitions import Machine  # state machine
import configparser  # parsing config file
import logging  # logging functions
import cups  # connection to cups printer driver
import usb  # check if printer is connected and turned on
from wand.image import Image as image  # image manipulation lib

import threading
from server import app
from photoCard import PhotoCard
from config_parser import TemplateParser, ConfigParser
# get the real path of the script
REAL_PATH = os.path.dirname(os.path.realpath(__file__))

"""
Class controlling the photobooth
"""


class Photobooth:
    # define state machine for taking photos
    FSMstates = ['PowerOn', 'Start', 'CountdownPhoto', 'TakePhoto', 'ShowPhoto', 'CreateCard', 'ShowCard', 'PrintCard',
                 'RefillPaper', 'RefillInk', 'Restart']

    def __init__(self):
        # create the card objects
        self.layout = [PhotoCard(), PhotoCard()]

        self.initStateMachine()

        logging.debug("Read Config File")
        self.config = ConfigParser().readConfiguration()

        logging.debug("Config GPIO")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.config.pin_button_right, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.config.pin_button_left, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.config.pin_button_right, GPIO.FALLING, callback=self.Button2pressed, bouncetime=500)
        GPIO.add_event_detect(self.config.pin_button_left, GPIO.FALLING, callback=self.Button1pressed, bouncetime=500)

        logging.debug("Set TimeStamp for Buttons")
        self.time_stamp_button1 = time.time()
        self.time_stamp_button2 = time.time()

        self.button1active = False
        self.button2active = False

        logging.debug("Setup Camera")
        # Setup Camera
        try:
            self.camera = picamera.PiCamera()
        except:
            logging.CRITICAL("error initializing the camera - exiting")
            raise SystemExit

        self.camera.resolution = (self.config.photo_w, self.config.photo_h)
        self.camera.hflip = self.config.flip_screen_h
        self.camera.vflip = self.config.flip_screen_v
        self.startpreview()

        self.photonumber = 1

        self.cycleCounter = 0

        # load the Logo of the Photobooth and display it
        self.overlayscreen_logo = self.overlay_image_transparency(self.config.screen_logo, 0, 5)

        # find the USB Drive, if connected
        self.PhotoCopyPath = self.GetMountpoint()


        # load the Card Layout
        self.readCardConfiguration(self.config.templates_file_path)

        # Start the Application
        self.on_enter_PowerOn()

    # ends the Application
    def __del__(self):
        logging.debug("__del__ Function")
        self.stoppreview()
        self.camera.close()
        GPIO.setmode(GPIO.BCM)
        GPIO.cleanup()
        del self.imagetemplate1
        del self.imagetemplate2

    # Init the State machine controlling the Photobooth
    def initStateMachine(self):
        logging.debug("Init State Machine")
        self.machine = Machine(model=self, states=self.FSMstates, initial='PowerOn', ignore_invalid_triggers=True)
        self.machine.add_transition(source='PowerOn', dest='PowerOn',
                                    trigger='Button1')  # power on self test - check if printer is conected
        self.machine.add_transition(source='PowerOn', dest='Start',
                                    trigger='PrinterFound')  # printer is on -> goto start
        self.machine.add_transition(source='Start', dest='CountdownPhoto', trigger='Button1')
        self.machine.add_transition(source='Start', dest='CountdownPhoto', trigger='Button2')
        self.machine.add_transition(source='CountdownPhoto', dest='TakePhoto',
                                    trigger='CountdownPhotoTimeout')  # timeout
        self.machine.add_transition(source='TakePhoto', dest='ShowPhoto', trigger='None')
        self.machine.add_transition(source='ShowPhoto', dest='CountdownPhoto', trigger='Button1')  # N=N - Again
        self.machine.add_transition(source='ShowPhoto', dest='CountdownPhoto', trigger='Button2')  # N++ - Next Picture
        self.machine.add_transition(source='ShowPhoto', dest='CreateCard', trigger='MaxPics')  #
        self.machine.add_transition(source='CreateCard', dest='ShowCard',
                                    trigger='None')  # N==4 amount of Pictures reached
        self.machine.add_transition(source='ShowCard', dest='PrintCard', trigger='Button1')  # print
        # self.machine.add_transition(source='ShowCard', dest='Start', trigger='Button2')  # do not print
        # self.machine.add_transition(source='PrintCard', dest='Start', trigger='PrintDone')  # print done
        self.machine.add_transition(source='ShowCard', dest='Restart', trigger='Button2')  # do not print
        self.machine.add_transition(source='PrintCard', dest='Restart', trigger='PrintDone')  # print done

        self.machine.add_transition(source='RefillPaper', dest='Restart',
                                    trigger='Button1')  # Refill Paper on printer
        self.machine.add_transition(source='RefillPaper', dest='Restart',
                                    trigger='Button2')  # Refill Paper on printer
        self.machine.add_transition(source='RefillInk', dest='Start',
                                    trigger='Button1')  # Refill Ink on printer
        self.machine.add_transition(source='RefillInk', dest='Start',
                                    trigger='Button2')  # Refill Ink on printer
        self.machine.add_transition(source='PrintCard', dest='RefillPaper',
                                    trigger='PaperEmpty')  # Refill Paper on printer
        self.machine.add_transition(source='PrintCard', dest='RefillInk',
                                    trigger='InkEmpty')  # Refill Ink on printer

    # Read the Card Creating Configuration
    def readCardConfiguration(self, path):
        self.layoutParser = TemplateParser(path)
        self.layout = self.layoutParser.layout
        self.imagetemplate1 = image(filename=self.layout[0].templateFileName)
        self.imagetemplate2 = image(filename=self.layout[1].templateFileName)

    # read the global configuration, folders, resolution....
    #self.config = 

    def setCameraColor(self, color):
        if color == "bw":
            self.camera.color_effects = (128, 128)  # turn camera to black and white
        elif color == "sepia":
            self.camera.color_effects = (100, 150)  # turn camera to black and white
        else:
            self.camera.color_effects = None


    # Button1 callback function. Actions depends on state of the Photobooth state machine

    def Button1pressed(self, event):
        logging.debug("Button1pressed")
        time_now = time.time()

        #if button was pressed
        if self.button1active:
            if (time_now - self.time_stamp_button1) < 3.0:
                return

        self.button1active = True

        # wait until button is released
        while not GPIO.input(self.pin_button_left):
            time.sleep(0.1)
            # if button pressed longer than 5 sec -> shutdown
            if (time.time() - time_now) > 5:
                subprocess.call("sudo poweroff", shell=True)
                return

        time.sleep(0.2)

        # if in PowerOnState - ignore Buttons
        if self.state == "PowerOn":
            return

        # if in PrintCard State - ignore Buttons
        if self.state == "PrintCard":
            return

        # debounce the button
        if (time_now - self.time_stamp_button1) >= 0.5:
            logging.debug("Debounce time reached")
            # from state start -> choose layout 1
            if self.state == "Start":
                logging.debug("State == Start -> Set Photonumbers")
                self.MaxPhotos = self.layout[0].piccount
                self.current_Layout = 1
                self.photonumber = 1

            logging.debug("self.button1 start")
            self.Button1()
            logging.debug("self.button1 ready -> Set new TimeStamp")
            self.time_stamp_button1 = time.time()
            self.button1active = False
            self.button2active = False

    # Button2 callback function. Actions depends on state of the Photobooth state machine
    def Button2pressed(self, event):
        logging.debug("Button2pressed")
        time_now = time.time()

        if self.button2active:
            if (time_now - self.time_stamp_button2) < 3.0:
                return

        self.button2active = True

        # wait until button is released
        while not GPIO.input(self.pin_button_right):
            time.sleep(0.1)

        time.sleep(0.2)

        # if in PowerOnState - ignore Buttons
        if self.state == "PowerOn":
            return

        # if in PrintCard State - ignore Buttons
        if self.state == "PrintCard":
            return

        # debounce the button
        if (time_now - self.time_stamp_button2) >= 0.5:
            logging.debug("Debounce time reached")

            # from state start -> choose layout 2
            if self.state == "Start":
                logging.debug("State == Start -> Set Photonumbers")
                self.MaxPhotos = self.layout[1].piccount
                self.current_Layout = 2
                self.photonumber = 1

            # from state Show Photo -> increase Photonumber
            if self.state == 'ShowPhoto':
                logging.debug("State == ShowPhoto -> increase Photonumber")
                self.photonumber += 1

                # last photo reached
                if self.photonumber > self.MaxPhotos:
                    logging.debug("maxpics")
                    self.MaxPics()
                    logging.debug("self.button2 ready -> Set new TimeStamp")
                    self.time_stamp_button2 = time.time()
                    return

            logging.debug("self.button2 start")
            self.Button2()
            logging.debug("self.button2 ready -> Set new TimeStamp")
            self.time_stamp_button2 = time.time()
            self.button1active = False
            self.button2active = False

    # create a small preview of the layout for the first screen
    def createCardLayoutPreview(self):
        logging.debug("createCardLayoutPreview")

        logging.debug(self.layout[0])
        logging.debug(self.layout[0].piccount)

        # Load Preview Pics
        for i in range(0, self.layout[0].piccount):
            logging.debug(self.layout[0].picture[i])
            self.layout[0].picture[i].img = image(
                filename = os.path.join(REAL_PATH, 'Media/demo' + str(i + 1) + '.jpg'))
            self.layout[0].picture[i].ProcessImage()


        # Load Preview Pics
        for i in range(0, self.layout[1].piccount):
            logging.debug(self.layout[1].picture[i])
            self.layout[1].picture[i].img = image(
                filename = os.path.join(REAL_PATH, 'Media/demo' + str(i + 1) + '.jpg'))
            self.layout[1].picture[i].ProcessImage()

        self.layout[0].processCard()
        self.layout[1].processCard()

        self.layout[0].cardImage.resize(int(1868 / 8), int(1261 / 8))
        self.layout[1].cardImage.resize(int(1868 / 8), int(1261 / 8))

        screen = image(width=self.config.screen_w, height=self.config.screen_h)

        # create screen
        screen.composite(self.layout[0].cardImage, 131, self.config.screen_h - 184)
        screen.composite(self.layout[1].cardImage, self.config.screen_w - int(1868 / 8) - 131, self.config.screen_h - 184)

        # save screen to file for displaying
        screen.save(filename=self.screen_choose_layout)

    # This function captures the photo
    def taking_photo(self, photo_number):
        logging.debug("Taking Photo")
        # get the filename also for later use
        self.lastfilename = self.layout[self.current_Layout - 1].picture[photo_number - 1].fileName

        ## take a picture
        self.camera.capture(self.lastfilename)
        logging.debug("Photo (" + str(photo_number) + ") saved: " + self.lastfilename)

    def start_webserver(self): 
        app.setup_photobooth(self, logging)
        app.run("0.0.0.0", 4010, debug = False)

    # Power On Check State
    # check if printer is connected and turned on
    def on_enter_PowerOn(self):
        logging.debug("now on_enter_PowerOn")
        self.overlay_screen_turnOnPrinter = -1

        t2 = threading.Thread(target=self.start_webserver, args=[])
        t2.start()

        if not self.CheckPrinter():
            logging.debug("no printer found")
            self.overlay_screen_turnOnPrinter = self.overlay_image_transparency(self.config.screen_turnOnPrinter, 0, 3)

        while not self.CheckPrinter():
            time.sleep(2)

        logging.debug("printer found")
        self.PrinterFound()

    # leave Power On Check State
    def on_exit_PowerOn(self):
        logging.debug("now on_exit_PowerOn")

        # create the preview of the layouts
        self.createCardLayoutPreview()

        # remove overlay "turn on printer", if still on display
        self.remove_overlay(self.overlay_screen_turnOnPrinter)

    # Start State -> Show initail Screen
    def on_enter_Start(self):
        self.button1active = False
        self.button2active = False
        
        logging.debug("now on_enter_Start")
        self.overlay_screen_blackbackground = self.overlay_image(self.config.screen_black, 0, 2)
        self.overlay_choose_layout = self.overlay_image_transparency(self.config.screen_choose_layout, 0, 7)

    # leave start screen
    def on_exit_Start(self):
        logging.debug("now on_exit_Start")
        # on start of every photosession, create an unique filename, containing date and time
        self.layout[0].fileNamePrefix = self.get_base_filename_for_images()
        self.layout[1].fileNamePrefix = self.get_base_filename_for_images()
        self.remove_overlay(self.overlay_choose_layout)

    # countdown to zero and take picture
    def on_enter_CountdownPhoto(self):
        logging.debug("now on_enter_CountdownPhoto")

        #set the picture color
        self.setCameraColor(self.layout[self.current_Layout - 1].picture[self.photonumber - 1].color)

        # print the countdown
        self.overlay_screen_Countdown = self.overlay_image_transparency(self.config.screen_countdown_5, 0, 7)
        time.sleep(1)
        self.remove_overlay(self.overlay_screen_Countdown)
        self.overlay_screen_Countdown = self.overlay_image_transparency(self.config.screen_countdown_4, 0, 7)
        time.sleep(1)
        self.remove_overlay(self.overlay_screen_Countdown)
        self.overlay_screen_Countdown = self.overlay_image_transparency(self.config.screen_countdown_3, 0, 7)
        time.sleep(1)
        self.remove_overlay(self.overlay_screen_Countdown)
        self.overlay_screen_Countdown = self.overlay_image_transparency(self.config.screen_countdown_2, 0, 7)
        time.sleep(1)
        self.remove_overlay(self.overlay_screen_Countdown)
        self.overlay_screen_Countdown = self.overlay_image_transparency(self.config.screen_countdown_1, 0, 7)
        time.sleep(1)
        self.remove_overlay(self.overlay_screen_Countdown)
        self.overlay_screen_Countdown = self.overlay_image_transparency(self.config.screen_countdown_0, 0, 7)
        time.sleep(1)
        self.remove_overlay(self.overlay_screen_Countdown)

        # countdown finished
        self.CountdownPhotoTimeout()

    def on_exit_CountdownPhoto(self):
        logging.debug("now on_exit_CountdownPhoto")

    # take a pciture
    def on_enter_TakePhoto(self):
        logging.debug("now on_enter_TakePhoto")
        self.taking_photo(self.photonumber)
        self.to_ShowPhoto()

    def on_exit_TakePhoto(self):
        logging.debug("now on_exit_TakePhoto")
        # turn off camera preview
        self.stoppreview()

    # show the picture
    def on_enter_ShowPhoto(self):
        logging.debug("now on_enter_ShowPhoto")

        # show last photo and menu
        self.overlay_screen_black = self.overlay_image(self.config.screen_black, 0, 5)
        self.overlay_last_photo = self.overlay_image(self.lastfilename, 0, 6)
        self.overlay_photo_number = self.overlay_image_transparency(self.screen_photo[self.photonumber - 1], 0, 8)

        # log filename
        logging.debug(str(self.lastfilename))

        # copy photo to USB Drive
        # if self.PhotoCopyPath is not None:
        #     logging.debug(str(self.PhotoCopyPath))
        #     logging.debug(os.path.basename(str(self.lastfilename)))
        #     logging.debug((str(self.PhotoCopyPath)) + '/' + os.path.basename(str(self.lastfilename)))
        #     shutil.copyfile((str(self.lastfilename)),
        #                     ((str(self.PhotoCopyPath)) + '/' + os.path.basename(str(self.lastfilename))))

        logging.debug("start resizing")
        logging.debug("self.photonumber")
        logging.debug(self.photonumber)
        logging.debug("self.current_Layout")
        logging.debug(self.current_Layout)

        # load the image to the layoutobject and process (resize / rotate the image)
        self.layout[self.current_Layout - 1].picture[self.photonumber - 1].LoadImage()
        self.layout[self.current_Layout - 1].picture[self.photonumber - 1].ProcessImage()

        self.overlay_again_next = self.overlay_image_transparency(self.config.screen_again_next, 0, 7)

        logging.debug("finish resizing")

    # state show photo
    def on_exit_ShowPhoto(self):
        logging.debug("now on_exit_ShowPhoto")
        self.remove_overlay(self.overlay_screen_black)
        self.remove_overlay(self.overlay_last_photo)
        self.remove_overlay(self.overlay_again_next)
        self.remove_overlay(self.overlay_photo_number)
        self.startpreview()

    # create photocard
    def on_enter_CreateCard(self):
        logging.debug("now on_enter_CreateCard")
        logging.debug("self.MaxPhotos")
        logging.debug(self.MaxPhotos)

        self.overlay_wait = self.overlay_image_transparency(self.config.screen_wait, 0, 7)

        # name of saved card for later use
        self.cardfilename = self.layout[self.current_Layout - 1].cardFileName

        # create the card
        self.layout[self.current_Layout - 1].processCard()

        # save the card to disk
        self.layout[self.current_Layout - 1].cardImage.save(filename=self.layout[self.current_Layout - 1].cardFileName)

        self.to_ShowCard()

    def on_exit_CreateCard(self):
        logging.debug("now on_exit_CreateCard")
        self.remove_overlay(self.overlay_wait)

    # show the photocard
    def on_enter_ShowCard(self):
        logging.debug("now on_enter_ShowCard")

        self.overlay_last_card = self.overlay_image(self.cardfilename, 0, 6)
        self.overlay_screen_print = self.overlay_image_transparency(self.config.screen_print, 0, 7)

        logging.debug("copying")
        # copy card to photo folder
        # if self.PhotoCopyPath is not None:
        #     logging.debug("Copy Card to USB Drive")
        #     shutil.copy2(str(self.cardfilename), str(self.PhotoCopyPath))

    def on_exit_ShowCard(self):
        logging.debug("now on_exit_ShowCard")
        self.startpreview()
        self.remove_overlay(self.overlay_last_card)
        self.remove_overlay(self.overlay_screen_print)

    # print the photocard
    def on_enter_PrintCard(self):
        logging.debug("now on_enter_PrintCard")
        # restart camera
        self.stoppreview()
        self.startpreview()

        if self.printPicsEnable == False:
            logging.debug("print enable = false")

        # print photo?
        if self.config.printPicsEnable == True:
            logging.debug("print enable = true")

            # connect to cups
            conn = cups.Connection()
            printername = list(conn.getPrinters().keys())

            print(printername)
    
            # use first printer
            logging.debug("Printer Name: " + printername[0])
            conn.enablePrinter(printername[0])
    
            # check printer state
            printerstate = conn.getPrinterAttributes(printername[0], requested_attributes=["printer-state-message"])
    
            # if printer in error state ->
            if str(printerstate).find("error:") > 0:
                logging.debug(str(printerstate))
                conn.cancelAllJobs(printername[0], my_jobs=True, purge_jobs=True)
                if str(printerstate).find("06") > 0:
                    logging.debug("goto refill ink")
                    self.InkEmpty()
                    return
                if str(printerstate).find("03") > 0:
                    logging.debug("goto refill paper")
                    self.PaperEmpty()
                    return
                if str(printerstate).find("02") > 0:
                    logging.debug("goto refill paper")
                    self.PaperEmpty()
                    return
                else:
                    logging.debug("Printer error: unbekannt")
    
            # Send the picture to the printer
            conn.printFile(printername[0], self.cardfilename, "Photo Booth", {})
    
            # short wait
            time.sleep(5)
    
            stop = 0
            TIMEOUT = 60
    
            # Wait until the job finishes
            while stop < TIMEOUT:
                printerstate = conn.getPrinterAttributes(printername[0], requested_attributes=["printer-state-message"])
    
                if str(printerstate).find("error:") > 0:
                    logging.debug(str(printerstate))
                    if str(printerstate).find("06") > 0:
                        logging.debug("goto refill ink")
                        self.InkEmpty()
                        return
                    if str(printerstate).find("03") > 0:
                        logging.debug("goto refill paper")
                        self.PaperEmpty()
                        return
                    if str(printerstate).find("02") > 0:
                        logging.debug("goto refill paper")
                        self.PaperEmpty()
                        return
                    else:
                        logging.debug("Printer error: unbekannt")
    
                if printerstate.get("printer-state-message") == "":
                    logging.debug("printer-state-message = /")
                    break
                stop += 1
                time.sleep(1)
    
        else:
            logging.debug("Print disabled")

        self.PrintDone()

    def on_exit_PrintCard(self):
        logging.debug("now on_exit_PrintCard")

    # show refill paper instructions
    def on_enter_RefillPaper(self):
        logging.debug("now on_enter_RefillPaper")
        self.overlayscreen_refillpaper = self.overlay_image(self.config.screen_change_paper, 0, 8)

    def on_exit_RefillPaper(self):
        logging.debug("now on_exit_RefillPaper")
        self.remove_overlay(self.overlayscreen_refillpaper)

    # show refill ink instructions
    def on_enter_RefillInk(self):
        logging.debug("now on_enter_RefillInk")
        self.overlayscreen_refillink = self.overlay_image(self.config.screen_change_ink, 0, 8)

    def on_exit_RefillInk(self):
        logging.debug("now on_exit_RefillInk")
        self.remove_overlay(self.overlayscreen_refillink)

    # restart the programm -> restart camera to prevent memory leak of image overlay function!
    def on_enter_Restart(self):
        logging.debug("now on_enter_Restart")
        logging.debug("restart Camera")

        self.camera.close()

        # Setup Camera
        try:
            self.camera = picamera.PiCamera()
        except:
            logging.CRITICAL("error initializing the camera - exiting")
            raise SystemExit

        self.camera.resolution = (self.config.photo_w, self.config.photo_h)
        self.camera.hflip = self.config.flip_screen_h
        self.camera.vflip = self.config.flip_screen_v
        self.startpreview()

        # load the Logo of the Photobooth and display it
        self.overlayscreen_logo = self.overlay_image_transparency(self.config.screen_logo, 0, 5)

        self.to_Start()

    # start the camera
    def startpreview(self):
        logging.debug("Start Camera preview")
        self.camera.start_preview(resolution=(self.config.screen_w, self.config.screen_h))
        # camera.color_effects = (128, 128)  # SW
        pass

    # stop the camera
    def stoppreview(self):
        logging.debug("Stop Camera Preview")
        self.camera.stop_preview()
        pass

    # create filename based on date and time
    def get_base_filename_for_images(self):
        logging.debug("Get BaseName for ImageFiles")
        # returns the filename base
        base_filename = self.config.photo_abs_file_path + str(datetime.now()).split('.')[0]
        base_filename = base_filename.replace(' ', '_')
        base_filename = base_filename.replace(':', '-')

        logging.debug(base_filename)
        return base_filename

    # remove screen overlay
    def remove_overlay(self, overlay_id):
        # If there is an overlay, remove it
        logging.debug("Remove Overlay")
        logging.debug(overlay_id)
        if overlay_id != -1:
            self.camera.remove_overlay(overlay_id)

    # overlay one image on screen
    def overlay_image(self, image_path, duration=0, layer=3):
        # Add an overlay (and time.sleep for an optional duration).
        # If time.sleep duration is not supplied, then overlay will need to be removed later.
        # This function returns an overlay id, which can be used to remove_overlay(id).

        if not os.path.exists(image_path):
            logging.debug("Overlay Image path not found!")
            logging.debug(image_path)
            return -1

        logging.debug("Overlay Image")
        # Load the arbitrarily sized image
        img = Image.open(image_path)
        # Create an image padded to the required size with
        # mode 'RGB'
        pad = Image.new('RGB', (
            ((img.size[0] + 31) // 32) * 32,
            ((img.size[1] + 15) // 16) * 16,
        ))
        # Paste the original image into the padded one
        pad.paste(img, (0, 0))

        # Add the overlay with the padded image as the source,
        # but the original image's dimensions
        try:
            o_id = self.camera.add_overlay(pad.tobytes(), size=img.size)
        except AttributeError:
            o_id = self.camera.add_overlay(pad.tostring(), size=img.size)  # Note: tostring() is deprecated in PIL v3.x

        o_id.layer = layer

        logging.debug("Overlay ID = " + str(o_id))

        del img
        del pad

        if duration > 0:
            time.sleep(duration)
            self.camera.remove_overlay(o_id)
            return -1  # '-1' indicates there is no overlay
        else:
            return o_id  # we have an overlay, and will need to remove it later

    # overlay omage with transparency
    def overlay_image_transparency(self, image_path, duration=0, layer=3):
        # Add an overlay (and time.sleep for an optional duration).
        # If time.sleep duration is not supplied, then overlay will need to be removed later.
        # This function returns an overlay id, which can be used to remove_overlay(id).

        if not os.path.exists(image_path):
            logging.debug("Overlay Image path not found!")
            logging.debug(image_path)
            return -1

        logging.debug("Overlay Transparency Image")
        logging.debug(image_path)
        # Load the arbitrarily sized image
        img = Image.open(image_path)
        # Create an image padded to the required size with
        # mode 'RGB'
        pad = Image.new('RGBA', (
            ((img.size[0] + 31) // 32) * 32,
            ((img.size[1] + 15) // 16) * 16,
        ))
        # Paste the original image into the padded one
        pad.paste(img, (0, 0), img)

        # Add the overlay with the padded image as the source,
        # but the original image's dimensions
        try:
            o_id = self.camera.add_overlay(pad.tobytes(), size=img.size)
        except AttributeError:
            o_id = self.camera.add_overlay(pad.tostring(), size=img.size)  # Note: tostring() is deprecated in PIL v3.x

        o_id.layer = layer

        logging.debug("Overlay ID = " + str(o_id))

        del img
        del pad

        if duration > 0:
            time.sleep(duration)
            self.camera.remove_overlay(o_id)
            return -1  # '-1' indicates there is no overlay
        else:
            return o_id  # we have an overlay, and will need to remove it later

    # get the usb drive mount point
    def GetMountpoint(self):
        logging.debug("Get USB Drive Mount Point")
        try:
            context = pyudev.Context()
            removable = [device for device in context.list_devices(subsystem='block', DEVTYPE='disk') if
                         device.attributes.asstring('removable') == "1"]

            partitions = [removable[0].device_node for removable[0] in
                          context.list_devices(subsystem='block', DEVTYPE='partition', parent=removable[0])]
            for p in psutil.disk_partitions():
                if p.device in partitions:
                    logging.debug("Mountpoint = " + p.mountpoint)
                    return p.mountpoint

        except:
            logging.debug("No Drive Found")
            return None

    # check if the printer is connected and turned on
    def CheckPrinter(self):
        logging.debug("CheckPrinter")

        if self.config.printPicsEnable == False:
            logging.debug("printing disabled")
            return True

        busses = usb.busses()
        for bus in busses:
            devices = bus.devices
            for dev in devices:
                if dev.idVendor == 1193:
                    logging.debug("Printer Found")
                    logging.debug("  idVendor: %d (0x%04x)" % (dev.idVendor, dev.idVendor))
                    logging.debug("  idProduct: %d (0x%04x)" % (dev.idProduct, dev.idProduct))
                    return True
        logging.debug("PrinterNotFound")
        return False


# Main Routine
def main():
    # start logging
    log_filename = str(datetime.now()).split('.')[0]
    log_filename = log_filename.replace(' ', '_')
    log_filename = log_filename.replace(':', '-')

    loggingfolder = REAL_PATH + "/Log/"

    if not os.path.exists(loggingfolder):
        os.mkdir(loggingfolder)

    # logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG, filename=REAL_PATH+"/test.log")
    logging.basicConfig(format='%(asctime)s-%(module)s-%(funcName)s:%(lineno)d - %(message)s', level=logging.DEBUG,
                        filename=loggingfolder + log_filename + ".log")
    logging.info("info message")
    logging.debug("debug message")

    while True:

        logging.debug("Starting Photobooth")
        logging.debug("Setting up Webserver")

        photobooth = Photobooth()
        logging.debug("Setting up Webserver - done")


        while True:
            time.sleep(0.1)
            pass

        #photobooth.__del__()




if __name__ == "__main__":
    try:
      #t1 = threading.Thread(target=main, args=[])
        main()


    except KeyboardInterrupt:
        logging.debug("keyboard interrupt")

    except Exception as exception:
        logging.critical("unexpected error: " + str(exception))
        logging.exception(exception)

    finally:
        logging.debug("logfile closed")
