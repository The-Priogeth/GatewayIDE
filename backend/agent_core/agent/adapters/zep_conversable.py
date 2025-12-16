# backend/agents/adapters/zep_conversable.py
from __future__ import annotations
from typing import Any, Dict, List
from .base import Agent

class ZepConversableAgentAdapter(Agent):
    """
    Adapter: macht einen autogen.ConversableAgent (deine alte Demo) V3-kompatibel.
    Erwartet ein Objekt mit .generate_reply(messages) o.ä.
    """
    role: str = "assistant"

    def __init__(self, wrapped, role: str = "assistant"):
        self.wrapped = wrapped
        self.role = role

    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = [{"role": "user", "content": goal}]
        # Je nach API deiner Demo ggf. anpassen:
        try:
            out = self.wrapped.generate_reply(messages)  # sync in autogen
        except Exception:
            out = None
        text = (out or "").strip()
        return {"content": text, "actions": [], "signals": {}}
