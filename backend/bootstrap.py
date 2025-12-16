# backend/bootstrap.py
from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Awaitable, Optional, cast

from dotenv import load_dotenv, find_dotenv
from contextvars import ContextVar
from zep_cloud.client import AsyncZep
from loguru import logger

from .agent_core import messaging as _messaging
from .agent_core.agents import build_agents
from .agent_core.hma.hma_config import DEFAULT_HMA_CONFIG
from .agent_core.hma.hma import HMA
from .agent_core.tool_reg import setup_tools
from .memory.manager import MemoryManager
from .memory.memory import ZepMemory
from .reset_utils import delete_thread_if_exists, generate_new_id

# --- Globaler Correlation-Id-Context ----------------------------------------
corr_id_var: ContextVar[str] = ContextVar("corr_id", default="no-corr")

# Runtime-Singleton
_runtime_singleton: SimpleNamespace | None = None


# ---- Bootstrap-Helfer: Thread + ZepMemory anlegen --------------------------
async def _ensure_thread(
    zep: AsyncZep,
    *,
    label: str,
    user_id_env: Optional[str],
    thread_id_env: Optional[str],
) -> tuple[str, ZepMemory]:
    """
    Stellt sicher, dass für das gegebene Label ein User + Thread existieren
    und liefert (thread_id, ZepMemory)-Tuple zurück.
    """

    logger.debug(f"🔧 [Bootstrap] Initialisiere Thread-Scope '{label}'…")

    # 1) User-ID bestimmen
    user_id = user_id_env or os.getenv("ZEP_USER_ID") or f"user_{label}"
    tid = thread_id_env

    # 2) Hard Reset aktiv?
    hard_reset = os.getenv("GATEWAY_THREAD_RESET", "0") == "1"
    if hard_reset and tid:
        logger.info(f"🧹 [Bootstrap] Hard-Reset aktiv – lösche bestehenden Thread: {tid}")
        await delete_thread_if_exists(zep, tid)
        tid = None

    # 3) Falls keine Thread-ID → neu generieren
    if not tid:
        tid = f"thread_{label}_{generate_new_id()}"
        logger.info(f"🆕 [Bootstrap] Neue Thread-ID erzeugt: {tid}")

    thread_id = tid

    # 4) User-„Profil“ für Debug / UI
    if label.startswith("t1"):
        first_name = os.getenv("GENERIC_USER_NAME", "User")
        last_name = ""
    else:
        first_name = label.upper()
        last_name = "Agent"

    # 5) User erzeugen (idempotent)
    try:
        await cast(
            Awaitable[object],
            zep.user.add(
                user_id=user_id,
                email=f"{user_id}@example.local",
                first_name=first_name,
                last_name=last_name,
            ),
        )
        logger.debug(f"👤 [Bootstrap] User erzeugt/aktualisiert: {user_id}")
    except Exception:
        logger.debug(f"👤 [Bootstrap] User existiert bereits: {user_id}")

    # 6) Thread erzeugen (idempotent)
    try:
        await cast(
            Awaitable[object],
            zep.thread.create(
                thread_id=thread_id,
                user_id=user_id,
            ),
        )
        logger.debug(f"🧵 [Bootstrap] Thread erzeugt: {thread_id}")
    except Exception:
        logger.debug(f"🧵 [Bootstrap] Thread existiert bereits: {thread_id}")

    # 7) ZepMemory-Wrapper instanziieren
    mem = ZepMemory(
        client=zep,
        user_id=user_id,
        thread_id=thread_id,
    )
    logger.debug(f"📦 [Bootstrap] Memory-Wrapper aktiv: {label} -> {thread_id}")

    return thread_id, mem



