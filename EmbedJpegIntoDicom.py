from io import BytesIO
import PIL
import datetime
import pydicom
from pydicom.valuerep import VR
import glob
import json
import numpy as np
from pathlib import Path
home = Path.home()
import requests

path_to_project = "Numerisation/test_dicomization/test_sphaeroptica/Study/Serie"
SOURCE = f'{home}/{path_to_project}/*.jpg'
calib_file = f'{home}/{path_to_project}/calibration.json'
images = sorted(glob.glob(SOURCE))
i = 0


with open(calib_file, 'rb') as f:
    calib_dict = json.load(f)
    
    
intrinsics_matrix = [i.item(0) for i in np.nditer(np.array(calib_dict["intrinsics"]["camera matrix"]["matrix"]))]
distortion_matrix = [i.item(0) for i in np.nditer(np.array(calib_dict["intrinsics"]["distortion matrix"]["matrix"]))]

study_uid = pydicom.uid.generate_uid()
series_uid = pydicom.uid.generate_uid()

extrinsics_list = calib_dict["extrinsics"]

for image in images:    
    camera = os.path.basename(image)
    print(camera)
    ds = pydicom.dataset.Dataset()
    ds.PatientName = 'Philodicus^sp_dcm'
    ds.PatientID = 'EADIPT123456453'
    ds.PatientBirthDate = '20200914'
    ds.PatientSex = 'O'

    now = datetime.datetime.now()
    ds.StudyDate = now.strftime('%Y%m%d')
    ds.StudyTime = now.strftime('%H%M%S')

    ds.ImageType = [ 'ORIGINAL', 'PRIMARY' ]
    ds.Laterality = 'L'
    ds.LossyImageCompression = '01'
    ds.Modality = 'XC'  # External-camera photography
    ds.SOPClassUID = pydicom.uid.VLPhotographicImageStorage
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = series_uid
    ds.StudyInstanceUID = study_uid

    ds.AccessionNumber = None
    ds.ReferringPhysicianName = None
    ds.SeriesNumber = None
    ds.StudyID = None
    ds.InstanceNumber = None
    ds.Manufacturer = None
    ds.PatientOrientation = None
    ds.AcquisitionContextSequence = None
    ds.InstanceNumber = i+1


    # Basic encapsulation of color JPEG
    # https://pydicom.github.io/pydicom/stable/tutorials/pixel_data/compressing.html

    with open(image, 'rb') as f:
        frames = [ f.read() ]
        ds.PixelData = pydicom.encaps.encapsulate(frames)

    with PIL.Image.open(image) as im:
        ds.Rows = im.size[1]
        ds.Columns = im.size[0]
        
        im.thumbnail((1500, 1000))
        thumbnail_buffer = BytesIO()
        im.save(thumbnail_buffer, format="JPEG")
        thumbnail_buffer.getvalue()

    ds.PlanarConfiguration = 0
    ds.SamplesPerPixel = 3
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PhotometricInterpretation = 'YBR_FULL_422'

    ds['PixelData'].VR = 'OB'  # always for encapsulated pixel data
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    meta = pydicom.dataset.FileMetaDataset()
    meta.TransferSyntaxUID = pydicom.uid.JPEGBaseline8Bit
    ds.file_meta = meta
    
    extrinsics_matrix = np.array(extrinsics_list[camera]["matrix"])
    rotation_matrix = [i.item(0) for i in np.nditer(extrinsics_matrix[:3,:3])]
    translation_matrix = [i.item(0) for i in np.nditer(extrinsics_matrix[:3,3])]
    
    block = ds.private_block(0x4231, "Sphaeroptica", create=True)
    block.add_new(0x27, VR.FD, intrinsics_matrix)
    block.add_new(0x28, VR.FD, rotation_matrix)
    block.add_new(0x29, VR.FD, translation_matrix)
    block.add_new(0x30, VR.FD, distortion_matrix)
    
    """
    "4231,1027"   : [ "FD", "Intrinsics", 4, 4, "Sphaeroptica"],
    "4231,1028"   : [ "FD", "RotationMat", 9, 9, "Sphaeroptica"],
    "4231,1029"   : [ "FD", "TranslationMat", 3, 3, "Sphaeroptica"],
    "4231,1030"   : [ "FD", "DistortionCoefficients", 4, 8, "Sphaeroptica"]
    """
    file_name = f'/home/psadmin/Numerisation/test_dicomization/dicomized_sphaeroptica/sc_{i : 06d}.dcm'

    ds.save_as(file_name, write_like_original=False)
    
    with open(file_name, 'rb') as f:
        bytes_dcm = f.read()
    
    response = requests.post('http://localhost:8042/instances', bytes_dcm)
    
    response.raise_for_status()
    
    uuid = response.json()["ID"]
    
    r = requests.put(f'http://localhost:8042/instances/{uuid}/attachments/thumbnail', data=thumbnail_buffer.getvalue())
    i += 1
