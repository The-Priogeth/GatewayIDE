# backend/bootstrap.py  — Slim-kompatibel zu konstruktor/hma/selectors/routing
from __future__ import annotations
import os, asyncio
from types import SimpleNamespace
from typing import Any, Awaitable, Optional, cast

from dotenv import load_dotenv, find_dotenv
from zep_cloud.client import AsyncZep
from autogen_core.memory import MemoryContent, MemoryMimeType

from backend.zep_autogen import ZepUserMemory
from backend.agent_core.konstruktor import build_hma
from backend.agent_core import messaging as _messaging

# ---- Kleine Adapter ----------------------------------------------------------
class LLMAdapter:
    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model

    def completion(self, *, system: str, prompt: str) -> str:
        # Einfacher Heuristik-Finalizer:
        # - nimm aus dem Final-Prompt den Block "# Interner Zwischenstand\n ... "
        # - picke die erste "## DemoName\nAntwort" als Kurzantwort
        import re
        m = re.search(r"# Interner Zwischenstand\s+(.+?)\n\n# Anweisung", prompt, flags=re.DOTALL)
        inner = (m.group(1).strip() if m else "").split("\n\n")
        short = ""
        for block in inner:
            if block.strip().startswith("## "):
                # nimm die erste inhaltliche Zeile nach der Überschrift
                lines = block.splitlines()
                short = "\n".join(lines[1:]).strip()
                break
        short = (short[:280] + "…") if len(short) > 280 else (short or "Okay.")
        return short + '\n<<<ROUTE>>> {"deliver_to":"user","args":{}} <<<END>>>'

class DemoAdapter:
    """
    Adapter um AG2-ConversableAgent wie Demos mit .run(user_text, context) zu nutzen.
    """
    def __init__(self, agent) -> None:
        self.agent = agent
        self.name = getattr(agent, "name", agent.__class__.__name__)

    def run(self, *, user_text: str, context: str) -> str:
        # Übergibt Kontext kompakt als System-Einleitung; je nach AG2-Setup ggf. anders
        sys = f"[Kontext]\n{context}\n\n[Aufgabe]\n{user_text}"
        out = self.agent.generate_reply(messages=[{"role": "user", "content": sys}], sender=None)
        # tolerant normalisieren (AG2 liefert je nach Config tuple/bool+resp etc.)
        if isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], (bool, type(None))):
            _, rep = out
            return str(rep)
        return str(out)

# ---- Bootstrap-Helfer --------------------------------------------------------
async def _ensure_thread(
    zep: AsyncZep,
    *, label: str,
    user_id_env: Optional[str],
    thread_id_env: Optional[str],
) -> tuple[str, ZepUserMemory]:
    user_id = user_id_env or os.getenv("ZEP_USER_ID") or f"user_{label}"
    thread_id = thread_id_env or f"thread_{label}"

    first_name = os.getenv("GENERIC_USER_NAME", "User") if label.startswith("t1") else label.upper()
    last_name  = "" if label.startswith("t1") else "Agent"
    try:
        await cast(Awaitable[object], zep.user.add(
            user_id=user_id,
            email=f"{user_id}@example.local",
            first_name=first_name,
            last_name=last_name,
        ))
    except Exception:
        pass
    try:
        await cast(Awaitable[object], zep.thread.create(thread_id=thread_id, user_id=user_id))
    except Exception:
        pass

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

# ---- Runtime ---------------------------------------------------------------
_runtime_singleton: SimpleNamespace | None = None

