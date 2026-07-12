from datetime import date

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
    incident_ids = fields.One2many(
        comodel_name='transitops.incident',
        inverse_name='vehicle_id',
        string='Incidents',
    )
    incident_count = fields.Integer(compute='_compute_incident_count', string='Incidents')
    maintenance_ids = fields.One2many(
        comodel_name='transitops.maintenance',
        inverse_name='vehicle_id',
        string='Maintenance Records',
    )
    maintenance_count = fields.Integer(compute='_compute_maintenance_count', string='Maintenance')
    maintenance_health_score = fields.Float(compute='_compute_maintenance_metrics', string='Vehicle Health Score', readonly=True, store=True)
    next_maintenance_date = fields.Date(compute='_compute_maintenance_metrics', string='Next Maintenance Date', readonly=True, store=True)
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

    def _compute_incident_count(self):
        incident_data = self.env['transitops.incident'].read_group(
            [('vehicle_id', 'in', self.ids)],
            ['vehicle_id'],
            ['vehicle_id'],
        )
        mapped_data = {item['vehicle_id'][0]: item['vehicle_id_count'] for item in incident_data}
        for record in self:
            record.incident_count = mapped_data.get(record.id, 0)

    def _compute_maintenance_count(self):
        maintenance_data = self.env['transitops.maintenance'].read_group(
            [('vehicle_id', 'in', self.ids)],
            ['vehicle_id'],
            ['vehicle_id'],
        )
        mapped_data = {item['vehicle_id'][0]: item['vehicle_id_count'] for item in maintenance_data}
        for record in self:
            record.maintenance_count = mapped_data.get(record.id, 0)

    @api.depends(
        'maintenance_ids.status',
        'maintenance_ids.next_due_date',
        'maintenance_ids.service_date',
        'maintenance_ids.completion_date',
        'maintenance_ids.maintenance_type',
    )
    def _compute_maintenance_metrics(self):
        today = fields.Date.context_today(self)
        for record in self:
            maintenance_records = record.maintenance_ids.sorted(
                key=lambda maintenance: (
                    maintenance.next_due_date or date(9999, 12, 31),
                    maintenance.service_date or date(9999, 12, 31),
                    maintenance.id,
                )
            )
            open_records = maintenance_records.filtered(lambda maintenance: maintenance.status in ('draft', 'scheduled', 'in_progress'))
            completed_records = maintenance_records.filtered(lambda maintenance: maintenance.status == 'completed')

            next_due = False
            if open_records:
                next_due = open_records[0].next_due_date or open_records[0].service_date
            elif maintenance_records:
                future_records = maintenance_records.filtered(lambda maintenance: maintenance.next_due_date)
                if future_records:
                    next_due = future_records[0].next_due_date
                else:
                    next_due = maintenance_records[0].service_date

            score = 100.0
            if not maintenance_records:
                score = 100.0
            elif open_records:
                latest_open = open_records[0]
                if latest_open.status == 'in_progress':
                    score = 75.0
                elif latest_open.next_due_date and latest_open.next_due_date < today:
                    overdue_days = (today - latest_open.next_due_date).days
                    score = max(25.0, 60.0 - (overdue_days * 2))
                elif latest_open.next_due_date and latest_open.next_due_date <= today.replace(day=today.day):
                    score = 80.0
                else:
                    score = 90.0
            elif completed_records:
                latest_completed = completed_records.sorted(
                    key=lambda maintenance: (
                        maintenance.completion_date or maintenance.service_date or date(1, 1, 1),
                        maintenance.id,
                    )
                )[-1]
                if latest_completed.completion_date:
                    completion_date = fields.Datetime.to_datetime(latest_completed.completion_date).date()
                    days_since_completion = (today - completion_date).days
                    if days_since_completion <= 30:
                        score = 98.0
                    elif days_since_completion <= 90:
                        score = 92.0
                    else:
                        score = 86.0

            record.maintenance_health_score = max(0.0, min(100.0, score))
            record.next_maintenance_date = next_due

    def action_view_incidents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Incidents',
            'res_model': 'transitops.incident',
            'view_mode': 'tree,kanban,form,calendar,pivot,graph',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_view_maintenance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance',
            'res_model': 'transitops.maintenance',
            'view_mode': 'tree,kanban,form,calendar,pivot,graph',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }