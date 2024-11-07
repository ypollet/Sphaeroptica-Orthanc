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


RUN /.venv/bin/pip install pandas