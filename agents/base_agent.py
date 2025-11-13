# agents/base_agent.py
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

class BaseAgent:
    """Base class for all agents in the CrewAI multi-agent system.
    
    Provides async message passing through a shared broker.
    Each agent has its own inbox (async queue) and can send structured messages.
    """

    def __init__(self, name: str, broker: Any):
        self.name = name
        self.broker = broker
        self.inbox: asyncio.Queue = asyncio.Queue()

    async def send(self, to: str, performative: str, content: Dict[str, Any], log: bool = True):
        """Send a message to another agent via the broker."""
        msg = {
            "id": str(uuid.uuid4()),
            "from": self.name,
            "to": to,
            "performative": performative,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content,
        }
        await self.broker.publish(msg)

        if log:
            print(f"[{self.name}] → Sent '{performative}' to {to}")

    async def receive(self) -> Dict[str, Any]:
        """Wait (block) until a message is available in the inbox."""
        msg = await self.inbox.get()
        print(f"[{self.name}] ← Received '{msg['performative']}' from {msg['from']}")
        return msg

    def receive_nowait(self):
        """Non-blocking message check (returns None if no message)."""
        try:
            return self.inbox.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def run(self):
        """Override this in each subclass to define agent-specific logic."""
        raise NotImplementedError(f"{self.name} must implement its own run() method.")
