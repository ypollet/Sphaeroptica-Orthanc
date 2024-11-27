# Sphaeroptica - 3D Viewer on calibrated images - Orthanc Plugin

# Copyright (C) 2024 Yann Pollet, Royal Belgian Institute of Natural Sciences

#

# This program is free software: you can redistribute it and/or

# modify it under the terms of the GNU Affero General Public License

# as published by the Free Software Foundation, either version 3 of

# the License, or (at your option) any later version.

# 

# This program is distributed in the hope that it will be useful, but

# WITHOUT ANY WARRANTY; without even the implied warranty of

# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU

# Affero General Public License for more details.

#

# You should have received a copy of the GNU Affero General Public License

# along with this program. If not, see <http://www.gnu.org/licenses/>.

from base64 import encodebytes
import io
import os
import json
import numpy as np

from photogrammetry import helpers, converters, reconstruction

import orthanc

##############################################################################
#                                                                            #
#------------------------------- SPHAEROPTICA -------------------------------#
#                                                                            #
##############################################################################


shortcuts_metadata = {"FRONT": "shortcut_F",
                      "POST": "shortcut_P",
                      "LEFT": "shortcut_L",
                      "RIGHT": "shortcut_R",
                      "INFERIOR": "shortcut_I",
                      "SUPERIOR": "shortcut_S"
                    }

# definitions
SITE = {
        'logo': 'Sphaeroptica',
        'version': '2.0.0'
}

OWNER = {
        'name': 'Royal Belgian Institute of Natural Sciences',
}

def triangulate(output, uri, **request):
  if request['method'] == 'POST':
    data = json.loads(request['body'])
    poses = data['poses']
    
    orthanc.LogWarning(f"Triangulate position of {len(poses)} poses")

    proj_points = []
    for image in poses:
      
      tags = json.loads(orthanc.RestApiGet(f"/instances/{image}/simplified-tags"))
      intrinsics = np.matrix([float(x) for x in tags["IntrinsicsMatrix"].split("\\")]).reshape((3,3))
      rotation = np.matrix([float(x) for x in tags["RotationMatrix"].split("\\")]).reshape((3,3))
      trans = np.matrix([float(x) for x in tags["TranslationMatrix"].split("\\")]).reshape((3,1))
      dist_coeffs = np.matrix([float(x) for x in tags["DistortionCoefficients"].split("\\")]).reshape(1, -1)
      #print(np.concatenate([dist_coeffs, np.matrix([0 for x in range(8 - dist_coeffs.shape[1])])], axis=1))
      
      ext = np.hstack((rotation, trans))
      extrinsics =  np.vstack((ext, [0, 0, 0 ,1]))
      
      proj_mat = reconstruction.projection_matrix(intrinsics, extrinsics)
      pose = np.matrix([poses[image]['x'], poses[image]['y']])
      undistorted_pos = reconstruction.undistort_iter(np.array([pose]).reshape((1,1,2)), intrinsics, dist_coeffs)
      proj_points.append(helpers.ProjPoint(proj_mat, undistorted_pos))
    
    # Triangulation computation with all the undistorted landmarks
    landmark_pos = reconstruction.triangulate_point(proj_points)
    to_jsonify = {
                    "position": landmark_pos.tolist()
                 }
                  
  
    output.AnswerBuffer(json.dumps(to_jsonify, indent = 3), 'application/json')
  
  else:
    output.SendMethodNotAllowed('POST')
orthanc.RegisterRestCallback('/sphaeroptica/triangulate', triangulate)
          

def reproject(output, uri, **request):
  if request['method'] == 'GET':
    instanceId = request['groups'][0]
    position = np.array([float(request["get"]["x"]), float(request["get"]["y"]), float(request["get"]["z"]), float(request["get"]["w"]) if "w" in request["get"] else 1.0])
    orthanc.LogWarning(f"Reproject {position} at {instanceId}")
    
    
    tags = json.loads(orthanc.RestApiGet(f"/instances/{instanceId}/simplified-tags"))
    intrinsics = np.matrix([float(x) for x in tags["IntrinsicsMatrix"].split("\\")]).reshape((3,3))
    dist_coeffs = np.matrix([float(x) for x in tags["DistortionCoefficients"].split("\\")]).reshape(1, -1)
    
    rotation = np.matrix([float(x) for x in tags["RotationMatrix"].split("\\")]).reshape((3,3))
    trans = np.matrix([float(x) for x in tags["TranslationMatrix"].split("\\")]).reshape((3,1))
    ext = np.hstack((rotation, trans))
    
    pose = reconstruction.project_points(position, intrinsics, ext, dist_coeffs)
    
    
    to_jsonify = {
                    "pose": {"x": pose.item(0), "y": pose.item(1)}
                  }
  
    output.AnswerBuffer(json.dumps(to_jsonify, indent = 3), 'application/json')
  else:
    output.SendMethodNotAllowed('GET')

