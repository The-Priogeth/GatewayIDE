# backend/agent_core/konstruktor.py
from __future__ import annotations
from typing import Any, Iterable
from backend.agent_core.hma.hma import HMA
from backend.agent_core.hma.speaker import Speaker
from backend.agent_core.hma.hma_config import HMAConfig

__all__ = ["build_hma"]

def build_hma(*, runtime, llm_client, demo_registry, config: HMAConfig) -> HMA:
    speaker = Speaker(runtime=runtime)
    return HMA(
        som_system_prompt=config.som_system_prompt,
        templates=config,
        demos=demo_registry,
        messaging=runtime.messaging,
        llm=llm_client,
        speaker=speaker,
        ctx_provider=getattr(runtime, "ctx_provider", None),  # <<<< NEU
    )