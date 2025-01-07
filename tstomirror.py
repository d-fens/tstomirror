#!/usr/bin/env python
import os
import sys
import time
import logging
import urllib3
import requests
from zipfile import ZipFile
import zipfile
import shutil
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import binascii

# default variables, we need the DLCIndex to start the initial download and other files to find
# this is the current URL
URL_MIRROR = "http://oct2018-4-35-0-uam5h44a.tstodlc.eamobile.com/netstorage/gameasset/direct/simpsons/"
# this is the path within the URL_MIRROR we need to go to
DLC_INDEX = "dlc/DLCIndex.zip"

# setup logging to stdout and a file if we want to parse later
# this is useful for requests.get failures and also unexpected parsing failures of the xml files
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/output/debug.log"),
        logging.StreamHandler()
    ]
)

# setup a requests session to override files and act as a 'normal' tsto client
# this isn't needed but when mirroring it's best to act as 'normal'
session = requests.Session()
session.headers.update({
  # we don't mirror all headers so in theory br is accepted-encoding missing, connection keep-alive would be there too
  # tsto missing headers in this are EA-SELL-ID, mh_client_datetime, currentClientSessionId
  'User-Agent': urllib3.util.SKIP_HEADER,  # https://github.com/psf/requests/issues/5671
  'Content-Type': 'application/xml; charset=UTF-8',
  'mh_client_version': 'Android.4.69.5',
  'client_version': '4.69.5',
  'server_api_version': '4.0.01',
  'platform': 'android',
  'os_version': '9.0.0',
  'hw_model_id': '0 0.0',
  'data_param_1': '1495502718',
})

def check_file_ok(filename, delete=True):
  if not os.path.exists(filename):
    return False

  if os.path.exists(filename) and filename.endswith(".zip"):
    if not zipfile.is_zipfile(filename):
      if delete:
        os.remove(filename)  # delete invalid file
        logging.warning("Invalid zipfile (deleting) for %s", filename)
      else:
        logging.warning("Invalid zipfile for %s", filename)
      return False

    # TODO: crc32 check against xml value
    #with open(filename, 'rb') as fd:
    #  crc32 = binascii.crc32(fd.read())

  return True

# basic download file but to a replica folder so that mirroring the data later is easier
# this does not resume the data so there may be issues and improvments TODO: potential bugs
def mirror_file(url, cache=True, output_dir="/output/static/"):
  o = urlparse(url)
  f = output_dir + o.netloc + o.path

  # make sure things aren't broken completely when it was cached
  check_file_ok(f, delete=True)

  if os.path.exists(f) and cache:  # cached explicitly
    logging.debug("URL is cached, ignoring download %s", url)
    return f

  logging.info("Downloading %s", url)

  Path(f).parent.mkdir(parents=True, exist_ok=True)

  response = session.get(url, stream=True)
  if response.status_code != 200:
    logging.warning("Unexpected non-200 for %s", url)
    response.raise_for_status()

  with open(f, 'wb') as fd:
    shutil.copyfileobj(response.raw, fd)

  # make sure we haven't downloaded a broken file either
  check_file_ok(f, delete=True)

  return f

# parse the packages we need from each DLC index
def get_packages_from_dlc_index(filename):
  package_urls = []

  with ZipFile(filename) as z:
    if len(z.namelist()) > 1:
      logging.warning("[%s] DLC index file contains more than one file in the zip", filename)
    dlc_xml_filename = z.namelist()[0]
    logging.info("Attempting to parse packages from zipped DLC XML index file [%s] from the zip [%s]", dlc_xml_filename, filename)
    with z.open(dlc_xml_filename) as fd:
      root = ET.fromstring(fd.read())
      for package in root.iter('Package'):
        filename_nodes = package.findall('FileName')
        if len(filename_nodes) != 1:
          logging.warning("[%s] Unexpected FileName in Package is greater than 1", filename)

        filename_node = filename_nodes[0]  # lets take the first one, and there should only be one
        if 'val' not in filename_node.attrib:
          logging.warning("[%s] Unexpected 'val' missing from FileName node", filename)

        package_urls.append(URL_MIRROR + filename_node.attrib['val'].replace(':','/'))
  return package_urls

# needed for the DLC master list, don't cache this for any updates
file_path = mirror_file(URL_MIRROR + DLC_INDEX, cache=False)
# parse the master list and then download all the other DLC content, within each DLC is a package file that also needs to be downloaded
# these package files content the actual game resources e.g. some scripts, listings, images, music, video etc
with ZipFile(file_path) as z:
  if 'DLCIndex.xml' not in z.namelist():
    logging.warning('DLCIndex.xml does not exist in zip [%s], invalid index file', file_path)
    raise Exception("a")
  with z.open('DLCIndex.xml') as fd:
    root = ET.fromstring(fd.read())
    for index in root.iter('IndexFile'):
      if 'index' not in index.attrib:
        logging.warning("Missing index attribute in index element for master DLC indexes [%s]", file_path)
        continue
      dlc_url = index.attrib['index'].replace(':', '/')
      dlc_url = URL_MIRROR + dlc_url
      try:
        dlc_index = mirror_file(dlc_url)
      except requests.exceptions.HTTPError as e:
        continue  # broken dlc, just skip for now, a number of early DLCs are 404

      # download every package from *all* the DLCs, some will exist from the master
      # but there is alot in the other DLC indexes
      urls = get_packages_from_dlc_index(dlc_index)
      for url in urls:
        mirror_file(url, cache=True)
