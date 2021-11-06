import json
import os
import platform
import shutil
import subprocess
import time
import urllib.request

from collections import OrderedDict
from operator import itemgetter
from urllib.request import Request
from typing import Any, List, Union
from xml.etree import ElementTree as ET

from models.messages import DRIVER_XML, DRIVER_XML_DEPENDENCY
from models.product import Dependency, Product
from models.script_template import INSTALL_APP_APPLE_SCRIPT


class APM:
    url_templates = {
        'xml': 'https://cdn-ffc.oobesaas.adobe.com/core/v4/products/all?_type=xml&channel=ccm,sti&platform=macuniversal,osx10-64,osx10,arm64&productType=Desktop',
        'json': 'https://cdn-ffc.oobesaas.adobe.com/core/v3/applications'
    }

    ADOBE_REQ_HEADERS = {
        'X-Adobe-App-Id': 'accc-hdcore-desktop',
        'User-Agent': 'Adobe Application Manager 2.0',
        'X-Api-Key': 'CC_HD_ESD_1_0'
    }

    product_listing = None

    def __init__(self):
        self.platform = self._get_platform()
        self.get_product_listing()

    def _get_platform(self) -> str:
        return platform.machine()

    def _get_progress(self, total: int, elapsed: float, size: float) -> tuple[float, float, float, float]:
        progress = round(total / pow(1024, 2), 2)
        adj_size = round(size / pow(1024, 2), 2)
        speed = round((progress / elapsed), 2)
        percent = round((progress / adj_size) * 100, 2)

        return progress, adj_size, speed, percent

    def _download(self, file_path: str, url: str, size: int, headers: dict[Any, Any]) -> None:
        r = Request(url, headers=headers)

        with urllib.request.urlopen(r) as rl:
            with open(file_path, 'wb') as f:
                total_bytes = 0
                start = time.time()

                while True:
                    elapsed = 1 + time.time() - start
                    chunk = rl.read(8192)
                    total_bytes += len(chunk)

                    if not chunk:
                        break

                    progress, adj_size, speed, percent = self._get_progress(
                        total_bytes, elapsed, size)

                    print(
                        f'{file_path} -> {progress:.2f} MB / {adj_size:.2f} MB\t{percent:.2f}%\t{speed:.2f} MB\\s', end='\r')
                    f.write(chunk)

    @staticmethod
    def _r(url, headers: dict[str, str]) -> str:
        r = Request(url, headers=headers)

        with urllib.request.urlopen(r) as rl:
            return rl.read()

    @staticmethod
    def string_to_xml(xml_string: str) -> ET.Element:
        return ET.fromstring(xml_string)

    def _xml_to_product(self, p: ET.Element, productGuid: str, language: str = 'en_US') -> Product:
        version, id = itemgetter('version', 'id')(p.attrib)
        name = p.find('displayName').text
        pf = p.find('platforms/platform').get('id')
        buildGuid = p.find(
            'platforms/platform/languageSet').get('buildGuid')

        deps = list(p.find('platforms/platform/languageSet/dependencies'))
        dependencies = [Dependency(d.find('sapCode').text, d.find(
            'baseVersion').text, productGuid) for d in deps if deps]

        return Product(id, name, version, pf, dependencies, buildGuid, language, {})

    def _process_xml(self, xml: ET.Element) -> dict:
        products = {}
        p_map = {c: p for p in xml.iter() for c in p}

        for p in xml.findall('channel/products/product'):
            if p_map[p_map[p]].get('name') != 'ccm':
                continue

            id = p.get('id')
            buildGuid = p.find(
                'platforms/platform/languageSet').get('buildGuid', '')

            if not products.get(id):
                products[id] = {'versions': OrderedDict()}

            products[id]['versions'][p.get(
                'version')] = self._xml_to_product(p, buildGuid)

        return products

    def _create_driver_xml(self, product: Product, language: str, directory: str):
        driver = DRIVER_XML.format(
            name=product.name,
            sapCode=product.id,
            version=product.version,
            installPlatform=product.platform,
            dependencies='\n'.join(
                DRIVER_XML_DEPENDENCY.format(sapCode=d.id, version=d.version)
                for d in product.dependencies
            ),
            language=language
        )

        with open(os.path.join(directory, 'driver.xml'), 'w') as f:
            f.write(driver)

    def _create_icon_path(self, dest: str):
        path = '/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Install.app/Contents/Resources/CreativeCloudInstaller.icns'
        shutil.copyfile(path, os.path.join(dest,
                                           'Contents', 'Resources', 'applet.icns'))

    def _get_product_xml(self):
        return self._r(self.url_templates['xml'], self.ADOBE_REQ_HEADERS)

    def _get_product_json(self, buildGuid: str) -> dict[Any, Any]:
        return json.loads(self._r(self.url_templates['json'], {**self.ADOBE_REQ_HEADERS, **{'x-adobe-build-guid': buildGuid}}))

    def get_product_listing(self):
        xml_raw = self._get_product_xml()
        xml = self.string_to_xml(xml_raw)
        self.product_listing = self._process_xml(xml)

    def get_product(self, sapCode: str, version: str) -> Union[Product, None]:
        if self.product_listing:
            return self.product_listing[sapCode]['versions'][version]

    def _get_download_urls(self, product_json: dict[Any, Any], language: str, cdn: str) -> List[dict[str, str]]:
        return [{'size': p['DownloadSize'], 'path': f'{cdn}{p["Path"]}', 'name': p['fullPackageName']} for p in product_json['Packages']['Package'] if p['Type'] == 'core' or language in p['Condition']]

    def _app_script(self, install_dir: str):
        with subprocess.Popen(['/usr/bin/osacompile', '-l', 'JavaScript', '-o', install_dir], stdin=subprocess.PIPE) as p:
            p.communicate(INSTALL_APP_APPLE_SCRIPT.encode('utf-8'))

    def _create_app_json(self, json_path: str, app_json: Any):
        with open(json_path, 'w') as f:
            json.dump(app_json, f, separators=(',', ':'))

    def _create_directory(self, item: Union[Product, Dependency], install_dir: str):
        products_dir = os.path.join(
            install_dir, 'Contents', 'Resources', 'products')
        product_dir = os.path.join(products_dir, item.id)
        app_json_path = os.path.join(product_dir, 'application.json')
        os.makedirs(product_dir, exist_ok=True)
        self._create_app_json(app_json_path, item.app_json)
