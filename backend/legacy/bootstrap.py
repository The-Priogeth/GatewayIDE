# backend/bootstrap.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional, Dict, Literal, cast

from loguru import logger
from zep_cloud.client import AsyncZep
from zep_cloud.core.api_error import ApiError

# ZEP-Memory: Thread-scope (für Chat/Manager) & Full-scope (für REST-APIs)
from backend.memory.memory_zep_thread import ZepThreadMemory
from backend.memory.memory import ZepMemory

# V3-Manager & Policy (kein Hub&Spokes mehr)
from backend.groupchat_manager import GroupChatManager, HubPolicy

# Leichte AG2-Adapter (einfacher Assistent mit optionaler Prompt-Funktion)
from backend.agents.adapters.ag2 import Ag2AssistantAdapter  # stelle sicher, dass dieses Modul existiert
from backend.prompts import render_planner, render_implement   # deine Prompt-Bausteine


# ──────────────────────────────────────────────────────────────────────────────
# Runtime-Zustand: wird 1:1 im FastAPI-Lifespan nach app.state gespiegelt
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class RuntimeState:
    zep_client: Any
    user_id: str
    thread_id: Optional[str]
    lobby: Any                 # stabile Chat-Surface (z. B. für /api/chat Alias)
    memory: Optional[Any]      # volle Memory-Fassade für /api/memory/*
    mem_thread: Optional[Any]  # Thread-Memory (Konversation/Turns)
    hub: Optional[Any]         # GroupChatManager (V3)
    # orch_nested: bool          # erhalten für /api/status (kompakt, optional)
    # persist_cfg: dict          # dito (nur Anzeigezwecke /api/status)


_RUNTIME: Optional[RuntimeState] = None  # idempotenter Cache


# ──────────────────────────────────────────────────────────────────────────────
# ZEP: User/Thread robust sicherstellen (idempotent, fail-fast bei echten Fehlern)
# ──────────────────────────────────────────────────────────────────────────────
async def _ensure_user(client: AsyncZep, user_id: str) -> None:
    try:
        await client.user.get(user_id)
    except ApiError as e:
        if getattr(e, "status_code", None) == 404:
            await client.user.add(user_id=user_id)
        else:
            raise


async def _ensure_thread(client: AsyncZep, desired_id: str, user_id: str) -> str:
    """
    Stellt einen Thread mit fester ID sicher und gibt die *kanonische* ID zurück.
    (ZEP-Versionen unterscheiden sich in Feldnamen → defensiv ableiten.)
    """
    t = None
    try:
        t = await client.thread.create(thread_id=desired_id, user_id=user_id)
    except ApiError as e:
        if getattr(e, "status_code", None) in (400, 409):
            try:
                t = await client.thread.get(thread_id=desired_id)
            except Exception:
                t = None
        else:
            raise

    return (
        getattr(t, "thread_id", None)
        or getattr(t, "uuid", None)
        or getattr(t, "id", None)
        or desired_id
    )


