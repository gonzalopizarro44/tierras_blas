{
    'name': 'Permisos de Usuarios',
    'version': '1.0',
    'summary': 'Gestión centralizada de permisos de usuario',
    'author': 'Gonzalo Pizarro',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'portal',
        'website',
    ],

    'data': [
        'security/groups.xml',
        'views/portal_templates.xml',
    ],

    'installable': True,
    'application': False,
}
