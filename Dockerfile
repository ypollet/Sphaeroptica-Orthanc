# Sphaeroptica - 3D Viewer on calibrated images - Orthanc Plugin

# Copyright (C) 2024 Yann Pollet, Royal Belgian Institute of Natural Sciences

#

# This program is free software: you can redistribute it and/or

# modify it under the terms of the GNU General Public License as

# published by the Free Software Foundation, either version 3 of the

# License, or (at your option) any later version.

# 

# This program is distributed in the hope that it will be useful, but

# WITHOUT ANY WARRANTY; without even the implied warranty of

# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU

# General Public License for more details.

#

# You should have received a copy of the GNU General Public License

# along with this program. If not, see <http://www.gnu.org/licenses/>.

FROM jodogne/orthanc-python

# This example is using a virtual env that is not mandatory when using Docker containers
# but recommended since python 3.11 and Debian bookworm based images where you get a warning
# when installing system-wide packages.
RUN apt-get update && apt install -y python3-venv
RUN python3 -m venv /.venv

# for Sphaeroptica
RUN /.venv/bin/pip install numpy colour
ENV PYTHONPATH=/.venv/lib64/python3.11/site-packages/

RUN mkdir /etc/orthanc/python
RUN mkdir /etc/orthanc/python/photogrammetry
COPY photogrammetry/* /etc/orthanc/python/photogrammetry


RUN mkdir /etc/orthanc/sphaeroptica
COPY frontend/dist/ /etc/orthanc/sphaeroptica