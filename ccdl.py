#!/usr/bin/env python3
"""
This is the Adobe Offline Package downloader.

CHANGELOG
(0.1.4)
+ Added M1 support. Defaults to yes when running on an M1 processor.
+ Added option to make another package after end.
+ Default picks picks newest version if one isn't specified
+ Default picks PhotoShop if nothing is entered, since it was used as the example.
+ Added Platform to version listing.

(0.1.3)
+ Went back to getting old URL.
+ Only show Versions actually Downloadable
+ Shows all Versions avalible

(0.1.2-hotfix1)
+ updated script to work with new api (newer downloads work now)
+ added workaround for broken installer on big sur
+ made everything even more messy and disgusting
"""
import argparse
import json
import locale
import os
import platform
import shutil
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

session = requests.Session()

VERSION = 4
VERSION_STR = '0.1.4'
CODE_QUALITY = 'Mildly_AWFUL'

INSTALL_APP_APPLE_SCRIPT = '''
const app = Application.currentApplication()
app.includeStandardAdditions = true

ObjC.import('Cocoa')
ObjC.import('stdio')
ObjC.import('stdlib')

ObjC.registerSubclass({
  name: 'HandleDataAction',
  methods: {
      'outData:': {
          types: ['void', ['id']],
          implementation: function(sender) {
              const data = sender.object.availableData
              if (data.length !== '0') {
                  const output = $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js
                  const res = parseOutput(output)
                  if (res) {
                      switch (res.type) {
                          case 'progress':
                              Progress.additionalDescription = `Progress: ${res.data}%`
                              Progress.completedUnitCount = res.data
                              break
                          case 'exit':
                              if (res.data === 0) {
                                  $.puts(JSON.stringify({ title: 'Installation succeeded' }))
                              } else {
                                  $.puts(JSON.stringify({ title: `Failed with error code ${res.data}` }))
                              }
                              $.exit(0)
                              break
                      }
                  }
                  sender.object.waitForDataInBackgroundAndNotify
              } else {
                  $.NSNotificationCenter.defaultCenter.removeObserver(this)
              }
          }
      }
  }
})

function parseOutput(output) {
  let matches

  matches = output.match(/Progress: ([0-9]{1,3})%/)
  if (matches) {
      return {
          type: 'progress',
          data: parseInt(matches[1], 10)
      }
  }

  matches = output.match(/Exit Code: ([0-9]{1,3})/)
  if (matches) {
      return {
          type: 'exit',
          data: parseInt(matches[1], 10)
      }
  }

  return false
}

function shellescape(a) {
  var ret = [];

  a.forEach(function(s) {
    if (/[^A-Za-z0-9_\\/:=-]/.test(s)) {
      s = "'"+s.replace(/'/g,"'\\\\''")+"'";
      s = s.replace(/^(?:'')+/g, '') // unduplicate single-quote at the beginning
        .replace(/\\\\\'''/g, "\\\\'" ); // remove non-escaped single-quote if there are enclosed between 2 escaped
    }
    ret.push(s);
  });

  return ret.join(' ');
}


function run() {
  const appPath = app.pathTo(this).toString()
  //const driverPath = appPath.substring(0, appPath.lastIndexOf('/')) + '/products/driver.xml'
  const driverPath = appPath + '/Contents/Resources/products/driver.xml'
  const hyperDrivePath = '/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Setup'

  // The JXA Objective-C bridge is completely broken in Big Sur
  if (!$.NSProcessInfo && parseFloat(app.doShellScript('sw_vers -productVersion')) >= 11.0) {
      app.displayAlert('GUI unavailable in Big Sur', {
          message: 'JXA is currently broken in Big Sur.\\nInstall in Terminal instead?',
          buttons: ['Cancel', 'Install in Terminal'],
          defaultButton: 'Install in Terminal',
          cancelButton: 'Cancel'
      })
      const cmd = shellescape([ 'sudo', hyperDrivePath, '--install=1', '--driverXML=' + driverPath ])
      app.displayDialog('Run this command in Terminal to install (press \\'OK\\' to copy to clipboard)', { defaultAnswer: cmd })
      app.setTheClipboardTo(cmd)
      return
  }

  const args = $.NSProcessInfo.processInfo.arguments
  const argv = []
  const argc = args.count
  for (var i = 0; i < argc; i++) {
      argv.push(ObjC.unwrap(args.objectAtIndex(i)))
  }
  delete args

  const installFlag = argv.indexOf('-y') > -1

  if (!installFlag) {
      app.displayAlert('Adobe Package Installer', {
          message: 'Start installation now?',
          buttons: ['Cancel', 'Install'],
          defaultButton: 'Install',
          cancelButton: 'Cancel'
      })

      const output = app.doShellScript(`"${appPath}/Contents/MacOS/applet" -y`, { administratorPrivileges: true })
      const alert = JSON.parse(output)
      alert.params ? app.displayAlert(alert.title, alert.params) : app.displayAlert(alert.title)
      return
  }

  const stdout = $.NSPipe.pipe
  const task = $.NSTask.alloc.init

  task.executableURL = $.NSURL.alloc.initFileURLWithPath(hyperDrivePath)
  task.arguments = $(['--install=1', '--driverXML=' + driverPath])
  task.standardOutput = stdout

  const dataAction = $.HandleDataAction.alloc.init
  $.NSNotificationCenter.defaultCenter.addObserverSelectorNameObject(dataAction, 'outData:', $.NSFileHandleDataAvailableNotification, $.initialOutputFile)

  stdout.fileHandleForReading.waitForDataInBackgroundAndNotify

  let err = $.NSError.alloc.initWithDomainCodeUserInfo('', 0, '')
  const ret = task.launchAndReturnError(err)
  if (!ret) {
      $.puts(JSON.stringify({
          title: 'Error',
          params: {
              message: 'Failed to launch task: ' + err.localizedDescription.UTF8String
          }
      }))
      $.exit(0)
  }

  Progress.description =  "Installing packages..."
  Progress.additionalDescription = "Preparing…"
  Progress.totalUnitCount = 100

  task.waitUntilExit
}
'''

