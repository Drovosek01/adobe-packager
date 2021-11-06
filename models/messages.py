# XML Strings
CDN_XML = 'channel/cdn/secure'
PRODUCTS_XML = 'channel/products/product'
PRODUCT_DEPENDENCIES = 'platforms/platform/languageSet/dependencies'
PRODUCT_INFO = 'productInfoPage'
LANGUAGE_SET = 'platforms/platform/languageSet'
CC_INSTALL_LOC = '/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Setup'

# Menu messages
CC_NOT_INSTALLED = 'Adobe HyperDrive installer not found.\nPlease make sure the Creative Cloud app is installed.'
REQ_CHECK_PASS = 'All requirements have been met'
INVALID_SAP_CODE = 'Please select a valid program (code)'
LANGUAGE_DEFAULT = 'en_US'

# Languages
LANGUAGES = ['en_US', 'en_GB', 'en_IL', 'en_AE', 'es_ES', 'es_MX', 'pt_BR', 'fr_FR', 'fr_CA', 'fr_MA', 'it_IT', 'de_DE', 'nl_NL',
             'ru_RU', 'uk_UA', 'zh_TW', 'zh_CN', 'ja_JP', 'ko_KR', 'pl_PL', 'hu_HU', 'cs_CZ', 'tr_TR', 'sv_SE', 'nb_NO', 'fi_FI', 'da_DK']

# Driver Template
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
