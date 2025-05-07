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

from io import BytesIO
import PIL
import datetime
import pydicom
from pydicom.valuerep import VR
import glob
import json
import numpy as np
import requests
import os

path_to_project = "data/papillon_big"
SOURCE = f"{path_to_project}/*.jpg"
calib_file = f"{path_to_project}/calibration.json"
images = sorted(glob.glob(SOURCE))
i = 0


with open(calib_file, "rb") as f:
    calib_dict = json.load(f)


intrinsics_matrix = calib_dict["intrinsics"]["cameraMatrix"]["data"]
distortion_matrix = calib_dict["intrinsics"]["distortionMatrix"]["data"]

study_uid = pydicom.uid.generate_uid()
series_uid = pydicom.uid.generate_uid()

extrinsics_list = calib_dict["extrinsics"]

thumbnails_width = calib_dict["thumbnails_width"]
thumbnails_height = calib_dict["thumbnails_height"]

commands = calib_dict["commands"]

for image in images:
    camera = os.path.basename(image)
    print(camera)
    ds = pydicom.dataset.Dataset()
    ds.PatientName = "Papillon^Test"
    ds.PatientID = "Papillon10275665"
    ds.PatientBirthDate = "20200914"
    ds.PatientSex = "O"

    now = datetime.datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")

    ds.ImageType = ["ORIGINAL", "PRIMARY"]
    ds.Laterality = "L"
    ds.LossyImageCompression = "01"
    ds.Modality = "XC"  # External-camera photography
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
    ds.InstanceNumber = i + 1

    # Basic encapsulation of color JPEG
    # https://pydicom.github.io/pydicom/stable/tutorials/pixel_data/compressing.html

    with open(image, "rb") as f:
        frames = [f.read()]
        ds.PixelData = pydicom.encaps.encapsulate(frames)

    with PIL.Image.open(image) as im:
        ds.Rows = im.size[1]
        ds.Columns = im.size[0]

        im.thumbnail((thumbnails_width, thumbnails_height))
        thumbnail_buffer = BytesIO()
        im.save(thumbnail_buffer, format="JPEG")
        thumbnail_buffer.getvalue()

    ds.PlanarConfiguration = 0
    ds.SamplesPerPixel = 3
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PhotometricInterpretation = "YBR_FULL_422"

    ds["PixelData"].VR = "OB"  # always for encapsulated pixel data
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    meta = pydicom.dataset.FileMetaDataset()
    meta.TransferSyntaxUID = pydicom.uid.JPEGBaseline8Bit
    ds.file_meta = meta

    extrinsics_matrix = np.matrix(extrinsics_list[camera]["matrix"]["data"]).reshape(
        (
            extrinsics_list[camera]["matrix"]["shape"]["row"],
            extrinsics_list[camera]["matrix"]["shape"]["col"],
        )
    )
    rotation_matrix = [i.item(0) for i in np.nditer(extrinsics_matrix[:3, :3])]
    translation_matrix = [i.item(0) for i in np.nditer(extrinsics_matrix[:3, 3])]

    block = ds.private_block(0x4231, "Sphaeroptica", create=True)
    block.add_new(0x27, VR.FD, intrinsics_matrix)
    block.add_new(0x28, VR.FD, rotation_matrix)
    block.add_new(0x29, VR.FD, translation_matrix)
    block.add_new(0x30, VR.FD, distortion_matrix)

    """
    "4231,1027"   : [ "FD", "IntrinsicsMatrix", 4, 4, "Sphaeroptica"],
    "4231,1028"   : [ "FD", "RotationMatrix", 9, 9, "Sphaeroptica"],
    "4231,1029"   : [ "FD", "TranslationMatrix", 3, 3, "Sphaeroptica"],
    "4231,1030"   : [ "FD", "DistortionCoefficients", 4, 8, "Sphaeroptica"]
    """
    out: BytesIO = BytesIO()
    ds.save_as(out, write_like_original=False)

    response = requests.post("http://localhost:8042/instances", out.getvalue())

    response.raise_for_status()

    uuid = response.json()["ID"]
    series_uuid = response.json()["ParentSeries"]

    r = requests.put(
        f"http://localhost:8042/instances/{uuid}/attachments/thumbnail",
        data=thumbnail_buffer.getvalue(),
    )
    i += 1

for shortcut in commands.keys():
    print(shortcut)
    coordinates = commands[shortcut]
    data = f"{coordinates['longitude']};{coordinates['latitude']}"
    response = requests.put(
        f"http://localhost:8042/series/{series_uuid}/metadata/shortcut_{shortcut[0]}",
        data=data,
    )
    response.raise_for_status()
