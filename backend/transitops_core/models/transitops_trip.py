from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TransitOpsTrip(models.Model):
    _name = 'transitops.trip'
    _description = 'TransitOps Trip'
    _rec_name = 'trip_name'
    _order = 'trip_date desc, start_time desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    trip_id = fields.Char(string='Trip ID', required=True, tracking=True)
    trip_name = fields.Char(string='Trip Name', required=True, tracking=True)
    route_id = fields.Many2one(
        comodel_name='transitops.route',
        string='Route',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    assigned_vehicle_id = fields.Many2one(
        comodel_name='transitops.fleet.vehicle',
        string='Assigned Vehicle',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    assigned_driver_id = fields.Many2one(
        comodel_name='transitops.driver',
        string='Assigned Driver',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    latitude = fields.Float(related='assigned_vehicle_id.latitude', store=True, readonly=True)
    longitude = fields.Float(related='assigned_vehicle_id.longitude', store=True, readonly=True)
    live_speed = fields.Float(related='assigned_vehicle_id.live_speed', store=True, readonly=True)
    live_heading = fields.Float(related='assigned_vehicle_id.live_heading', store=True, readonly=True)
    live_last_updated = fields.Datetime(related='assigned_vehicle_id.live_last_updated', store=True, readonly=True)
    trip_date = fields.Date(required=True, tracking=True)
    start_time = fields.Datetime(required=True, tracking=True)
    end_time = fields.Datetime(tracking=True)
    current_stop_id = fields.Many2one(
        comodel_name='transitops.stop',
        string='Current Stop',
        tracking=True,
        ondelete='set null',
    )
    current_status = fields.Selection(
        selection=[
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('delayed', 'Delayed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        default='scheduled',
        tracking=True,
    )
    eta = fields.Datetime(string='ETA', tracking=True)
    distance_covered = fields.Float(required=True, default=0.0, tracking=True)
    total_distance = fields.Float(required=True, tracking=True)
    delay_minutes = fields.Integer(required=True, default=0, tracking=True)
    passenger_count = fields.Integer(required=True, default=0, tracking=True)
    fuel_consumption = fields.Float(required=True, default=0.0, tracking=True)
    trip_notes = fields.Text(tracking=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('trip_id_uniq', 'unique(trip_id)', 'Trip ID must be unique.'),
        ('trip_name_uniq', 'unique(trip_name)', 'Trip Name must be unique.'),
    ]

    @api.constrains(
        'trip_id',
        'trip_name',
        'route_id',
        'assigned_vehicle_id',
        'assigned_driver_id',
        'trip_date',
        'start_time',
        'end_time',
        'current_stop_id',
        'current_status',
        'eta',
        'distance_covered',
        'total_distance',
        'delay_minutes',
        'passenger_count',
        'fuel_consumption',
    )
    def _check_trip_values(self):
        for record in self:
            if not record.trip_id.strip():
                raise ValidationError('Trip ID is required.')
            if not record.trip_name.strip():
                raise ValidationError('Trip Name is required.')
            if record.total_distance <= 0:
                raise ValidationError('Total distance must be greater than zero.')
            if record.distance_covered < 0:
                raise ValidationError('Distance covered cannot be negative.')
            if record.distance_covered > record.total_distance:
                raise ValidationError('Distance covered cannot exceed total distance.')
            if record.delay_minutes < 0:
                raise ValidationError('Delay minutes cannot be negative.')
            if record.passenger_count < 0:
                raise ValidationError('Passenger count cannot be negative.')
            if record.fuel_consumption < 0:
                raise ValidationError('Fuel consumption cannot be negative.')
            if record.end_time and record.end_time < record.start_time:
                raise ValidationError('End time must be after start time.')
            if record.current_stop_id and record.current_stop_id.route_id != record.route_id:
                raise ValidationError('Current stop must belong to the selected route.')
            if record.assigned_vehicle_id not in record.route_id.assigned_vehicle_ids:
                raise ValidationError('Assigned vehicle must be linked to the selected route.')
            if record.assigned_driver_id not in record.route_id.assigned_driver_ids:
                raise ValidationError('Assigned driver must be linked to the selected route.')
            if record.current_status == 'scheduled':
                if record.assigned_vehicle_id.availability == 'on_trip' or record.assigned_driver_id.availability == 'on_trip':
                    raise ValidationError('Scheduled trips cannot use resources that are already on trip.')
            if record.current_status in ('in_progress', 'delayed'):
                if record.assigned_vehicle_id.availability != 'on_trip':
                    raise ValidationError('Trips in progress require the vehicle to be on trip.')
                if record.assigned_driver_id.availability != 'on_trip':
                    raise ValidationError('Trips in progress require the driver to be on trip.')
            if record.current_status == 'completed' and not record.end_time:
                raise ValidationError('Completed trips must have an end time.')
            if record.current_status == 'cancelled' and record.current_stop_id:
                raise ValidationError('Cancelled trips should not have a current stop.')
            if record.current_status == 'completed':
                if record.assigned_vehicle_id.availability == 'on_trip' or record.assigned_driver_id.availability == 'on_trip':
                    raise ValidationError('Completed trips cannot leave resources on trip.')

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id:
            self.assigned_vehicle_id = False
            self.assigned_driver_id = False
            self.current_stop_id = False

    @api.onchange('current_status')
    def _onchange_current_status(self):
        if self.current_status in ('completed', 'cancelled'):
            self.active = False
        else:
            self.active = True
        if self.current_status == 'cancelled':
            self.current_stop_id = False

    def action_dispatch_trip(self):
        for record in self:
            if record.current_status != 'scheduled':
                raise ValidationError('Only scheduled trips can be dispatched.')
            record._validate_dispatch_readiness()
            record._apply_dispatch()

    def action_complete_trip(self):
        for record in self:
            if record.current_status not in ('in_progress', 'delayed'):
                raise ValidationError('Only in progress or delayed trips can be completed.')
            record._apply_completion()

    def action_cancel_trip(self):
        for record in self:
            if record.current_status == 'completed':
                raise ValidationError('Completed trips cannot be cancelled.')
            record._apply_cancellation()

    def _validate_dispatch_readiness(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        vehicle = self.assigned_vehicle_id
        driver = self.assigned_driver_id

        if not vehicle or not driver:
            raise ValidationError('Trip dispatch requires both a vehicle and a driver.')
        if vehicle.availability != 'available':
            raise ValidationError('Selected vehicle must be available.')
        if driver.availability != 'available':
            raise ValidationError('Selected driver must be available.')
        if vehicle.maintenance_status == 'in_service':
            raise ValidationError('Selected vehicle is under maintenance.')
        if driver.license_expiry < today:
            raise ValidationError('Selected driver license is expired.')
        if vehicle.capacity < self.passenger_count:
            raise ValidationError('Selected vehicle capacity is not sufficient for the passenger count.')
        if self.route_id and self.current_stop_id and self.current_stop_id.route_id != self.route_id:
            raise ValidationError('Current stop must belong to the selected route.')

    def _apply_dispatch(self):
        self.ensure_one()
        first_stop = self.route_id.stop_ids.sorted(lambda stop: (stop.stop_sequence, stop.id))[:1]
        self.write({
            'current_status': 'in_progress',
            'current_stop_id': first_stop.id if first_stop else self.current_stop_id.id,
            'active': True,
        })
        self.assigned_vehicle_id.write({
            'availability': 'on_trip',
            'assigned_driver_id': self.assigned_driver_id.id,
        })
        self.assigned_driver_id.write({
            'availability': 'on_trip',
            'assigned_vehicle_id': self.assigned_vehicle_id.id,
        })
        self.env['transitops.notification'].notify_once(
            'trip_dispatch',
            self,
            f'Trip {self.trip_id} has been dispatched.',
            recipient=self.create_uid,
        )

    def _apply_completion(self):
        self.ensure_one()
        completion_time = fields.Datetime.now()
        self.write({
            'current_status': 'completed',
            'end_time': self.end_time or completion_time,
            'current_stop_id': False,
            'active': False,
        })
        self.assigned_vehicle_id.write({
            'availability': 'available',
            'assigned_driver_id': False,
        })
        self.assigned_driver_id.write({
            'availability': 'available',
            'assigned_vehicle_id': False,
        })
        self.env['transitops.notification'].notify_once(
            'trip_completion',
            self,
            f'Trip {self.trip_id} has been completed.',
            recipient=self.create_uid,
        )

    def _apply_cancellation(self):
        self.ensure_one()
        self.write({
            'current_status': 'cancelled',
            'current_stop_id': False,
            'active': False,
        })
        if self.assigned_vehicle_id:
            self.assigned_vehicle_id.write({
                'availability': 'available',
                'assigned_driver_id': False,
            })
        if self.assigned_driver_id:
            self.assigned_driver_id.write({
                'availability': 'available',
                'assigned_vehicle_id': False,
            })
        self.env['transitops.notification'].notify_once(
            'trip_cancellation',
            self,
            f'Trip {self.trip_id} has been cancelled.',
            recipient=self.create_uid,
        )
