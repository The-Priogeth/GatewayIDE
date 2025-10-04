"""
core.py — Zep v3 + AG2 (lokales Repo unter backend/ag2) mit CaptainAgent-Memory-Hooks

Voraussetzung: Deine CaptainAgent-Datei ist wie besprochen gepatcht und nimmt
optionale Hooks entgegen:
  - memory_context_provider: Callable[[], str]
  - memory_logger: Callable[[str, str, str], None]

Ablauf:
- .env laden → Keys auslesen
- Zep Async-Client → User + Thread
- ZepUserMemory zum Persistieren
- Drei CaptainAgents (Historiker/Analyst/Moderator), KEIN memory=[] Param
- Vor jeder Interaktion: aktuellen Zep-Kontext ziehen und via Hook injizieren
- Chat wird SNYC über UserProxyAgent gestartet (per to_thread, blockiert Eventloop nicht)
- Antworten werden per memory_logger in Zep persistiert und lokal gesammelt

Install:
    pip install "ag2[openai,captainagent]" zep-cloud zep-autogen python-dotenv

Start:
    python backend/core.py  (falls du diese Datei als backend/core.py speicherst)
"""
from __future__ import annotations

import os
import uuid
import asyncio
from typing import Dict

from dotenv import load_dotenv, find_dotenv
from zep_cloud.client import AsyncZep
from zep_autogen import ZepUserMemory
from autogen_core.memory import MemoryContent, MemoryMimeType

# AG2 aus lokalem Repo unter backend/ag2 nutzen
from ag2.autogen.agentchat.contrib.captainagent import CaptainAgent
from ag2.autogen.agentchat.user_proxy_agent import UserProxyAgent
from ag2.autogen import LLMConfig

# -----------------------------
# Utilities
# -----------------------------

def _require_env(var_name: str) -> str:
    val = os.getenv(var_name)
    if not val:
        raise RuntimeError(f"Umgebungsvariable {var_name} fehlt.")
    return val


# -----------------------------
# Hauptablauf
# -----------------------------
async def main() -> None:
    # .env laden
    load_dotenv(find_dotenv(usecwd=True))

    # Keys/Model
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_api_key = _require_env("OPENAI_API_KEY")
    zep_api_key = _require_env("ZEP_API_KEY")
    zep_base_url = os.getenv("ZEP_BASE_URL")

    # Zep-Client
    zep = AsyncZep(api_key=zep_api_key, base_url=zep_base_url) if zep_base_url else AsyncZep(api_key=zep_api_key)

    # User & Thread
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    thread_id = f"thread_{uuid.uuid4().hex[:16]}"

    await zep.user.add(
        user_id=user_id,
        email=f"{user_id}@example.local",
        first_name="Demo",
        last_name="User",
    )
    await zep.thread.create(thread_id=thread_id, user_id=user_id)

    # Zep-Memory (Persistenz)
    memory = ZepUserMemory(client=zep, user_id=user_id, thread_id=thread_id, thread_context_mode="summary")

    # llm_config pro Agent
    llm_cfg = LLMConfig(
        api_type="openai",
        config_list=[{
            "model": openai_model,
            "api_key": openai_api_key,
            # optional: "temperature": 0.2,
        }],
        # optional global defaults:
        # temperature=0.2,
    )

    # Systemprompts
    base_sys_hist = ("Du bist 'Historiker': "
                     "Erkläre Hintergründe, Ursachen und zeitliche Einordnung sachlich.")
    base_sys_analyst = ("Du bist 'Analyst': "
                        "Ergänze Lücken, prüfe Logik und nenne wichtige Konsequenzen.")
    base_sys_mod = ("Du bist 'Moderator': "
                    "Fasse die Kernaussagen klar und prägnant zusammen.")

    # Antworten sammeln (aus memory_logger)
    responses: Dict[str, str] = {"Historiker": "", "Analyst": "", "Moderator": ""}

    # Logger-Fabrik, die in Zep persistiert + lokal mitschreibt
    def make_memory_logger(label: str):
        def _logger(role: str, name: str, content: str):
            # Persistieren (async fire-and-forget)
            asyncio.get_event_loop().create_task(
                memory.add(MemoryContent(
                    content=content,
                    mime_type=MemoryMimeType.TEXT,
                    metadata={"type": "message", "role": role, "name": label},
                ))
            )
            # Lokale Antwort für die Konsole
            if role == "assistant":
                responses[label] = content
        return _logger

    # Kontext-Provider: liest jeweils die zuletzt ermittelte context_text-Variable (pro Run gesetzt)
    context_text = ""
    def context_provider() -> str:
        return context_text

    # Drei CaptainAgents (nutzen die Hooks)
    agent1 = CaptainAgent(
        name="Historiker",
        system_message=base_sys_hist,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
        memory_context_provider=context_provider,
        memory_logger=make_memory_logger("Historiker"),
    )
    agent2 = CaptainAgent(
        name="Analyst",
        system_message=base_sys_analyst,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
        memory_context_provider=context_provider,
        memory_logger=make_memory_logger("Analyst"),
    )
    agent3 = CaptainAgent(
        name="Moderator",
        system_message=base_sys_mod,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
        memory_context_provider=context_provider,
        memory_logger=make_memory_logger("Moderator"),
    )

    # UserProxy für den Start der Chats (SYNC-API → in Thread ausführen)
    user = UserProxyAgent(name="User", human_input_mode="NEVER", llm_config=False, code_execution_config=False)

    # Demo-Query
    user_query = "Was waren zentrale Ursachen und wesentliche Folgen des Zweiten Weltkriegs?"
    print(f"\n[User] {user_query}")
    await memory.add(MemoryContent(content=user_query, mime_type=MemoryMimeType.TEXT,
                                   metadata={"type": "message", "role": "user", "name": "DemoUser"}))

    async def initiate_with(agent, label: str, base_prompt: str):
        nonlocal context_text
        # Frischen Zep-Kontext holen und für den Hook bereitstellen
        ctx = await zep.thread.get_user_context(thread_id=thread_id, mode="summary")
        context_text = (ctx.context or "").strip()
        # Sync-Aufruf in Thread ausführen
        await asyncio.to_thread(user.initiate_chat, agent, message=user_query)
        # Konsole
        if responses[label]:
            print(f"\n[{label}]\n{responses[label]}")

    # Drei Läufe
    await initiate_with(agent1, "Historiker", base_sys_hist)
    await memory.add(MemoryContent(content=responses["Historiker"], mime_type=MemoryMimeType.TEXT,
                                   metadata={"type": "message", "role": "assistant", "name": "Historiker"}))

    await initiate_with(agent2, "Analyst", base_sys_analyst)
    await memory.add(MemoryContent(content=responses["Analyst"], mime_type=MemoryMimeType.TEXT,
                                   metadata={"type": "message", "role": "assistant", "name": "Analyst"}))

    await initiate_with(agent3, "Moderator", base_sys_mod)
    await memory.add(MemoryContent(content=responses["Moderator"], mime_type=MemoryMimeType.TEXT,
                                   metadata={"type": "message", "role": "assistant", "name": "Moderator"}))

    # Zusammenfassung aus Zep
    final_ctx = await zep.thread.get_user_context(thread_id=thread_id, mode="summary")
    print("\n[Zep-Kontext-Summary]\n" + (final_ctx.context or "<leer>"))


if __name__ == "__main__":
    asyncio.run(main())
