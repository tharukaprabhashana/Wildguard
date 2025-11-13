import os, json, asyncio
from jsonschema import validate, ValidationError
from .base_agent import BaseAgent
from crewai_client import CrewAIClient

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "vet_agent.txt")
SCHEMA_PATH = os.path.join(BASE_DIR, "schemas", "vet_response.schema.json")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    VET_PROMPT = f.read()
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    VET_SCHEMA = json.load(f)


class VetAgent(BaseAgent):
    """Decides on treatment requests; simulates treatment duration."""

    def __init__(self, name: str, broker):
        super().__init__(name, broker)
        self.crewai = CrewAIClient()
        self.active_cases = 0

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        print(f"[VetAgent] Registered and ready for treatment requests")
        while True:
            msg = await self.receive()
            if msg.get("performative") == "request_treatment":
                req = msg.get("content", {})
                context = {"request": req, "active_cases": self.active_cases}
                res = await self.crewai.run_agent("VetAgent", VET_PROMPT, context)
                try:
                    validate(instance=res, schema=VET_SCHEMA)
                except ValidationError as e:
                    print(f"[VetAgent] Schema error: {e.message}. Using fallback decision.")
                    res = {"decision": "accept", "reason": "fallback", "expected_treatment_time": 30}

                if res.get("decision") == "accept":
                    self.active_cases += 1
                    asyncio.create_task(self._complete_case(res.get("expected_treatment_time", 30)))

                await self.send("CoordinatorAgent", "vet_response", {"response": res})
                await self.send("BlackboardAgent", "log", {"vet_response": res})

    async def _complete_case(self, minutes: int):
        await asyncio.sleep(min(5, minutes / 10))  # compressed simulation
        self.active_cases = max(0, self.active_cases - 1)
