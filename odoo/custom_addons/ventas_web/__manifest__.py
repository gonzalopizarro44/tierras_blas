{
    'name': 'Ventas Web',
    'version': '2.0',
    'summary': 'Panel web avanzado para gestión de ventas',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'sale',
        'sale_management',
        'product',
        'stock',
        'account',
    ],

    'data': [
        'security/groups.xml',
        'views/ventas_template.xml',
        'views/nueva_venta.xml',
    ],

    'installable': True,
    'application': False,
}