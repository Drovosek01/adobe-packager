import os

from ccdl import APM

if __name__ == '__main__':
    apm = APM()
    p = apm.get_product('PHSP', '23.0')
    if p:
        p_json = apm._get_product_json(p.buildGuid)
        urls = apm._get_download_urls(
            p_json, p.language, p_json['Cdn']['Secure'])
        install_dir = os.path.join('./', p.install_name)
        products_dir =  os.path.join(install_dir, 'Contents', 'Resources', 'products')
        product_dir = os.path.join(products_dir, p.id)
        apm._app_script(p.install_name)
        apm._create_icon_path(install_dir)

        for d in p.dependencies:
            j = apm._get_product_json(d.buildGuid)
            d.app_json = j
            apm._create_directory(d, install_dir)
        
        apm._create_driver_xml(p, p.language, products_dir)
        apm._create_directory(p, install_dir)

        for url in urls:
            apm._download(os.path.join(product_dir, url['name']), url['path'], int(url['size']), apm.ADOBE_REQ_HEADERS)