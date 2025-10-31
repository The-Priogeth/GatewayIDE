# backend/agent_core/hma_config.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class HMAConfig:
    som_system_prompt: str
    som_plan_template: str
    som_final_template: str
    capabilities: Dict[str, str] = field(default_factory=dict)
    max_parallel_targets: int = 3

DEFAULT_HMA_CONFIG = HMAConfig(
    som_system_prompt=(
        "Du bist die innere Stimme (SOM) des Haupt-Meta-Agenten. "
        "Denke knapp, priorisiere, entscheide ein Ziel: user|task|lib|trn."
    ),
    som_plan_template="{user_text}\n\n# Kontext\n{context}\n\n# Fähigkeiten\n{capabilities}\n",
    som_final_template=(
        "{user_text}\n\n"
        "# Interner Zwischenstand\n"
        "{aggregate}\n\n"
        "# Anweisung\n"
        "Antworte in Ich-Form (kurz & präzise). "
        "Beende deine Ausgabe mit EXAKT EINER zusätzlichen Zeile:\n"
        "<<<ROUTE>>> {{\"deliver_to\":\"user|task|lib|trn\",\"args\":{{}}}} <<<END>>>"
    ),
)
