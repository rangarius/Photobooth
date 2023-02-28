import os
import json
from json import JSONEncoder
from flask import Flask, request, render_template, request, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
from config_parser import TemplateParser, ConfigParser
import logging
from datetime import datetime  # datetime routine
import secrets
from pathlib import Path
from flask_cors import CORS
import base64
        



class ConfigEncoder(JSONEncoder):
   def default(self, o):
      try:
          o.__json__
      except:
         return o.__dict__


REAL_PATH = os.path.dirname(os.path.realpath(__file__))

class WebServer(Flask): 
   photobooth = None
   configParser = None
   templateParser = None
   logging = None

   def setup_photobooth(self, photobooth, logging):
      #self.photobooth = photobooth
      self.photobooth= photobooth
      self.logging = logging


      logging.debug("Setting Up Config Parser")
      if self.configParser is None:
         self.configParser = ConfigParser(self.logging)
      self.configParser.readConfiguration()
      
      logging.debug("Setting Up Template Parser")
      if self.templateParser is None: 
         self.templateParser = TemplateParser(self.configParser.config.templates_file_path)
      self.templateParser.readCardConfiguration()
      # app.config[‘MAX_CONTENT_PATH’] = 

      
      
      
      #pass

app = WebServer(__name__)
CORS(app)
SECRET_FILE_PATH = Path(".flask_secret")

try:
   with SECRET_FILE_PATH.open("r") as secret_file:
      app.secret_key = secret_file.read()
      app.config['SECRET_KEY'] = app.secret_key
except FileNotFoundError:
   # Let's create a cryptographically secure code in that file
   with SECRET_FILE_PATH.open("w") as secret_file:
      app.secret_key = secrets.token_hex(32)
      secret_file.write(app.secret_key)
      app.config['SECRET_KEY'] = app.secret_key

#####CONFIG OPERATIONS
@app.route('/config', methods = ['GET', 'POST'])
def list_config():
   if request.method == "GET": 
      config = app.configParser.config
      configJSONData = json.dumps(config, indent=4, cls=ConfigEncoder)
      return configJSONData
   elif request.method == "POST":
      data = request.get_json()
      app.configParser(data)
      config = app.configParser.config
      configJSONData = json.dumps(config, indent=4, cls=ConfigEncoder)
      return configJSONData

@app.route("/config/save", methods=["GET"])
def save_config():
   app.configParser.writeConfig()

#####LAYOUT OPERATIONS
@app.route('/layouts', methods = ['GET'])
def list_layouts():
   layouts = app.templateParser.layout
   configJSONData = json.dumps(layouts, indent=4, cls=ConfigEncoder)
   print(configJSONData)
   return configJSONData

@app.route("/layout/save", methods = ["GET"])
def save_layout(id):
   app.templateParser.writeCardConfig()
   app.photobooth.to_Start()
   return jsonify({"msg": "success"})

@app.route("/layout/edit/<id>", methods = ["POST"])
def edit_layout(id):
   if request.method == "POST":
      data = request.get_json()
      if "new_image" in data:
         image_basecode = data["new_image"]
         with open(os.path.join(app.configParser.config.templates_file_path, "picture_"+str(id)+".png"), "wb") as fh:
            con_basecode = image_basecode.split(',')[1]
            img_str_encoded = str.encode(con_basecode)
            image_data = base64.urlsafe_b64decode(img_str_encoded)
            fh.write(image_data)
      app.templateParser.writeCardConfig()
      app.photobooth.to_Start()
   return jsonify({"msg": "success"})

@app.route("/upload/systemImage", methods=["POST"])
def upload_system_image():
   if request.method == "POST":
      data = request.get_json()
      if data["name"] & data["image_data"]  is not None:
         with open(app.configParser.config.templates_file_path, data["name"], "wb") as fh:
            con_basecode = data["image_data"].split(",")[1]
            img_str_encoded = str.encode(con_basecode)
            image_data = base64.urlsafe_b64decode(img_str_encoded)
            fh.write(image_data)
            app.photobooth.to_Start()

#####PHOTOBOOTH OPERATIONS
@app.route('/restart', methods = ['GET'])
def restart_photobooth():
   app.photobooth.to_Start()
   return "Success"

#####GENERAL HELPERS
@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)

####MOCKING

class Photobooth:

   def __init__(self) -> None:
      pass

   def to_Start():
      pass 
   


if __name__ == "__main__":

    log_filename = str(datetime.now()).split('.')[0]
    log_filename = log_filename.replace(' ', '_')
    log_filename = log_filename.replace(':', '-')

    loggingfolder = REAL_PATH + "/Log/"

    if not os.path.exists(loggingfolder):
        os.mkdir(loggingfolder)

    # logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG, filename=REAL_PATH+"/test.log")
    logging.basicConfig(format='%(asctime)s-%(module)s-%(funcName)s:%(lineno)d - %(message)s', level=logging.DEBUG,
                        filename=loggingfolder + "webserver_" + log_filename + ".log")
    logging.info("info message")
    logging.debug("debug message")
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