from datetime import timedelta

from odoo import api, fields, models, _


class TransitOpsNotification(models.Model):
    _name = 'transitops.notification'
    _description = 'TransitOps Notification History'
    _rec_name = 'notification_number'
    _order = 'notification_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    notification_number = fields.Char(required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)
    notification_type = fields.Selection(
        selection=[
            ('upcoming_maintenance', 'Upcoming Maintenance'),
            ('vehicle_overdue_maintenance', 'Vehicle Overdue Maintenance'),
            ('trip_dispatch', 'Trip Dispatch'),
            ('trip_completion', 'Trip Completion'),
            ('trip_cancellation', 'Trip Cancellation'),
            ('incident_reported', 'Incident Reported'),
            ('incident_resolved', 'Incident Resolved'),
            ('driver_license_expiry', 'Driver License Expiry'),
            ('vehicle_registration_expiry', 'Vehicle Registration Expiry'),
            ('vehicle_insurance_expiry', 'Vehicle Insurance Expiry'),
        ],
        required=True,
        tracking=True,
    )
    source_model = fields.Char(required=True, tracking=True)
    source_res_id = fields.Integer(required=True, tracking=True)
    source_name = fields.Char(tracking=True)
    notification_date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    recipient_id = fields.Many2one('res.users', tracking=True, ondelete='set null')
    message = fields.Text(required=True, tracking=True)
    notification_key = fields.Char(required=True, tracking=True)
    notification_count = fields.Integer(default=1)
    state = fields.Selection(
        selection=[
            ('sent', 'Sent'),
            ('acknowledged', 'Acknowledged'),
        ],
        required=True,
        default='sent',
        tracking=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('notification_key_uniq', 'unique(notification_key)', 'Notification key must be unique to avoid duplicate notifications.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('notification_number', _('New')) == _('New'):
                vals['notification_number'] = self.env['ir.sequence'].next_by_code('transitops.notification') or _('New')
        return super().create(vals_list)

    def _get_source_record(self):
        self.ensure_one()
        return self.env[self.source_model].browse(self.source_res_id).exists()

    def action_acknowledge(self):
        self.write({'state': 'acknowledged'})

    def action_open_source(self):
        self.ensure_one()
        source_record = self._get_source_record()
        if not source_record:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.source_name or self.notification_number,
            'res_model': self.source_model,
            'res_id': source_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def _notification_label(self, notification_type):
        return dict(self._fields['notification_type'].selection).get(notification_type, notification_type)

    @api.model
    def _make_key(self, notification_type, source_model, source_res_id, suffix=''):
        return f'{notification_type}:{source_model}:{source_res_id}:{suffix}'

    @api.model
    def notify_once(self, notification_type, source_record, message, recipient=None, suffix=''):
        source_record = source_record.exists()
        if not source_record:
            return False

        key = self._make_key(notification_type, source_record._name, source_record.id, suffix)
        existing = self.search([('notification_key', '=', key)], limit=1)
        if existing:
            return existing

        recipient = recipient or source_record.create_uid or self.env.user
        notification = self.create({
            'notification_type': notification_type,
            'source_model': source_record._name,
            'source_res_id': source_record.id,
            'source_name': getattr(source_record, 'display_name', False) or getattr(source_record, 'name', False) or getattr(source_record, 'trip_name', False) or getattr(source_record, 'incident_number', False) or getattr(source_record, 'maintenance_id', False) or getattr(source_record, 'vehicle_number', False) or getattr(source_record, 'employee_id', False) or str(source_record.id),
            'recipient_id': recipient.id if recipient else False,
            'message': message,
            'notification_key': key,
            'state': 'sent',
        })

        notification.message_post(body=message)
        source_record.message_post(body=message)

        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if activity_type and recipient:
            source_record.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=recipient.id,
                summary=self._notification_label(notification_type),
                note=message,
            )
        return notification

    @api.model
    def _cron_process_operational_notifications(self):
        today = fields.Date.context_today(self)
        window = timedelta(days=7)
        vehicle_model = self.env['transitops.fleet.vehicle']
        driver_model = self.env['transitops.driver']
        maintenance_model = self.env['transitops.maintenance']
        trip_model = self.env['transitops.trip']
        incident_model = self.env['transitops.incident']

        for maintenance in maintenance_model.search([('status', 'in', ('draft', 'scheduled', 'in_progress'))]):
            if maintenance.next_due_date and maintenance.next_due_date <= today + window:
                self.notify_once('upcoming_maintenance', maintenance, f'Maintenance {maintenance.maintenance_id} is due soon.', recipient=maintenance.assigned_mechanic_id)
            if maintenance.status == 'in_progress' or (maintenance.next_due_date and maintenance.next_due_date < today):
                self.notify_once('vehicle_overdue_maintenance', maintenance, f'Maintenance {maintenance.maintenance_id} is overdue or in progress.', recipient=maintenance.assigned_mechanic_id)

        for driver in driver_model.search([]):
            if driver.license_expiry and driver.license_expiry <= today + timedelta(days=30):
                self.notify_once('driver_license_expiry', driver, f'Driver license for {driver.name} is expiring soon.', recipient=driver.create_uid)

        for vehicle in vehicle_model.search([]):
            if vehicle.registration_expiry and vehicle.registration_expiry <= today + timedelta(days=30):
                self.notify_once('vehicle_registration_expiry', vehicle, f'Vehicle registration for {vehicle.vehicle_number} is expiring soon.', recipient=vehicle.create_uid)
            if vehicle.insurance_expiry and vehicle.insurance_expiry <= today + timedelta(days=30):
                self.notify_once('vehicle_insurance_expiry', vehicle, f'Vehicle insurance for {vehicle.vehicle_number} is expiring soon.', recipient=vehicle.create_uid)

        for trip in trip_model.search([('current_status', 'in', ('in_progress', 'completed', 'cancelled'))]):
            if trip.current_status == 'in_progress':
                self.notify_once('trip_dispatch', trip, f'Trip {trip.trip_id} has been dispatched.', recipient=trip.create_uid)
            elif trip.current_status == 'completed':
                self.notify_once('trip_completion', trip, f'Trip {trip.trip_id} has been completed.', recipient=trip.create_uid)
            elif trip.current_status == 'cancelled':
                self.notify_once('trip_cancellation', trip, f'Trip {trip.trip_id} has been cancelled.', recipient=trip.create_uid)

        for incident in incident_model.search([('status', 'in', ('reported', 'resolved'))]):
            if incident.status == 'reported':
                self.notify_once('incident_reported', incident, f'Incident {incident.incident_number} has been reported.', recipient=incident.reporter_id)
            elif incident.status == 'resolved':
                self.notify_once('incident_resolved', incident, f'Incident {incident.incident_number} has been resolved.', recipient=incident.reporter_id)
