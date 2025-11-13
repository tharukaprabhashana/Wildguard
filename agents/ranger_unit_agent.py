import os, json
from jsonschema import validate, ValidationError
from .base_agent import BaseAgent
from crewai_client import CrewAIClient

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "ranger_unit.txt")
SCHEMA_PATH = os.path.join(BASE_DIR, "schemas", "bid.schema.json")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    RANGER_PROMPT = f.read()
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    BID_SCHEMA = json.load(f)


class RangerUnitAgent(BaseAgent):
    """Responds to call_for_bids with structured bid proposal and executes awarded contract."""

    def __init__(self, name: str, broker, unit_id: str = None, gear: str = "standard", base_gps=None):
        super().__init__(name, broker)
        self.crewai = CrewAIClient()
        self.unit_id = unit_id or name
        self.gear = gear
        self.base_gps = base_gps or {"lat": 6.92, "lon": 79.88}
        self.status = "idle"

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        print(f"[{self.unit_id}] Registered and ready for missions")
        while True:
            msg = await self.receive()
            pf = msg.get("performative")
            content = msg.get("content", {})

            if pf == "call_for_bids" and "incident" in content:
                inc = content["incident"]
                context = {
                    "incident": inc,
                    "unit": {"unit_id": self.unit_id, "gear": self.gear, "base_gps": self.base_gps}
                }
                res = await self.crewai.run_agent("RangerUnitAgent", RANGER_PROMPT, context)
                try:
                    validate(instance=res, schema=BID_SCHEMA)
                except ValidationError as e:
                    print(f"[RangerUnit:{self.unit_id}] Schema error: {e.message}. Fallback bid.")
                    res = {
                        "unit_id": self.unit_id,
                        "eta_minutes": 15,
                        "equipment_ready": True,
                        "estimated_success": 0.6,
                        "cost": 50.0
                    }
                await self.send("CoordinatorAgent", "bid", {"bid": res})
                await self.send("BlackboardAgent", "log", {"bid": res})

            elif pf == "award_contract" and "dispatch" in content:
                dispatch = content["dispatch"]
                self.status = "enroute"
                await self.send("BlackboardAgent", "log", {"award": dispatch})
                # Could add route planning later
