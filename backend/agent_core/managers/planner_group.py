# backend/managers/planner_group.py
from __future__ import annotations
from typing import Any, Dict, Optional
from backend.groupchat_manager import GroupChatManager, HubPolicy
from backend.agents.adapters.ag2 import Ag2AssistantAdapter
from backend.prompts import render_planner

def _planner_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return render_planner(goal, ctx.get("deliverables") or [], ctx.get("constraints") or [])

def _develop_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Entwickle einen präzisen Umsetzungsplan für:\n{goal}\n\nSchritte, Artefakte, Testkriterien."

def _subtasks_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Zerlege das Ziel in priorisierte Teilaufgaben mit klaren Definitionen:\n{goal}"

class PlannerGroupChatManager(GroupChatManager):
    """(brain, research, advanced_research, develop, subtasks) – brain = Plan-Denker."""
    def __init__(self, *, memory, policy: Optional[HubPolicy] = None) -> None:
        agents = {
            "brain": Ag2AssistantAdapter(
                role="brain",
                system_message="Plan-Denker. Verdichtet Inputs zu tragfähigen Plänen.",
                make_prompt=_planner_prompt,
            ),
            "research": Ag2AssistantAdapter(
                role="research",
                system_message="Plan-Research. Ergänze Lücken, liefere Quellenideen (Tools vorbereitet).",
            ),
            "advanced_research": Ag2AssistantAdapter(
                role="advanced_research",
                system_message="Plan-Deep-Dive. Methodische Absicherung (Tools vorbereitet).",
            ),
            "develop": Ag2AssistantAdapter(
                role="develop",
                system_message="Entwickler der Vorgehensweise. Feinplanung, Qualitätssicherung.",
                make_prompt=_develop_prompt,
            ),
            "subtasks": Ag2AssistantAdapter(
                role="subtasks",
                system_message="Task-Creator. Erzeuge priorisierte Teilaufgaben mit Akzeptanzkriterien.",
                make_prompt=_subtasks_prompt,
            ),
            "return": Ag2AssistantAdapter(
                role="return",
                system_message="Formatiere den finalen Plan knapp & klar für Übergabe.",
            ),
        }
        super().__init__(memory=memory, policy=policy, agents=agents)
