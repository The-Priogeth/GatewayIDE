# backend/bootstrap.py
from __future__ import annotations
import os, uuid, asyncio
from types import SimpleNamespace
from typing import Any, Awaitable, cast
from dotenv import load_dotenv, find_dotenv
from zep_cloud.client import AsyncZep

from backend.zep_autogen import ZepUserMemory
from autogen_core.memory import MemoryContent, MemoryMimeType

from backend.agent_core.konstruktor import build_hma
from backend.agent_core.hma_config import DEFAULT_HMA_CONFIG

from backend.agent_core.messaging import (
    MessagingRouter, DeliverTo, PBuffer, MemorySink, Transport
)

from backend.ag2.autogen.agentchat import ConversableAgent
from backend.agent_core.managers.taskmanager import MetaAgentTaskManager
from backend.agent_core.managers.librarian   import MetaAgentLibrarian
from backend.agent_core.managers.trainer     import MetaAgentTrainer


async def _setup_thread(zep: AsyncZep, *, label: str) -> tuple[str, ZepUserMemory]:
    user_id = f"{label}_{uuid.uuid4().hex[:6]}"
    thread_id = f"thread_{label}_{uuid.uuid4().hex[:6]}"
    await cast(Awaitable[object], zep.user.add(
        user_id=user_id,
        email=f"{user_id}@example.local",
        first_name=label.upper(),
        last_name="Channel",
    ))
    await cast(Awaitable[object], zep.thread.create(thread_id=thread_id, user_id=user_id))
    mem = ZepUserMemory(
        client=zep,
        user_id=user_id,
        thread_id=thread_id,
        thread_context_mode="summary",
    )
    return thread_id, mem


class ContextProvider:
    def __init__(self, *, zep: AsyncZep, thread_id: str, mode: str = "summary") -> None:
        self._zep = zep
        self._thread_id = thread_id
        self._mode = mode
        self._summary: str = ""

    async def refresh(self) -> None:
        try:
            ctx = await self._zep.thread.get_user_context(thread_id=self._thread_id, mode=self._mode)
            self._summary = (ctx.context or "").strip()
        except Exception:
            pass

    def get(self) -> str:
        return self._summary

    def update(self, text: str) -> None:
        self._summary = (text or "").strip()


_runtime_singleton: SimpleNamespace | None = None

