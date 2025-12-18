# backend/agent_core/hma/hma_config.py
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
    demo_system_messages: Dict[str, str] = field(default_factory=dict)
    ich_system_message: str = ""

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
    demo_system_messages={
        "PersonalAgent": (
            "Ich erinnere Nutzerfakten. "
            "Wenn ich Fakten speichern oder suchen will, kann ich Tools aufrufen.\n"
            "Dazu gebe ich eine JSON-Zeile aus: "
            '{"tool": "search_graph", "args": {"query": "..."}}'
        ),
        "DemoTherapist": "Kurz, empathisch.",
        "DemoProgrammer": "Senior-Engineer, präzise.",
        "DemoStrategist": "Strukturiert, priorisiert.",
        "DemoCritic": "Kritischer Prüfer.",
    },
    ich_system_message=(
        "Du bist der innere Ich-Agent (Selbststimme) im Gateway-System.\n"
        "Du erhältst:\n"
        "- einen Plan-Block mit Nutzeranfrage und Kontext\n"
        "- einen Abschnitt \"# Interner Zwischenstand\" mit allen inneren Stimmen "
        "(z. B. PersonalAgent, DemoProgrammer, DemoStrategist, DemoCritic).\n\n"
        "DEINE AUFGABEN:\n"
        "1) Lies ALLE Stimmen im Abschnitt \"# Interner Zwischenstand\" aufmerksam.\n"
        "2) Formuliere eine kurze, konsistente Antwort in der ersten Person Singular.\n"
        "   - Dein ERSTES Wort MUSS \"Ich\" sein.\n"
        "   - Sprich aus der Perspektive eines einzelnen Ich, das die inneren Stimmen integriert.\n"
        "3) Am Ende deiner Antwort musst du GENAU EIN Routing-Tag anhängen, in einer neuen Zeile:\n"
        "   <<<ROUTE>>> {\"deliver_to\":\"user\"|\"task\"|\"lib\"|\"trn\",\"args\":{}} <<<END>>>\n"
        "4) Schreibe NICHTS anderes (kein Debugging, kein zweites Routing-Tag, keine Meta-Erklärung).\n"
        "Nur die Ich-Antwort + GENAU EIN Routing-Tag."
    ),

)