orthanc.RegisterRestCallback('/sphaeroptica/(.*)/reproject', reproject)


def get_response_image(instance) -> bytearray:
    return orthanc.RestApiGet(f"/instances/{instance}/content/7fe0-0010/1")


# send single image
def image(output, uri, **request):
  if request['method'] == 'GET':
    instanceId = request['groups'][0]
    orthanc.LogWarning(f"Request full image of {instanceId}")
    try:
      instanceId = request['groups'][0]
      image_binary = get_response_image(instanceId)
      output.AnswerBuffer(image_binary, 'image/jpeg')
    except Exception as error:
      orthanc.LogError(error)
  else:
    output.SendMethodNotAllowed('GET')
  
orthanc.RegisterRestCallback('/sphaeroptica/(.*)/full-image', image)

# send single image
def thumbnail(output, uri, **request):
  if request['method'] == 'GET':
    instanceId = request['groups'][0]
    orthanc.LogWarning(f"Request full image of {instanceId}")
    try:
      instanceId = request['groups'][0]
      image_binary = get_response_image(instanceId)
      output.AnswerBuffer(image_binary, 'image/jpeg')
    except Exception as error:
      orthanc.LogError(error)
  else:
    output.SendMethodNotAllowed('GET')
  
orthanc.RegisterRestCallback('/sphaeroptica/(.*)/thumbnail', image)
  

# send_shortcuts page
def shortcuts(output, uri, **request):
  if request['method'] == 'GET':
    seriesId = request['groups'][0]
    orthanc.LogWarning(f"Request sphaeroptica shortcuts of {seriesId}")
    try:
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
orthanc.RegisterRestCallback('/sphaeroptica/(.*)/shortcuts', shortcuts)

# send images
def images(output, uri, **request):
  if request['method'] == 'GET':
    seriesId = request['groups'][0]
    orthanc.LogWarning(f"Request sphaeroptica camera images of {seriesId}")
    try:
      orthanc_dict = json.loads(orthanc.RestApiGet(f"/series/{seriesId}/instances-tags?simplify"))
      
      to_jsonify = {}
      encoded_images = []
      centers = {}
      centers_x = []
      centers_y = []
      centers_z = []
      for instance, tags in orthanc_dict.items():
        try:
          image_data = {"image": "",
            "name" : instance,
            "height" : tags["Rows"],
            "width" : tags["Columns"]
          }
          
          rotation = np.array([float(x) for x in tags["RotationMatrix"].split("\\")]).reshape((3,3))
          trans = np.array([float(x) for x in tags["TranslationMatrix"].split("\\")]).reshape((3,1))
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

orthanc.RegisterRestCallback('/sphaeroptica/(.*)/images', images)

extension = '''
    const SPHAEROPTICA_PLUGIN_SOP_CLASS_UID = '1.2.840.10008.5.1.4.1.1.77.1.4'
    $('#series').live('pagebeforeshow', function() {
      var seriesId = $.mobile.pageData.uuid;
    
      GetResource('/series/' + seriesId, function(series) {
        GetResource('/instances/' + series['Instances'][0] + '/tags?simplify', function(instance) {
          console.log(instance['SOPClassUID']);

          if (instance['SOPClassUID'] == SPHAEROPTICA_PLUGIN_SOP_CLASS_UID) {
            $('#sphaeroptica-button').remove();

            var b = $('<a>')
                .attr('id', 'sphaeroptica-button')
                .attr('data-role', 'button')
                .attr('href', '#')
                .attr('data-icon', 'search')
                .attr('data-theme', 'e')
                .text('Sphaeroptica Viewer')
                .button();

            b.insertAfter($('#series-info'));
            b.click(function(e) {
              window.open('../sphaeroptica/ui/index.html?series=' + seriesId);
            })
          }
        });
      });
    });
    '''
orthanc.ExtendOrthancExplorer(extension)