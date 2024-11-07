from base64 import encodebytes
import io
import os
import json
import numpy as np

from photogrammetry import helpers, converters, reconstruction

import pandas

import orthanc


##############################################################################
#                                                                            #
#------------------------------- RAPPORT ODS --------------------------------#
#                                                                            #
##############################################################################

def CreateReport(output, uri, **request):
    if request['method'] != 'GET' :
        output.SendMethodNotAllowed('GET')
    else:
        referer = request['headers'].get('referer', None)
        if referer is None:
            base = 'http://localhost:8042'
        else:
            base = os.path.dirname(os.path.dirname(referer))

        level = request['groups'][0]
        id = request['groups'][1]

        all_tags_sheet = None

        if level == 'instances':
            tags = json.loads(orthanc.RestApiGet('/instances/%s/tags' % id))
            data = []
            for (k, v) in tags.items():
                if v['Type'] == 'String':
                    value = v['Value']
                elif v['Type'] == 'Sequence':
                    value = '(sequence)'
                else:
                    value = '(other)'
                data.append([ '0x%s' % k.split(',') [0],
                              '0x%s' % k.split(',') [1],
                              v['Name'],
                              value ])

            all_tags_sheet = pandas.DataFrame(data, columns = [ 'Group', 'Element', 'Name', 'Value' ])

        main_tags = []

        info = json.loads(orthanc.RestApiGet('/%s/%s' % (level, id)))
        for (k, v) in info['MainDicomTags'].items():
            main_tags.append([ info['Type'], k, v ])

        if level == 'studies':
            studyInstanceUID = info['MainDicomTags']['StudyInstanceUID']
            for (k, v) in info['PatientMainDicomTags'].items():
                main_tags.append([ 'Patient', k, v ])
        elif level == 'series':
            study = json.loads(orthanc.RestApiGet('/series/%s/study' % id))
            seriesInstanceUID = info['MainDicomTags']['SeriesInstanceUID']
            studyInstanceUID = study['MainDicomTags']['StudyInstanceUID']
            for (k, v) in study['MainDicomTags'].items():
                main_tags.append([ 'Study', k, v ])
            for (k, v) in study['PatientMainDicomTags'].items():
                main_tags.append([ 'Patient', k, v ])

            someInstance = info['Instances'][0]
            metadata = json.loads(orthanc.RestApiGet('/instances/%s/metadata?expand' % someInstance))
            content = json.loads(orthanc.RestApiGet('/instances/%s/content' % someInstance))
            sopClassUID = metadata['SopClassUid']
        elif level == 'instances':
            someInstance = id
            metadata = json.loads(orthanc.RestApiGet('/instances/%s/metadata?expand' % id))
            content = json.loads(orthanc.RestApiGet('/instances/%s/content' % id))
            sopClassUID = metadata['SopClassUid']
            transferSyntaxUID = metadata['TransferSyntax']
            study = json.loads(orthanc.RestApiGet('/instances/%s/study' % id))
            series = json.loads(orthanc.RestApiGet('/instances/%s/series' % id))
            for (k, v) in series['MainDicomTags'].items():
                main_tags.append([ 'Series', k, v ])
            for (k, v) in study['MainDicomTags'].items():
                main_tags.append([ 'Study', k, v ])
            for (k, v) in study['PatientMainDicomTags'].items():
                main_tags.append([ 'Patient', k, v ])

        main_tags_sheet = pandas.DataFrame(main_tags, columns = [ 'Level', 'Name', 'Value' ])

        viewers = []

        if level == 'studies':
            viewers.append([ 'OHIF - Basic', os.path.join(base, 'ohif/viewer?url=../studies/%s/ohif-dicom-json' % id) ])
            viewers.append([ 'OHIF - Volume', os.path.join(base, 'ohif/viewer?hangingprotocolId=mprAnd3DVolumeViewport&url=../studies/%s/ohif-dicom-json' % id) ])
            viewers.append([ 'Kitware VolView', os.path.join(base, 'volview/index.html?names=[archive.zip]&urls=[../studies/%s/archive]') % id ])
            viewers.append([ 'Stone Web viewer', os.path.join(base, 'stone-webviewer/index.html?study=%s' % studyInstanceUID) ])
        elif level == 'series':
            viewers.append([ 'Kitware VolView', os.path.join(base, 'volview/index.html?names=[archive.zip]&urls=[../series/%s/archive]' % id) ])
            viewers.append([ 'Stone Web viewer', os.path.join(base, 'stone-webviewer/index.html?study=%s&series=%s' % (studyInstanceUID, seriesInstanceUID)) ])
            viewers.append([ 'Orthanc Web viewer', os.path.join(base, 'web-viewer/app/viewer.html?series=%s' % id) ])
            if sopClassUID == '1.2.840.10008.5.1.4.1.1.77.1.6':  # WSI
                viewers.append([ 'Whole-slide imaging viewer', os.path.join(base, 'wsi/app/viewer.html?series=%s' % id) ])
                viewers.append([ 'OpenSeadragon', os.path.join(base, 'wsi/app/openseadragon.html?image=../iiif/tiles/%s/info.json' % id) ])
                viewers.append([ 'Mirador', os.path.join(base, 'wsi/app/mirador.html?iiif-content=../iiif/series/%s/manifest.json' % id) ])
                viewers.append([ 'IIIF manifest', os.path.join(base, 'wsi/iiif/series/%s/manifest.json' % id) ])
        elif level == 'instances':
            if sopClassUID == '1.2.840.10008.5.1.4.1.1.104.1':  # PDF
                viewers.append([ 'Encapsulated PDF file', os.path.join(base, 'instances/%s/pdf' % id) ])

            if (transferSyntaxUID == '1.2.840.10008.1.2.4.50' and  # JPEG
                '7fe0-0010' in content and
                len(json.loads(orthanc.RestApiGet('/instances/%s/content/7fe0-0010' % id))) == 2):
                viewers.append([ 'Raw JPEG frame', os.path.join(base, 'instances/%s/content/7fe0-0010/1' % id) ])

        if level in [ 'instances', 'series' ]:
            if sopClassUID == '1.2.840.10008.5.1.4.1.1.104.3':  # STL
                viewers.append([ 'Basic STL viewer', os.path.join(base, 'stl/app/three.html?instance=%s' % someInstance) ])
                viewers.append([ 'Online3DViewer', os.path.join(base, 'stl/app/o3dv.html?instance=%s' % someInstance) ])
                viewers.append([ 'Encapsulated STL model', os.path.join(base, 'instances/%s/stl' % someInstance) ])

            if sopClassUID == '1.2.840.10008.5.1.4.1.1.66':  # Raw, for Nexus
                if ('4205-0010' in content and
                    '4205-1001' in content and
                    orthanc.RestApiGet('/instances/%s/content/4205-0010' % someInstance).decode('utf-8') == 'OrthancSTL'):
                    viewers.append([ 'Basic Nexus viewer', os.path.join(base, 'stl/nexus/threejs.html?model=../../instances/%s/nexus' % someInstance) ])
                    viewers.append([ '3DHOP', os.path.join(base, 'stl/3dhop/3DHOP_all_tools.html?instance=%s' % someInstance) ])
                    viewers.append([ 'Encapsulated Nexus model', os.path.join(base, 'instances/%s/nexus' % someInstance) ])


        viewers_sheet = pandas.DataFrame(viewers, columns = [ 'Name', 'URL' ])

        b = io.BytesIO()
        with pandas.ExcelWriter(b, engine='odf') as writer:
            viewers_sheet.to_excel(writer, sheet_name='Viewers')
            main_tags_sheet.to_excel(writer, sheet_name='Main DICOM tags')

            if not all_tags_sheet is None:
                all_tags_sheet.to_excel(writer, sheet_name='All tags')

        output.AnswerBuffer(b.getvalue(), 'application/vnd.oasis.opendocument.spreadsheet')

