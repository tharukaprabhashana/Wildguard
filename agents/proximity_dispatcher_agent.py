"""
Proximity Dispatcher Agent for Yala National Park
Replaces bidding system with realistic distance-based dispatch
"""

import math
from agents.base_agent import BaseAgent
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.yala_sanctuary import RANGER_STATIONS, TERRAIN_TYPES, VEHICLE_SPECS, get_terrain_type, get_base_speed_kmh


class ProximityDispatcherAgent(BaseAgent):
    """
    Dispatches the nearest available ranger station to incident location.
    Uses real Yala geography and calculates actual travel times.
    """
    
    def __init__(self, name, broker, station_name, station_config):
        super().__init__(name, broker)
        self.station_name = station_name
        self.lat = station_config["lat"]
        self.lon = station_config["lon"]
        self.vehicles = station_config["vehicles"]
        self.equipment = station_config["equipment"]
        self.staff_count = station_config["staff_count"]
        self.description = station_config["description"]
        self.is_busy = False  # Track if station is currently deployed
        self.current_incident = None
        print(f"[{self.name}] Station initialized at {self.station_name}: ({self.lat:.4f}, {self.lon:.4f})")
        print(f"  Vehicles: {', '.join(self.vehicles)}")
        print(f"  Staff: {self.staff_count}, Equipment: {', '.join(self.equipment)}")
    
    def calculate_distance_km(self, lat1, lon1, lat2, lon2):
        """Calculate actual distance using Haversine formula."""
        R = 6371  # Earth radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def estimate_eta_minutes(self, distance_km, terrain_type, vehicle_type):
        """
        Calculate estimated time of arrival based on:
        - Distance
        - Terrain difficulty
        - Vehicle capabilities
        """
        # Get terrain speed multiplier
        terrain_multiplier = TERRAIN_TYPES.get(terrain_type, {}).get("speed_multiplier", 0.7)
        
        # Get vehicle max speed
        vehicle_max_speed = VEHICLE_SPECS.get(vehicle_type, {}).get("max_speed_kmh", 50)
        
        # Effective speed = base speed * terrain multiplier, capped by vehicle max
        base_speed = get_base_speed_kmh()
        effective_speed = min(base_speed * terrain_multiplier, vehicle_max_speed * 0.8)  # 80% of max for safety
        
        # Add prep time (5 minutes to mobilize)
        prep_time = 5
        
        # Calculate travel time
        travel_time = (distance_km / effective_speed) * 60  # convert hours to minutes
        
        return prep_time + travel_time
    
    def assess_capability(self, incident):
        """
        Check if this station can handle the incident based on:
        - Equipment availability
        - Staff capacity
        - Vehicle suitability
        """
        injury_severity = incident.get("injury_severity", "medium")
        species = incident.get("species", "unknown")
        
        # Check if we have required equipment
        required_equipment = set()
        if injury_severity in ["high", "critical"]:
            required_equipment.add("first_aid")
        if species in ["elephant", "leopard", "sloth_bear"]:
            required_equipment.add("tranquilizer_kit")
        
        has_equipment = required_equipment.issubset(set(self.equipment))
        
        # Determine best vehicle for the job
        best_vehicle = self.vehicles[0]  # default to first vehicle
        if injury_severity == "critical" and "4x4_Ambulance" in self.vehicles:
            best_vehicle = "4x4_Ambulance"
        elif species == "elephant" and "Rescue_Truck" in self.vehicles:
            best_vehicle = "Rescue_Truck"
        
        return {
            "capable": has_equipment and not self.is_busy,
            "best_vehicle": best_vehicle,
            "confidence": 0.9 if has_equipment else 0.5
        }
    
    async def run(self):
        """Listen for dispatch requests from coordinator."""
        # Register with broker first
        await self.broker.register(self.name, self.inbox)
        print(f"[{self.name}] Station {self.station_name} ready for dispatch")
        
        while True:
            msg = await self.receive()
            pf = msg.get("performative")
            content = msg.get("content", {})
            
            if pf == "request_availability":
                # Coordinator asking if we can respond
                incident = content.get("incident", {})
                incident_gps = incident.get("gps", {})
                
                print(f"[{self.name}] Availability request for incident {incident.get('id', 'unknown')}")
                
                # Calculate distance and ETA
                distance_km = self.calculate_distance_km(
                    self.lat, self.lon,
                    incident_gps.get("lat", 0), incident_gps.get("lon", 0)
                )
                
                # Determine terrain at incident location
                terrain = get_terrain_type(incident_gps.get("lat", 0), incident_gps.get("lon", 0))
                
                # Assess if we can handle this incident
                capability = self.assess_capability(incident)
                best_vehicle = capability["best_vehicle"]
                
                # Calculate ETA
                eta_minutes = self.estimate_eta_minutes(distance_km, terrain, best_vehicle)
                
                # Send availability response
                response = {
                    "station_name": self.station_name,
                    "distance_km": round(distance_km, 2),
                    "eta_minutes": round(eta_minutes, 1),
                    "terrain": terrain,
                    "vehicle": best_vehicle,
                    "available": not self.is_busy,
                    "capable": capability["capable"],
                    "confidence": capability["confidence"],
                    "staff_available": self.staff_count,
                    "equipment": self.equipment,
                    "reasoning": f"{self.station_name} is {distance_km:.1f}km away via {terrain} terrain. ETA {eta_minutes:.0f} min with {best_vehicle}."
                }
                
                print(f"[{self.name}] Distance: {distance_km:.2f}km, ETA: {eta_minutes:.1f}min, Available: {not self.is_busy}")
                
                await self.send(msg.get("from"), "availability_response", {
                    "incident_id": incident.get("id"),
                    "response": response
                })
            
            elif pf == "dispatch_order":
                # Coordinator has assigned this incident to us
                incident_id = content.get("incident_id")
                print(f"[{self.name}] 🚨 DISPATCHED to incident {incident_id}")
                print(f"  Deploying: {content.get('vehicle', 'unknown vehicle')}")
                print(f"  ETA: {content.get('eta_minutes', 'unknown')} minutes")
                
                self.is_busy = True
                self.current_incident = incident_id
                
                # Send confirmation
                await self.send("BlackboardAgent", "log", {
                    "dispatch": {
                        "station": self.station_name,
                        "incident_id": incident_id,
                        "status": "en_route",
                        "vehicle": content.get("vehicle"),
                        "eta_minutes": content.get("eta_minutes")
                    }
                })
                
                # Acknowledge to coordinator
                await self.send(msg.get("from"), "dispatch_acknowledged", {
                    "station_name": self.station_name,
                    "incident_id": incident_id,
                    "message": f"{self.station_name} team en route. ETA {content.get('eta_minutes', 'unknown')} minutes."
                })
            
            elif pf == "incident_resolved":
                # Incident complete, station available again
                print(f"[{self.name}] Incident {content.get('incident_id')} resolved. Station back in service.")
                self.is_busy = False
                self.current_incident = None
