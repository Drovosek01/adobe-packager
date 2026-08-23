#!/usr/bin/env python3

import argparse
import json
import locale
import os
import platform
import random
import shutil
import string
import re
import sys
import subprocess
import importlib
from collections import OrderedDict
from subprocess import PIPE, Popen
from xml.etree import ElementTree as ET

import requests
import signal

def ensure_import(import_name: str, package_name: str = None):
    """
    Checks for the presence of a module. If it is not installed,
    attempts to install it via pip and import it again. 

    :param import_name: The name used for importing (e.g., 'babel' or 'PIL')
    :param package_name: The pip package name, if different from import_name (e.g., 'Pillow')
    :return: The Python module
    """
    if package_name is None:
        package_name = import_name

    try:
        return importlib.import_module(import_name)
    except ImportError:
        print(f"Module '{import_name}' not found. Trying to install: {package_name}...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", package_name], check=True)
        try:
            return importlib.import_module(import_name)
        except ImportError:
            sys.exit(f"""Failed to import '{import_name}' even after installation!
Install it manually:
    pip install {package_name}
Or check project status: https://pypi.org/project/{package_name}/""")

babel = ensure_import("babel")
from babel import Locale
from babel.core import UnknownLocaleError

tqdm = ensure_import("tqdm")


# ===== ===== =====
# START CODE
# ===== ===== =====

def signal_handler(sig, frame):
    print('\n\n[!] Operation cancelled. Exiting...')
    sys.exit(0)

# We register a handler for the SIGINT signal (which sends Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

session = requests.sessions.Session()

VERSION_STR = '0.3.3'

# path to dir where current file
script_dir = os.path.dirname(os.path.realpath(__file__))
macos_version_current = platform.mac_ver()[0]

ADOBE_PRODUCTS_XML_URL = 'https://prod-rel-ffc-ccm.oobesaas.adobe.com/adobe-ffc-external/core/v{urlVersion}/products/all?_type=xml&channel=ccm&channel=sti&platform={installPlatform}&productType=Desktop'
ADOBE_APPLICATION_JSON_URL = 'https://cdn-ffc.oobesaas.adobe.com/core/v3/applications'

DRIVER_XML = '''<DriverInfo>
    <ProductInfo>
        <Name>Adobe {name}</Name>
        <SAPCode>{sapCode}</SAPCode>
        <CodexVersion>{version}</CodexVersion>
        <Platform>{installPlatform}</Platform>
        <EsdDirectory>./{sapCode}</EsdDirectory>
        <Dependencies>
{dependencies}
        </Dependencies>
    </ProductInfo>
    <RequestInfo>
        <InstallDir>/Applications</InstallDir>
        <InstallLanguage>{language}</InstallLanguage>
    </RequestInfo>
</DriverInfo>
'''

DRIVER_XML_DEPENDENCY = '''         <Dependency>
                <SAPCode>{sapCode}</SAPCode>
                <BaseVersion>{version}</BaseVersion>
                <EsdDirectory>./{sapCode}</EsdDirectory>
            </Dependency>'''

ADOBE_REQ_HEADERS = {
    'X-Adobe-App-Id': 'accc-apps-panel-desktop',
    'User-Agent': 'Adobe Application Manager 2.0',
    'X-Api-Key': 'CC_HD_ESD_1_0',
    "Accept-Encoding": "gzip",
    'Cookie': 'fg=' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(26)) + '======'
}

ADOBE_DL_HEADERS = {
    'User-Agent': 'Creative Cloud',
    "Accept-Encoding": "gzip"
}

ADOBE_CC_MAC_ICON_PATH = '/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Install.app/Contents/Resources/CreativeCloudInstaller.icns'
MAC_VOLUME_ICON_PATH = '/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/CDAudioVolumeIcon.icns'


def compare_versions(v1, v2):
    """
    Compares two version strings.
    Returns:
     1, if v1 > v2
    -1, if v1 < v2
     0, if v1 == v2
    """
    # Split the strings at the dot and convert each part to an int
    parts1 = [int(x) for x in str(v1).split('.')]
    parts2 = [int(x) for x in str(v2).split('.')]
    
    # We equalize the length of the lists by adding zeros (for example, 13 becomes 13.0.0)
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))
    
    if parts1 > parts2:
        return 1
    elif parts1 < parts2:
        return -1
    else:
        return 0


def r(url, headers=ADOBE_REQ_HEADERS):
    """Retrieve a from a url as a string."""
    req = session.get(url, headers=headers, stream=True)
    req.encoding = 'utf-8'
    return req.text


