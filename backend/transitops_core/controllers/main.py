from odoo import fields, http
from odoo.http import request


class TransitOpsLiveTrackingController(http.Controller):

    @http.route('/transitops/api/live_tracking/vehicles', type='json', auth='user')
    def live_tracking_vehicles(self):
        vehicles = request.env['transitops.fleet.vehicle'].sudo().search([('active', '=', True)])
        payload = []
        for vehicle in vehicles:
            trip = request.env['transitops.trip'].sudo().search([
                ('assigned_vehicle_id', '=', vehicle.id),
                ('current_status', 'in', ('scheduled', 'in_progress', 'delayed')),
            ], limit=1, order='trip_date desc, start_time desc, id desc')
            payload.append({
                'id': vehicle.id,
                'vehicle_number': vehicle.vehicle_number,
                'vehicle_type': vehicle.vehicle_type,
                'availability': vehicle.availability,
                'maintenance_status': vehicle.maintenance_status,
                'latitude': vehicle.latitude,
                'longitude': vehicle.longitude,
                'speed': vehicle.live_speed,
                'heading': vehicle.live_heading,
                'last_updated': fields.Datetime.to_string(vehicle.live_last_updated) if vehicle.live_last_updated else False,
                'trip': {
                    'id': trip.id if trip else False,
                    'trip_id': trip.trip_id if trip else False,
                    'trip_name': trip.trip_name if trip else False,
                    'current_status': trip.current_status if trip else False,
                    'route_name': trip.route_id.route_name if trip else False,
                    'driver_name': trip.assigned_driver_id.name if trip else False,
                } if trip else False,
            })
        return {'vehicles': payload}

    @http.route('/transitops/api/live_tracking/update', type='json', auth='user', csrf=False)
    def live_tracking_update(self, vehicle_id, latitude, longitude, speed=0.0, heading=0.0, last_updated=False):
        vehicle = request.env['transitops.fleet.vehicle'].sudo().browse(int(vehicle_id)).exists()
        if not vehicle:
            return {'ok': False, 'error': 'Vehicle not found'}
        vehicle._update_live_tracking(
            vehicle,
            float(latitude),
            float(longitude),
            float(speed or 0.0),
            float(heading or 0.0),
            fields.Datetime.to_datetime(last_updated) if last_updated else False,
        )
        return {'ok': True}