import os
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class GoogleMapsService:
    """Service for location geocoding (using Nominatim - free, no API key needed)"""
    
    def __init__(self):
        # Use Nominatim (OpenStreetMap) - free and no API key required
        self.geocoding_url = "https://nominatim.openstreetmap.org/search"
        self.reverse_url = "https://nominatim.openstreetmap.org/reverse"
        self.headers = {
            'User-Agent': 'SmartDisasterMAS/1.0'  # Required by Nominatim
        }
    
    def geocode_address(self, address: str) -> Optional[Dict]:
        """Convert address to lat/lon coordinates using Nominatim"""
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        
        try:
            response = requests.get(
                self.geocoding_url, 
                params=params, 
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data:
                result = data[0]
                return {
                    "lat": float(result["lat"]),
                    "lon": float(result["lon"]),
                    "formatted_address": result.get("display_name", ""),
                    "place_id": result.get("place_id"),
                    "address_components": []
                }
            else:
                print(f"Geocoding failed: No results found")
                return None
                
        except Exception as e:
            print(f"Error geocoding address: {e}")
            return None
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """Convert lat/lon to address using Nominatim"""
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        
        try:
            response = requests.get(
                self.reverse_url, 
                params=params, 
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data:
                return {
                    "formatted_address": data.get("display_name", ""),
                    "place_id": data.get("place_id"),
                    "address_components": []
                }
            else:
                return None
                
        except Exception as e:
            print(f"Error reverse geocoding: {e}")
            return None
    
    def search_places(self, query: str, location: Optional[Dict] = None) -> List[Dict]:
        """Search for places by text query using Nominatim"""
        params = {
            "q": query,
            "format": "json",
            "limit": 10,
            "addressdetails": 1
        }
        
        # Add viewbox if location provided (bias results to area)
        if location:
            # Create a bounding box around the location (roughly 50km)
            delta = 0.5  # ~50km
            lat, lon = location['lat'], location['lon']
            params["viewbox"] = f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}"
            params["bounded"] = 1
        
        try:
            response = requests.get(
                self.geocoding_url, 
                params=params, 
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    "name": place.get("name", place.get("display_name", "").split(",")[0]),
                    "formatted_address": place.get("display_name", ""),
                    "lat": float(place["lat"]),
                    "lon": float(place["lon"]),
                    "place_id": place.get("place_id")
                }
                for place in data
            ]
                
        except Exception as e:
            print(f"Error searching places: {e}")
            return []