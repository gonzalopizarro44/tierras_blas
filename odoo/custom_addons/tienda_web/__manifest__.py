{
    'name': 'Tienda Web Personalizada',
    'version': '1.0',
    'summary': 'Personalización de tienda online con solicitud de cotización',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'website_sale',
        'product',
    ],

    'data': [
        'views/tienda_template.xml',
    ],

    'installable': True,
    'application': False,
}