# ──────────────────────────────────────────────────────────────────────────────
# Öffentliche Fabrik: baut ZEP, Memory, Manager und Chat-Fassade (idempotent)
# ──────────────────────────────────────────────────────────────────────────────
async def ensure_runtime() -> RuntimeState:
    """
    Baut die komplette Runtime **einmalig** und cached sie:
    - ZEP-Client
    - Memory (Thread & Full)
    - GroupChatManager inkl. Agents (Brain/Planner/Executer/Return/Doc)
    - Chat-Fassade (stabiler Surface-Endpunkt)
    - Ein *einziger* kompakter Status-Log am Ende.
    """
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME

    # 1) ZEP-Client
    api_key = os.environ["ZEP_API_KEY"]  # hart erforderlich → KeyError wenn nicht gesetzt
    base = _sanitized_base()
    client = AsyncZep(api_key=api_key, base_url=base) if base else AsyncZep(api_key=api_key)

    # 2) User + Thread (kanonische ID)
    user_id = os.getenv("ZEP_USER_ID") or os.getenv("GATEWAY_USER_ID", "local_Aaron")
    desired_tid = os.getenv("ZEP_THREAD_ID") or f"thread_{user_id}"
    await _ensure_user(client, user_id)
    canonical_tid = await _ensure_thread(client, desired_tid, user_id)

    # 3) Memory aufbauen
    #    - mem_thread: wird vom Manager/Chat verwendet (Turn-/Thread-Kontext)
    #    - mem_full:   wird von REST-/Admin-Endpunkten verwendet (/api/memory/*)
    mem_thread = ZepThreadMemory(client=client, user_id=user_id, thread_id=canonical_tid)
    mem_full   = ZepMemory(     client=client, user_id=user_id, thread_id=canonical_tid)
    await mem_full.ensure_thread()  # REST-Thread sicherstellen (fail-fast ok)

    # 4) (optionale) Statusflags für /api/status – minimal belassen
    #    Wir halten die Felder bei, damit bestehende UIs nicht brechen.
    # orch_nested = os.getenv("ORCH_NESTED", "false").lower() == "true"
    # persist_cfg = {"workcell": "inmem", "orchestrator": "graph", "agent_st": "inmem"}

    # 5) Agents definieren (AG2-Adapter)
    #    Hinweise:
    #    - `system_message`: Rolle & Stil
    #    - `make_prompt`:    dynamischer Prompt-Builder pro Rolle (optional)
    def _planner_prompt(goal: str, ctx: Dict[str, Any]) -> str:
        return render_planner(goal, ctx.get("deliverables") or [], ctx.get("constraints") or [])

    def _executer_prompt(goal: str, ctx: Dict[str, Any]) -> str:
        plan = ctx.get("plan") or goal
        return render_implement(plan, ctx.get("deliverables") or [], ctx.get("constraints") or [])

    agents = {
        "brain": Ag2AssistantAdapter(
            role="brain",
            system_message=(
                "Du bist Brain: fasse Annahmen & offene Fragen kurz zusammen "
                "und nenne den nächsten sinnvollen Schritt. Antworte kompakt."
            ),
            # human_input_mode nicht setzen → keine Literal-Typwarnung in Pylance
        ),
        "planner": Ag2AssistantAdapter(
            role="planner",
            system_message="Du planst klare, umsetzbare Schritte.",
            make_prompt=_planner_prompt,
        ),
        "executer": Ag2AssistantAdapter(
            role="executer",
            system_message="Du setzt den Plan in konkrete Artefakte/Code um.",
            make_prompt=_executer_prompt,
        ),
        "return": Ag2AssistantAdapter(
            role="return",
            system_message="Formatiere die Nutzerantwort kurz & klar. Keine internen Logs.",
        ),
        "doc": Ag2AssistantAdapter(
            role="doc",
            system_message="Hilf beim Abrufen/Notieren von Wissen (Tools vorbereitet).",
        ),
    }

    # 6) Manager + Chat-Fassade
    hub = GroupChatManager(memory=mem_thread, policy=HubPolicy(), agents=agents)
    lobby = hub.build_chat_facade(
        zep_facade=mem_thread,
        user_id=user_id,
        thread_id=canonical_tid,
    )

    # 7) Zusammenstellen & Cachen
    _RUNTIME = RuntimeState(
        zep_client=client,
        user_id=user_id,
        thread_id=canonical_tid,
        lobby=lobby,
        memory=mem_full,
        mem_thread=mem_thread,
        hub=hub,
        # orch_nested=orch_nested,
        # persist_cfg=persist_cfg,
    )

    # 8) Ein kompakter Status-Log (keine Logflut)
    #    → gut lesbar in Container-Logs / CI
    tm_raw = (os.getenv("THREAD_MODE", "isolated") or "isolated").lower()
    thread_mode: Literal["isolated", "shared"] = cast(
        Literal["isolated", "shared"],
        "shared" if tm_raw == "shared" else "isolated",
    )
    logger.info(
        "runtime: user={} thread={} zep_base={} thread_mode={} agents={}",
        user_id,
        canonical_tid,
        (base or "<default>"),
        thread_mode,
        ",".join(sorted(agents.keys())),
    )

    return _RUNTIME

# ──────────────────────────────────────────────────────────────────────────────
# Hilfsfunktion: BASE_URL säubern (…/api(/v2) am Ende abschneiden, wenn gegeben)
# ──────────────────────────────────────────────────────────────────────────────
def _sanitized_base() -> Optional[str]:
    # nach möglichkeit ohne diese funktion auskommen!
    raw = (os.getenv("ZEP_BASE_URL", "") or os.getenv("ZEP_API_BASE_URL", "") or "").strip()
    if not raw:
        return None
    base = raw.rstrip("/")
    if base.endswith("/api/v2"):
        base = base[:-7]
    elif base.endswith("/api"):
        base = base[:-4]
    return base or None

__all__ = ["RuntimeState", "ensure_runtime"]