from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TransitOpsFleetVehicle(models.Model):
    _name = 'transitops.fleet.vehicle'
    _description = 'TransitOps Fleet Vehicle'
    _rec_name = 'vehicle_number'
    _order = 'vehicle_number asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    vehicle_number = fields.Char(required=True, tracking=True)
    vehicle_type = fields.Selection(
        selection=[
            ('car', 'Car'),
            ('van', 'Van'),
            ('bus', 'Bus'),
            ('truck', 'Truck'),
            ('motorbike', 'Motorbike'),
            ('other', 'Other'),
        ],
        required=True,
        default='other',
        tracking=True,
    )
    capacity = fields.Integer(required=True, default=1, tracking=True)
    fuel_type = fields.Selection(
        selection=[
            ('petrol', 'Petrol'),
            ('diesel', 'Diesel'),
            ('electric', 'Electric'),
            ('hybrid', 'Hybrid'),
            ('cng', 'CNG'),
            ('lng', 'LNG'),
            ('other', 'Other'),
        ],
        required=True,
        default='diesel',
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('retired', 'Retired'),
        ],
        required=True,
        default='active',
        tracking=True,
    )
    current_location = fields.Char(tracking=True)
    assigned_driver_id = fields.Many2one(
        comodel_name='transitops.driver',
        string='Assigned Driver',
        tracking=True,
        ondelete='set null',
    )
    odometer = fields.Float(required=True, default=0.0, tracking=True)
    maintenance_status = fields.Selection(
        selection=[
            ('ok', 'OK'),
            ('due', 'Due Soon'),
            ('overdue', 'Overdue'),
            ('in_service', 'In Service'),
        ],
        required=True,
        default='ok',
        tracking=True,
    )
    availability = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('assigned', 'Assigned'),
            ('in_transit', 'In Transit'),
            ('on_trip', 'On Trip'),
            ('maintenance', 'Maintenance'),
            ('unavailable', 'Unavailable'),
        ],
        required=True,
        default='available',
        tracking=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('vehicle_number_uniq', 'unique(vehicle_number)', 'Vehicle number must be unique.'),
    ]

    @api.constrains('capacity', 'odometer')
    def _check_numeric_values(self):
        for record in self:
            if record.capacity <= 0:
                raise ValidationError('Vehicle capacity must be greater than zero.')
            if record.odometer < 0:
                raise ValidationError('Odometer reading cannot be negative.')

    @api.constrains('availability', 'status', 'maintenance_status', 'assigned_driver_id')
    def _check_operational_consistency(self):
        for record in self:
            if record.status == 'retired' and record.availability != 'unavailable':
                raise ValidationError('Retired vehicles must be marked as unavailable.')
            if record.maintenance_status == 'in_service' and record.availability not in ('maintenance', 'unavailable'):
                raise ValidationError('Vehicles in service must be marked as maintenance or unavailable.')
            if record.availability == 'available' and record.assigned_driver_id:
                raise ValidationError('Available vehicles should not have an assigned driver.')
            if record.availability == 'on_trip' and not record.assigned_driver_id:
                raise ValidationError('Vehicles on trip must have an assigned driver.')
            if record.availability == 'on_trip' and record.maintenance_status == 'in_service':
                raise ValidationError('Vehicles in service cannot be on trip.')
            if record.assigned_driver_id and record.assigned_driver_id.assigned_vehicle_id and record.assigned_driver_id.assigned_vehicle_id != record:
                raise ValidationError('Assigned driver must reference the same vehicle.')

    @api.onchange('availability')
    def _onchange_availability(self):
        if self.availability == 'available':
            self.assigned_driver_id = False

    @api.onchange('status')
    def _onchange_status(self):
        if self.status == 'retired':
            self.availability = 'unavailable'
            self.assigned_driver_id = False

    @api.onchange('assigned_driver_id')
    def _onchange_assigned_driver_id(self):
        if self.assigned_driver_id and self.assigned_driver_id.assigned_vehicle_id and self.assigned_driver_id.assigned_vehicle_id != self:
            self.assigned_driver_id = False