def get_products_xml(url):
    """
    First stage of parsing the XML.
    Downloads XML and optionally saves it as plain text
    """
    if args.useSavedXML:
        given_path = f"products.xml" if args.useSavedXML == True else args.useSavedXML
        file_path = os.path.abspath(given_path)

        if not os.path.exists(file_path):
            print(f"ERROR: Not found XML-file for parse: {file_path}")
            exit(1)
        else:
            print(f"\nSource XML-file for parse is: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            xml_text= f.read()
    else:
        print('\nDownloading products.xml\n')
        print(f"Source URL is: {url}")

        # wrap the request in the try-except block to protect against network failures.
        try:
            # timeout=(15, 100) means: 15 seconds to connect to the server, 100 seconds to wait for data
            response = session.get(url, headers=ADOBE_REQ_HEADERS, stream=True, timeout=(15, 100))
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"\n[!] NETWORK ERROR: Failed to download products.xml")
            print(f"Details: {e}")
            print("Check your internet connection, VPN, or try running the script again later.")
            exit(1)
        
        # Checking the file size from the server
        total_size = int(response.headers.get('content-length', 0))
        
        # HACK: If the server has hidden the size, we set an approximate guideline (35 MB),
        # to force tqdm to turn on the visual progress bar mode
        if total_size == 0:
            print('\nThe server did not return the file size, so we set the potential size to 35 MB.')
            total_size = 35 * 1024 * 1024  # 35 MB in bytes
            
        chunks = []
        from tqdm import tqdm
        
        # Adding bar_format for beautiful and clean output
        try:
            with tqdm(total=total_size, 
                      unit='B', 
                      unit_scale=True, 
                      desc="Downloading",
                      bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                      
                for chunk in response.iter_content(chunk_size=16384):
                    if chunk:
                        chunks.append(chunk)
                        pbar.update(len(chunk))
        except (requests.exceptions.RequestException, ConnectionResetError) as e:
            print(f"\n[!] NETWORK ERROR: Connection broke during download.")
            print(f"Details: {e}")
            exit(1)
                    
        xml_bytes = b"".join(chunks)
        xml_text = xml_bytes.decode('utf-8')

    if args.saveXML and not args.useSavedXML:
        save_path = f"products.xml" if args.saveXML == True else args.saveXML

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(xml_text)
        print(f"Saved source XML to {save_path}")

        root, ext = os.path.splitext(save_path)
        save_path_beautified = root + ".beautified.xml"
        tree = ET.parse(save_path)
        ET.indent(tree, space="  ", level=0)
        tree.write(save_path_beautified, encoding="utf-8", xml_declaration=True)
        print(f"Saved beautified XML to {save_path_beautified}")

    return ET.fromstring(xml_text)


def skip_product(product) -> bool:
    """
    Based on various parameters, we determine whether the submitted product should be
    included in the final sample or whether it should be skipped and not shown in the future.
    """

    min_supported_os = product.find('platforms/platform/systemCompatibility/operatingSystem/range')
    if min_supported_os == None:
        return False
    
    min_supported_os_text = min_supported_os.text
    if len(min_supported_os_text) == 0:
        return False
    
    if args.onlyWithSupportOS:
        # leave only digits and dots in the string
        min_supported_os_ver = re.sub(r"[^\d.]", "", min_supported_os_text)
        result_comparing = compare_versions(min_supported_os_ver, args.onlyWithSupportOS)

        # if the system requirements of the product require an OS
        # newer than the one specified in the argument, then skip this product
        if result_comparing > 0:
            return True
        else:
            return False
    else:
        return False


def parse_products_xml(products_xml, urlVersion, allowedPlatforms):
    """2nd stage of parsing the XML."""
    if int(urlVersion) == 6:
        prefix = 'channels/'
    else:
        prefix = ''
    
    cdn = products_xml.find(prefix + 'channel/cdn/secure').text
    products = {}
    parent_map = {c: p for p in products_xml.iter() for c in p}

    for p in products_xml.findall(prefix + 'channel/products/product'):
        if skip_product(p):
            continue

        sap = p.get('id')
        # TODO: add function download products not only from 'ccm' channel
        hidden = parent_map[parent_map[p]].get('name') != 'ccm'
        displayName = p.find('displayName').text
        productVersion = p.get('version')

        if not products.get(sap):
            products[sap] = {
                'hidden': hidden,
                'displayName': displayName,
                'sapCode': sap,
                'versions': OrderedDict()
            }

        for pf in p.findall('platforms/platform'):
            baseVersion = pf.find('languageSet').get('baseVersion')
            buildGuid = pf.find('languageSet').get('buildGuid')
            appplatform = pf.get('id')
            dependencies = list(pf.findall('languageSet/dependencies/dependency'))
            applanguages = [
                    loc.get('name') 
                    for loc in pf.findall('languageSet/locales/locale') 
                    if loc.get('name')
                ]
            if productVersion in products[sap]['versions']:
                if products[sap]['versions'][productVersion]['apPlatform'] in allowedPlatforms:
                    break # There's no single-arch binary if macuniversal is available

            if sap == 'APRO':
                baseVersion = productVersion
                if urlVersion == 4 or urlVersion == 5:
                    productVersion = pf.find('languageSet/nglLicensingInfo/appVersion').text
                if urlVersion == 6:
                    for b in products_xml.findall('builds/build'):
                        if b.get("id") == sap and b.get("version") == baseVersion:
                            productVersion = b.find('nglLicensingInfo/appVersion').text
                            break
                buildGuid = pf.find('languageSet/urls/manifestURL').text
                # This is actually manifest URL

            products[sap]['versions'][productVersion] = {
                'sapCode': sap,
                'baseVersion': baseVersion,
                'productVersion': productVersion,
                'apPlatform': appplatform,
                'languages': applanguages,
                'dependencies': [{
                    'sapCode': d.find('sapCode').text, 'version': d.find('baseVersion').text
                } for d in dependencies],
                'buildGuid': buildGuid
            }
    return products, cdn


def questiony(question: str) -> bool:
    """Question prompt default Y."""
    reply = None
    while reply not in ("", "y", "n"):
        reply = input(f"{question} (Y/n): ").lower()
    return (reply in ("", "y", "yes"))


def questionn(question: str) -> bool:
    """Question prompt default N."""
    reply = None
    while reply not in ("", "y", "n"):
        reply = input(f"{question} (y/N): ").lower()
    return (reply in ("", "n", "no"))


def get_application_json(buildGuid):
    """Retrieve JSON."""
    headers = ADOBE_REQ_HEADERS.copy()
    headers['x-adobe-build-guid'] = buildGuid
    return json.loads(r(ADOBE_APPLICATION_JSON_URL, headers))


def get_download_path():
    """Ask for desired download folder"""
    if (args.destination):
        # Expand the '~' symbol into the full path to the home folder
        expanded_path = os.path.expanduser(args.destination)
        # Convert it to an absolute path (in case a relative path was provided, e.g., './downloads')
        dest = os.path.abspath(expanded_path)
        print('\nUsing provided destination: ' + dest)
    else:
        print('\nPlease navigate to the desired downloads folder, or cancel to abort.')
        p = Popen(['/usr/bin/osascript', '-e',
                  'tell application (path to frontmost application as text)\nset _path to choose folder\nPOSIX path of _path\nend'], stdout=PIPE)
        dest = p.communicate()[0].decode('utf-8').strip()
        if (p.returncode != 0):
            print('Exiting...')
            exit()
    return dest

def download_file(url, product_dir, sapCode, version, name=None):
    """Download a file"""
    if not name:
        name = url.split('/')[-1].split('?')[0]
    print('Url is: ' + url)
    print('[{}_{}] Downloading {}'.format(sapCode, version, name))
    file_path = os.path.join(product_dir, name)
    response = session.head(url, stream=True, headers=ADOBE_DL_HEADERS)
    total_size_in_bytes = int(
        response.headers.get('content-length', 0))
    if (args.skipExisting and os.path.isfile(file_path) and os.path.getsize(file_path) == total_size_in_bytes):
        print('[{}_{}] {} already exists, skipping'.format(sapCode, version, name))
    else:
        response = session.get(
            url, stream=True, headers=ADOBE_REQ_HEADERS)
        total_size_in_bytes = int(
            response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kibibyte
        progress_bar = tqdm(total=total_size_in_bytes,
                            unit='iB', unit_scale=True)
        with open(file_path, 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)
        progress_bar.close()
        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            print("ERROR, something went wrong")


def download_APRO(appInfo, cdn):
    """Download APRO"""
    manifest = get_products_xml(cdn + appInfo['buildGuid'])
    downloadURL = manifest.find('asset_list/asset/asset_path').text
    dest = get_download_path()
    sapCode = appInfo['sapCode']
    version = appInfo['productVersion']
    name = 'Intall {}_{}_{}.dmg'.format(sapCode, version, appInfo['apPlatform'])
    print('')
    print('sapCode: ' + sapCode)
    print('version: ' + version)
    print('installLanguage: ' + 'ALL')
    print('dest: ' + os.path.join(dest, name))

    print('\nDownloading...\n')

    print('[{}_{}] Selected 1 package'.format(sapCode, version))
    download_file(downloadURL, dest, sapCode, version, name)

    print('\nInstaller successfully downloaded. Open ' + os.path.join(dest, name) + ' and run Acrobat/Acrobat DC Installer.pkg to install.')
    return


def show_version():
    ye = int((32 - len(VERSION_STR)) / 2)
    print('=================================')
    print('= Adobe macOS Package Generator =')
    print('{} {} {}\n'.format('=' * ye, VERSION_STR,
          '=' * (31 - len(VERSION_STR) - ye)))


def get_products():
    if (args.ignoreNoCreativeCloud):
        print('Not checking Creative Cloud installation, created installer may use a fallback icon if CC is not installed.')
    elif (not os.path.isfile('/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Setup')):
        print('Adobe HyperDrive installer not found.\nPlease make sure the Creative Cloud app is installed.')
        exit(1)

    selectedVersion = None
    if args.urlVersion:
        cleaned_val = re.sub(r"[^\d]", "", args.urlVersion)
        if len(cleaned_val) == 0:
            print('Invalid argument "{}" for {}'.format(args.urlVersion, 'URL version'))
            exit(1)
        else:
            selectedVersion = cleaned_val

    while not selectedVersion:
        val = input('\nEnter the URL version (usually v4/v5/v6) for downloading products.xml, or nothing for v6: ') or '6'
        cleaned_val = re.sub(r"[^\d]", "", val)
        if len(cleaned_val) == 0:
            print('Invalid URL version: {}'.format(val))
        else:
            selectedVersion = cleaned_val
    print('Selected version: v' + str(selectedVersion))

    if args.Auth:
        ADOBE_REQ_HEADERS['Authorization'] = args.Auth

    isAppleSiliconOnly = -1
    allowedPlatforms = ['macuniversal']

    if args.arch:
        archArgLower = args.arch.lower()
        if archArgLower == 'native' or archArgLower == 'nativeonly':
            if platform.machine() == 'arm64':
                isAppleSiliconOnly = True
                allowedPlatforms.append('macarm64')
            else:
                isAppleSiliconOnly = False
                allowedPlatforms.append('osx10-64')
                allowedPlatforms.append('osx10')
        elif archArgLower == 'x86_64' or archArgLower == 'x64' or archArgLower == 'intel':
            isAppleSiliconOnly = False
        elif archArgLower == 'arm64' or archArgLower == 'arm' or archArgLower == 'm1':
            isAppleSiliconOnly = True
        else:
            print('Invalid argument "{}" for {}'.format(args.arch, 'architecture'))
    
    if isAppleSiliconOnly == -1:
        if platform.machine() == 'arm64':
            isAppleSiliconOnly = questiony('Do you want to make Apple Silicon native packages')
        else:
            isAppleSiliconOnly = False
    
    if isAppleSiliconOnly:
        allowedPlatforms.append('macarm64')
        print('Note: If the Adobe program is NOT listed here, there is no native Apple Silicon version.')
        print('      Use the non native version with Rosetta 2 until an Apple Silicon version is available.')
    else:
        allowedPlatforms.append('osx10-64')
        allowedPlatforms.append('osx10')

    productsPlatform = 'osx10-64,osx10,macarm64,macuniversal'
    adobeurl = ADOBE_PRODUCTS_XML_URL.format(urlVersion=selectedVersion, installPlatform=productsPlatform)

    products_xml = get_products_xml(adobeurl)

    print('\nParsing products.xml\n')
    products, cdn = parse_products_xml(products_xml, selectedVersion, allowedPlatforms)

    print('CDN: ' + cdn)
    sapCodes = {}
    for p in products.values():
        if not p['hidden']:
            versions = p['versions']
            version = None
            lastv = None
            for v in reversed(versions.values()):
                if v['buildGuid'] and v['apPlatform'] in allowedPlatforms:
                    lastv = v['productVersion']
            if lastv:
                sapCodes[p['sapCode']] = p['displayName']
    
    products_amount = len(sapCodes)
    print(str(products_amount) + ' products found:')

    if products_amount == 0:
        exit(0)

    if args.sapCode and products.get(args.sapCode.upper()) is None:
        print('\nProvided SAP Code not found in products: ' + args.sapCode)
        exit(1)

    return products, cdn, sapCodes, allowedPlatforms


def remove_dependency_app_json(data: dict, sap_code: str) -> bool:
    """
    Deletes the dependency with the specified SAPCode.
    Returns True if the dependency was found and deleted.
    """

    deps_container = data.get("Dependencies")
    if not deps_container:
        return False

    deps = deps_container.get("Dependency")
    if not deps:
        return False

    isACRRemoved = False

    # If the list of dependencies is
    if isinstance(deps, list):
        original_len = len(deps)
        deps_container["Dependency"] = [
            d for d in deps if d.get("SAPCode") != sap_code
        ]
        isACRRemoved = len(deps_container["Dependency"]) != original_len

    # If there is only one dependency (dict instead of list)
    elif isinstance(deps, dict):
        if deps.get("SAPCode") == sap_code:
            deps_container["Dependency"] = []
            isACRRemoved = True

    return isACRRemoved


def remove_non_core_packages(data: dict) -> bool:
    """
    Deletes all packages with Type == 'non-core' from application.json.
    Returns True if the 1 or more 'non-core' package was found and deleted.
    """

    packages_container = data.get("Packages")
    if not packages_container:
        return False
    
    packages = packages_container.get("Package")
    if not packages:
        return False

    isNonCoresRemoved = False

    # If the list of packages is
    if isinstance(packages, list):
        original_len = len(packages)
        # leave only those packages where Type is present (not None) and it is not equal to "non-core"
        packages_container["Package"] = [
            p for p in packages 
               if p.get("Type") is not None and p.get("Type") != "non-core"
        ]
        isNonCoresRemoved = len(packages_container["Package"]) != original_len

    # If there is only one package (dict instead of list)
    elif isinstance(packages, dict):
        if packages.get("Type") == "non-core":
            packages_container["Package"] = []
            isNonCoresRemoved = True

    # TODO: be better not just truncate Modules array but
    # check ReferencePackages for all items and remove it and modules
    # if it same with removed Package name
    if "Modules" in data and "Module" in data.get("Modules", {}):
        data["Modules"]["Module"] = []

    return isNonCoresRemoved


def remove_packages_by_arch(data: dict, skipPlatformStr: str) -> bool:
    """
    Deletes all packages for platform/arch what need skip from application.json.
    Returns True if the 1 or more package was found and deleted.
    """

    packages_container = data.get("Packages")
    if not packages_container:
        return False
    
    packages = packages_container.get("Package")
    if not packages:
        return False

    isPackagesRemoved = False

    # If the list of packages is
    if isinstance(packages, list):
        original_len = len(packages)
        # leave only those packages where value Condition is present (not None) and it is not equal to "[OSArchitecture]==skipPlatformStr"
        packages_container["Package"] = [
            p for p in packages 
               if p.get("Condition") is None or p.get("Condition") != "[OSArchitecture]=={}".format(skipPlatformStr)
        ]
        isPackagesRemoved = len(packages_container["Package"]) != original_len

    return isPackagesRemoved


def remove_check_compatibility(data: dict) -> bool:
    """
    Delete point CheckCompatibility from SystemRequirement from application.json file
    Returns True if the 1 or more points was found and deleted.
    """
    # maybe MinimumSupportedClientVersion need remove too?

    systemreq_container = data.get("SystemRequirement")
    if not systemreq_container:
        return False
    
    compatibility = systemreq_container.get("CheckCompatibility")
    if not compatibility:
        return False
    
    data["SystemRequirement"].pop("CheckCompatibility", None)
    
    return True


def remove_packages_by_modules_refs(
    data: dict,
    substr: str,
    fieldName: str = "DisplayName"
) -> bool:
    """
    Removes modules with substring in the specified field (default: DisplayName),
    as well as their associated packages.
    Returns True if 1 or more module found.
    """

    removed_packages = []
    removed_modules = []
    isModuleRemoved = False

    modules_container = data.get("Modules")
    if not modules_container:
        return False
    modules = modules_container.get("Module")
    if not modules:
        return False

    packages_container = data.get("Packages")
    if not packages_container:
        return False
    packages = packages_container.get("Package")
    if not packages:
        return False

    # collecting package names for removal
    package_names_to_remove = set()

    for module in modules:
        field_value = module.get(fieldName, "")
        if substr.lower() in field_value.lower():
            isModuleRemoved = True
            removed_modules.append(module.get("Id"))

            ref = module.get("ReferencePackages", {}).get("ReferencePackage", [])
            if isinstance(ref, list):
                package_names_to_remove.update(ref)
            elif isinstance(ref, str):
                package_names_to_remove.add(ref)

    # removing packages
    new_packages = []
    for pkg in packages:
        name = pkg.get("PackageName")
        if name in package_names_to_remove:
            removed_packages.append(name)
        else:
            new_packages.append(pkg)

    packages_container["Package"] = new_packages

    # removing modules
    new_modules = [
        m for m in modules
        if substr.lower() not in m.get(fieldName, "").lower()
    ]

    modules_container["Module"] = new_modules
    packages_container["Package"] = new_packages

    return isModuleRemoved


def get_cleaned_os_locale():
    # Default region mapping for languages when the user's region differs
    DEFAULT_REGION_MAP = {
        'en': 'US',
        'es': 'ES',
        'pt': 'BR',
        'fr': 'FR',
        'it': 'IT',
        'de': 'DE',
        'nl': 'NL',
        'ru': 'RU',
        'uk': 'UA',
        'zh': 'CN',
        'ja': 'JP',
        'ko': 'KR',
        'pl': 'PL',
        'hu': 'HU',
        'cs': 'CZ',
        'tr': 'TR',
        'sv': 'SE',
        'nb': 'NO',
        'fi': 'FI',
        'da': 'DK',
    }
    try:
        # 1. Get the primary interface language (e.g., "en-US", "ru-RU", or just "en")
        lang_out = subprocess.check_output(
            ["defaults", "read", "-g", "AppleLanguages"], text=True
        )
        # Parse output in format '(\n    "en-RU",\n    "ru-RU"\n)'
        first_lang = lang_out.split('"')[1]  # E.g., got "en-RU" or "zh-Hans-CN"
        
        # Extract the base language code (first 2 letters)
        main_lang = first_lang.split('-')[0].lower()

        # 2. Get the system region
        locale_out = subprocess.check_output(
            ["defaults", "read", "-g", "AppleLocale"], text=True
        ).strip()
        
        region = locale_out.split('_')[-1] if '_' in locale_out else 'US'

        # 3. Construct the matching locale
        # If the combination is known (e.g., en_US, en_GB, es_MX), keep it
        # Otherwise fall back to the primary region for that language (en -> en_US instead of en_RU)
        if main_lang == 'en' and region not in ['US', 'GB', 'IL', 'AE', 'CA', 'AU']:
            return f"en_{DEFAULT_REGION_MAP.get(main_lang, 'US')}"
        elif main_lang == 'fr' and region not in ['FR', 'CA', 'MA']:
            return f"fr_{DEFAULT_REGION_MAP.get(main_lang, 'FR')}"
        elif main_lang == 'es' and region not in ['ES', 'MX']:
            return f"es_{DEFAULT_REGION_MAP.get(main_lang, 'ES')}"
        
        return f"{main_lang}_{DEFAULT_REGION_MAP.get(main_lang, region.upper())}"

    except Exception:
        return "en_US"


def select_language(available_langs: list) -> str:
    # Clearing the list from 'ALL'
    base_langs = [code for code in available_langs if code != 'ALL']

    os_locale = get_cleaned_os_locale()

    if os_locale in base_langs:
        # remove system code from the general list and put it first among ordinary languages
        other_langs = [code for code in base_langs if code != os_locale]
        ordered_langs = [os_locale] + other_langs
    else:
        ordered_langs = base_langs

    # form the final list: 'ALL' is always in the 1st position
    clean_langs = ['ALL'] + ordered_langs

    lang_objects = []

    for code in clean_langs:
        if code == 'ALL':
            lang_objects.append({
                'code': 'ALL',
                'name_en': 'All Languages',
                'name_native': 'All Languages'
            })
            continue
        if code == 'mul':
            lang_objects.append({
                'code': 'mul',
                'name_en': 'Multilingual',
                'name_native': 'Multiple Languages'
            })
            continue

        try:
            loc = Locale.parse(code)
            name_en = loc.get_display_name('en').title()
            name_native = loc.get_display_name(code).title()

            lang_objects.append({
                'code': code,
                'name_en': name_en,
                'name_native': name_native
            })
        except (UnknownLocaleError, ValueError):
            if code == 'no_NO':
                lang_objects.append({
                    'code': 'no_NO',
                    'name_en': 'Norwegian (Norway)',
                    'name_native': 'Norsk (Norge)'
                })
            elif code == 'fr_XM':
                lang_objects.append({
                    'code': 'fr_XM',
                    'name_en': 'French (Saint Martin)',
                    'name_native': 'Français (Saint-Martin)'
                })
            elif code == 'en_XM':
                lang_objects.append({
                    'code': 'en_XM',
                    'name_en': 'English (Saint Martin)',
                    'name_native': 'English (Saint Martin)'
                })
            else:
                lang_objects.append({
                    'code': code,
                    'name_en': 'Unknown lang name',
                    'name_native': 'Unknown lang name'
                })

    # Print the table to the terminal
    # Set the width of the columns
    w_num, w_code, w_en, w_native = 4, 10, 30, 30

    header = f"{'N':<{w_num}} | {'Lang code':<{w_code}} | {'Name on English':<{w_en}} | {'Name on native':<{w_native}}"
    divider = f"{'-'*w_num}-+-{'-'*w_code}-+-{'-'*w_en}-+-{'-'*w_native}"

    print(header)
    print(divider)

    valid_inputs = {}
    actual_lang_codes = [code for code in clean_langs if code != 'ALL']

    for idx, lang in enumerate(lang_objects, 1):
        num_str = str(idx)
        code = lang['code']
        
        valid_inputs[num_str] = code
        valid_inputs[code.upper()] = code

        row = f"{num_str:<{w_num}} | {code:<{w_code}} | {lang['name_en']:<{w_en}} | {lang['name_native']:<{w_native}}"
        print(row)

    print(divider)

    # Validation and processing of multiple inputs
    while True:
        raw_input = input("\nEnter numbers (N) or Lang codes (separated by comma) or press Enter for 'ALL': ").strip()

        # If the user has not entered anything, select 'ALL'
        if not raw_input:
            print("Nothing is selected; choosing the option 'ALL'.")
            return ",".join(actual_lang_codes)

        # Split by commas, remove spaces and convert to uppercase
        tokens = [token.strip().upper() for token in raw_input.split(',') if token.strip()]

        # We verify that all entered elements are valid.
        if not all(token in valid_inputs for token in tokens):
            print("Invalid input! Make sure all items are valid row numbers or language codes from the table.")
            continue

        # Collecting the selected codes (while maintaining order and without duplicates)
        selected_codes = []
        for token in tokens:
            code = valid_inputs[token]
            if code not in selected_codes:
                selected_codes.append(code)

        # If there is 'ALL' among the selected ones, we return ALL language codes separated by commas
        if 'ALL' in selected_codes:
            return ",".join(actual_lang_codes)

        # Otherwise, we return the selected codes separated by commas
        return ",".join(selected_codes)


def get_install_language(product):
    # Parsed languages in the xml
    all_langs = ['en_US', 'en_GB', 'en_IL', 'en_AE', 'es_ES', 'es_MX', 'pt_BR', 'fr_FR', 'fr_CA', 'fr_MA', 'it_IT', 'de_DE', 'nl_NL', 'ru_RU', 'uk_UA', 'zh_TW', 'zh_CN', 'ja_JP', 'ko_KR', 'pl_PL', 'hu_HU', 'cs_CZ', 'tr_TR', 'sv_SE', 'nb_NO', 'fi_FI', 'da_DK', 'no_NO', 'fr_XM', 'en_XM', 'ALL']

    # Detecting Current set default Os language
    deflocal = locale.getlocale()[0]

    if not deflocal:
        deflocal = 'en_US'

    oslang = get_cleaned_os_locale()
    if args.osLanguage:
        oslang = args.osLanguage
    elif deflocal:
        oslang = deflocal

    if oslang in all_langs:
        deflang = oslang
    else:
        deflang = 'en_US'

    installLanguage = None
    if args.installLanguage:
        if args.installLanguage in all_langs:
            print('\nUsing provided language code: ' + args.installLanguage)
            installLanguage = args.installLanguage
        else:
            print('\nProvided language code not available: ' + args.installLanguage)

    if not installLanguage:
        if len(product['languages']) > 0:
            print('Available languages for selected product: {}'.format(', '.join(product['languages'])))
            print('Formatted output and selection of supported languages:')
            installLanguage = select_language(product['languages'])
        else:
            print('No list of supported languages ​​was found for the selected product.')
            print('Select language from all possible from Adobe: {}'.format(', '.join(product['languages'])))
            while installLanguage is None:
                val = input(
                    f'\nEnter the desired install language, or nothing for [{deflang}]: ') or deflang
                if val.upper() == 'ALL':
                    installLanguage = ','.join([lang for lang in all_langs if lang != 'ALL'])
                else:
                    if len(val) == 5:
                        val = val[0:2].lower() + val[2] + val[3:5].upper()
                    elif len(val) == 3:
                        val = val.lower()
                    if val in all_langs:
                        installLanguage = val
                    else:
                        print('{} is not available. Please use a value from the list above.'.format(val))
            
    if oslang != installLanguage:
        if installLanguage != 'ALL':
            while oslang not in all_langs:
                print('Could not detect your default Language for MacOS.')
                oslang = input(
                    f'\nEnter the your OS Language, or nothing for [{installLanguage}]: ') or installLanguage
                if oslang not in all_langs:
                    print(
                        '{} is not available. Please use a value from the list above.'.format(oslang))


def run_ccdl(products, cdn, sapCodes, allowedPlatforms):
    """Run Main execution."""
    sapCode = args.sapCode.upper() if args.sapCode else None
    skipPlatform = ''

    if ('macarm64' in allowedPlatforms) and ('osx10-64' not in allowedPlatforms):
        skipPlatform = 'x64'
    elif ('osx10-64' in allowedPlatforms) and ('macarm64' not in allowedPlatforms):
        skipPlatform = 'arm64'
    
    if not sapCode:
        for s, d in sapCodes.items():
            print('[{}]{}{}'.format(s, (10 - len(s)) * ' ', d))

        while sapCode is None:
            val = input(
                '\nEnter the SAP Code of the desired product (eg. PHSP for Photoshop): ').upper() or 'PHSP'
            if products.get(val):
                sapCode = val
            else:
                print(
                    '{} is not a valid SAP Code. Please use a value from the list above.'.format(val))

    product = products.get(sapCode)
    versions = product['versions']
    version = None

    # Check if the version argument is provided
    if (args.version):
        # Use regex to match patterns like last25, last_25, latest25, latest_25, newest25, newest_25
        # Group 1: Matches 'last', 'latest', or 'newest' (case-insensitive)
        # Group 2: Matches one or more digits following an optional underscore
        version_match = re.fullmatch(r'(last|latest|newest)_?(\d+)', args.version, re.IGNORECASE)
        if version_match:
            # Extract the major version number from the matched pattern (e.g., '25' from 'last25')
            requested_major_version = version_match.group(1)
            print('\nRequested latest version from {}.x.x'.format(requested_major_version))
            for candidate_version in versions:
                # Extract the major version from the candidate version (e.g., '25' from '25.1.0')
                candidate_major_version = str(candidate_version).split('.', 1)[0]
                if candidate_major_version == requested_major_version:
                    version = candidate_version
                    print('Found version: {}'.format(version))
                    break
            if not version:
                print('Not found requested version\n')

        # Handle explicit requests for the latest version
        elif (args.version) == 'latest' or (args.version) == 'newest' or (args.version) == 'last':
            # Use the first version in the list (assumed to be the latest)
            version = list(versions.keys())[0]
            print('\nUsing provided version latest: ' + version)

        # Handle explicit version requests (e.g., '1.2.3')
        elif versions.get(args.version):
            print('\nUsing provided version: ' + args.version)
            version = args.version
            
        # Handle cases where the version is not found
        else:
            print('\nProvided version not found: ' + args.version)

    if not version:
        lastv = None
        for v in reversed(versions.values()):

            if v['buildGuid'] and v['apPlatform'] in allowedPlatforms:
                print('{} Platform: {} - {}'.format(product['displayName'], v['apPlatform'], v['productVersion']))
                lastv = v['productVersion']

        while version is None:
            val = input('\nEnter the desired version. Nothing for ' + lastv + ': ') or lastv
            if versions.get(val):
                version = val
            else:
                print('{} is not a valid version. Please use a value from the list above.'.format(val))

    if sapCode == 'APRO':
        download_APRO(versions[version], cdn)
        return

    installLanguage = get_install_language(product['versions'][version])
    dest = get_download_path()

    print('')

    prodInfo = versions[version]
    prods_to_download = []
    dependencies = prodInfo['dependencies']
    for d in dependencies:
        firstArch = firstGuid = buildGuid = None

        if str(d['sapCode']) == 'ACR':
            if args.skipDependencyACR:
                continue
            else:
                needDownloadACR = questiony('Do you want include CameraRaw in this package')
                if not needDownloadACR:
                    continue

        for p in products[d['sapCode']]['versions']:
            if products[d['sapCode']]['versions'][p]['baseVersion'] == d['version']:
                if not firstGuid:
                    firstGuid = products[d['sapCode']]['versions'][p]['buildGuid']
                    firstArch = products[d['sapCode']]['versions'][p]['apPlatform']
                if products[d['sapCode']]['versions'][p]['apPlatform'] in allowedPlatforms:
                    buildGuid = products[d['sapCode']]['versions'][p]['buildGuid']
                    break
        if not buildGuid:
            buildGuid = firstGuid
        prods_to_download.append({'sapCode': d['sapCode'], 'version': d['version'],
                                  'buildGuid': buildGuid, "isDependency": True})

    prods_to_download.insert(
        0, {'sapCode': prodInfo['sapCode'], 'version': prodInfo['productVersion'], 'buildGuid': prodInfo['buildGuid'], "isDependency": False})
    apPlatform = prodInfo['apPlatform']

    if args.notWrapInApp:
        dest_folder_name = 'Adobe {}_{}-{}-{}'.format(sapCode, version, installLanguage, apPlatform)
        result_path = os.path.join(dest, dest_folder_name)
        os.makedirs(result_path, exist_ok=True)
        products_dir = os.path.join(result_path, 'products')
    else:
        install_app_name = 'Install {}_{}-{}-{}.app'.format(sapCode, version, installLanguage, apPlatform)
        result_path = os.path.join(dest, install_app_name)
        applescript_path = os.path.join(script_dir, "install_script.applescript")

        try:
            with open(applescript_path, "r", encoding="utf-8") as f:
                INSTALL_APP_APPLE_SCRIPT = f.read()
        except FileNotFoundError:
            print(f"ERROR: File not found - {applescript_path}")
            exit(1)

        print('\nCreating {}'.format(install_app_name))

        with Popen(['/usr/bin/osacompile', '-l', 'JavaScript', '-o', os.path.join(dest, result_path)], stdin=PIPE) as p:
            p.communicate(INSTALL_APP_APPLE_SCRIPT.encode('utf-8'))

        if os.path.isfile(ADOBE_CC_MAC_ICON_PATH):
            icon_path = ADOBE_CC_MAC_ICON_PATH
        else:
            icon_path = MAC_VOLUME_ICON_PATH
        shutil.copyfile(icon_path, os.path.join(result_path,
                        'Contents', 'Resources', 'applet.icns'))

        products_dir = os.path.join(
            result_path, 'Contents', 'Resources', 'products')
    
    print('sapCode: ' + sapCode)
    print('version: ' + version)
    print('installLanguage: ' + installLanguage)
    print('dest: ' + result_path)

    print('\nPreparing...\n')

    for p in prods_to_download:
        s, v = p['sapCode'], p['version']
        product_dir = os.path.join(products_dir, s)
        app_json_path = os.path.join(product_dir, 'application.json')
        backup_path = app_json_path + ".original"

        if p['isDependency']:
            print('package-component is target dependency')
        else:
            print('package-component is target product')

        print('[{}_{}] Downloading application.json'.format(s, v))
        app_json = get_application_json(p['buildGuid'])

        print('[{}_{}] Creating folder for product'.format(s, v))
        os.makedirs(product_dir, exist_ok=True)

        print('[{}_{}] Saving application.json'.format(s, v))
        with open(app_json_path, 'w') as file:
            json.dump(app_json, file, separators=(',', ':'))

        if args.skipDependencyACR:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_dependency_app_json(data, 'ACR'):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] ACR dependency removed'.format(s, v))

        if (args.skipNonCorePackages and not p['isDependency']) or args.skipNonCorePackagesAll:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_non_core_packages(data):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] Non-Core packages removed'.format(s, v))

        if args.skipModuleC4D:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_packages_by_modules_refs(data, 'Cinema 4D'):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] Maxon Cinema 4D packages removed'.format(s, v))

        if args.skipModulesSpeechToText:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_packages_by_modules_refs(data, 'Speech to Text'):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] Speech to Text packages removed'.format(s, v))

        if args.skipModulesSuperCaf:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_packages_by_modules_refs(data, 'SuperCaf', 'Id'):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] SuperCaf packages removed'.format(s, v))

        if args.skipModulesUltraCaf:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_packages_by_modules_refs(data, 'UltraCaf', 'Id'):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] UltraCaf packages removed'.format(s, v))        

        if args.removeCheckCompatibility:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_check_compatibility(data):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data
                        print('[{}_{}] CheckCompatibility removed'.format(s, v))

        if len(skipPlatform) > 0:
            with open(app_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if remove_packages_by_arch(data, skipPlatform):
                    if not os.path.exists(backup_path):
                        shutil.copy2(app_json_path, backup_path)

                    with open(app_json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                        app_json = data

        p['application_json'] = app_json
        print('')

    print('Downloading...\n')

    for p in prods_to_download:
        s, v = p['sapCode'], p['version']
        app_json = p['application_json']
        product_dir = os.path.join(products_dir, s)

        if p['isDependency']:
            print('package-component is target dependency')
        else:
            print('package-component is target product')

        print('[{}_{}] Parsing available packages'.format(s, v))
        core_pkg_count = 0
        noncore_pkg_count = 0
        typeless_pkg_count = 0
        
        packages = app_json['Packages']['Package']
        download_urls = []
        for pkg in packages:
            if pkg.get('Type') and pkg['Type'] == 'core':
                core_pkg_count += 1
                download_urls.append(cdn + pkg['Path'])
            else:
                if (args.skipNonCorePackages and not p['isDependency']) or args.skipNonCorePackagesAll:
                    continue
                # TODO: actually parse `Condition` and check it properly (and maybe look for & add support for conditions other than installLanguage)
                language_is_suitable = (
                        installLanguage == "ALL"
                        or 'Condition' not in pkg
                        or '[installLanguage]' not in pkg['Condition']
                        or '[installLanguage]==' + installLanguage in pkg['Condition']
                        or '[installLanguage]==' + oslang in pkg['Condition']
                )

                if pkg.get('Type') and pkg['Type'] == 'non-core':
                    noncore_pkg_count += 1
                    if language_is_suitable:
                        download_urls.append(cdn + pkg['Path'])

                if pkg.get('Type') is None:
                    typeless_pkg_count += 1
                    if language_is_suitable:
                        download_urls.append(cdn + pkg['Path'])


        if (args.skipNonCorePackages and not p['isDependency']) or args.skipNonCorePackagesAll:
            print('[{}_{}] Selected {} core packages'.format(s, v, core_pkg_count))
        else:
            print('[{}_{}] Selected {} core packages and {} non-core packages and {} packages without type'.format(s, v, core_pkg_count, noncore_pkg_count, typeless_pkg_count))

        for url in download_urls:
            download_file(url, product_dir, s, v)
        
        print('')

    print('\nGenerating driver.xml')

    if args.skipDependencyACR:
        dependencies = '\n'.join([
            DRIVER_XML_DEPENDENCY.format(
                sapCode=d['sapCode'],
                version=d['version']
            )
            for d in prodInfo['dependencies']
            if d['sapCode'] != 'ACR'
        ])
    else:
        dependencies='\n'.join([
            DRIVER_XML_DEPENDENCY.format(
                sapCode=d['sapCode'],
                version=d['version']
            )
            for d in prodInfo['dependencies']
        ])

    driver = DRIVER_XML.format(
        name=product['displayName'],
        sapCode=prodInfo['sapCode'],
        version=prodInfo['productVersion'],
        installPlatform=apPlatform,
        dependencies=dependencies,
        language=installLanguage
    )

    with open(os.path.join(products_dir, 'driver.xml'), 'w') as f:
        f.write(driver)
        f.close()

    print('\nPackage successfully created.')

    if args.notWrapInApp:
        print('Use driver.xml to install.')
    else:
        print('Run {} to install.'.format(result_path))

    return


if __name__ == '__main__':
    show_version()

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--installLanguage',
                        help='Language code (eg. en_US)', action='store')
    parser.add_argument('-o', '--osLanguage',
                        help='OS Language code (eg. en_US)', action='store')
    parser.add_argument('-s', '--sapCode',
                        help='SAP code for desired product (eg. PHSP)', action='store')
    parser.add_argument('-v', '--version',
                        help='Version of desired product (eg. 21.0.3) or just write word "last"', action='store')
    parser.add_argument('-d', '--destination',
                        help='Directory to download installation files to', action='store')
    parser.add_argument('-a', '--arch',
                        help='Set the architecture to download (eg. x64 or arm64) or just write word "native"', action='store')
    parser.add_argument('-u', '--urlVersion',
                        help="Get app info from v4/v5/v6 url (eg. v6)", action='store')
    parser.add_argument('-A', '--Auth',
                        help='Add a bearer_token to to authenticate your account, e.g. downloading Xd', action='store')
    parser.add_argument('--ignoreNoCreativeCloud',
                        help='Ignore no creative cloud and just fallback to generic icon', action='store_true')
    parser.add_argument('--noRepeatPrompt',
                        help="Don't prompt for additional downloads", action='store_true')
    parser.add_argument('--skipExisting',
                        help="Skip existing files, e.g. resuming failed downloads", action='store_true')
    parser.add_argument("--saveXML",
                        help="The path to save the uploaded file products.xml following the transmitted path.\
                              If the argument is passed without specifying the path, the xml file will be saved in the script folder.",
                        nargs='?', const=True,)
    parser.add_argument("--useSavedXML",
                        help="The path to xml-file like products.xml. If the argument is passed without \
                              specifying the path, the xml-file will be products.xml in the script folder.",
                        nargs='?', const=True,)
    parser.add_argument('--skipDependencyACR',
                        help="Skip downloading CameraRaw for package", action='store_true')
    parser.add_argument('--skipNonCorePackages',
                        help="Skip downloading packages whose type is specified as non-core in all application.json file only for the target Adobe product.", action='store_true')
    parser.add_argument('--skipNonCorePackagesAll',
                        help="Skip downloading packages whose type is specified as non-core in all application.json files. This is dangerous because in some dependency components, all packages may not have any package type marking and therefore will be considered as non-core and will be removed from the application.the json file. For example in: COCM, COMP, COPS, CORE, CORG. And when you try to install a program downloaded by Adobe with such dependencies without packages, error 107 will appear during installation.", action='store_true')
    parser.add_argument('--skipModuleC4D',
                        help="Skip downloading Cinema 4D packages whose type is specified as non-core in application.json files usually for After Effects only", action='store_true')
    parser.add_argument('--skipModulesSpeechToText',
                        help="Skip downloading Speech to Text packages whose type is specified as non-core in application.json files usually for Premiere Pro only", action='store_true')
    parser.add_argument('--skipModulesSuperCaf',
                        help="Skip downloading SuperCafModels packages whose type is specified as non-core in application.json files usually for Photoshop only", action='store_true')
    parser.add_argument('--skipModulesUltraCaf',
                        help="Skip downloading UltraCafModels packages whose type is specified as non-core in application.json files usually for Photoshop only", action='store_true')
    parser.add_argument('--removeCheckCompatibility',
                        help="Remove point CheckCompatibility from SystemRequirement from application.json files", action='store_true')
    parser.add_argument('--notWrapInApp',
                        help="Just download adobe product to folder and not warp it into application", action='store_true')
    parser.add_argument('--onlyWithSupportOS',
                        help="Show only products supported on the specified macOS version. \
                            If you pass just an argument without parameters, the current macOS version on which the script is running will be selected.",
                        nargs='?', const=macos_version_current,)
    args = parser.parse_args()

    products, cdn, sapCodes, allowedPlatforms = get_products()

    while True:
        run_ccdl(products, cdn, sapCodes, allowedPlatforms)
        if args.noRepeatPrompt or not questiony('\n\nDo you want to create another package'):
            break
