# broker.py
import asyncio
from collections import defaultdict

class Broker:
    def __init__(self):
        self.queues = {}

    async def register(self, agent_name, queue):
        self.queues[agent_name] = queue
        print(f"[Broker] ✓ Registered agent: {agent_name}")

    async def publish(self, msg):
        if msg["to"] == "broadcast":
            for q in self.queues.values():
                await q.put(msg)
            return
        target = msg["to"]
        if target in self.queues:
            await self.queues[target].put(msg)
            # print(f"[Broker] ✓ Delivered '{msg['performative']}' from {msg['from']} to {target}")
        else:
            # simple fallback: log
            print(f"[Broker] ✗ Unknown target {target} from {msg['from']} ; message id {msg['id']}")
