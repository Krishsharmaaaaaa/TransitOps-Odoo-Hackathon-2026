from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TransitOpsIncident(models.Model):
    _name = 'transitops.incident'
    _description = 'TransitOps Incident'
    _rec_name = 'incident_number'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    incident_number = fields.Char(string='Incident Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)
    title = fields.Char(string='Incident Title', required=True, tracking=True)
    vehicle_id = fields.Many2one('transitops.fleet.vehicle', string='Vehicle', tracking=True, ondelete='restrict')
    driver_id = fields.Many2one('transitops.driver', string='Driver', tracking=True, ondelete='restrict')
    trip_id = fields.Many2one('transitops.trip', string='Trip', tracking=True, ondelete='restrict')
    reporter_id = fields.Many2one('res.users', string='Reporter', required=True, default=lambda self: self.env.user, tracking=True, ondelete='restrict')
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now, tracking=True)
    severity = fields.Selection(
        selection=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        required=True,
        default='low',
        tracking=True,
    )
    category = fields.Selection(
        selection=[
            ('breakdown', 'Breakdown'),
            ('accident', 'Accident'),
            ('delay', 'Delay'),
            ('traffic', 'Traffic'),
            ('fuel_issue', 'Fuel Issue'),
            ('driver_issue', 'Driver Issue'),
            ('other', 'Other'),
        ],
        required=True,
        default='other',
        tracking=True,
    )
    description = fields.Text(required=True, tracking=True)
    root_cause = fields.Text(tracking=True)
    resolution = fields.Text(tracking=True)
    cost = fields.Float(required=True, default=0.0, tracking=True)
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('reported', 'Reported'),
            ('investigating', 'Investigating'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
        ],
        required=True,
        default='draft',
        tracking=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('incident_number_uniq', 'unique(incident_number)', 'Incident Number must be unique.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('incident_number', _('New')) == _('New'):
                vals['incident_number'] = self.env['ir.sequence'].next_by_code('transitops.incident') or _('New')
        return super().create(vals_list)

    @api.constrains('incident_number', 'title', 'cost', 'vehicle_id', 'driver_id', 'trip_id', 'date')
    def _check_incident_values(self):
        for record in self:
            if not record.incident_number.strip():
                raise ValidationError('Incident Number is required.')
            if not record.title.strip():
                raise ValidationError('Incident Title is required.')
            if record.cost < 0:
                raise ValidationError('Cost cannot be negative.')
            if record.trip_id and record.vehicle_id and record.trip_id.assigned_vehicle_id != record.vehicle_id:
                raise ValidationError('Vehicle must match the selected trip.')
            if record.trip_id and record.driver_id and record.trip_id.assigned_driver_id != record.driver_id:
                raise ValidationError('Driver must match the selected trip.')

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.trip_id:
            self.vehicle_id = self.trip_id.assigned_vehicle_id
            self.driver_id = self.trip_id.assigned_driver_id

    def action_reported(self):
        self.write({'status': 'reported'})
        for record in self:
            record.env['transitops.notification'].notify_once(
                'incident_reported',
                record,
                f'Incident {record.incident_number} has been reported.',
                recipient=record.reporter_id,
            )

    def action_investigating(self):
        self.write({'status': 'investigating'})

    def action_resolved(self):
        self.write({'status': 'resolved'})
        for record in self:
            record.env['transitops.notification'].notify_once(
                'incident_resolved',
                record,
                f'Incident {record.incident_number} has been resolved.',
                recipient=record.reporter_id,
            )

    def action_closed(self):
        self.write({'status': 'closed', 'active': False})

    def action_set_draft(self):
        self.write({'status': 'draft', 'active': True})

    def _message_auto_subscribe_followers(self, updated_values, followers=None):
        return super()._message_auto_subscribe_followers(updated_values, followers=followers)
