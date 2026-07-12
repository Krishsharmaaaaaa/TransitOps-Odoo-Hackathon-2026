from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TransitOpsDriver(models.Model):
    _name = 'transitops.driver'
    _description = 'TransitOps Driver'
    _rec_name = 'name'
    _order = 'name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Char(required=True, tracking=True)
    name = fields.Char(required=True, tracking=True)
    phone = fields.Char(required=True, tracking=True)
    email = fields.Char(tracking=True)
    license_number = fields.Char(required=True, tracking=True)
    license_expiry = fields.Date(required=True, tracking=True)
    experience = fields.Integer(required=True, default=0, tracking=True)
    address = fields.Text(tracking=True)
    emergency_contact = fields.Char(required=True, tracking=True)
    assigned_vehicle_id = fields.Many2one(
        comodel_name='transitops.fleet.vehicle',
        string='Assigned Vehicle',
        tracking=True,
        ondelete='set null',
    )
    availability = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('assigned', 'Assigned'),
            ('on_duty', 'On Duty'),
            ('on_trip', 'On Trip'),
            ('off_duty', 'Off Duty'),
            ('on_leave', 'On Leave'),
            ('unavailable', 'Unavailable'),
        ],
        required=True,
        default='available',
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
        ],
        required=True,
        default='active',
        tracking=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('employee_id_uniq', 'unique(employee_id)', 'Employee ID must be unique.'),
        ('license_number_uniq', 'unique(license_number)', 'License number must be unique.'),
    ]

    @api.constrains('phone', 'email', 'experience', 'license_expiry', 'availability', 'status', 'assigned_vehicle_id')
    def _check_driver_values(self):
        for record in self:
            if not record.phone.strip():
                raise ValidationError('Phone number is required.')
            if record.email and '@' not in record.email:
                raise ValidationError('Please enter a valid email address.')
            if record.experience < 0:
                raise ValidationError('Experience cannot be negative.')
            if record.license_expiry and record.license_expiry < fields.Date.context_today(record):
                raise ValidationError('License expiry date must be in the future.')
            if record.status == 'inactive' and record.availability not in ('off_duty', 'unavailable'):
                raise ValidationError('Inactive drivers must be off duty or unavailable.')
            if record.status == 'suspended' and record.availability != 'unavailable':
                raise ValidationError('Suspended drivers must be unavailable.')
            if record.availability == 'available' and record.assigned_vehicle_id:
                raise ValidationError('Available drivers should not have an assigned vehicle.')
            if record.availability == 'on_trip' and not record.assigned_vehicle_id:
                raise ValidationError('Drivers on trip must have an assigned vehicle.')
            if record.assigned_vehicle_id and record.assigned_vehicle_id.assigned_driver_id and record.assigned_vehicle_id.assigned_driver_id != record:
                raise ValidationError('Assigned vehicle must reference the same driver.')

    @api.onchange('status')
    def _onchange_status(self):
        if self.status == 'inactive':
            self.availability = 'off_duty'
        elif self.status == 'suspended':
            self.availability = 'unavailable'
            self.assigned_vehicle_id = False

    @api.onchange('availability')
    def _onchange_availability(self):
        if self.availability == 'available':
            self.assigned_vehicle_id = False

    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_id(self):
        if self.assigned_vehicle_id and self.assigned_vehicle_id.assigned_driver_id and self.assigned_vehicle_id.assigned_driver_id != self:
            self.assigned_vehicle_id = False