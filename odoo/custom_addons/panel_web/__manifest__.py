{
    'name': 'Panel Web',
    'version': '2.0',
    'summary': 'Dashboard administrativo avanzado con métricas, indicadores, alertas y gráficos',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'sale',
        'sale_management',
        'purchase',
        'stock',
        'product',
        'account',
        'permisos_usuarios',
    ],

    'data': [
        'security/groups.xml',
        'views/panel.xml',
    ],

    'installable': True,
    'application': False,
}
