{
    'name': 'Inventario Web',
    'version': '1.1',
    'summary': 'Panel web para gestión de inventario',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'stock',
        'product',
    ],

    'data': [
        'security/groups.xml',
        'views/inventario_template.xml',
    ],

    'installable': True,
    'application': False,
}