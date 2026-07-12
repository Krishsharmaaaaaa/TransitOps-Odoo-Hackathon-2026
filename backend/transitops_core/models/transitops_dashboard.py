from datetime import date

from odoo import api, fields, models


class TransitOpsDashboard(models.Model):
    _name = 'transitops.dashboard'
    _description = 'TransitOps Executive Dashboard'
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(required=True, default='Executive Dashboard')
    active = fields.Boolean(default=True)
    metric_line_ids = fields.One2many('transitops.dashboard.metric', 'dashboard_id', string='Metric Lines')
    last_refreshed_on = fields.Datetime(string='Last Refreshed On', readonly=True)

    total_vehicles = fields.Integer(compute='_compute_kpis', string='Total Vehicles')
    available_vehicles = fields.Integer(compute='_compute_kpis', string='Available Vehicles')
    vehicles_on_trip = fields.Integer(compute='_compute_kpis', string='Vehicles On Trip')
    vehicles_under_maintenance = fields.Integer(compute='_compute_kpis', string='Vehicles Under Maintenance')

    total_drivers = fields.Integer(compute='_compute_kpis', string='Total Drivers')
    available_drivers = fields.Integer(compute='_compute_kpis', string='Available Drivers')
    drivers_on_trip = fields.Integer(compute='_compute_kpis', string='Drivers On Trip')

    active_trips = fields.Integer(compute='_compute_kpis', string='Active Trips')
    completed_trips = fields.Integer(compute='_compute_kpis', string='Completed Trips')
    cancelled_trips = fields.Integer(compute='_compute_kpis', string='Cancelled Trips')

    open_incidents = fields.Integer(compute='_compute_kpis', string='Open Incidents')
    resolved_incidents = fields.Integer(compute='_compute_kpis', string='Resolved Incidents')

    scheduled_maintenance = fields.Integer(compute='_compute_kpis', string='Scheduled Maintenance')
    in_progress_maintenance = fields.Integer(compute='_compute_kpis', string='In Progress Maintenance')
    completed_maintenance = fields.Integer(compute='_compute_kpis', string='Completed Maintenance')

    @api.model
    def _get_dashboard_metrics_payload(self):
        vehicle_groups = self.env['transitops.fleet.vehicle'].read_group([], ['availability'], ['availability'])
        driver_groups = self.env['transitops.driver'].read_group([], ['availability'], ['availability'])
        trip_groups = self.env['transitops.trip'].read_group([], ['current_status'], ['current_status'])
        incident_groups = self.env['transitops.incident'].read_group([], ['status'], ['status'])
        maintenance_groups = self.env['transitops.maintenance'].read_group([], ['status'], ['status'])

        vehicle_counts = {group['availability']: group['__count'] for group in vehicle_groups}
        driver_counts = {group['availability']: group['__count'] for group in driver_groups}
        trip_counts = {group['current_status']: group['__count'] for group in trip_groups}
        incident_counts = {group['status']: group['__count'] for group in incident_groups}
        maintenance_counts = {group['status']: group['__count'] for group in maintenance_groups}

        active_trip_count = sum(trip_counts.get(status, 0) for status in ('scheduled', 'in_progress', 'delayed'))
        open_incident_count = sum(incident_counts.get(status, 0) for status in ('draft', 'reported', 'investigating'))

        return {
            'fleet': {
                'total_vehicles': sum(vehicle_counts.values()),
                'available_vehicles': vehicle_counts.get('available', 0),
                'vehicles_on_trip': vehicle_counts.get('on_trip', 0),
                'vehicles_under_maintenance': vehicle_counts.get('maintenance', 0),
            },
            'drivers': {
                'total_drivers': sum(driver_counts.values()),
                'available_drivers': driver_counts.get('available', 0),
                'drivers_on_trip': driver_counts.get('on_trip', 0),
            },
            'trips': {
                'active_trips': active_trip_count,
                'completed_trips': trip_counts.get('completed', 0),
                'cancelled_trips': trip_counts.get('cancelled', 0),
            },
            'incidents': {
                'open_incidents': open_incident_count,
                'resolved_incidents': incident_counts.get('resolved', 0),
            },
            'maintenance': {
                'scheduled_maintenance': maintenance_counts.get('scheduled', 0),
                'in_progress_maintenance': maintenance_counts.get('in_progress', 0),
                'completed_maintenance': maintenance_counts.get('completed', 0),
            },
            'metric_lines': [
                ('fleet', 'Total Vehicles', sum(vehicle_counts.values())),
                ('fleet', 'Available Vehicles', vehicle_counts.get('available', 0)),
                ('fleet', 'Vehicles On Trip', vehicle_counts.get('on_trip', 0)),
                ('fleet', 'Vehicles Under Maintenance', vehicle_counts.get('maintenance', 0)),
                ('drivers', 'Total Drivers', sum(driver_counts.values())),
                ('drivers', 'Available Drivers', driver_counts.get('available', 0)),
                ('drivers', 'Drivers On Trip', driver_counts.get('on_trip', 0)),
                ('trips', 'Active Trips', active_trip_count),
                ('trips', 'Completed Trips', trip_counts.get('completed', 0)),
                ('trips', 'Cancelled Trips', trip_counts.get('cancelled', 0)),
                ('incidents', 'Open Incidents', open_incident_count),
                ('incidents', 'Resolved Incidents', incident_counts.get('resolved', 0)),
                ('maintenance', 'Scheduled Maintenance', maintenance_counts.get('scheduled', 0)),
                ('maintenance', 'In Progress Maintenance', maintenance_counts.get('in_progress', 0)),
                ('maintenance', 'Completed Maintenance', maintenance_counts.get('completed', 0)),
            ],
        }

    @api.depends_context('uid')
    def _compute_kpis(self):
        payload = self._get_dashboard_metrics_payload()
        for record in self:
            record.total_vehicles = payload['fleet']['total_vehicles']
            record.available_vehicles = payload['fleet']['available_vehicles']
            record.vehicles_on_trip = payload['fleet']['vehicles_on_trip']
            record.vehicles_under_maintenance = payload['fleet']['vehicles_under_maintenance']
            record.total_drivers = payload['drivers']['total_drivers']
            record.available_drivers = payload['drivers']['available_drivers']
            record.drivers_on_trip = payload['drivers']['drivers_on_trip']
            record.active_trips = payload['trips']['active_trips']
            record.completed_trips = payload['trips']['completed_trips']
            record.cancelled_trips = payload['trips']['cancelled_trips']
            record.open_incidents = payload['incidents']['open_incidents']
            record.resolved_incidents = payload['incidents']['resolved_incidents']
            record.scheduled_maintenance = payload['maintenance']['scheduled_maintenance']
            record.in_progress_maintenance = payload['maintenance']['in_progress_maintenance']
            record.completed_maintenance = payload['maintenance']['completed_maintenance']

    def action_refresh_dashboard(self):
        self.ensure_one()
        payload = self._get_dashboard_metrics_payload()
        self.metric_line_ids.unlink()
        self.env['transitops.dashboard.metric'].create([
            {
                'dashboard_id': self.id,
                'metric_group': group,
                'metric_name': name,
                'metric_value': value,
                'metric_key': f'{group}:{name}',
            }
            for group, name, value in payload['metric_lines']
        ])
        self.write({'last_refreshed_on': fields.Datetime.now()})
        return self._open_dashboard()

    def _open_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Executive Dashboard',
            'res_model': 'transitops.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_metric_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard Metrics',
            'res_model': 'transitops.dashboard.metric',
            'view_mode': 'tree,kanban,form',
            'domain': [('dashboard_id', '=', self.id)],
            'context': {'default_dashboard_id': self.id},
        }

    def action_open_metric_graph(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard Metrics Graph',
            'res_model': 'transitops.dashboard.metric',
            'view_mode': 'graph',
            'domain': [('dashboard_id', '=', self.id)],
            'context': {'default_dashboard_id': self.id},
        }

    def action_open_metric_pivot(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard Metrics Pivot',
            'res_model': 'transitops.dashboard.metric',
            'view_mode': 'pivot',
            'domain': [('dashboard_id', '=', self.id)],
            'context': {'default_dashboard_id': self.id},
        }