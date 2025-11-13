import os, json, time, asyncio
from jsonschema import validate, ValidationError
from .base_agent import BaseAgent
from crewai_client import CrewAIClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.yala_sanctuary import get_location_name

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "coordinator.txt")
SCHEMA_PATH = os.path.join(BASE_DIR, "schemas", "dispatch.schema.json")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    COORD_PROMPT = f.read()
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    DISPATCH_SCHEMA = json.load(f)


class CoordinatorAgent(BaseAgent):
    """
    Proximity-based coordinator for WildGuard.
    Requests availability from ranger stations and dispatches nearest available unit.
    """

    def __init__(self, name: str, broker, station_names=None):
        super().__init__(name, broker)
        self.crewai = CrewAIClient()
        self.station_names = station_names or ["Palatupana", "Katagamuwa", "Yala_HQ", "Galge", "Buttawa"]
        self.triage_by_incident = {}
        # Optional VetAgent trigger after dispatch (set WILDGUARD_VET_TRIGGER=1 to enable)
        self.enable_vet_trigger = os.getenv("WILDGUARD_VET_TRIGGER", "0") in ("1", "true", "True")

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        print(f"[CoordinatorAgent] Registered and waiting for incidents...")
        print(f"[CoordinatorAgent] Monitoring stations: {', '.join(self.station_names)}")
        while True:
            msg = await self.receive()
            pf = msg.get("performative")
            content = msg.get("content", {})
            print(f"[CoordinatorAgent] ← Received '{pf}' from {msg.get('from')}")

            if pf == "advertise_incident" and "incident" in content:
                incident = content["incident"]
                incident_gps = incident.get("gps", {})
                location_name = get_location_name(incident_gps.get("lat", 0), incident_gps.get("lon", 0))
                print(f"[CoordinatorAgent] Processing incident for {incident.get('species', 'unknown')} at {location_name}")
                
                # Request availability from all stations
                for station in self.station_names:
                    await self.send(station, "request_availability", {"incident": incident})
                    print(f"[CoordinatorAgent] → Sent availability request to {station}")
                
                # Collect availability responses for a window
                responses = []
                start = time.time()
                window = 2.0  # 2 seconds to get all responses
                while time.time() - start < window:
                    timeout_left = window - (time.time() - start)
                    try:
                        m = await asyncio.wait_for(self.inbox.get(), timeout=timeout_left)
                        if m.get("performative") == "availability_response":
                            responses.append(m["content"]["response"])
                        elif m.get("performative") == "triage_summary":
                            self.triage_by_incident[incident["id"]] = m["content"]["triage"]
                        else:
                            # non-response messages re-queue
                            await self.inbox.put(m)
                    except asyncio.TimeoutError:
                        break

                if not responses:
                    # no responses -> notify comms and log
                    await self.send("CommunicationAgent", "broadcast", {"message": "No ranger stations responded. Escalating incident."})
                    await self.send("BlackboardAgent", "log", {"no_responses": {"incident_id": incident["id"]}})
                    continue
                
                # Filter only available and capable stations
                available_stations = [r for r in responses if r.get("available") and r.get("capable")]
                
                if not available_stations:
                    # All busy or incapable
                    await self.send("CommunicationAgent", "broadcast", {
                        "message": f"All stations busy or unable to respond to {incident.get('species')} incident. Monitoring situation."
                    })
                    await self.send("BlackboardAgent", "log", {"all_busy": {"incident_id": incident["id"], "responses": responses}})
                    continue
                
                # Select nearest available station (lowest distance)
                available_stations.sort(key=lambda x: x.get("distance_km", 9999))
                selected = available_stations[0]
                
                print(f"[CoordinatorAgent] ✓ Selected {selected['station_name']}: {selected['distance_km']}km, ETA {selected['eta_minutes']}min")
                print(f"[CoordinatorAgent] Reasoning: {selected['reasoning']}")
                
                # Create dispatch order
                dispatch_order = {
                    "incident_id": incident["id"],
                    "station_name": selected["station_name"],
                    "distance_km": selected["distance_km"],
                    "eta_minutes": selected["eta_minutes"],
                    "vehicle": selected["vehicle"],
                    "terrain": selected["terrain"],
                    "reasoning": selected["reasoning"],
                    "all_options": responses  # For transparency
                }
                
                # Send dispatch order to selected station
                await self.send(selected["station_name"], "dispatch_order", dispatch_order)
                
                # Log to blackboard
                await self.send("BlackboardAgent", "log", {"dispatch_order": dispatch_order})
                
                # Inform comms
                await self.send("CommunicationAgent", "inform", {
                    "incident": incident,
                    "dispatch": dispatch_order
                })

                # Optional: trigger VetAgent for treatment decision/logging
                if self.enable_vet_trigger:
                    vet_req = {
                        "incident_id": incident.get("id"),
                        "station_name": selected["station_name"],
                        "location": incident.get("gps") or incident.get("location"),
                        "species": incident.get("species"),
                        "injury_severity": incident.get("injury_severity"),
                        "triage": self.triage_by_incident.get(incident["id"]),
                        "eta_minutes": selected["eta_minutes"]
                    }
                    await self.send("VetAgent", "request_treatment", vet_req)
                    await self.send("BlackboardAgent", "log", {"request_treatment": vet_req})

            elif pf == "triage_summary" and "triage" in content:
                triage = content["triage"]
                self.triage_by_incident[triage["incident_id"]] = triage
                await self.send("BlackboardAgent", "log", {"triage_summary": triage})
            
            elif pf == "dispatch_acknowledged":
                # Station confirmed they're en route
                print(f"[CoordinatorAgent] ✓ {content.get('station_name')} acknowledged dispatch")
                await self.send("BlackboardAgent", "log", {"dispatch_acknowledged": content})
