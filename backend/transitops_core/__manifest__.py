{
    'name': 'TransitOps Core',
    'version': '18.0.1.0.0',
    'category': 'Operations',
    'summary': 'Smart transport operations platform for fleet, dispatch, and service management',
    'description': """
TransitOps Core
===============

Base backend module for managing transport operations, including fleet data,
dispatch coordination, route planning, trip execution, and operational visibility.
    """,
    'author': 'TransitOps Team',
    'license': 'LGPL-3',
    'website': '',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/transitops_fleet_vehicle_views.xml',
        'views/transitops_driver_views.xml',
        'views/transitops_route_views.xml',
        'views/transitops_stop_views.xml',
        'views/transitops_trip_views.xml',
        'views/transitops_dashboard_views.xml',
        'views/transitops_menus.xml',
        'data/transitops_data.xml',
    ],
    'demo': [],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
}
