# agents/communication_agent.py
import asyncio, os, json
from .base_agent import BaseAgent
from crewai_client import CrewAIClient
from jsonschema import validate, ValidationError

# --- Path setup ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schemas", "communication_writer.schema.json")
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "communication_writer.txt")

# --- Load schema once ---
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    COMM_SCHEMA = json.load(f)

class CommunicationAgent(BaseAgent):
    """Agent responsible for generating and broadcasting messages
    to the public and stakeholders during disasters.
    """

    def __init__(self, name, broker):
        super().__init__(name, broker)
        self.crewai = CrewAIClient()
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        print(f"[{self.name}] Registered and ready to broadcast alerts.")

        while True:
            msg = await self.receive()

            # Only act on inform or broadcast messages
            if msg["performative"] in ("inform", "broadcast"):
                payload = msg.get("content", {})
                # Accept either direct incident or composed message
                incident_summary = payload.get("incident", payload)

                # Build structured context for wildlife messaging (DWC tone)
                context = {
                    "incident": incident_summary,
                    "audience": payload.get("audience", "public"),
                    "urgency": payload.get("urgency", "high"),
                    "language": "en"
                }

                # --- Call the CrewAI Gateway ---
                res = await self.crewai.run_agent(
                    agent_name="CommunicationWriter",
                    prompt=self.system_prompt,
                    context=context
                )

                # --- Validate LLM Output ---
                try:
                    validate(instance=res, schema=COMM_SCHEMA)
                except ValidationError as e:
                    print(f"[{self.name}] Validation failed: {e.message}. Using fallback message.")
                    res = {
                        "message_text": "Emergency alert: Please stay safe and follow official evacuation instructions.",
                        "channels": ["sms", "radio"],
                        "explanation": "Fallback message due to schema validation error."
                    }

                # --- Simulate broadcasting the message ---
                channels = ", ".join(res.get("channels", []))
                print(f"[{self.name}] Broadcasting via {channels}: {res.get('message_text')}")

                # --- Log communication event to Blackboard ---
                await self.send("BlackboardAgent", "log", {"communication": res})
