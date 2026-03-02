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
from collections import OrderedDict
from subprocess import PIPE, Popen
from xml.etree import ElementTree as ET

import requests

try:
    from tqdm.auto import tqdm
except ImportError:
    print("Trying to Install required module: tqdm\n")
    os.system('pip3 install --user tqdm')
    try:
        from tqdm.auto import tqdm
    except ImportError:
        sys.exit("""You need tqdm!
                install it from http://pypi.python.org/pypi/tqdm
                or run: pip3 install tqdm.""")

session = requests.sessions.Session()

VERSION = 4
VERSION_STR = '0.3.0'

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
        response = session.get(url, headers=ADOBE_REQ_HEADERS, stream=True)
        response.encoding = 'utf-8'
        xml_text = response.text

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
    return (reply in ("", "y"))


def questionn(question: str) -> bool:
    """Question prompt default N."""
    reply = None
    while reply not in ("", "y", "n"):
        reply = input(f"{question} (y/N): ").lower()
    return (reply in ("y", "Y"))


def get_application_json(buildGuid):
    """Retrieve JSON."""
    headers = ADOBE_REQ_HEADERS.copy()
    headers['x-adobe-build-guid'] = buildGuid
    return json.loads(r(ADOBE_APPLICATION_JSON_URL, headers))


def get_download_path():
    """Ask for desired download folder"""
    if (args.destination):
        print('\nUsing provided destination: ' + args.destination)
        dest = args.destination
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
        val = input('\nPlease enter the URL version (usually v4/v5/v6) for downloading products.xml, or nothing for v6: ') or '6'
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

    if args.nativeOnly:
        if platform.machine() == 'arm64':
            isAppleSiliconOnly = True
            allowedPlatforms.append('macarm64')
        else:
            isAppleSiliconOnly = False
            allowedPlatforms.append('osx10-64')
            allowedPlatforms.append('osx10')
    else:
        if args.arch:
            if args.arch.lower() == 'x86_64' or args.arch.lower() == 'x64' or args.arch.lower() == 'intel':
                isAppleSiliconOnly = False
            elif args.arch.lower() == 'arm64' or args.arch.lower() == 'arm' or args.arch.lower() == 'm1':
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