# ---- Runtime: Zep, Threads, Tools, HMA -------------------------------------
# ---- Runtime: Zep, Threads, Tools, HMA -------------------------------------
async def ensure_runtime() -> SimpleNamespace:
    """
    Initialisiert Zep-Client, Threads T1..T6, zentrale Tool-Registry,
    MemoryManager (ctx_provider) und den HMA (inkl. Demos).
    Nutzt ein Singleton, damit die Runtime nur einmal aufgebaut wird.
    """
    global _runtime_singleton
    if _runtime_singleton is not None:
        logger.debug("♻️ [Bootstrap] Runtime-Singleton bereits initialisiert – reusing instance.")
        return _runtime_singleton

    logger.info("🚀 [Bootstrap] Initialisiere Gateway-Runtime…")

    # --- ENV / Zep-Client ----------------------------------------------------
    load_dotenv(find_dotenv(usecwd=True))

    model_name = os.getenv("LLM_MODEL", "gpt-4o")
    zep_api_key = os.getenv("ZEP_API_KEY")
    zep_base = os.getenv("ZEP_BASE_URL")

    if not zep_api_key:
        logger.error("❌ [Bootstrap] ZEP_API_KEY fehlt – Backend kann nicht starten.")
        raise RuntimeError("ZEP_API_KEY fehlt")

    if zep_base:
        zep = AsyncZep(api_key=cast(str, zep_api_key), base_url=zep_base)
        logger.info(f"🔌 [Bootstrap] Zep-Client bereit (base_url={zep_base}, model={model_name})")
    else:
        zep = AsyncZep(api_key=cast(str, zep_api_key))
        logger.info(f"🔌 [Bootstrap] Zep-Client bereit (default base_url, model={model_name})")

    # --- Threads & Memories T1..T6 ------------------------------------------
    t1_thread_id, t1_memory = await _ensure_thread(
        zep,
        label="t1_root",
        user_id_env=os.getenv("T1_USER_ID") or os.getenv("ZEP_USER_ID"),
        thread_id_env=os.getenv("T1_THREAD_ID"),
    )

    base_user = os.getenv("T1_USER_ID") or os.getenv("ZEP_USER_ID") or f"user_t1_root"

    t2_thread_id, t2_memory = await _ensure_thread(
        zep,
        label="t2_user_visible",
        user_id_env=base_user,
        thread_id_env=os.getenv("T2_THREAD_ID"),
    )
    t3_thread_id, t3_memory = await _ensure_thread(
        zep,
        label="t3_meta_proto",
        user_id_env=base_user,
        thread_id_env=os.getenv("T3_THREAD_ID"),
    )
    t4_thread_id, t4_memory = await _ensure_thread(
        zep,
        label="t4_lib_internal",
        user_id_env=base_user,
        thread_id_env=os.getenv("T4_THREAD_ID"),
    )
    t5_thread_id, t5_memory = await _ensure_thread(
        zep,
        label="t5_task_internal",
        user_id_env=base_user,
        thread_id_env=os.getenv("T5_THREAD_ID"),
    )
    t6_thread_id, t6_memory = await _ensure_thread(
        zep,
        label="t6_trn_internal",
        user_id_env=base_user,
        thread_id_env=os.getenv("T6_THREAD_ID"),
    )

    logger.info(
        "✅ [Bootstrap] Threads bereit | T1={} T2={} T3={} T4={} T5={} T6={}",
        t1_thread_id,
        t2_thread_id,
        t3_thread_id,
        t4_thread_id,
        t5_thread_id,
        t6_thread_id,
    )

    # --- Tool-Setup über zentrale Registry (tool_reg) ------------------------
    graph_id = os.getenv("ZEP_GRAPH_ID", "gateway_main")
    logger.info(f"🧬 [Bootstrap] Initialisiere Tools & Graph-API (graph_id={graph_id})…")

    tool_ctx = await setup_tools(
        zep=zep,
        base_user=base_user,
        graph_id=graph_id,
    )
    logger.info("🛠️ [Bootstrap] Tools & Graph-API bereit.")

    # --- Runtime-Container (Namespace) --------------------------------------
    runtime_ns = SimpleNamespace(
        # Zep / Graph
        zep_client=zep,
        graph_api_provider=tool_ctx.graph_api_provider,
        get_api=tool_ctx.get_api,
        # Threads / Memories
        t1_thread_id=t1_thread_id,
        t1_memory=t1_memory,
        t2_thread_id=t2_thread_id,
        t2_memory=t2_memory,
        t3_thread_id=t3_thread_id,
        t3_memory=t3_memory,
        t4_thread_id=t4_thread_id,
        t4_memory=t4_memory,
        t5_thread_id=t5_thread_id,
        t5_memory=t5_memory,
        t6_thread_id=t6_thread_id,
        t6_memory=t6_memory,
        # Messaging / Tools
        messaging=_messaging,
        pbuffer_dir=None,
        tools=tool_ctx.tools,
        tool_registry=tool_ctx.tool_registry,
        call_tool=tool_ctx.call_tool,
    )

    # --- Zentrale Memory-Fassade (ctx_provider) -----------------------------
    runtime_ns.memory = MemoryManager(t1_memory, get_api=tool_ctx.get_api)
    runtime_ns.ctx_provider = runtime_ns.memory
    logger.info("🧠 [Bootstrap] MemoryManager als ctx_provider registriert.")

    # GraphAPI in alle ZepMemory-Instanzen injizieren
    for mem in (t1_memory, t2_memory, t3_memory, t4_memory, t5_memory, t6_memory):
        try:
            mem.set_api(tool_ctx.get_api)
        except Exception:
            logger.debug("ℹ️ [Bootstrap] ZepMemory-Instanz unterstützt set_api nicht (legacy-Version?).")

    # --- Demo-Agenten + HMA in einem Block bauen ----------------------------
    logger.debug("🤖 [Bootstrap] Baue Demo-Agenten & LLM-Client…")
    demo_registry, llm_client = build_agents(
        model_name=model_name,
        call_tool=tool_ctx.call_tool,
    )
    runtime_ns.demo_registry = demo_registry
    runtime_ns.llm_client = llm_client

    logger.debug("🧩 [Bootstrap] Initialisiere HMA…")
    runtime_ns.hma = HMA(
        som_system_prompt=DEFAULT_HMA_CONFIG.som_system_prompt,
        templates=DEFAULT_HMA_CONFIG,
        demos=demo_registry,
        messaging=runtime_ns.messaging,
        llm=llm_client,
        ctx_provider=runtime_ns.ctx_provider,
        runtime=runtime_ns,
    )

    logger.info("🤖 [Bootstrap] Agenten & HMA bereit.")

    # --- Singleton setzen und zurückgeben -----------------------------------
    _runtime_singleton = runtime_ns
    globals()["_runtime_singleton"] = _runtime_singleton

    logger.info("🏁 [Bootstrap] Gateway-Runtime vollständig initialisiert.")
    return _runtime_singleton
