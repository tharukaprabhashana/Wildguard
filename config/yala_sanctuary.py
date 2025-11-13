"""
Yala National Park Configuration
Real locations of ranger stations, wildlife corridors, and terrain data
for Sri Lankan wildlife rescue operations.
"""

# ============================================================
# 🗺️ Yala National Park Geospatial Data (Updated & Formatted)
# ============================================================

# Park Boundary — Block 1 (Main Tourist Area)
YALA_BOUNDARY = {
    "name": "Yala National Park – Block 1",
    "min_lat": 6.250000,   # Approximate southern boundary
    "max_lat": 6.450000,   # Approximate northern boundary
    "min_lon": 81.300000,  # Approximate western boundary
    "max_lon": 81.700000,  # Approximate eastern boundary
    "center": {"lat": 6.372000, "lon": 81.517000}  # ✅ Verified central coordinate
}

# ============================================================
# 🚨 Ranger Stations — with best-available coordinates
# ============================================================

RANGER_STATIONS = {
    "Palatupana": {
        "lat": 6.281451,  # ✅ Verified via Google Maps (Main Gate)
        "lon": 81.412595,
        "vehicles": ["4x4_Ambulance", "Patrol_Jeep_1"],
        "staff_count": 8,
        "equipment": ["tranquilizer_kit", "first_aid", "radio", "GPS"],
        "description": "Main entrance – Block 1; closest to Yala beach area."
    },
    "Katagamuwa": {
        "lat": 6.395370,  # ⚠️ Approx. via Kataragama–Situlpawwa Road entrance
        "lon": 81.335650,
        "vehicles": ["4x4_Patrol", "Motorcycle"],
        "staff_count": 5,
        "equipment": ["tranquilizer_kit", "radio", "GPS"],
        "description": "Western entry point via Kataragama road. Requires GPS field verification."
    },
    "Yala_HQ": {
        "lat": 6.370000,  # ⚠️ Approx. (HQ not public)
        "lon": 81.520000,
        "vehicles": ["Command_Vehicle", "Vet_Mobile_Unit", "Rescue_Truck"],
        "staff_count": 15,
        "equipment": [
            "full_medical", "tranquilizer_kit", "capture_nets",
            "radio", "GPS", "drone"
        ],
        "description": "Central headquarters inside Block 1. (Unverified coordinate)"
    },
    "Galge": {
        "lat": 6.442565,
        "lon": 81.572456,
        "vehicles": ["4x4_Patrol", "Rescue_Jeep"],
        "staff_count": 6,
        "equipment": ["tranquilizer_kit", "first_aid", "radio"],
        "description": "Eastern sector post near Galge entrance. Monitors elephant corridors."
    },
    "Buttawa": {
        "lat": 6.388000,  # ⚠️ Approximate (Buttawa Tank vicinity)
        "lon": 81.505000,
        "vehicles": ["Patrol_Jeep_2"],
        "staff_count": 4,
        "equipment": ["radio", "GPS", "first_aid"],
        "description": "Interior patrol post in leopard territory. (Approximate coordinate)"
    }
}

# ============================================================
# 🐾 Wildlife Hotspots — approximate centroids
# ============================================================

WILDLIFE_HOTSPOTS = {
    "Elephant_Gathering": {
        "lat": 6.350000,
        "lon": 81.520000,
        "radius_km": 3.0,
        "common_species": ["elephant", "wild_buffalo"],
        "description": "Main elephant gathering area near watering holes."
    },
    "Leopard_Rock": {
        "lat": 6.400000,
        "lon": 81.480000,
        "radius_km": 2.5,
        "common_species": ["leopard", "deer"],
        "description": "Rocky outcrops – highest leopard density in the park."
    },
    "Menik_River_Corridor": {
        "lat": 6.421754,
        "lon": 81.597519,
        "radius_km": 4.0,
        "common_species": ["elephant", "crocodile", "water_buffalo", "deer"],
        "description": "Menik River corridor – key access and watering area."
    },
    "Grassland_Plains": {
        "lat": 6.360000,
        "lon": 81.540000,
        "radius_km": 3.5,
        "common_species": ["deer", "wild_boar", "peacock"],
        "description": "Open grasslands (e.g., Pelessa plains) with good visibility."
    },
    "Coastal_Strip": {
        "lat": 6.319393,  
        "lon": 81.471863,
        "radius_km": 2.0,
        "common_species": ["elephant", "sloth_bear"],
        "description": "Coastal zone where animals cool off near the sea."
    }
}

# Terrain characteristics
TERRAIN_TYPES = {
    "forest_dense": {
        "speed_multiplier": 0.3,
        "description": "Dense forest with limited vehicle access",
        "common_areas": ["northern sections"]
    },
    "scrubland": {
        "speed_multiplier": 0.7,
        "description": "Mixed scrub and small trees",
        "common_areas": ["central park"]
    },
    "grassland": {
        "speed_multiplier": 1.0,
        "description": "Open plains with good visibility",
        "common_areas": ["eastern plains"]
    },
    "wetland": {
        "speed_multiplier": 0.2,
        "description": "Marshy areas near rivers and lagoons",
        "common_areas": ["river corridors"]
    },
    "road": {
        "speed_multiplier": 1.5,
        "description": "Main safari tracks",
        "common_areas": ["tourist routes"]
    }
}

