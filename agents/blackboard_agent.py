import asyncio, os, json
from datetime import datetime, timezone
from .base_agent import BaseAgent

class BlackboardAgent(BaseAgent):
    """Central persistent store & blackboard for WildGuard.
    Categorizes logged events (incident adverts, bids, awards, triage, vet responses).
    """

    def __init__(self, name, broker, filename="logs/blackboard.log"):
        super().__init__(name, broker)
        self.filename = filename
        self._lock = asyncio.Lock()
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        self.stats = {
            "incidents": 0,
            "bids": 0,
            "awards": 0,
            "triage": 0,
            "vet_responses": 0
        }
        print(f"[{self.name}] Logging to {self.filename}")

    async def _append(self, record: dict):
        async with self._lock:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def run(self):
        await self.broker.register(self.name, self.inbox)
        print(f"[{self.name}] Ready for blackboard logging.")
        while True:
            msg = await self.receive()
            perf = msg.get("performative")
            content = msg.get("content", {})
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from": msg.get("from"),
                "performative": perf,
                "content": content
            }
            # Categorize stats
            if "advertise_incident" in content:
                self.stats["incidents"] += 1
            if "bid" in content:
                self.stats["bids"] += 1
            if "award_contract" in content:
                self.stats["awards"] += 1
            if "triage" in content or "triage_summary" in content:
                self.stats["triage"] += 1
            if "vet_response" in content:
                self.stats["vet_responses"] += 1
            record["stats"] = self.stats
            await self._append(record)
            print(f"[{self.name}] Logged {perf}. Totals: {self.stats}")
