# backend/agents/doc.py
from __future__ import annotations
from typing import Any, Dict
from .base import Agent

class DocAgent(Agent):
    """
    Platzhalter für ZEP-gestütztes recall/remember (Bibliothekarin).
    In `ctx` kann z.B. eine `doc`-Fassade übergeben werden.
    """
    role = "doc"
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # Beispiel (später aktivieren):
        # results = await ctx["doc"].recall(query=goal, k=5)
        return {"content": "", "actions": [], "signals": {}}
