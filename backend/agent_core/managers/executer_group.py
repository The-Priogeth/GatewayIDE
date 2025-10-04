# backend/managers/executer_group.py
from __future__ import annotations
from typing import Any, Dict, Optional
from backend.groupchat_manager import GroupChatManager, HubPolicy
from backend.agents.adapters.ag2 import Ag2AssistantAdapter
from backend.prompts import render_implement

def _executer_brain_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Leite Ausführung aus Plan ab (Klarheit, Risiken, Checks):\n{goal}"

def _coder_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    plan = ctx.get("plan") or goal
    return render_implement(plan, ctx.get("deliverables") or [], ctx.get("constraints") or [])

def _writer_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Erzeuge saubere Endtexte/Dokumentation zum Ziel/Ergebnis:\n{goal}"

class ExecuterGroupChatManager(GroupChatManager):
    """(brain, coder, writer) – Tools vorbereitet (Code-Exec, Files, …)."""
    def __init__(self, *, memory, policy: Optional[HubPolicy] = None) -> None:
        agents = {
            "brain": Ag2AssistantAdapter(
                role="brain",
                system_message="Execution-Denker. Plane Umsetzungsschritte & Checks.",
                make_prompt=_executer_brain_prompt,
            ),
            "coder": Ag2AssistantAdapter(
                role="coder",
                system_message="Coder. Generiere präzisen, ausführbaren Code (Tools vorbereitet).",
                make_prompt=_coder_prompt,
            ),
            "writer": Ag2AssistantAdapter(
                role="writer",
                system_message="Writer. Formatiere Ergebnisse & Anleitungen klar.",
                make_prompt=_writer_prompt,
            ),
            "return": Ag2AssistantAdapter(
                role="return",
                system_message="Kuratierter Output für Nutzer – kurz, klar, ohne interne Logs.",
            ),
        }
        super().__init__(memory=memory, policy=policy, agents=agents)
