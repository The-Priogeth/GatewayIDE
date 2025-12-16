from __future__ import annotations
from backend.ag2.autogen.agentchat import ConversableAgent


class PlanningAgent(ConversableAgent):
    def __init__(self, *, llm_config):
        super().__init__(
        name="PlanningAgent",
        system_message=(
        "Du strukturierst komplexe Aufgaben in wenige, klare Schritte. "
        "Bevorzuge Abhängigkeiten und Reihenfolgen. Antworte kompakt."
        ),
        llm_config=llm_config,
        human_input_mode="NEVER",
        )