orthanc.RegisterRestCallback('/(patients|studies|series|instances)/(.*)/report.ods', CreateReport)



extension = ''

for item in [
        ('patients', 'patient'),
        ('studies', 'study'),
        ('series', 'series'),
        ('instances', 'instance'),
]:
    plural = item[0]
    singular = item[1]

    extension += '''
    $('#%s').live('pagebeforeshow', function() {
      $('#%s-report-button').remove();

      var b = $('<a>')
          .attr('id', '%s-report-button')
          .attr('data-role', 'button')
          .attr('href', '#')
          .attr('data-icon', 'gear')
          .attr('data-theme', 'e')
          .text('Download report')
          .button()
          .click(function(e) {
            window.open('../%s/' + $.mobile.pageData.uuid + '/report.ods');
          });

      b.insertAfter($('#%s-access'));
    });
    ''' % (singular, singular, singular, plural, singular)

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

'''def index(output, uri, **request):
  orthanc.LogWarning("Sending Sphaeroptica html")
  index_html = orthanc.RestApiGetAfterPlugins(f"/sphaeroptica/frontend/index.html")
  orthanc.LogWarning("Sphaeroptica html received")
  output.AnswerBuffer(index_html, 'text/html')
orthanc.RegisterRestCallback('/sphaeroptica/app', index)

def my_static(output, uri, **request):
  filename = request["groups"][0]
  file = orthanc.RestApiGetAfterPlugins(f"/sphaeroptica/frontend/{filename}")
  match filename.split(".")[-1]:
    case "js":
      mime = "text/javascript"
    case "css":
      mime = "text/css"
    case "html":
      mime = "text/html"
    case _:
      mime = "text/plain"
      
  orthanc.LogWarning(f"Sending static file {filename} : {mime}")
  output.AnswerBuffer(file, mime)
orthanc.RegisterRestCallback('/sphaeroptica/static/(.*)', my_static)'''

