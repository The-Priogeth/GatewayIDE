# backend/managers/brain_group.py
from __future__ import annotations
from typing import Any, Dict, Optional
from backend.groupchat_manager import GroupChatManager, HubPolicy
from backend.agents.adapters.ag2 import Ag2AssistantAdapter

def _q_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    dels = ctx.get("deliverables") or []; cons = ctx.get("constraints") or []
    extra = []
    if dels: extra.append("Lieferobjekte:\n- " + "\n- ".join(map(str, dels)))
    if cons: extra.append("Randbedingungen:\n- " + "\n- ".join(map(str, cons)))
    ex = ("\n\n" + "\n\n".join(extra)) if extra else ""
    return f"Ziel:\n{goal}{ex}\n\nStelle präzise Rückfragen und kläre Annahmen."

def _research_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Recherchiere strukturiert zum Ziel:\n{goal}\n\nGib kurz: Fakten, Quellenansätze, Unsicherheiten."

def _adv_research_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Tiefe Analyse & Recherche (Methodik/Plan, Hypothesen, Datenbedarf):\n{goal}"

def _critic_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    return f"Kritisiere/prüfe den aktuellen Entwurf/Plan zum Ziel:\n{goal}\n\nNenne Lücken & Verbesserungen."

class BrainGroupChatManager(GroupChatManager):
    """Verschachtelter Manager: (assistant, questioning, critic, research, advanced_research)."""
    def __init__(self, *, memory, policy: Optional[HubPolicy] = None) -> None:
        agents = {
            # „brain“ dient nur dazu, dass GroupChatManager diesen zuerst wählt
            "brain": Ag2AssistantAdapter(
                role="brain",
                system_message=(
                    "Du bist Brain-Assistent. Fasse Annahmen/Fragen kurz und "
                    "nenne den nächsten Schritt. Antworte kompakt."
                ),
                # make_prompt = default (Goal durchreichen)
            ),
            "questioning": Ag2AssistantAdapter(
                role="questioning",
                system_message="Sokratischer Fragesteller. Klärt Spezifikation & Annahmen.",
                make_prompt=_q_prompt,
            ),
            "critic": Ag2AssistantAdapter(
                role="critic",
                system_message="Strenger Reviewer. Finde Lücken/Fehler, mache konkrete Verbesserungen.",
                make_prompt=_critic_prompt,
            ),
            "research": Ag2AssistantAdapter(
                role="research",
                system_message="Research-Agent. Schlägt Recherchepfade vor (Tools vorbereitet).",
                make_prompt=_research_prompt,
            ),
            "advanced_research": Ag2AssistantAdapter(
                role="advanced_research",
                system_message="Advanced Research. Tiefe Analyse, Methodik, Datenbedarf (Tools vorbereitet).",
                make_prompt=_adv_research_prompt,
            ),
            "return": Ag2AssistantAdapter(
                role="return",
                system_message="Formatiere das interne Ergebnis kurz & klar für Übergabe.",
            ),
        }
        super().__init__(memory=memory, policy=policy, agents=agents)
