# -*- coding: utf-8 -*-
{
    'name': 'Compras Web',
    'version': '2.0',
    'summary': 'Panel web avanzado para gestión de compras',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'purchase',
        'purchase_stock',
        'product',
        'stock',
        'account',
    ],

    'data': [
        'security/groups.xml',
        'views/compras_template.xml',
        'views/nueva_compra.xml',
    ],

    'installable': True,
    'application': False,
}