{
    'name': 'Custom Signup Flow',
    'version': '1.0',
    'summary': 'Custom registration flow with DNI and activation via reset password.',
    'description': 'Modifies the signup flow to require DNI and set password via email.',
    'category': 'Website/Website',
    'depends': ['auth_signup', 'website'],
    'data': [
        'views/signup_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'custom_signup_flow/static/src/css/signup_custom.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