ADOBE_PRODUCTS_XML_URL = 'https://cdn-ffc.oobesaas.adobe.com/core/v4/products/all?_type=xml&channel=ccm,sti&platform={installPlatform}&productType=Desktop'
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
    'X-Adobe-App-Id': 'accc-hdcore-desktop',
    'User-Agent': 'Adobe Application Manager 2.0',
    'X-Api-Key': 'CC_HD_ESD_1_0'
}


def dl(filename, url):
    """Download files from a url."""
    with session.get(url, stream=True, headers=ADOBE_REQ_HEADERS) as r:
        with open(filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)


def r(url, headers=ADOBE_REQ_HEADERS):
    """Retrieve a from a url as a string."""
    req = session.get(url, headers=headers)
    req.encoding = 'utf-8'
    return req.text


def get_products_xml(adobeurl):
    """First stage of parsing the XML."""
    print('Source URL is: ' + adobeurl)
    return ET.fromstring(r(adobeurl))


def parse_products_xml(products_xml):
    """2nd stage of parsing the XML."""
    cdn = products_xml.find('channel/cdn/secure').text
    products = {}
    parent_map = {c: p for p in products_xml.iter() for c in p}
    for p in products_xml.findall('channel/products/product'):
        displayName = p.find('displayName').text
        sap = p.get('id')
        version = p.get('version')
        pf = p.find('platforms/platform')
        appplatform = pf.get('id')
        dependencies = list(
            p.find('platforms/platform/languageSet/dependencies'))

        if not products.get(sap):
            if p.find('productInfoPage'):
                print(p.find('productInfoPage').text)
            products[sap] = {
                'hidden': parent_map[parent_map[p]].get('name') != 'ccm',
                'displayName': displayName,
                'sapCode': sap,
                'versions': OrderedDict()
            }

        products[sap]['versions'][version] = {
            'sapCode': sap,
            'version': version,
            'apPlatform': appplatform,
            'dependencies': [{
                'sapCode': d.find('sapCode').text, 'version': d.find('baseVersion').text
            } for d in dependencies],
            'buildGuid': p.find('platforms/platform/languageSet').get('buildGuid')
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


def runccdl():
    """Run Main exicution."""
    ye = int((32 - len(VERSION_STR)) / 2)
    print('=================================')
    print('= Adobe macOS Package Generator =')
    print('{} {} {}\n'.format('=' * ye, VERSION_STR,
          '=' * (31 - len(VERSION_STR) - ye)))

    if (args.ignoreNoCreativeCloud):
        print('Not checking Creative Cloud installation, created installer may use a fallback icon if CC is not installed.')
    elif (not os.path.isfile('/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Setup')):
        print('Adobe HyperDrive installer not found.\nPlease make sure the Creative Cloud app is installed.')
        exit(1)

    if args.arch:
        if args.arch.lower() == "arm64" or args.arch == "m1" or args.arch == "as":
            ism1 = True
        else:
            ism1 = False
    else:
        if platform.machine() == 'arm64':
            ism1 = questiony('Do you want to make M1 native packages')
        else:
            ism1 = questionn('Do you want to make M1 native packages')

    if ism1:
        adobeurlm1 = ADOBE_PRODUCTS_XML_URL.format(
            installPlatform='macarm64,macuniversal')
    adobeurl = ADOBE_PRODUCTS_XML_URL.format(
        installPlatform='macuniversal,osx10-64,osx10')

    print('Downloading products.xml\n')
    print(adobeurl)
    products_xml = get_products_xml(adobeurl)
    if ism1:
        products_xmlm1 = get_products_xml(adobeurlm1)

    print('Parsing products.xml')
    products, cdn = parse_products_xml(products_xml)
    if ism1:
        productsintel = products
        products, cdn = parse_products_xml(products_xmlm1)

    print('CDN: ' + cdn)
    sapCodes = {}
    for p in products.values():
        if not p['hidden']:
            versions = p['versions']
            version = None
            lastv = None
            for v in reversed(versions.values()):
                if v['buildGuid']:
                    lastv = v['version']
            if lastv:
                sapCodes[p['sapCode']] = p['displayName']
    if ism1:
        print(
            'Note: If the Adobe program is NOT listed here, there is no native M1 version.')
        print('      Use the non native version with Rosetta 2 until an M1 version is available.')
    print(
        str(len(sapCodes)) + ' products found:')

    sapCode = None
    if (args.sapCode):
        if products.get(args.sapCode):
            print('\nUsing provided SAP Code: ' + args.sapCode)
            sapCode = args.sapCode
        else:
            print('\nProvided SAP Code not found in products: ' + args.sapCode)

    print('')

    if not sapCode:
        for s, d in sapCodes.items():
            print('[{}] {}'.format(s, d))

        while sapCode is None:
            val = input(
                '\nPlease enter the SAP Code of the desired product (eg. PHSP for Photoshop): ') or 'PHSP'
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
        for v in reversed(versions.values()):

            if v['buildGuid']:
                print(
                    '{} Platform: {} - {}'.format(product['displayName'], v['apPlatform'], v['version']))
                lastv = v['version']

        while version is None:
            val = input(
                '\nPlease enter the desired version. Nothing for ' + lastv + ': ') or lastv
            if versions.get(val):
                version = val
            else:
                print(
                    '{} is not a valid version. Please use a value from the list above.'.format(val))

    print('')
    langs = ['en_US', 'en_GB', 'en_IL', 'en_AE', 'es_ES', 'es_MX', 'pt_BR', 'fr_FR', 'fr_CA', 'fr_MA', 'it_IT', 'de_DE', 'nl_NL',
             'ru_RU', 'uk_UA', 'zh_TW', 'zh_CN', 'ja_JP', 'ko_KR', 'pl_PL', 'hu_HU', 'cs_CZ', 'tr_TR', 'sv_SE', 'nb_NO', 'fi_FI', 'da_DK', 'ALL']
    # Detecting Current set default Os language. Doesn't seem to always work.
    deflocal = locale.getdefaultlocale()
    deflocal = deflocal[0]
    oslang = None

    if (args.osLanguage):
        oslang = args.osLanguage
    elif deflocal:
        oslang = deflocal

    if oslang in langs:
        deflang = oslang
    else:
        deflang = 'en_US'

    installLanguage = None
    if (args.installLanguage):
        if (args.installLanguage in langs):
            print('\nUsing provided language: ' + args.installLanguage)
            installLanguage = args.installLanguage
        else:
            print('\nProvided language not available: ' + args.installLanguage)

    if not installLanguage:
        print('Available languages: {}'.format(', '.join(langs)))
        while installLanguage is None:
            val = input(
                f'\nPlease enter the desired install language, or nothing for [{deflang}]: ') or deflang
            if (val in langs):
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
    dest = None
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

    print('')

    prodInfo = versions[version]
    prods_to_download = []
    dependencies = prodInfo['dependencies']
    for d in dependencies:
        try:
            prods_to_download.append({'sapCode': d['sapCode'], 'version': d['version'],
                                      'buildGuid': products[d['sapCode']]['versions'][d['version']]['buildGuid']})
        except KeyError:
            prods_to_download.append({'sapCode': d['sapCode'], 'version': d['version'],
                                     'buildGuid': productsintel[d['sapCode']]['versions'][d['version']]['buildGuid']})

    prods_to_download.insert(
        0, {'sapCode': prodInfo['sapCode'], 'version': prodInfo['version'], 'buildGuid': prodInfo['buildGuid']})
    apPlatform = prodInfo['apPlatform']
    install_app_name = 'Install {}_{}-{}-{}.app'.format(
        sapCode, version, installLanguage, apPlatform)
    install_app_path = os.path.join(dest, install_app_name)
    print('sapCode: ' + sapCode)
    print('version: ' + version)
    print('installLanguage: ' + installLanguage)
    print('dest: ' + install_app_path)
    print(prods_to_download)

    print('\nCreating {}'.format(install_app_name))

    install_app_path = os.path.join(
        dest, install_app_name)
    with Popen(['/usr/bin/osacompile', '-l', 'JavaScript', '-o', os.path.join(dest, install_app_path)], stdin=PIPE) as p:
        p.communicate(INSTALL_APP_APPLE_SCRIPT.encode('utf-8'))

    if (os.path.isfile('/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Install.app/Contents/Resources/CreativeCloudInstaller.icns')):
        icon_path = '/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Install.app/Contents/Resources/CreativeCloudInstaller.icns'
    else:
        icon_path = '/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/CDAudioVolumeIcon.icns'
    shutil.copyfile(icon_path, os.path.join(install_app_path,
                    'Contents', 'Resources', 'applet.icns'))

    products_dir = os.path.join(
        install_app_path, 'Contents', 'Resources', 'products')

    print('\nPreparing...\n')

    for p in prods_to_download:
        s, v = p['sapCode'], p['version']
        product_dir = os.path.join(products_dir, s)
        app_json_path = os.path.join(product_dir, 'application.json')

        print('[{}_{}] Downloading application.json'.format(s, v))
        app_json = get_application_json(p['buildGuid'])
        p['application_json'] = app_json

        print('[{}_{}] Creating folder for product'.format(s, v))
        os.makedirs(product_dir, exist_ok=True)

        print('[{}_{}] Saving application.json'.format(s, v))
        with open(app_json_path, 'w') as file:
            json.dump(app_json, file, separators=(',', ':'))

        print('')

    print('Downloading...\n')

    for p in prods_to_download:
        s, v = p['sapCode'], p['version']
        app_json = p['application_json']
        product_dir = os.path.join(products_dir, s)

        print('[{}_{}] Parsing available packages'.format(s, v))
        core_pkg_count = 0
        noncore_pkg_count = 0
        packages = app_json['Packages']['Package']
        download_urls = []
        for pkg in packages:
            if pkg.get('Type') and pkg['Type'] == 'core':
                core_pkg_count += 1
                download_urls.append(cdn + pkg['Path'])
            else:
                # TODO: actually parse `Condition` and check it properly (and maybe look for & add support for conditions other than installLanguage)
                if installLanguage == "ALL":
                    noncore_pkg_count += 1
                    download_urls.append(cdn + pkg['Path'])
                else:
                    if ((not pkg.get('Condition')) or installLanguage in pkg['Condition'] or oslang in pkg['Condition']):
                        noncore_pkg_count += 1
                        download_urls.append(cdn + pkg['Path'])
        print('[{}_{}] Selected {} core packages and {} non-core packages'.format(s,
              v, core_pkg_count, noncore_pkg_count))

        for url in download_urls:
            name = url.split('/')[-1].split('?')[0]
            print('Url is: ' + url)
            print('[{}_{}] Downloading {}'.format(s, v, name))
            # dl(os.path.join(product_dir, name), url)
            file_path = os.path.join(product_dir, name)
            response = session.head(url, stream=True, headers=ADOBE_REQ_HEADERS)
            total_size_in_bytes = int(response.headers.get('content-length', 0))
            if (args.skipExisting and os.path.isfile(file_path) and os.path.getsize(file_path) == total_size_in_bytes):
                print('[{}_{}] {} already exists, skipping'.format(s, v, name))
            else:
                response = session.get(url, stream=True, headers=ADOBE_REQ_HEADERS)
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

    print('\nGenerating driver.xml')

    driver = DRIVER_XML.format(
        name=product['displayName'],
        sapCode=prodInfo['sapCode'],
        version=prodInfo['version'],
        installPlatform=apPlatform,
        dependencies='\n'.join([DRIVER_XML_DEPENDENCY.format(
            sapCode=d['sapCode'],
            version=d['version']
        ) for d in prodInfo['dependencies']]),
        language=installLanguage
    )

    with open(os.path.join(products_dir, 'driver.xml'), 'w') as f:
        f.write(driver)
        f.close()

    print('\nPackage successfully created. Run {} to install.'.format(install_app_path))
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--installLanguage',
                        help='Language code (eg. en_US)', action='store')
    parser.add_argument('-o', '--osLanguage',
                        help='OS Language code (eg. en_US)', action='store')
    parser.add_argument(
        '-s', '--sapCode', help='SAP code for desired product (eg. PHSP)', action='store')
    parser.add_argument(
        '-v', '--version', help='Version of desired product (eg. 21.0.3)', action='store')
    parser.add_argument('-d', '--destination',
                        help='Directory to download installation files to', action='store')
    parser.add_argument('-a', '--arch',
                        help='Set the architecture to download', action='store')
    parser.add_argument('--ignoreNoCreativeCloud',
                        help='Ignore no creative cloud and just fallback to generic icon', action='store_true')
    parser.add_argument('--noRepeatPrompt', help="Don't prompt for additional downloads", action='store_true'),
    parser.add_argument('--skipExisting', help="Skip existing files, e.g. resuming failed downloads", action='store_true'),
    args = parser.parse_args()

    runcc = True
    while runcc:
        runccdl()
        if args.noRepeatPrompt:
            runcc = False
        else:
            runcc = questiony('\n\nDo you want to create another package')