async def ensure_runtime() -> SimpleNamespace:
    global _runtime_singleton
    if _runtime_singleton is not None:
        return _runtime_singleton

    load_dotenv(find_dotenv(usecwd=True))
    llm_model    = os.getenv("LLM_MODEL", "gpt-4o")
    zep_api_key  = os.getenv("ZEP_API_KEY")
    zep_base_url = os.getenv("ZEP_BASE_URL")
    if not zep_api_key:
        raise RuntimeError("ZEP_API_KEY fehlt")

    zep = AsyncZep(api_key=cast(str, zep_api_key), base_url=zep_base_url) if zep_base_url else AsyncZep(api_key=cast(str, zep_api_key))

    t1_thread_id, t1_memory = await _setup_thread(zep, label="t1_root")
    ctx_provider = ContextProvider(zep=zep, thread_id=t1_thread_id, mode="summary")
    await ctx_provider.refresh()

    t2_thread_id, t2_memory = await _setup_thread(zep, label="t2_user_visible")
    t3_thread_id, t3_memory = await _setup_thread(zep, label="t3_meta_proto")
    t4_thread_id, t4_memory = await _setup_thread(zep, label="t4_lib_internal")
    t5_thread_id, t5_memory = await _setup_thread(zep, label="t5_task_internal")
    t6_thread_id, t6_memory = await _setup_thread(zep, label="t6_trn_internal")

    llm_cfg: dict[str, Any] = {"model": llm_model}

    demos = [
        ConversableAgent(name="DemoTherapist",  system_message="Kurz, empathisch.",          llm_config=llm_cfg, human_input_mode="NEVER"),
        ConversableAgent(name="DemoProgrammer", system_message="Senior-Engineer, präzise.",  llm_config=llm_cfg, human_input_mode="NEVER"),
        ConversableAgent(name="DemoStrategist", system_message="Strukturiert, priorisiert.", llm_config=llm_cfg, human_input_mode="NEVER"),
        ConversableAgent(name="DemoCritic",     system_message="Kritischer Prüfer.",         llm_config=llm_cfg, human_input_mode="NEVER"),
    ]

    meta_lib  = MetaAgentLibrarian(  name="Librarian",   llm_config=llm_cfg, human_input_mode="NEVER")
    meta_task = MetaAgentTaskManager(name="TaskManager", llm_config=llm_cfg, human_input_mode="NEVER")
    meta_trn  = MetaAgentTrainer(    name="Trainer",     llm_config=llm_cfg, human_input_mode="NEVER")

    async def _call_agent_and_persist(agent, *, text: str, mem: ZepUserMemory, agent_name: str, thread_label: str):
        await mem.add(MemoryContent(
            content=text, mime_type=MemoryMimeType.TEXT,
            metadata={"type":"message","role":"assistant","name":"HMA","channel":"inbound"}
        ))
        out = agent.generate_reply(messages=[{"role":"user","content":text}], sender=None)
        # tolerant normalisieren
        if isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], (bool, type(None))):
            _, rep = out
            text_out = str(rep)
        else:
            text_out = str(out)
        await mem.add(MemoryContent(
            content=text_out, mime_type=MemoryMimeType.TEXT,
            metadata={"type":"message","role":"assistant","name":agent_name,"channel":"outbound"}
        ))
        return text_out

    def to_user(text: str) -> None:
        return None

    def to_task(text: str) -> None:
        asyncio.create_task(_call_agent_and_persist(meta_task, text=text, mem=t5_memory, agent_name="TaskManager", thread_label="T5"))

    def to_lib(text: str) -> None:
        asyncio.create_task(_call_agent_and_persist(meta_lib,  text=text, mem=t4_memory, agent_name="Librarian",   thread_label="T4"))

    def to_trn(text: str) -> None:
        asyncio.create_task(_call_agent_and_persist(meta_trn,  text=text, mem=t6_memory, agent_name="Trainer",     thread_label="T6"))

    transport = Transport(
        to_user=to_user,
        to_task=to_task,
        to_lib=to_lib,
        to_trn=to_trn,
    )

    PBUFFER_DIR = os.getenv("PBUFFER_DIR", "/app/pbuffer")
    pbuffer = PBuffer(dirpath=PBUFFER_DIR)

    sink_t1 = MemorySink(thread_id=t1_thread_id, memory=t1_memory)
    sink_t2 = MemorySink(thread_id=t2_thread_id, memory=t2_memory)
    sink_t3 = MemorySink(thread_id=t3_thread_id, memory=t3_memory)

    messaging = MessagingRouter(
        pbuffer=pbuffer,
        sink_t1=sink_t1,
        sink_t2=sink_t2,
        sink_t3=sink_t3,
        transport=transport,
    )

    def memory_logger(role: str, name: str, content: str) -> None:
        async def _w():
            try:
                # Nur USER-Eingaben oder explizite T1-Dialogeinträge verbleiben in T1.
                # Interne Assistant-/SOM-Logs bitte nicht nach T1 kippen.
                if str(role).lower() == "user":
                    await t1_memory.add(MemoryContent(
                        content=str(content),
                        mime_type=MemoryMimeType.TEXT,
                        metadata={"type": "message", "role": role, "name": name, "thread": "T1"},
                    ))
                await ctx_provider.refresh()
            except Exception:
                pass
        asyncio.create_task(_w())

    hma_pack = build_hma(
        llm_config=llm_cfg,
        demo_profiles=demos,
        lobby_agents=[meta_task, meta_lib, meta_trn],
        hma_config=DEFAULT_HMA_CONFIG,
        memory_context_provider=ctx_provider.get,
        memory_logger=memory_logger,
        messaging=messaging,
    )

    _runtime_singleton = SimpleNamespace(
        zep_client=zep,
        t1_thread_id=t1_thread_id, t1_memory=t1_memory,
        t2_thread_id=t2_thread_id, t2_memory=t2_memory,
        t3_thread_id=t3_thread_id, t3_memory=t3_memory,
        t4_thread_id=t4_thread_id, t4_memory=t4_memory,
        t5_thread_id=t5_thread_id, t5_memory=t5_memory,
        t6_thread_id=t6_thread_id, t6_memory=t6_memory,
        ctx_provider=ctx_provider,
        hma=hma_pack,
        messaging=messaging,
        meta_task=meta_task, meta_lib=meta_lib, meta_trn=meta_trn,
        pbuffer_dir=PBUFFER_DIR,
    )
    return _runtime_singleton
