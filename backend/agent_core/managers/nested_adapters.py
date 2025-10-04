# backend/managers/nested_adapters.py
from __future__ import annotations
from typing import Any, Dict

class NestedManagerAgent:
    """Adapter: lässt einen GroupChatManager wie einen Agenten wirken."""
    role: str
    def __init__(self, role: str, manager: Any) -> None:
        self.role = role
        self.manager = manager

    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        res = await self.manager.group_once(
            goal=goal,
            deliverables=ctx.get("deliverables") or [],
            constraints=ctx.get("constraints") or [],
        )
        reply = (res.get("reply") or "").strip()
        sig = {"status": res.get("status", "final")}
        if "trace" in res:
            sig["trace"] = res["trace"]
        return {"content": reply, "actions": [], "signals": sig}
