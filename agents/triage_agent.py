import os, json
from jsonschema import validate, ValidationError
from .base_agent import BaseAgent
from crewai_client import CrewAIClient

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "triage_agent.txt")
SCHEMA_PATH = os.path.join(BASE_DIR, "schemas", "triage_agent.schema.json")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    TRIAGE_PROMPT = f.read()
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    TRIAGE_SCHEMA = json.load(f)


class TriageAgent(BaseAgent):
    """Maintains incident registry and produces triage assessments."""

    def __init__(self, name: str, broker):
        super().__init__(name, broker)
        self.crewai = CrewAIClient()
        self.incidents = {}

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        print(f"[TriageAgent] Registered and ready for triage assessments")
        while True:
            msg = await self.receive()
            pf = msg.get("performative")
            content = msg.get("content", {})

            if pf == "inform" and "incident" in content:
                inc = content["incident"]
                self.incidents[inc["id"]] = inc
                context = {"incident": inc}
                res = await self.crewai.run_agent("TriageAgent", TRIAGE_PROMPT, context)
                try:
                    validate(instance=res, schema=TRIAGE_SCHEMA)
                except ValidationError as e:
                    print(f"[TriageAgent] Schema error: {e.message}. Using fallback triage.")
                    res = {
                        "incident_id": inc["id"],
                        "priority": int(min(5, max(1, inc.get("priority", 3)))),
                        "required_resources": ["ranger_unit"],
                        "access_difficulty": inc.get("access_difficulty", "open"),
                        "recommended_actions": ["Stabilize animal", "Monitor from safe distance"]
                    }

                # Notify coordinator and log
                await self.send("CoordinatorAgent", "triage_summary", {"triage": res})
                await self.send("BlackboardAgent", "log", {"triage": res})
