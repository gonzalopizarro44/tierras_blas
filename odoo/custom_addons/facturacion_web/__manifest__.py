# -*- coding: utf-8 -*-
{
    'name': 'Facturación Web',
    'version': '1.0',
    'summary': 'Panel web para gestión de facturas de clientes y proveedores',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'account',
        'sale',
        'purchase',
        'product',
    ],

    'data': [
        'security/groups.xml',
        'views/facturacion_template.xml',
        'views/nueva_factura.xml',
    ],

    'installable': True,
    'application': False,
}
