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
        'website_sale_wishlist',
        'product',
    ],
    'data': [
        'views/tienda_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'tienda_web/static/src/css/tienda_web.css',
            'tienda_web/static/src/js/tienda_whatsapp.js',
        ],
    },
    'installable': False,
    'application': False,
}