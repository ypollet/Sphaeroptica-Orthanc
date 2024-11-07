from flask import Flask, send_from_directory, jsonify, request, send_file, abort

from flask_cors import CORS, cross_origin

from base64 import encodebytes
import io
import os
import json
import numpy as np

from photogrammetry import helpers, converters, reconstruction

import os
import dotenv

import requests
from requests.auth import HTTPBasicAuth

dotenv.load_dotenv(".env.local") | dotenv.load_dotenv() 


auth = None #HTTPBasicAuth(os.environ.get("ORTHANC_USERNAME"), os.environ.get("ORTHANC_PASSWD"))
orthanc_server = os.environ.get("ORTHANC_SERVER")

shortcuts_metadata = {"FRONT": "shortcut_F",
                      "POST": "shortcut_P",
                      "LEFT": "shortcut_L",
                      "RIGHT": "shortcut_R",
                      "INFERIOR": "shortcut_I",
                      "SUPERIOR": "shortcut_S"
                    }


cwd = os.getcwd()

# configuration
DEBUG = True
DATA_FOLDER = f"{cwd}/data"

# instantiate the app
app = Flask(__name__, static_folder="frontend/dist/static", template_folder="frontend/dist", static_url_path="/static")
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config.from_object(__name__)

# definitions
SITE = {
        'logo': 'Sphaeroptica',
        'version': '2.0.0'
}

OWNER = {
        'name': 'Royal Belgian Institute of Natural Sciences',
}

# pass data to the frontend
site_data = {
    'site': SITE,
    'owner': OWNER
}
@app.route('/<path:filename>')
def serveFile(filename):
  print(f"Sending file : {filename}")
  return send_from_directory("frontend/dist", filename)
'''
@app.route('/static/<path:filename>')
def my_static(filename):
  return send_from_directory("frontend/dist/static", filename)'''


@app.route('/<id>/triangulate', methods=['POST'])
def triangulate(id):
  if request.method == 'POST':
    data = request.get_json()
    poses = data['poses']

    proj_points = []
    for image in poses:
      response = requests.get(url=f"{orthanc_server}/instances/{image}/simplified-tags",auth=auth)
      if not response.ok:
        abort(404)
      tags : dict = json.loads(response.content)
      intrinsics = np.matrix([float(x) for x in tags["Intrinsics"].split("\\")]).reshape((3,3))
      rotation = np.matrix([float(x) for x in tags["RotationMat"].split("\\")]).reshape((3,3))
      trans = np.matrix([float(x) for x in tags["TranslationMat"].split("\\")]).reshape((3,1))
      dist_coeffs = np.matrix([float(x) for x in tags["DistortionCoefficients"].split("\\")]).reshape(1, -1)
      #print(np.concatenate([dist_coeffs, np.matrix([0 for x in range(8 - dist_coeffs.shape[1])])], axis=1))
      
      ext = np.hstack((rotation, trans))
      extrinsics =  np.vstack((ext, [0, 0, 0 ,1]))
      
      proj_mat = reconstruction.projection_matrix(intrinsics, extrinsics)
      pose = np.matrix([poses[image]['x'], poses[image]['y']])
      undistorted_pos = reconstruction.undistort_iter(np.array([pose]).reshape((1,1,2)), intrinsics, dist_coeffs)
      print(f"{image} => \n{proj_mat}\n{undistorted_pos}")
      proj_points.append(helpers.ProjPoint(proj_mat, undistorted_pos))
    
    # Triangulation computation with all the undistorted landmarks
    landmark_pos = reconstruction.triangulate_point(proj_points)
    print(f"Position = {landmark_pos}") 
  
    return {"result": {
          "position": landmark_pos.tolist()
       }
    }
          

