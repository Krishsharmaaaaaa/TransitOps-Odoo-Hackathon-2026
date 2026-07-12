/** @odoo-module **/

import { Component, onMounted, onWillUnmount, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS, loadCSS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

class TransitOpsLiveTrackingMap extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.mapRef = useRef("map");
        this.state = useState({ vehicles: [], loaded: false });
        this.map = null;
        this.markers = [];
        this.refreshTimer = null;

        onWillStart(async () => {
            await loadCSS(LEAFLET_CSS);
            await loadJS(LEAFLET_JS);
        });

        onMounted(() => {
            this._initializeMap();
            this._loadVehicles();
            this.refreshTimer = setInterval(() => this._loadVehicles(), 20000);
        });

        onWillUnmount(() => {
            if (this.refreshTimer) {
                clearInterval(this.refreshTimer);
            }
            if (this.map) {
                this.map.remove();
            }
        });
    }

    _initializeMap() {
        this.map = window.L.map(this.mapRef.el, { zoomControl: true }).setView([0, 0], 2);
        window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(this.map);
    }

    _markerColor(vehicle) {
        if (vehicle.availability === "maintenance") {
            return "#d97706";
        }
        if (vehicle.availability === "on_trip") {
            return "#2563eb";
        }
        return "#16a34a";
    }

    _buildMarkerIcon(color) {
        return window.L.divIcon({
            className: "transitops-live-marker",
            html: `<span style="background:${color}"></span>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10],
        });
    }

    async _loadVehicles() {
        const result = await this.rpc("/transitops/api/live_tracking/vehicles", {});
        this.state.vehicles = result.vehicles || [];
        this._renderMarkers();
        this.state.loaded = true;
    }

    _renderMarkers() {
        for (const marker of this.markers) {
            this.map.removeLayer(marker);
        }
        this.markers = [];

        const vehicles = this.state.vehicles.filter((vehicle) => vehicle.latitude !== false && vehicle.latitude !== null && vehicle.longitude !== false && vehicle.longitude !== null);
        if (!vehicles.length) {
            return;
        }

        const bounds = [];
        for (const vehicle of vehicles) {
            const latLng = [vehicle.latitude, vehicle.longitude];
            bounds.push(latLng);
            const popup = `
                <div class="transitops-live-popup">
                    <strong>${vehicle.vehicle_number}</strong><br/>
                    <span>Status: ${vehicle.availability}</span><br/>
                    <span>Maintenance: ${vehicle.maintenance_status}</span><br/>
                    <span>Speed: ${vehicle.speed || 0} km/h</span><br/>
                    <span>Heading: ${vehicle.heading || 0}°</span><br/>
                    <span>Updated: ${vehicle.last_updated || 'N/A'}</span><br/>
                    ${vehicle.trip ? `<hr/><span>Trip: ${vehicle.trip.trip_id}</span><br/><span>${vehicle.trip.trip_name || ''}</span><br/><span>${vehicle.trip.route_name || ''}</span><br/><span>${vehicle.trip.driver_name || ''}</span>` : ''}
                </div>
            `;
            const marker = window.L.marker(latLng, { icon: this._buildMarkerIcon(this._markerColor(vehicle)) })
                .addTo(this.map)
                .bindPopup(popup);
            this.markers.push(marker);
        }

        this.map.fitBounds(bounds, { padding: [40, 40] });
    }
}

TransitOpsLiveTrackingMap.template = "transitops_core.LiveTrackingMap";

registry.category("actions").add("transitops_live_tracking_map", TransitOpsLiveTrackingMap);