def triangulate(output, uri, **request):
  if request['method'] == 'POST':
    data = json.loads(request['body'])
    poses = data['poses']
    
    orthanc.LogWarning(f"Triangulate position of {len(poses)} poses")

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
    intrinsics = np.matrix([float(x) for x in tags["Intrinsics"].split("\\")]).reshape((3,3))
    dist_coeffs = np.matrix([float(x) for x in tags["DistortionCoefficients"].split("\\")]).reshape(1, -1)
    
    rotation = np.matrix([float(x) for x in tags["RotationMat"].split("\\")]).reshape((3,3))
    trans = np.matrix([float(x) for x in tags["TranslationMat"].split("\\")]).reshape((3,1))
    ext = np.hstack((rotation, trans))
    
    pose = reconstruction.project_points(position, intrinsics, ext, dist_coeffs)
    
    
    to_jsonify = {
                    "pose": {"x": pose.item(0), "y": pose.item(1)}
                  }
  
    output.AnswerBuffer(json.dumps(to_jsonify, indent = 3), 'application/json')
  else:
    output.SendMethodNotAllowed('GET')

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
  if request['method'] == 'GET':
    instanceId = request['groups'][0]
    orthanc.LogWarning(f"Request full image of {instanceId}")
    try:
      instanceId = request['groups'][0]
      image_binary = get_response_image(instanceId)
      output.AnswerBuffer(image_binary, 'text/plain')
    except Exception as error:
      orthanc.LogError(error)
  else:
    output.SendMethodNotAllowed('GET')
  
orthanc.RegisterRestCallback('/sphaeroptica/(.*)/full-image', image)
  

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

orthanc.RegisterRestCallback('/sphaeroptica/(.*)/images', images)

extension += '''
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