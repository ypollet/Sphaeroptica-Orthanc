from base64 import encodebytes
import io
import os
import json
import numpy as np

from photogrammetry import helpers, converters, reconstruction

import os

import orthanc


shortcuts_metadata = {"FRONT": "shortcut_F",
                      "POST": "shortcut_P",
                      "LEFT": "shortcut_L",
                      "RIGHT": "shortcut_R",
                      "INFERIOR": "shortcut_I",
                      "SUPERIOR": "shortcut_S"
                    }

cwd = os.getcwd()



# definitions
SITE = {
        'logo': 'Sphaeroptica',
        'version': '2.0.0'
}

OWNER = {
        'name': 'Royal Belgian Institute of Natural Sciences',
}



def triangulate(output, uri, **request):
  if request.method == 'POST':
    data = json.loads(request['body'])
    poses = data['poses']

    proj_points = []
    for image in poses:
      
      tags = json.loads(orthanc.RestApiGet(f"/instances/{image}/simplified-tags"))
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
    to_jsonify = {"result": {
                      "position": landmark_pos.tolist()
                    }
                  }
  
    output.AnswerBuffer(json.dumps(to_jsonify, indent = 3), 'application/json')
  
  else:
    output.SendMethodNotAllowed('POST')
orthanc.RegisterRestCallback('/sphaeroptica/triangulate', triangulate)
          

def reproject(output, uri, **request):
  if request.method == 'POST':
    data = request.get_json()
    position = np.array(data["position"])
    image_name = data['image']
    
    tags = json.loads(orthanc.RestApiGet(f"/instances/{image_name}/simplified-tags"))
    intrinsics = np.matrix([float(x) for x in tags["Intrinsics"].split("\\")]).reshape((3,3))
    dist_coeffs = np.matrix([float(x) for x in tags["DistortionCoefficients"].split("\\")]).reshape(1, -1)
    
    rotation = np.matrix([float(x) for x in tags["RotationMat"].split("\\")]).reshape((3,3))
    trans = np.matrix([float(x) for x in tags["TranslationMat"].split("\\")]).reshape((3,1))
    ext = np.hstack((rotation, trans))
    extrinsics =  np.vstack((ext, [0, 0, 0 ,1]))
    
    pose = reconstruction.project_points(position, intrinsics, ext, dist_coeffs)
    
    
    to_jsonify = {"result":{
          "pose": {"x": pose.item(0), "y": pose.item(1)}
       }}
  
    output.AnswerBuffer(json.dumps(to_jsonify, indent = 3), 'application/json')
  else:
    output.SendMethodNotAllowed('POST')

orthanc.RegisterRestCallback('/sphaeroptica/(.*)/reproject', reproject)

def get_response_thumbnail(instance):
    byte_arr = orthanc.RestApiGet(f"/instances/{instance}/attachments/thumbnail/data")
    encoded_img = encodebytes(byte_arr).decode('ascii') # encode as base64
    format = "jpeg"
    return {"image": f"data:image/{format};base64, {encoded_img}",
            "name" : instance,
            "format": format,
          }

def get_response_image(instance) -> bytearray:
    byte_arr = orthanc.RestApiGet(f"/instances/{instance}/content/7fe0-0010/1")
    return byte_arr


# send single image
def image(output, uri, **request):
  if request.method == 'GET':
    try:
      instanceId = request['groups'][0]
      image_binary = get_response_image(instanceId)
      output.AnswerBuffer(image_binary, 'text/plain')
    except Exception as error:
      orthanc.LogError(error)
  else:
    output.SendMethodNotAllowed('GET')
  

  

# send_shortcuts page
def shortcuts(output, uri, **request):
  if request.method == 'GET':
    try:
      seriesId = request['groups'][0]
      shortcut_dict = json.loads(orthanc.RestApiGet(f"/series/{seriesId}/metadata?expand"))
      
      to_jsonify = {}
      to_jsonify["commands"] = dict()
      for command, shortcut in shortcuts_metadata.items():
        to_jsonify["commands"][command] = shortcut_dict[shortcut]
      output.AnswerBuffer(json.dumps(to_jsonify), "application/json")
    except ValueError as e:
      orthanc.LogError(e)
  else:
    output.SendMethodNotAllowed('GET')

# send images
def images(output, uri, **request):
  if request.method == 'GET':
    try:
      seriesId = request['groups'][0]
      orthanc_dict = json.loads(orthanc.RestApiGet(f"/series/{seriesId}/instances-tags?simplify"))
      
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
      output.AnswerBuffer(json.dumps(to_jsonify), "application/json")
    except ValueError as e:
      orthanc.LogError(e)
  else:
    output.SendMethodNotAllowed('GET')