@app.route('/<id>/reproject', methods=['POST'])
def reproject(id):
  if request.method == 'POST':
    data = request.get_json()
    position = np.array(data["position"])
    image_name = data['image']
    
    response = requests.get(url=f"{orthanc_server}/instances/{image_name}/simplified-tags",auth=auth)
    if not response.ok:
      abort(404)
    tags : dict = json.loads(response.content)
    intrinsics = np.matrix([float(x) for x in tags["Intrinsics"].split("\\")]).reshape((3,3))
    dist_coeffs = np.matrix([float(x) for x in tags["DistortionCoefficients"].split("\\")]).reshape(1, -1)
    
    rotation = np.matrix([float(x) for x in tags["RotationMat"].split("\\")]).reshape((3,3))
    trans = np.matrix([float(x) for x in tags["TranslationMat"].split("\\")]).reshape((3,1))
    ext = np.hstack((rotation, trans))
    extrinsics =  np.vstack((ext, [0, 0, 0 ,1]))
    
    pose = reconstruction.project_points(position, intrinsics, ext, dist_coeffs)
    
    
    return {"result":{
          "pose": {"x": pose.item(0), "y": pose.item(1)}
       }}

def get_response_thumbnail(instance):
    byte_arr = requests.get(url=f"{orthanc_server}/instances/{instance}/attachments/thumbnail/data",auth=auth).content
    encoded_img = encodebytes(byte_arr).decode('ascii') # encode as base64
    format = "jpeg"
    return {"image": f"data:image/{format};base64, {encoded_img}",
            "name" : instance,
            "format": format,
          }

def get_response_image(instance):
    byte_arr = requests.get(url=f"{orthanc_server}/instances/{instance}/content/7fe0-0010/1",auth=auth).content
    return byte_arr


# send single image
@app.route('/<id>/<image_id>')
@cross_origin()
def image(id,image_id):
  try:
    image_binary = get_response_image(image_id)
    return send_file(
      io.BytesIO(image_binary),
      mimetype='image/jpeg',
      as_attachment=False)       
  except Exception as error:
    print(error)
  

  

# send_shortcuts page
@app.route('/<id>/shortcuts')
@cross_origin()
def shortcuts(id):
  response = requests.get(url=f"{orthanc_server}/series/{id}/metadata?expand",auth=auth)
  if not response.ok:
    abort(404)
  
  shortcut_dict = json.loads(response.content)
  to_jsonify = {}
  to_jsonify["commands"] = dict()
  for command, shortcut in shortcuts_metadata.items():
    to_jsonify["commands"][command] = shortcut_dict[shortcut]
  return jsonify(to_jsonify)


# send images
@app.route('/<id>/images')
@cross_origin()
def images(id):
  
  
  response = requests.get(url=f"{orthanc_server}/series/{id}/instances-tags?simplify",auth=auth)
  if not response.ok:
    abort(404)
  orthanc_dict : dict = json.loads(response.content)
  
  to_jsonify = {}
  encoded_images = []
  centers = {}
  centers_x = []
  centers_y = []
  centers_z = []
  for instance, tags in orthanc_dict.items():
    try:
      image_data = get_response_thumbnail(instance)
      image_data.update({
        "height" : tags["Rows"],
        "width" : tags["Columns"]
      })
      
      rotation = np.array([float(x) for x in tags["RotationMat"].split("\\")]).reshape((3,3))
      trans = np.array([float(x) for x in tags["TranslationMat"].split("\\")]).reshape((3,1))
      C = converters.get_camera_world_coordinates(rotation, trans)
      
      centers[instance] = C
      centers_x.append(C.item(0)) # x
      centers_y.append(C.item(1)) # y
      centers_z.append(C.item(2)) # z
            
      encoded_images.append(image_data)
    except Exception as error:
       print(error)
       continue
  _, center = reconstruction.sphereFit(centers_x, centers_y, centers_z)
  
  for image_data in encoded_images:
    instance = image_data["name"]
    C = centers[instance]
    vec = C - center
    long, lat = converters.get_long_lat(vec)
    image_data["longitude"], image_data["latitude"] = converters.rad2degrees(long), converters.rad2degrees(lat)
    
  to_jsonify["images"] = encoded_images
  return jsonify({'result': to_jsonify})

if __name__ == '__main__':
  print("HELLO")
  app.run(debug=True, port=5001)
