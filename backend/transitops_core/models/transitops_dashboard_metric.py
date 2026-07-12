from odoo import fields, models


class TransitOpsDashboardMetric(models.Model):
    _name = 'transitops.dashboard.metric'
    _description = 'TransitOps Dashboard Metric'
    _rec_name = 'metric_name'
    _order = 'metric_group, metric_name'

    dashboard_id = fields.Many2one('transitops.dashboard', required=True, ondelete='cascade')
    metric_group = fields.Selection(
        selection=[
            ('fleet', 'Fleet'),
            ('drivers', 'Drivers'),
            ('trips', 'Trips'),
            ('incidents', 'Incidents'),
            ('maintenance', 'Maintenance'),
        ],
        required=True,
    )
    metric_name = fields.Char(required=True)
    metric_key = fields.Char(required=True)
    metric_value = fields.Integer(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('dashboard_metric_key_uniq', 'unique(dashboard_id, metric_key)', 'Each dashboard metric must be unique per dashboard.'),
    ]