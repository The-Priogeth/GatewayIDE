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
        "Du denkst in der Ich-Form, planst Handlungen und formulierst schließlich die Ich-Antwort. "
        "Du bist knapp, priorisierst und vermeidest Halluzinationen. "
        "Du entscheidest, ob die finale Ich-Antwort an den Nutzer oder an einen Funktions-Agent (task/lib/trn) gehen soll."
    ),
    som_plan_template=(
        "{user_text}\n\n"
        "# Kontext (falls vorhanden)\n{context}\n\n"
        "# Fähigkeiten (Kanäle)\n{capabilities}\n\n"
        "# Aufgabe\n"
        "1) Denke kurz in der Ich-Form (2–4 Sätze), was ich jetzt tun sollte.\n"
        "2) Erzeuge anschließend NUR dieses JSON (ohne weitere Worte):\n\n"
        "{{\n"
        '  "thought": "Ich-Form, 1–2 Sätze (kurz)",\n'
        '  "actions": [\n'
        '    {{"target": "task|lib|trn", "message": "kurzer Auftrag"}},\n'
        "    ...\n"
        "  ]\n"
        "}}\n\n"
        "Regeln: Maximal {max_targets} Aktionen. Nur task/lib/trn als target. "
        "Wenn keine externe Aktion nötig ist, liefere actions=[]."
    ),
    # WICHTIG: Erst die Ich-Antwort, DANN das Routing-JSON. Kein Text nach dem JSON.
    som_final_template=(
        "{user_text}\n\n"
        "# Interner Zwischenstand\n{aggregate}\n\n"
        "# Aufgabe\n"
        "1) Formuliere meine finale Antwort in der Ich-Form. "
        "   Halte dich kurz; nenne ggf. 1–3 konkrete nächste Schritte.\n"
        "2) Hänge NACH der Antwort in einer neuen Zeile NUR folgendes JSON an (ohne weitere Worte):\n"
        '{{"deliver_to":"user|task|lib|trn"}}'
    ),
    capabilities={
        "task": "Aufgaben strukturieren, Pläne/Implementierungsschritte vorschlagen.",
        "lib":  "Recherche/Belege/Faktenprüfung, kurze Exzerpte.",
        "trn":  "Lernpfade, Schritt-für-Schritt-Guides, Übungen/Coaching."
    },
    max_parallel_targets=3,
)
