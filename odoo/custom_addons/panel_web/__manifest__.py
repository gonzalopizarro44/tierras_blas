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
    'assets': {
        'web.assets_frontend': [
            'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js',
            'panel_web/static/src/css/panel.css',
            'panel_web/static/src/js/panel.js',
        ],
    },

    'installable': True,
    'application': False,
}
