# backend/agents/planner.py
from __future__ import annotations
from typing import Any, Dict
from .base import Agent, _llm_chat
from backend.prompts import render_planner

class PlannerAgent(Agent):
    role = "planner"
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        prompt = render_planner(goal, ctx.get("deliverables") or [], ctx.get("constraints") or [])
        out = _llm_chat([{"role": "user", "content": prompt}]) or ""
        return {"content": out.strip(), "actions": [], "signals": {}}
