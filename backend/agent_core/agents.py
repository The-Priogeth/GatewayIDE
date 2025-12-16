# backend/agent_core/agents.py
from __future__ import annotations

import os
from typing import Any, Callable, List, Tuple

from ..ag2.autogen.agentchat import ConversableAgent
from .demo_adapter import DemoAdapter
from .llm_adapter import LLMAdapter


def build_agents(
    *,
    model_name: str,
    call_tool: Callable[..., Any],
) -> Tuple[List[DemoAdapter], LLMAdapter]:
    """
    Baut die inneren Demo-Agenten (PersonalAgent, Programmer, etc.)
    und den Ich-Agenten (als ConversableAgent, gewrappt in LLMAdapter).

    Rückgabe:
        demo_registry: Liste von DemoAdapter-Instanzen
        ich_llm:       LLMAdapter, der den Ich-Agenten kapselt
    """

    # --- Demos (AG2) ---------------------------------------------------------
    llm_cfg: dict[str, Any] = {"model": model_name}

    raw_demos: List[ConversableAgent] = [
        ConversableAgent(
            name="PersonalAgent",
            system_message=(
                "Ich erinnere Nutzerfakten. "
                "Wenn ich Fakten speichern oder suchen will, kann ich Tools aufrufen.\n"
                "Dazu gebe ich eine JSON-Zeile aus: "
                '{"tool": "search_graph", "args": {"query": "..."}}'
            ),
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoTherapist",
            system_message="Kurz, empathisch.",
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoProgrammer",
            system_message="Senior-Engineer, präzise.",
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoStrategist",
            system_message="Strukturiert, priorisiert.",
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoCritic",
            system_message="Kritischer Prüfer.",
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
    ]

    demo_registry: List[DemoAdapter] = [
        DemoAdapter(a, call_tool=call_tool) for a in raw_demos
    ]

    # --- Ich-Agent -----------------------------------------------------------
    ich_model_name = os.getenv("ICH_MODEL", model_name)
    ich_llm_cfg: dict[str, Any] = {"model": ich_model_name}

    ich_agent = ConversableAgent(
        name="IchAgent",
        system_message=(
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
            "   - \"user\": direkte Antwort an den Nutzer (Standard)\n"
            "   - \"task\": an den TaskManager (technische/Umsetzungsaufgaben)\n"
            "   - \"lib\": an den Librarian (Recherche/Quellenarbeit)\n"
            "   - \"trn\": an den Trainer (Lern-/Reflexionskontext)\n"
            "4) Schreibe NICHTS anderes:\n"
            "   - Kein zusätzliches Debugging.\n"
            "   - Kein zweites Routing-Tag.\n"
            "   - Keine Meta-Erklärung darüber, was du tust.\n"
            "Nur die Ich-Antwort + GENAU EIN Routing-Tag."
        ),
        llm_config=ich_llm_cfg,
        human_input_mode="NEVER",
    )

    ich_llm = LLMAdapter(agent=ich_agent)
    return demo_registry, ich_llm
