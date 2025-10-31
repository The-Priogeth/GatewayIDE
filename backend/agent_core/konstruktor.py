# backend/agent_core/konstruktor.py
from __future__ import annotations

__all__ = ["build_hma"]

def build_hma(*, demo_registry, llm_client):
    from backend.agent_core.hma.hma_config import DEFAULT_HMA_CONFIG
    from backend.agent_core.hma.hma import HMA
    return HMA(
        som_system_prompt=DEFAULT_HMA_CONFIG.som_system_prompt,
        templates=DEFAULT_HMA_CONFIG,
        demos=demo_registry,
        messaging=__import__("backend.agent_core.messaging", fromlist=[""]),
        llm=llm_client,
    )