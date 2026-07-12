from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TransitOpsStop(models.Model):
    _name = 'transitops.stop'
    _description = 'TransitOps Stop'
    _rec_name = 'stop_name'
    _order = 'route_id, stop_sequence, stop_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    stop_id = fields.Char(string='Stop ID', required=True, tracking=True)
    stop_name = fields.Char(string='Stop Name', required=True, tracking=True)
    route_id = fields.Many2one(
        comodel_name='transitops.route',
        string='Route',
        required=True,
        tracking=True,
        ondelete='cascade',
    )
    stop_sequence = fields.Integer(string='Stop Sequence', required=True, tracking=True)
    latitude = fields.Float(required=True, tracking=True)
    longitude = fields.Float(required=True, tracking=True)
    expected_arrival_time = fields.Datetime(required=True, tracking=True)
    expected_departure_time = fields.Datetime(required=True, tracking=True)
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('completed', 'Completed'),
        ],
        required=True,
        default='draft',
        tracking=True,
    )
    landmark = fields.Char(tracking=True)
    notes = fields.Text(tracking=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('stop_id_uniq', 'unique(stop_id)', 'Stop ID must be unique.'),
        ('stop_sequence_route_uniq', 'unique(route_id, stop_sequence)', 'Stop sequence must be unique per route.'),
    ]

    @api.constrains('stop_id', 'stop_name', 'stop_sequence', 'latitude', 'longitude', 'expected_arrival_time', 'expected_departure_time')
    def _check_stop_values(self):
        for record in self:
            if not record.stop_id.strip():
                raise ValidationError('Stop ID is required.')
            if not record.stop_name.strip():
                raise ValidationError('Stop Name is required.')
            if record.stop_sequence <= 0:
                raise ValidationError('Stop sequence must be greater than zero.')
            if not -90.0 <= record.latitude <= 90.0:
                raise ValidationError('Latitude must be between -90 and 90.')
            if not -180.0 <= record.longitude <= 180.0:
                raise ValidationError('Longitude must be between -180 and 180.')
            if record.expected_departure_time < record.expected_arrival_time:
                raise ValidationError('Expected departure time must be after or equal to expected arrival time.')

    @api.constrains('status', 'route_id')
    def _check_status_consistency(self):
        for record in self:
            if record.status == 'completed' and not record.route_id:
                raise ValidationError('Completed stops must be linked to a route.')

    @api.onchange('status')
    def _onchange_status(self):
        if self.status == 'completed':
            self.active = False
        elif self.status in ('draft', 'active', 'inactive'):
            self.active = True