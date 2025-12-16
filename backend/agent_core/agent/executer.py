# backend/agents/executer.py
from __future__ import annotations
from typing import Any, Dict
from .base import Agent, _llm_chat
from backend.prompts import render_implement

class ExecuterAgent(Agent):
    """
    Führt Plan um (nur intern). Der Text ist Ergebnis/Artefakt-Skizze,
    nicht für den User bestimmt – ReturnAgent kuratiert später.
    """
    role = "executer"
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        plan = ctx.get("plan") or goal
        prompt = render_implement(plan, ctx.get("deliverables") or [], ctx.get("constraints") or [])
        out = _llm_chat([{"role": "user", "content": prompt}]) or ""
        return {"content": out.strip(), "actions": [], "signals": {}}
