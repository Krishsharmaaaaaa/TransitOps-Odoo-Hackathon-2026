from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TransitOpsRoute(models.Model):
    _name = 'transitops.route'
    _description = 'TransitOps Route'
    _rec_name = 'route_name'
    _order = 'route_id asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    route_id = fields.Char(string='Route ID', required=True, tracking=True)
    route_name = fields.Char(string='Route Name', required=True, tracking=True)
    source = fields.Char(required=True, tracking=True)
    destination = fields.Char(required=True, tracking=True)
    total_distance = fields.Float(string='Total Distance', required=True, tracking=True, help='Route distance in kilometers.')
    estimated_duration = fields.Float(string='Estimated Duration', required=True, tracking=True, help='Estimated duration in hours.')
    route_type = fields.Selection(
        selection=[
            ('urban', 'Urban'),
            ('intercity', 'Intercity'),
            ('shuttle', 'Shuttle'),
            ('school', 'School'),
            ('freight', 'Freight'),
            ('express', 'Express'),
            ('other', 'Other'),
        ],
        required=True,
        default='other',
        tracking=True,
    )
    number_of_stops = fields.Integer(string='Number of Stops', required=True, default=0, tracking=True)
    assigned_vehicle_ids = fields.Many2many(
        comodel_name='transitops.fleet.vehicle',
        relation='transitops_route_vehicle_rel',
        column1='route_id',
        column2='vehicle_id',
        string='Assigned Vehicles',
        tracking=True,
    )
    assigned_driver_ids = fields.Many2many(
        comodel_name='transitops.driver',
        relation='transitops_route_driver_rel',
        column1='route_id',
        column2='driver_id',
        string='Assigned Drivers',
        tracking=True,
    )
    stop_ids = fields.One2many(
        comodel_name='transitops.stop',
        inverse_name='route_id',
        string='Stops',
    )
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('inactive', 'Inactive'),
            ('completed', 'Completed'),
        ],
        required=True,
        default='draft',
        tracking=True,
    )
    notes = fields.Text(tracking=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('route_id_uniq', 'unique(route_id)', 'Route ID must be unique.'),
        ('route_name_uniq', 'unique(route_name)', 'Route Name must be unique.'),
    ]

    @api.constrains('route_id', 'route_name', 'total_distance', 'estimated_duration', 'number_of_stops', 'assigned_vehicle_ids', 'assigned_driver_ids')
    def _check_route_values(self):
        for record in self:
            if not record.route_id.strip():
                raise ValidationError('Route ID is required.')
            if not record.route_name.strip():
                raise ValidationError('Route Name is required.')
            if record.total_distance <= 0:
                raise ValidationError('Total distance must be greater than zero.')
            if record.estimated_duration <= 0:
                raise ValidationError('Estimated duration must be greater than zero.')
            if record.number_of_stops < 0:
                raise ValidationError('Number of stops cannot be negative.')
            if record.status == 'active' and not record.assigned_vehicle_ids:
                raise ValidationError('Active routes must have at least one assigned vehicle.')
            if record.status == 'active' and not record.assigned_driver_ids:
                raise ValidationError('Active routes must have at least one assigned driver.')

    @api.onchange('status')
    def _onchange_status(self):
        if self.status == 'completed':
            self.active = False
        elif self.status in ('draft', 'active', 'paused'):
            self.active = True