async def ensure_runtime() -> SimpleNamespace:
    """
    Initialisiert Zep-Client, Threads T1..T6, ContextProvider, Demos (AG2) + HMA (Slim).
    """
    global _runtime_singleton
    if _runtime_singleton is not None:
        return _runtime_singleton

    load_dotenv(find_dotenv(usecwd=True))
    model_name  = os.getenv("LLM_MODEL", "gpt-4o")
    zep_api_key = os.getenv("ZEP_API_KEY")
    zep_base    = os.getenv("ZEP_BASE_URL")
    if not zep_api_key:
        raise RuntimeError("ZEP_API_KEY fehlt")

    zep = AsyncZep(api_key=cast(str, zep_api_key), base_url=zep_base) if zep_base else AsyncZep(api_key=cast(str, zep_api_key))

    # Threads & Memories
    t1_thread_id, t1_memory = await _ensure_thread(
        zep, label="t1_root",
        user_id_env=os.getenv("T1_USER_ID") or os.getenv("ZEP_USER_ID"),
        thread_id_env=os.getenv("T1_THREAD_ID"),
    )
    base_user = os.getenv("T1_USER_ID") or os.getenv("ZEP_USER_ID")
    t2_thread_id, t2_memory = await _ensure_thread(zep, label="t2_user_visible", user_id_env=base_user, thread_id_env=os.getenv("T2_THREAD_ID"))
    t3_thread_id, t3_memory = await _ensure_thread(zep, label="t3_meta_proto",   user_id_env=base_user, thread_id_env=os.getenv("T3_THREAD_ID"))
    t4_thread_id, t4_memory = await _ensure_thread(zep, label="t4_lib_internal", user_id_env=base_user, thread_id_env=os.getenv("T4_THREAD_ID"))
    t5_thread_id, t5_memory = await _ensure_thread(zep, label="t5_task_internal", user_id_env=base_user, thread_id_env=os.getenv("T5_THREAD_ID"))
    t6_thread_id, t6_memory = await _ensure_thread(zep, label="t6_trn_internal",  user_id_env=base_user, thread_id_env=os.getenv("T6_THREAD_ID"))

    ctx_provider = ContextProvider(zep=zep, thread_id=t1_thread_id, mode="summary")
    await ctx_provider.refresh()

    # Demos (AG2) bauen und mit DemoAdapter wrappen
    from backend.ag2.autogen.agentchat import ConversableAgent
    llm_cfg: dict[str, Any] = {"model": model_name}  # bleibt für AG2-Demos relevant

    raw_demos = [
        ConversableAgent(name="PersonalAgent",
            system_message=(
                "Ich bin der persönliche Assistent. "
                "Ich merke mir stabile, nicht-flüchtige Fakten über den Nutzer (z.B. Name, Präferenzen). "
                "Antworte kurz."
            ),
            llm_config=llm_cfg, human_input_mode="NEVER"
        ),
        ConversableAgent(name="DemoTherapist",  system_message="Kurz, empathisch.",          llm_config=llm_cfg, human_input_mode="NEVER"),
        ConversableAgent(name="DemoProgrammer", system_message="Senior-Engineer, präzise.",  llm_config=llm_cfg, human_input_mode="NEVER"),
        ConversableAgent(name="DemoStrategist", system_message="Strukturiert, priorisiert.", llm_config=llm_cfg, human_input_mode="NEVER"),
        ConversableAgent(name="DemoCritic",     system_message="Kritischer Prüfer.",         llm_config=llm_cfg, human_input_mode="NEVER"),
    ]
    demo_registry = [DemoAdapter(a) for a in raw_demos]

    # (Optional) einfacher Memory-Logger für T1 – bleibt wie gehabt
    def memory_logger(role: str, name: str, content: str) -> None:
        async def _w():
            try:
                if str(role).lower() == "user":
                    text = str(content)
                    await t1_memory.add(MemoryContent(
                        content=text,
                        mime_type=MemoryMimeType.TEXT,
                        metadata={"type": "message", "role": role, "name": name, "thread": "T1"},
                    ))
                    # Mini-Name-Extractor
                    import re
                    m = re.search(r"\bmein\s+name\s+ist\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{2,})\b", text, flags=re.IGNORECASE)
                    if m:
                        user_name = m.group(1).strip()
                        await t1_memory.add(MemoryContent(
                            content=f"Merke: Der Nutzer heißt {user_name}.",
                            mime_type=MemoryMimeType.TEXT,
                            metadata={"type": "message", "role": "system", "name": "Profile", "thread": "T1"},
                        ))
                await ctx_provider.refresh()
            except Exception:
                pass
        asyncio.create_task(_w())

    # LLM-Client (Adapter) für HMA
    llm_client = LLMAdapter(model=model_name)

    # HMA bauen (Slim-Signatur!)
    hma = build_hma(demo_registry=demo_registry, llm_client=llm_client)



    _runtime_singleton = SimpleNamespace(
        zep_client=zep,
        t1_thread_id=t1_thread_id, t1_memory=t1_memory,
        t2_thread_id=t2_thread_id, t2_memory=t2_memory,
        t3_thread_id=t3_thread_id, t3_memory=t3_memory,
        t4_thread_id=t4_thread_id, t4_memory=t4_memory,
        t5_thread_id=t5_thread_id, t5_memory=t5_memory,
        t6_thread_id=t6_thread_id, t6_memory=t6_memory,
        ctx_provider=ctx_provider,
        hma=hma,                     # <-- direkte Instanz, nicht dict
        messaging=_messaging,        # <-- bereitstellen, damit main.py nicht crasht
        pbuffer_dir=None,            # <-- Platzhalter (oder realen Pfad setzen)
        memory_logger=memory_logger,
    )
    globals()["_runtime_singleton"] = _runtime_singleton
    return _runtime_singleton
