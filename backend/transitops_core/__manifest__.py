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
    'depends': ['base', 'mail', 'web'],
    'data': [
        'data/transitops_sequence.xml',
        'security/transitops_security.xml',
        'data/transitops_notification_cron.xml',
        'data/transitops_maintenance_cron.xml',
        'security/ir.model.access.csv',
        'data/transitops_data.xml',
        'views/transitops_fleet_vehicle_views.xml',
        'views/transitops_driver_views.xml',
        'views/transitops_route_views.xml',
        'views/transitops_stop_views.xml',
        'views/transitops_trip_views.xml',
        'views/transitops_incident_views.xml',
        'views/transitops_maintenance_views.xml',
        'views/transitops_notification_views.xml',
        'views/transitops_live_tracking_views.xml',
        'views/transitops_dashboard_metric_views.xml',
        'views/transitops_reporting_views.xml',
        'views/transitops_dashboard_views.xml',
        'views/transitops_menus.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'transitops_core/static/src/scss/live_tracking_map.scss',
            'transitops_core/static/src/js/live_tracking_map.js',
            'transitops_core/static/src/xml/live_tracking_map.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
