from odoo import fields, models


class TransitOpsDashboard(models.Model):
    _name = 'transitops.dashboard'
    _description = 'TransitOps Dashboard'
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)