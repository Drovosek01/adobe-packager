import os
from models.product import Product


class Driver:
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

    def __init__(self, product: Product, directory: str, driver_name: str = 'driver.xml'):
        self.driver_name = driver_name
        self.product = product
        self.directory = directory
        self.path = os.path.join(self.directory, self.driver_name)
        self.xml = self.DRIVER_XML.format(
            name=product.name,
            sapCode=product.id,
            version=product.version,
            installPlatform=product.platform,
            dependencies='\n'.join(
                self.DRIVER_XML_DEPENDENCY.format(
                    sapCode=d.id, version=d.version)
                for d in product.dependencies
            ),
            language=product.language
        )

    def write(self):
        with open(self.path, 'w') as f:
            f.write(self.xml)
