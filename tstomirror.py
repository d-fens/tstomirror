#!/usr/bin/env python
import os
import logging
import aiohttp
import asyncio
from aiohttp import ClientSession, ClientTimeout
from zipfile import ZipFile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import urllib3

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

# rate limit semaphore
sem = asyncio.Semaphore(10)

async def check_file_ok(filename, delete=True):
    if not os.path.exists(filename):
        return False

    if os.path.exists(filename) and filename.endswith(".zip"):
        if not zipfile.is_zipfile(filename):
            if delete:
                os.remove(filename)
                logging.warning("Invalid zipfile (deleting) for %s", filename)
            else:
                logging.warning("Invalid zipfile for %s", filename)
            return False

    return True

async def download_file(url, session, cache=True, output_dir="/output/"):
    async with sem:
        o = urlparse(url)
        f = output_dir + o.netloc + o.path

        await check_file_ok(f, delete=True)

        if os.path.exists(f) and cache:
            logging.debug("URL is cached, ignoring download %s", url)
            return f

        logging.info("Downloading %s", url)

        Path(f).parent.mkdir(parents=True, exist_ok=True)

        async with session.get(url) as response:
            if response.status != 200:
                logging.warning("Unexpected non-200 for %s", url)
                response.raise_for_status()

            with open(f, 'wb') as fd:
                async for chunk in response.content.iter_chunked(1024):
                    fd.write(chunk)

        await check_file_ok(f, delete=True)
        return f

async def get_packages_from_dlc_index(filename):
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

                filename_node = filename_nodes[0]
                if 'val' not in filename_node.attrib:
                    logging.warning("[%s] Unexpected 'val' missing from FileName node", filename)

                package_urls.append(URL_MIRROR + filename_node.attrib['val'].replace(':', '/'))
    return package_urls

async def main():
    # setup a requests session to override files and act as a 'normal' tsto client
    # this isn't needed but when mirroring it's best to act as 'normal'
    # we don't mirror all headers so in theory br is accepted-encoding missing, connection keep-alive would be there too
    # tsto missing headers in this are EA-SELL-ID, mh_client_datetime, currentClientSessionId
    headers = {
        'User-Agent': urllib3.util.SKIP_HEADER,
        'Content-Type': 'application/xml; charset=UTF-8',
        'mh_client_version': 'Android.4.69.5',
        'client_version': '4.69.5',
        'server_api_version': '4.0.01',
        'platform': 'android',
        'os_version': '9.0.0',
        'hw_model_id': '0 0.0',
        'data_param_1': '1495502718',
    }
        
    async with ClientSession(headers=headers, timeout=ClientTimeout(total=60)) as session:
        file_path = await download_file(URL_MIRROR + DLC_INDEX, session, cache=False)
        with ZipFile(file_path) as z:
            if 'DLCIndex.xml' not in z.namelist():
                logging.warning('DLCIndex.xml does not exist in zip [%s], invalid index file', file_path)
                raise Exception("a")
            with z.open('DLCIndex.xml') as fd:
                root = ET.fromstring(fd.read())
                tasks = []
                for index in root.iter('IndexFile'):
                    if 'index' not in index.attrib:
                        logging.warning("Missing index attribute in index element for master DLC indexes [%s]", file_path)
                        continue
                    dlc_url = index.attrib['index'].replace(':', '/')
                    dlc_url = URL_MIRROR + dlc_url
                    try:
                        dlc_index = await download_file(dlc_url, session)
                    except aiohttp.ClientResponseError:
                        continue

                    urls = await get_packages_from_dlc_index(dlc_index)
                    for url in urls:
                        tasks.append(download_file(url, session, cache=True))

                await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