def remove_packages_by_modules_refs(data: dict, substr: str) -> bool:
    """
    Removes modules with substring in the DisplayName,
    as well as their associated packages.
    Returns True if the 1 or more module found.
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
        display_name = module.get("DisplayName", "")
        if substr.lower() in display_name.lower():
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
        if substr.lower() not in m.get("DisplayName", "").lower()
    ]

    modules_container["Module"] = new_modules
    packages_container["Package"] = new_packages

    return isModuleRemoved


def run_ccdl(products, cdn, sapCodes, allowedPlatforms):
    """Run Main execution."""
    sapCode = args.sapCode
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
                '\nPlease enter the SAP Code of the desired product (eg. PHSP for Photoshop): ').upper() or 'PHSP'
            if products.get(val):
                sapCode = val
            else:
                print(
                    '{} is not a valid SAP Code. Please use a value from the list above.'.format(val))

    product = products.get(sapCode)
    versions = product['versions']
    version = None
    if (args.version):
        if versions.get(args.version):
            print('\nUsing provided version: ' + args.version)
            version = args.version
        else:
            print('\nProvided version not found: ' + args.version)

    print('')

    if not version:
        lastv = None
        for v in reversed(versions.values()):

            if v['buildGuid'] and v['apPlatform'] in allowedPlatforms:
                print('{} Platform: {} - {}'.format(product['displayName'], v['apPlatform'], v['productVersion']))
                lastv = v['productVersion']

        while version is None:
            val = input('\nPlease enter the desired version. Nothing for ' + lastv + ': ') or lastv
            if versions.get(val):
                version = val
            else:
                print('{} is not a valid version. Please use a value from the list above.'.format(val))
    print('')

    if sapCode == 'APRO':
        download_APRO(versions[version], cdn)
        return

    # TODO: Parse languages in the xml
    langs = ['en_US', 'en_GB', 'en_IL', 'en_AE', 'es_ES', 'es_MX', 'pt_BR', 'fr_FR', 'fr_CA', 'fr_MA', 'it_IT', 'de_DE', 'nl_NL',
             'ru_RU', 'uk_UA', 'zh_TW', 'zh_CN', 'ja_JP', 'ko_KR', 'pl_PL', 'hu_HU', 'cs_CZ', 'tr_TR', 'sv_SE', 'nb_NO', 'fi_FI', 'da_DK', 'ALL']
    # Detecting Current set default Os language. Fixed.
    deflocal = locale.getlocale()[0]
    if not deflocal:
        deflocal = 'en_US'

    oslang = None
    if args.osLanguage:
        oslang = args.osLanguage
    elif deflocal:
        oslang = deflocal

    if oslang in langs:
        deflang = oslang
    else:
        deflang = 'en_US'

    installLanguage = None
    if args.installLanguage:
        if args.installLanguage in langs:
            print('\nUsing provided language: ' + args.installLanguage)
            installLanguage = args.installLanguage
        else:
            print('\nProvided language not available: ' + args.installLanguage)

    if not installLanguage:
        print('Available languages: {}'.format(', '.join(langs)))
        while installLanguage is None:
            val = input(
                f'\nPlease enter the desired install language, or nothing for [{deflang}]: ') or deflang
            if len(val) == 5:
                val = val[0:2].lower() + val[2] + val[3:5].upper()
            elif len(val) == 3:
                val = val.upper()
            if val in langs:
                installLanguage = val
            else:
                print(
                    '{} is not available. Please use a value from the list above.'.format(val))
    if oslang != installLanguage:
        if installLanguage != 'ALL':
            while oslang not in langs:
                print('Could not detect your default Language for MacOS.')
                oslang = input(
                    f'\nPlease enter the your OS Language, or nothing for [{installLanguage}]: ') or installLanguage
                if oslang not in langs:
                    print(
                        '{} is not available. Please use a value from the list above.'.format(oslang))

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
                needDownloadACR = questionn('Do you want include CameraRaw in this package')
                if needDownloadACR:
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
                                  'buildGuid': buildGuid})

    prods_to_download.insert(
        0, {'sapCode': prodInfo['sapCode'], 'version': prodInfo['productVersion'], 'buildGuid': prodInfo['buildGuid']})
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

        if args.skipNonCorePackages:
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

    print('Downloading...')

    for p in prods_to_download:
        s, v = p['sapCode'], p['version']
        app_json = p['application_json']
        product_dir = os.path.join(products_dir, s)

        print('\n[{}_{}] Parsing available packages'.format(s, v))
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
                if args.skipNonCorePackages:
                    continue

                if pkg.get('Type') and pkg['Type'] == 'non-core':
                    noncore_pkg_count += 1
                    download_urls.append(cdn + pkg['Path'])
                if pkg.get('Type') is None:
                    typeless_pkg_count += 1
                    download_urls.append(cdn + pkg['Path'])
                # TODO: actually parse `Condition` and check it properly (and maybe look for & add support for conditions other than installLanguage)
                language_is_suitable = (
                        installLanguage == "ALL"
                        or 'Condition' not in pkg
                        or '[installLanguage]' not in pkg['Condition']
                        or '[installLanguage]==' + installLanguage in pkg['Condition']
                        or '[installLanguage]==' + oslang in pkg['Condition']
                )

                if language_is_suitable:
                    download_urls.append(cdn + pkg['Path'])

        if args.skipNonCorePackages:
            print('[{}_{}] Selected {} core packages'.format(s, v, core_pkg_count))
        else:
            print('[{}_{}] Selected {} core packages and {} non-core packages and {} packages without type'.format(s, v, core_pkg_count, noncore_pkg_count, typeless_pkg_count))

        for url in download_urls:
            download_file(url, product_dir, s, v)

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

    print('\nPackage successfully created. Run {} to install.'.format(result_path))
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
                        help='Version of desired product (eg. 21.0.3)', action='store')
    parser.add_argument('-d', '--destination',
                        help='Directory to download installation files to', action='store')
    parser.add_argument('-a', '--arch',
                        help='Set the architecture to download', action='store')
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
    parser.add_argument('--nativeOnly',
                        help="Show and download only those applications that are native to this platform", action='store_true')
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
                        help="Skip downloading packages whose type is specified as non-core in application.json files.", action='store_true')
    parser.add_argument('--skipModuleC4D',
                        help="Skip downloading Cinema 4D packages whose type is specified as non-core in application.json files usually for After Effects only", action='store_true')
    parser.add_argument('--skipModulesSpeechToText',
                        help="Skip downloading Speech to Text packages whose type is specified as non-core in application.json files usually for Premiere Pro only", action='store_true')
    parser.add_argument('--removeCheckCompatibility',
                        help="Remove point CheckCompatibility from SystemRequirement from application.json files", action='store_true')
    parser.add_argument('--notWrapInApp',
                        help="Just download adobe product to folder and not warp it into application", action='store_true')
    parser.add_argument('--onlyWithSupportOS',
                        help="Show only applications supported on the specified macOS version. \
                            If you pass just an argument without parameters, the current macOS version on which the script is running will be selected.",
                        nargs='?', const=macos_version_current,)
    args = parser.parse_args()

    products, cdn, sapCodes, allowedPlatforms = get_products()

    while True:
        run_ccdl(products, cdn, sapCodes, allowedPlatforms)
        if args.noRepeatPrompt or not questiony('\n\nDo you want to create another package'):
            break
