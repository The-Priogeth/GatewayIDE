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
        "Du fasst interne Agentenantworten zusammen, triffst eine Entscheidung "
        "und wählst EIN Ziel: user|task|lib|trn. "
        "Wenn du unsicher bist, wähle immer 'user'."
    ),
    som_plan_template=(
        "{user_text}\n\n"
        "# Kontext\n"
        "{context}\n\n"
        "# Fähigkeiten\n"
        "{capabilities}\n\n"
        "# Interner Zwischenstand der inneren Agenten\n"
        "{aggregate}\n\n"
    ),
    som_final_template=(
        "# Deine Aufgabe als SOM\n"
        "1. Beantworte die Frage des Nutzers direkt, in Ich-Form, kurz und präzise.\n"
        "2. Entscheide erst DANACH, ob eine Folgeaktion nötig ist:\n"
        "   - Wähle 'user', wenn deine Antwort für den Nutzer ausreicht (STANDARDFALL).\n"
        "   - Wähle 'task', wenn eine konkrete Weiterverarbeitung durch den Task-Manager nötig ist.\n"
        "   - Wähle 'lib', wenn zusätzliche Recherche/Wissen durch den Librarian nötig ist.\n"
        "   - Wähle 'trn', wenn Training/Reflexion durch den Trainer sinnvoll ist.\n"
        "3. Wenn du unsicher bist, wähle IMMER 'user'.\n\n"
        "Formatiere deine Ausgabe GENAU so:\n"
        "- Zuerst deine Antwort in natürlicher Sprache.\n"
        "- Danach EXAKT EINE zusätzliche Zeile im Format:\n"
        "<<<ROUTE>>> {{\"deliver_to\":\"user\",\"args\":{{}}}} <<<END>>>\n"
        "Ersetze in dieser ROUTE-Zeile NUR das Wort \"user\" durch GENAU EINEN der Werte: "
        "user, task, lib oder trn.\n"
        "Schreibe KEINE weiteren Kommentare oder Erklärungen in diese Zeile."
    ),
)
