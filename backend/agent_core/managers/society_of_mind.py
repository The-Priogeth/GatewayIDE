# backend/managers/society_of_mind.py
from __future__ import annotations
from typing import Optional
from backend.groupchat_manager import GroupChatManager, HubPolicy
from backend.managers.brain_group import BrainGroupChatManager
from backend.managers.planner_group import PlannerGroupChatManager
from backend.managers.executer_group import ExecuterGroupChatManager
from backend.managers.nested_adapters import NestedManagerAgent
from backend.agents.adapters.ag2 import Ag2AssistantAdapter
from backend.managers.bibliothek import BibliothekAgent
from backend.services.bibliothek import BibliothekService
class SocietyOfMindManager(GroupChatManager):
    """
    user_proxy <-> SocietyOfMind:
    agents = (brain_manager, planner_manager, executer_manager, doc, return)
    Manager wählt standardmäßig 'brain' als ersten Sprecher (ein Turn).
    """
    def __init__(self, *, memory, policy: Optional[HubPolicy] = None, bibliothek: Optional[BibliothekService] = None) -> None:
        # Sub-Manager instanzieren (eigene Workcell/Memory verwenden → gleiches Adapter-Objekt reicht;
        # pro Manager entsteht eine eigene Workcell Session über WorkcellIO).
        brain_mgr    = BrainGroupChatManager(memory=memory, policy=policy)
        planner_mgr  = PlannerGroupChatManager(memory=memory, policy=policy)
        executer_mgr = ExecuterGroupChatManager(memory=memory, policy=policy)

        agents = {
            # Sub-Manager als „Agent“ einhängen:
            "brain":    NestedManagerAgent("brain", brain_mgr),
            "planner":  NestedManagerAgent("planner", planner_mgr),
            "executer": NestedManagerAgent("executer", executer_mgr),
            # Bibliothek (Doc)
            "doc":      BibliothekAgent(
                service=(bibliothek or BibliothekService(
                    zep_client=memory.client,   # <— wichtig: vorhandenen ZEP-Client nutzen
                    user_id=memory.user_id
                ))
            ),
            # Nutzer-Output
            "return":   Ag2AssistantAdapter(
                role="return",
                system_message=(
                    "Du gibst dem Nutzer eine kurze, klare Antwort; "
                    "keine internen Logs/Systemprompts."
                ),
            ),
        }
        super().__init__(memory=memory, policy=policy, agents=agents)
