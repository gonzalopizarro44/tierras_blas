{
    'name': 'Tienda',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Catálogo de productos con contacto por WhatsApp',
    'description': """
        Módulo de tienda/catálogo simple para visualización de productos 
        del inventario y contacto directo vía WhatsApp.
    """,
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'website',
        'product',
        'stock',
    ],
    'data': [
        'views/tienda.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'tienda/static/src/css/tienda.css',
            'tienda/static/src/js/tienda.js',
        ],
    },
    'installable': True,
    'application': True,
}
