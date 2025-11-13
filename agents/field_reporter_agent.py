import asyncio, os, json, uuid, random
from datetime import datetime, timezone
from jsonschema import validate, ValidationError
from .base_agent import BaseAgent
from crewai_client import CrewAIClient

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "field_reporter.txt")
SCHEMA_PATH = os.path.join(BASE_DIR, "schemas", "incident.schema.json")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    FIELD_REPORTER_PROMPT = f.read()
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    INCIDENT_SCHEMA = json.load(f)


class FieldReporterAgent(BaseAgent):
    """Ingests ranger/citizen/camera reports and emits normalized wildlife incidents."""

    def __init__(self, name: str, broker, manual_mode: bool = False, event_interval: int = 5):
        super().__init__(name, broker)
        self.crewai = CrewAIClient()
        self.manual_mode = manual_mode
        self.event_interval = event_interval

    async def _emit_synthetic_report(self) -> dict:
        # Minimal synthetic wildlife report for demo
        species = random.choice(["elephant", "deer", "monkey"]) 
        lat = 6.90 + random.random() * 0.1
        lon = 79.85 + random.random() * 0.1
        raw = {
            "text": f"{species.capitalize()} observed limping near riverbank.",
            "gps": {"lat": lat, "lon": lon},
            "reporter": {"type": "ranger", "reliability": round(random.uniform(0.6, 0.95), 2)}
        }
        return raw

    async def sensor_loop(self):
        while True:
            await asyncio.sleep(self.event_interval)
            raw_report = await self._emit_synthetic_report()
            context = {"report": raw_report}

            res = await self.crewai.run_agent("FieldReporter", FIELD_REPORTER_PROMPT, context)
            # Validate and sanitize
            try:
                validate(instance=res, schema=INCIDENT_SCHEMA)
                incident = res
                # Ensure id exists
                if not incident.get("id"):
                    incident["id"] = str(uuid.uuid4())
            except ValidationError as e:
                print(f"[FieldReporter] Schema error: {e.message}. Using fallback.")
                incident = {
                    "id": str(uuid.uuid4()),
                    "species": "unknown",
                    "gps": raw_report.get("gps", {"lat": 0.0, "lon": 0.0}),
                    "observed_behavior": "unknown",
                    "injury_severity": "low",
                    "reporter_reliability": raw_report.get("reporter", {}).get("reliability", 0.5),
                    "access_difficulty": "open",
                    "priority": 2
                }

            # Annotate timestamp for logs (not part of schema requirement)
            incident_ts = {**incident, "timestamp": datetime.now(timezone.utc).isoformat()}

            # Send to coordinator and triage
            await self.send("CoordinatorAgent", "advertise_incident", {"incident": incident_ts})
            await self.send("TriageAgent", "inform", {"incident": incident_ts})
            # Log
            await self.send("BlackboardAgent", "log", {"advertise_incident": incident_ts})

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        # Only start sensor_loop if not in manual mode
        if not self.manual_mode:
            asyncio.create_task(self.sensor_loop())
        while True:
            # FieldReporter is primarily producer; can handle direct inform if needed
            msg = await self.receive()
            if msg.get("performative") == "inform" and "report" in msg.get("content", {}):
                try:
                    raw_report = msg["content"]["report"]
                    print(f"[FieldReporterAgent] Processing report: {raw_report.get('text', '')[:50]}...")
                    res = await self.crewai.run_agent("FieldReporter", FIELD_REPORTER_PROMPT, {"report": raw_report})
                    print(f"[FieldReporterAgent] LLM response type: {type(res)}, keys: {res.keys() if isinstance(res, dict) else 'N/A'}")
                    try:
                        validate(instance=res, schema=INCIDENT_SCHEMA)
                        if not res.get("id"): res["id"] = str(uuid.uuid4())
                        print(f"[FieldReporterAgent] ✓ Schema validation passed")
                    except ValidationError as e:
                        print(f"[FieldReporterAgent] Schema validation failed: {e.message}")
                        res = {"id": str(uuid.uuid4()), "species": "unknown", "gps": raw_report.get("gps", {"lat":0,"lon":0}), "observed_behavior": "unknown", "injury_severity": "low", "reporter_reliability": 0.5, "access_difficulty": "open", "priority": 2}
                    
                    # Annotate timestamp for logs (not part of schema requirement)
                    print(f"[FieldReporterAgent] Creating incident with timestamp...")
                    incident_ts = {**res, "timestamp": datetime.now(timezone.utc).isoformat()}
                    print(f"[FieldReporterAgent] Incident created: {incident_ts.get('id')}")
                    
                    print(f"[FieldReporterAgent] Sending advertise_incident to CoordinatorAgent...")
                    await self.send("CoordinatorAgent", "advertise_incident", {"incident": incident_ts})
                    print(f"[FieldReporterAgent] → Sent to CoordinatorAgent")
                    
                    await self.send("TriageAgent", "inform", {"incident": incident_ts})
                    print(f"[FieldReporterAgent] → Sent to TriageAgent")
                    
                    await self.send("BlackboardAgent", "log", {"advertise_incident": incident_ts})
                    print(f"[FieldReporterAgent] → Sent to BlackboardAgent")
                except Exception as e:
                    print(f"[FieldReporterAgent] ✗ ERROR processing report: {e}")
                    import traceback
                    traceback.print_exc()
