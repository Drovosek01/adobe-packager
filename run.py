import os

from ccdl import APM


def main():
    apm = APM()

    while not apm.product_listing:
        print('Retrieving product listing', end='\r')

    print('Getting product code')
    apm.print_product_list()
    product_code = input('Please enter the code of the program you want:\n')
    if apm.is_valid_product_code(product_code):
        exit()

    print('Getting version')
    apm.print_product_versions(product_code)
    product_version = input(
        'Please enter the version of the program you want:\n')
    if not apm.is_valid_product_version(product_code, product_version):
        exit()

    print('Getting language')
    apm.print_product_languages()
    product_language = input(
        'Please enter the language of the program you want:\n')
    if not apm.is_valid_product_language(product_language):
        exit()

    product = apm.get_product(product_code, product_version)
    if product:
        product.language = product_language
        apm.download(product)


if __name__ == '__main__':
    main()
