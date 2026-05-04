{
    'name': 'Presupuestos Web',
    'version': '1.0',
    'summary': 'Panel web para gestión de presupuestos (cotizaciones)',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'sale',
        'sale_management',
        'product',
        'account',
        'permisos_usuarios',
    ],

    'data': [
        'security/groups.xml',
        'views/presupuestos_template.xml',
        'views/presupuesto_nuevo.xml',
    ],

    'installable': True,
    'application': False,
}
