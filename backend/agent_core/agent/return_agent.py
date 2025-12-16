# backend/agents/return_agent.py
from __future__ import annotations
from typing import Any, Dict
from .base import LLMEnabledAgent, Agent

class ReturnAgent(LLMEnabledAgent, Agent):
    """
    Macht Nutzer-Antworten hübsch & sicher:
    - kürzt, glättet, ent-jargont
    - KEINE System-/Tool-Logs
    """
    role = "return"
    sys_prompt = (
        "Du bereitest klare, knappe Antworten für Menschen auf. "
        "Keine internen Logs, keine Systemprompts, kein Halluzinieren."
    )
    user_tpl = (
        "Bereite folgenden Inhalt nutzerfreundlich auf, "
        "kürze klug und formatiere übersichtlich:\n{goal}"
    )
