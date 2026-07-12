from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TransitOpsMaintenance(models.Model):
    _name = 'transitops.maintenance'
    _description = 'TransitOps Maintenance'
    _rec_name = 'maintenance_id'
    _order = 'service_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    maintenance_id = fields.Char(string='Maintenance ID', required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)
    vehicle_id = fields.Many2one('transitops.fleet.vehicle', string='Vehicle', required=True, tracking=True, ondelete='restrict')
    maintenance_type = fields.Selection(
        selection=[
            ('preventive', 'Preventive'),
            ('corrective', 'Corrective'),
            ('emergency', 'Emergency'),
        ],
        required=True,
        default='preventive',
        tracking=True,
    )
    workshop_id = fields.Many2one('res.partner', string='Workshop', required=True, tracking=True, ondelete='restrict', domain="[('is_company', '=', True)]")
    vendor_id = fields.Many2one('res.partner', string='Vendor', tracking=True, ondelete='restrict', domain="[('is_company', '=', True)]")
    assigned_mechanic_id = fields.Many2one('res.users', string='Engineer', required=True, tracking=True, ondelete='restrict')
    service_date = fields.Date(string='Scheduled Date', required=True, default=fields.Date.context_today, tracking=True)
    expected_completion = fields.Datetime(required=True, tracking=True)
    completion_date = fields.Datetime(string='Completion Date', tracking=True)
    estimated_cost = fields.Float(string='Estimated Cost', required=True, default=0.0, tracking=True)
    actual_cost = fields.Float(string='Actual Cost', required=True, default=0.0, tracking=True)
    odometer_reading = fields.Float(required=True, tracking=True)
    next_due_date = fields.Date(string='Next Due Date', required=True, tracking=True)
    vehicle_health_score = fields.Float(string='Vehicle Health Score', readonly=True, tracking=True)
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        default='draft',
        tracking=True,
    )
    notes = fields.Text(tracking=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('maintenance_id_uniq', 'unique(maintenance_id)', 'Maintenance ID must be unique.'),
        ('maintenance_vehicle_service_unique', 'unique(vehicle_id, service_date, maintenance_type)', 'A vehicle cannot have duplicate maintenance for the same date and type.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('maintenance_id', _('New')) == _('New'):
                vals['maintenance_id'] = self.env['ir.sequence'].next_by_code('transitops.maintenance') or _('New')
            if not vals.get('next_due_date'):
                vals['next_due_date'] = self._calculate_next_due_date(vals.get('service_date') or fields.Date.context_today(self), vals.get('maintenance_type') or 'preventive')
            vals.setdefault('vehicle_health_score', 100.0)
        records = super().create(vals_list)
        records._sync_vehicle_maintenance_state()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_vehicle_maintenance_state()
        return result

    @api.constrains('maintenance_id', 'vehicle_id', 'assigned_mechanic_id', 'service_date', 'expected_completion', 'completion_date', 'estimated_cost', 'actual_cost', 'odometer_reading', 'next_due_date')
    def _check_maintenance_values(self):
        for record in self:
            if not record.maintenance_id.strip():
                raise ValidationError('Maintenance ID is required.')
            if record.estimated_cost < 0:
                raise ValidationError('Estimated cost cannot be negative.')
            if record.actual_cost < 0:
                raise ValidationError('Actual cost cannot be negative.')
            if record.odometer_reading < 0:
                raise ValidationError('Odometer reading cannot be negative.')
            if record.completion_date and record.completion_date < fields.Datetime.to_datetime(record.expected_completion):
                raise ValidationError('Completion date cannot be earlier than expected completion.')
            if record.next_due_date and record.next_due_date < record.service_date:
                raise ValidationError('Next due date must be on or after the scheduled date.')
            if record.status == 'completed' and not record.completion_date:
                raise ValidationError('Completed maintenance must have a completion date.')
            if record.status == 'cancelled' and record.completion_date:
                raise ValidationError('Cancelled maintenance cannot have a completion date.')
            if record.status == 'scheduled' and record.vehicle_id.status == 'retired':
                raise ValidationError('Scheduled maintenance cannot be assigned to a retired vehicle.')

    @api.onchange('maintenance_type', 'service_date')
    def _onchange_next_due_date(self):
        for record in self:
            record.next_due_date = record._calculate_next_due_date(record.service_date or fields.Date.context_today(record), record.maintenance_type or 'preventive')

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.odometer_reading = self.vehicle_id.odometer

    @api.onchange('status')
    def _onchange_status(self):
        if self.status == 'draft':
            self.active = True
        elif self.status in ('completed', 'cancelled'):
            self.active = False

    def _calculate_next_due_date(self, service_date, maintenance_type):
        service_date = fields.Date.to_date(service_date)
        interval_map = {
            'preventive': 90,
            'corrective': 60,
            'emergency': 30,
        }
        return service_date + timedelta(days=interval_map.get(maintenance_type, 90))

    def action_set_draft(self):
        self.write({'status': 'draft', 'active': True})

    def action_schedule_maintenance(self):
        self.write({'status': 'scheduled', 'active': True})
        for record in self:
            record.message_post(body=_('Maintenance has been scheduled.'))

    def action_set_scheduled(self):
        self.action_schedule_maintenance()

    def action_start_maintenance(self):
        self.write({'status': 'in_progress', 'active': True})
        for record in self:
            record.message_post(body=_('Maintenance work started.'))

    def action_complete_maintenance(self):
        for record in self:
            if not record.actual_cost:
                record.actual_cost = record.estimated_cost
        self.write({
            'status': 'completed',
            'completion_date': fields.Datetime.now(),
            'active': False,
        })
        for record in self:
            record.message_post(body=_('Maintenance work completed.'))

    def action_cancel_maintenance(self):
        self.write({'status': 'cancelled', 'active': False})
        for record in self:
            record.message_post(body=_('Maintenance request was cancelled.'))

    def action_view_vehicle(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vehicle',
            'res_model': 'transitops.fleet.vehicle',
            'res_id': self.vehicle_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _sync_vehicle_maintenance_state(self):
        for record in self:
            if not record.vehicle_id:
                continue
            vehicle = record.vehicle_id
            maintenance_records = vehicle.maintenance_ids.sorted(
                key=lambda maintenance: (
                    maintenance.next_due_date or fields.Date.from_string('9999-12-31'),
                    maintenance.service_date or fields.Date.from_string('9999-12-31'),
                    maintenance.id,
                )
            )
            open_records = maintenance_records.filtered(lambda maintenance: maintenance.status in ('draft', 'scheduled', 'in_progress'))
            in_progress_records = open_records.filtered(lambda maintenance: maintenance.status == 'in_progress')
            overdue_records = open_records.filtered(lambda maintenance: maintenance.next_due_date and maintenance.next_due_date < fields.Date.context_today(record))
            due_soon_records = open_records.filtered(
                lambda maintenance: maintenance.next_due_date and fields.Date.context_today(record) <= maintenance.next_due_date <= fields.Date.context_today(record) + timedelta(days=7)
            )

            values = {}
            if in_progress_records:
                values.update({'maintenance_status': 'in_service', 'availability': 'maintenance', 'assigned_driver_id': False})
            elif overdue_records:
                values.update({'maintenance_status': 'overdue'})
                if vehicle.availability == 'maintenance':
                    values.update({'availability': 'available'})
            elif due_soon_records:
                values.update({'maintenance_status': 'due'})
            else:
                values.update({'maintenance_status': 'ok'})
                if vehicle.availability == 'maintenance':
                    values.update({'availability': 'available'})

            if values:
                vehicle.write(values)
            vehicle.invalidate_cache(['maintenance_status', 'availability'])
            vehicle._compute_maintenance_metrics()
            record.vehicle_health_score = vehicle.maintenance_health_score

    @api.model
    def _cron_maintenance_reminder(self):
        today = fields.Date.context_today(self)
        reminder_window = today + timedelta(days=7)
        due_records = self.search([
            ('status', 'in', ('draft', 'scheduled', 'in_progress')),
            '|',
            ('next_due_date', '<=', reminder_window),
            ('service_date', '<=', reminder_window),
        ])
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for record in due_records:
            record.message_post(body=_('Maintenance reminder: service is due soon or currently in progress.'))
            if activity_type:
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=record.assigned_mechanic_id.id,
                    summary=_('TransitOps Maintenance Reminder'),
                    note=_('Maintenance %s needs attention.') % record.maintenance_id,
                )
