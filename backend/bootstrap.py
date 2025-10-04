"""
bootstrap.py — Chat-/Runtime-Owner
----------------------------------
- ensure_runtime(): erstellt Zep-Client, Threads, Agenten und liefert ein Runtime-Objekt.
- chat_entry():     startet die interaktive Chat-Schleife mit der Runtime.
- main():           öffnet neues Terminal und startet chat_entry().
"""
from __future__ import annotations

import os, uuid
from typing import Dict
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv
from typing import cast
from zep_cloud.client import AsyncZep
from backend.zep_autogen import ZepUserMemory
from backend.agent import (
    build_llm_config,
    create_captains_with_internal_team,
    create_lobby,
    ContextProvider,
)


# ------------------------------------------------------------
# Datentyp für gemeinsame Runtime
# ------------------------------------------------------------
@dataclass
class RuntimeState:
    zep_client: AsyncZep
    user_id: str
    thread_id: str
    lobby: dict
    memory: Dict[str, ZepUserMemory]
    mem_thread: Dict[str, str]
    hub: dict

# ------------------------------------------------------------
# Setup-Helfer
# ------------------------------------------------------------
async def _setup_zep_user_thread(
    zep: AsyncZep, *, user_prefix: str
) -> tuple[str, str, ZepUserMemory]:
    user_id = f"{user_prefix}_{uuid.uuid4().hex[:8]}"
    thread_id = f"thread_{user_prefix}_{uuid.uuid4().hex[:8]}"
    await zep.user.add(
        user_id=user_id,
        email=f"{user_id}@example.local",
        first_name=user_prefix.capitalize(),
        last_name="Agent",
    )
    await zep.thread.create(thread_id=thread_id, user_id=user_id)
    mem = ZepUserMemory(
        client=zep, user_id=user_id, thread_id=thread_id, thread_context_mode="summary"
    )
    return thread_id, user_id, mem

# ------------------------------------------------------------
# ZENTRALE RUNTIME (einzige Quelle für Setup)
# ------------------------------------------------------------
_runtime_singleton: RuntimeState | None = None

async def ensure_runtime() -> RuntimeState:
    """Einmalige Initialisierung von Zep/Agenten/Threads; liefert RuntimeState."""
    global _runtime_singleton
    if _runtime_singleton is not None:
        return _runtime_singleton

    load_dotenv(find_dotenv(usecwd=True))
    openai_model   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    zep_api_key    = os.getenv("ZEP_API_KEY")
    zep_base_url   = os.getenv("ZEP_BASE_URL")
    missing = [k for k,v in {"OPENAI_API_KEY":openai_api_key, "ZEP_API_KEY":zep_api_key}.items() if not v]
    if missing:
        raise RuntimeError(f"Fehlende Umgebungsvariablen: {', '.join(missing)}")

    # Zep
    zep = AsyncZep(api_key=zep_api_key, base_url=zep_base_url) if zep_base_url else AsyncZep(api_key=zep_api_key)

    # LLM + Kontext
    # Nach obiger Prüfung sind Keys garantiert gesetzt → Typ verengen
    openai_api_key = cast(str, openai_api_key)
    zep_api_key    = cast(str, zep_api_key)
    llm_cfg = build_llm_config(model=openai_model, api_key=openai_api_key)
    ctx_provider = ContextProvider()

    # Root-Thread
    root_thread_id, root_user_id, root_memory = await _setup_zep_user_thread(zep, user_prefix="groupchat")

    # Captain-Threads
    labels = ("THINK", "PLAN", "EXECUTE")
    thread_map: Dict[str, str] = {}
    memory_map: Dict[str, ZepUserMemory] = {}
    for label in labels:
        t_id, _u_id, mem = await _setup_zep_user_thread(zep, user_prefix=label.lower())
        thread_map[label] = t_id
        memory_map[label] = mem

    # Captains + interne Teams
    captains, internal_map = create_captains_with_internal_team(
        llm_cfg=llm_cfg,
        context_provider=ctx_provider,
        zep_client=zep,
        memory_map=memory_map,
        thread_map=thread_map,
    )
    # Lobby (GroupChat + Manager, Auto-Pattern)
    lobby = create_lobby(llm_cfg, captains)
    _runtime_singleton = RuntimeState(
        zep_client=zep,
        user_id=root_user_id,
        thread_id=root_thread_id,
        lobby={"root_thread_id": root_thread_id, "root_memory": root_memory},
        memory=memory_map,
        mem_thread=thread_map,
        hub={
            "captains": captains,
            "internal_map": internal_map,
            "context_provider": ctx_provider,
            "lobby": lobby,
        },
    )
    return _runtime_singleton