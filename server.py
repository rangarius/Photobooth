import os
import json
from json import JSONEncoder
from flask import Flask, request, render_template, request, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
from config_parser import TemplateParser
import logging
from datetime import datetime  # datetime routine
import secrets
from pathlib import Path
from flask_cors import CORS
import base64



class ConfigEncoder(JSONEncoder):
   def default(self, o):
      return o.__dict__

REAL_PATH = os.path.dirname(os.path.realpath(__file__))

app = Flask(__name__)
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

app.config['UPLOAD_FOLDER'] = os.path.dirname(app.photobooth.CardConfigFile)
path = app.photobooth.CardConfigFile
configParser = TemplateParser(path)



# app.config[‘MAX_CONTENT_PATH’] = 
configParser.readCardConfiguration()

@app.route('/', methods = ['GET'])
def hello_world():
   image = False
   layouts = configParser.layout
   configJSONData = json.dumps(layouts, indent=4, cls=ConfigEncoder)
   return configJSONData


@app.route("/edit/<id>", methods = ["POST"])
def edit_layout(id):
   if request.method == "POST":
      data = request.get_json()
      if "new_image" in data:
         image_basecode = data["new_image"]
         with open(os.path.join(app.config['UPLOAD_FOLDER'], "picture"+data["id"]+".png"), "wb") as fh:
            con_basecode = image_basecode.split(',')[1]
            img_str_encoded = str.encode(con_basecode)
            image_data = base64.urlsafe_b64decode(img_str_encoded)
            fh.write(image_data)
      configParser.writeCardConfig(data)
   return jsonify({"msg": "success"})

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)