# Vehicle specifications
VEHICLE_SPECS = {
    "4x4_Ambulance": {
        "max_speed_kmh": 60,
        "capacity": 4,
        "equipment": ["stretcher", "medical_kit", "oxygen"],
        "best_for": ["critical_injuries", "transport"]
    },
    "4x4_Patrol": {
        "max_speed_kmh": 70,
        "capacity": 6,
        "equipment": ["tranquilizer_gun", "GPS", "radio"],
        "best_for": ["general_response", "tracking"]
    },
    "Patrol_Jeep_1": {
        "max_speed_kmh": 65,
        "capacity": 5,
        "equipment": ["first_aid", "radio"],
        "best_for": ["patrol", "investigation"]
    },
    "Patrol_Jeep_2": {
        "max_speed_kmh": 65,
        "capacity": 5,
        "equipment": ["first_aid", "radio"],
        "best_for": ["patrol", "investigation"]
    },
    "Vet_Mobile_Unit": {
        "max_speed_kmh": 50,
        "capacity": 3,
        "equipment": ["full_veterinary", "surgery_kit", "medications"],
        "best_for": ["medical_treatment", "surgery"]
    },
    "Command_Vehicle": {
        "max_speed_kmh": 55,
        "capacity": 8,
        "equipment": ["communications", "command_center", "drone"],
        "best_for": ["coordination", "major_incidents"]
    },
    "Motorcycle": {
        "max_speed_kmh": 80,
        "capacity": 2,
        "equipment": ["radio", "first_aid"],
        "best_for": ["rapid_response", "reconnaissance"]
    },
    "Rescue_Jeep": {
        "max_speed_kmh": 60,
        "capacity": 5,
        "equipment": ["capture_equipment", "nets", "ropes"],
        "best_for": ["animal_capture", "relocation"]
    },
    "Rescue_Truck": {
        "max_speed_kmh": 45,
        "capacity": 8,
        "equipment": ["heavy_equipment", "cages", "lifting_gear"],
        "best_for": ["large_animals", "elephant_rescue"]
    }
}

# Species commonly found in Yala
YALA_SPECIES = {
    "elephant": {
        "scientific_name": "Elephas maximus maximus",
        "population": "~300-350",
        "threat_level": "Endangered",
        "common_injuries": ["gunshot", "snare_wounds", "vehicle_collision", "human_conflict"]
    },
    "leopard": {
        "scientific_name": "Panthera pardus kotiya",
        "population": "~40-50 (highest density globally)",
        "threat_level": "Endangered",
        "common_injuries": ["snare_wounds", "territorial_fights", "poaching"]
    },
    "sloth_bear": {
        "scientific_name": "Melursus ursinus",
        "population": "~50-80",
        "threat_level": "Vulnerable",
        "common_injuries": ["human_conflict", "snare_wounds"]
    },
    "deer": {
        "scientific_name": "Axis axis ceylonensis",
        "population": "~5000+",
        "threat_level": "Least Concern",
        "common_injuries": ["predator_attack", "disease"]
    },
    "wild_boar": {
        "scientific_name": "Sus scrofa",
        "population": "~2000+",
        "threat_level": "Least Concern",
        "common_injuries": ["predator_attack", "snare_wounds"]
    },
    "crocodile": {
        "scientific_name": "Crocodylus palustris",
        "population": "~200+",
        "threat_level": "Vulnerable",
        "common_injuries": ["fishing_net", "human_conflict"]
    }
}


# Default terrain based on rough location within park
def get_terrain_type(lat, lon):
    """Estimate terrain type based on coordinates within Yala."""
    # Simplified terrain detection based on location
    if lon < 81.45:
        return "forest_dense"
    elif lat > 6.40:
        return "scrubland"
    elif lat < 6.30:
        return "grassland"
    elif 81.50 < lon < 81.57:
        return "wetland"
    else:
        return "scrubland"  # default

def get_base_speed_kmh():
    """Average vehicle speed in Yala terrain."""
    return 40  # km/h base speed for 4x4 in mixed terrain

def get_location_name(lat, lon):
    """
    Determine human-readable location name based on GPS coordinates.
    Returns nearest wildlife hotspot or station name.
    """
    import math
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Simple distance calculation."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    # Check wildlife hotspots first (more interesting names)
    nearest_hotspot = None
    min_distance = float('inf')
    
    for hotspot_name, hotspot_data in WILDLIFE_HOTSPOTS.items():
        distance = calculate_distance(lat, lon, hotspot_data["lat"], hotspot_data["lon"])
        if distance < min_distance:
            min_distance = distance
            nearest_hotspot = hotspot_name
    
    # If within hotspot radius, use that name
    if nearest_hotspot and min_distance <= WILDLIFE_HOTSPOTS[nearest_hotspot]["radius_km"]:
        return nearest_hotspot.replace("_", " ")
    
    # Otherwise check stations
    nearest_station = None
    min_station_distance = float('inf')
    
    for station_name, station_data in RANGER_STATIONS.items():
        distance = calculate_distance(lat, lon, station_data["lat"], station_data["lon"])
        if distance < min_station_distance:
            min_station_distance = distance
            nearest_station = station_name
    
    # Use "near [station]" format
    if nearest_station:
        return f"near {nearest_station}"
    
    return "Yala Block 1"  # default
