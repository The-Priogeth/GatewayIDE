# backend/bootstrap.py
from __future__ import annotations
import os, asyncio
from types import SimpleNamespace
from typing import Any, Awaitable, Optional, cast
from dotenv import load_dotenv, find_dotenv
from contextvars import ContextVar
from zep_cloud.client import AsyncZep
from autogen_core.memory import MemoryContent, MemoryMimeType
from autogen_core.tools import FunctionTool  # nur für Typ-Hinweise
from .agent_core import messaging as _messaging
from .agent_core.hma.hma_config import DEFAULT_HMA_CONFIG
from .agent_core.hma.hma import HMA
from .agent_core.hma.speaker import Speaker
from .memory.graph_api import GraphAPIProvider
from .memory.manager import MemoryManager
from .memory.memory import ZepMemory
from .memory.memory_tools import (
    create_search_graph_tool,
    create_add_graph_data_tool,
    create_set_ontology_tool,
    create_add_node_tool,
    create_add_edge_tool,
    create_clone_graph_tool,
    create_clone_user_graph_tool,
    create_get_graph_item_tool,
    create_get_node_edges_tool,
    create_delete_edge_tool,
    create_delete_episode_tool,
)

# global
corr_id_var: ContextVar[str] = ContextVar("corr_id", default="no-corr")

# ---- Kleine Adapter ----------------------------------------------------------
class LLMAdapter:
    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model

    def _route_by_intent(self, prompt_text: str, inner: str) -> str:
        t = f"{prompt_text}\n{inner}".lower()
        task_keys = [
            # EN
            "build", "compose", "docker", "fix", "error", "compile", "traceback", "log", "image", "container", "script",
            # DE
            "baue", "bauen", "fixe", "fixen", "fehler", "kompilier", "kompiliere",
            "protokoll", "skript", "erstelle code", "schreibe code",
            "implementier", "implementiere"
        ]
        lib_keys  = ["quelle", "primärquelle", "paper", "studie", "zitat", "zitier", "source", "doku", "dokumentation", "referenz"]
        trn_keys  = ["lerne", "trainiere", "übe", "routine", "feedback", "review mich", "kritisier mich", "reflexion"]

        if any(k in t for k in task_keys): return "task"
        if any(k in t for k in lib_keys):  return "lib"
        if any(k in t for k in trn_keys):  return "trn"
        return "user"

    def completion(self, *, system: str, prompt: str) -> str:
        import re
        # 1) inner material ziehen
        m = re.search(r"# Interner Zwischenstand\s+(.+?)\n\n# Anweisung", prompt, flags=re.DOTALL)
        inner_block = m.group(1).strip() if m else ""
        inner_chunks = inner_block.split("\n\n") if inner_block else []

        # 2) erste brauchbare Zeile aus Demos
        short = ""
        for block in inner_chunks:
            if block.strip().startswith("## "):
                lines = [l for l in block.splitlines()[1:] if l.strip()]
                if lines:
                    short = lines[0].strip()
                    break

        # 3) kleiner Wahrheitsanker: Name
        p_low = prompt.lower()
        if "aaron lindsay" in p_low and "wie heiße ich" in p_low:
            short = "Du heißt Aaron Lindsay."

        # 4) Fallback + Kürzung
        short = (short[:280] + "…") if len(short) > 280 else (short or "Okay.")

        # 5) Intent über den gesamten Prompt
        target = self._route_by_intent(prompt, inner_block)

        return f"{short}\n<<<ROUTE>>> {{\"deliver_to\":\"{target}\",\"args\":{{}}}} <<<END>>>"

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
) -> tuple[str, ZepMemory]: #from ZepUserMemory to ZepMemory
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

    mem = ZepMemory(
        client=zep,
        user_id=user_id,
        thread_id=thread_id,
        # thread_context_mode="summary", #from ZepUserMemory to ZepMemory
    )
    return thread_id, mem



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

    # --- Tool-Setup: zentraler GraphAPI-Provider + get_api Callback ----------
    GRAPH_ID = os.getenv("ZEP_GRAPH_ID", "gateway_main")
    provider = GraphAPIProvider(client=zep, graph_id=GRAPH_ID, user_id=base_user)
    get_api = provider.get_api

    tools: list[FunctionTool] = [
        create_search_graph_tool(get_api),
        create_add_graph_data_tool(get_api),
        create_set_ontology_tool(get_api),
        create_add_node_tool(get_api),
        create_add_edge_tool(get_api),
        create_clone_graph_tool(get_api),
        create_clone_user_graph_tool(get_api),
        create_get_graph_item_tool(get_api),
        create_get_node_edges_tool(get_api),
        create_delete_edge_tool(get_api),
        create_delete_episode_tool(get_api),
    ]
    tool_registry: dict[str, FunctionTool] = {t.name: t for t in tools}

    async def call_tool(name: str, /, **kwargs):
        """
        Einheitlicher Aufruf für registrierte FunctionTools.
        Nutzt bevorzugt .func (async), fällt auf .invoke(**kwargs) zurück.
        """
        tool = tool_registry.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        fn = getattr(tool, "func", None)
        if callable(fn):
            res = fn(**kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        inv = getattr(tool, "invoke", None)
        if callable(inv):
            res = inv(kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        raise RuntimeError(f"Tool {name} has neither async func nor invoke")

    # Demos (AG2) bauen und mit DemoAdapter wrappen
    from .ag2.autogen.agentchat import ConversableAgent
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


    # LLM-Client (Adapter) für HMA
    llm_client = LLMAdapter(model=model_name)


    runtime_ns = SimpleNamespace(
        zep_client=zep,
        graph_api_provider=provider,
        get_api=get_api,
        t1_thread_id=t1_thread_id, t1_memory=t1_memory,
        t2_thread_id=t2_thread_id, t2_memory=t2_memory,
        t3_thread_id=t3_thread_id, t3_memory=t3_memory,
        t4_thread_id=t4_thread_id, t4_memory=t4_memory,
        t5_thread_id=t5_thread_id, t5_memory=t5_memory,
        t6_thread_id=t6_thread_id, t6_memory=t6_memory,
        messaging=_messaging,
        pbuffer_dir=None,
        tools=tools,
        tool_registry=tool_registry,
        call_tool=call_tool,
    )
    # zentrale Memory-Fassade (einheitlicher Einstiegspunkt)
    runtime_ns.memory = MemoryManager(t1_memory, get_api=get_api)

    # ---- WICHTIG: GraphAPI in alle ZepMemory-Instanzen injizieren ----------
    # Dadurch verwenden T1..T6 ausschließlich die zentrale, persistente Instanz.
    for mem in (t1_memory, t2_memory, t3_memory, t4_memory, t5_memory, t6_memory):
        try:
            mem.set_api(get_api)
        except Exception:
            pass

    # 2) HMA direkt hier konstruieren (reduziert Abhängigkeiten)
    speaker = Speaker(runtime=runtime_ns)
    runtime_ns.hma = HMA(
        som_system_prompt=DEFAULT_HMA_CONFIG.som_system_prompt,
        templates=DEFAULT_HMA_CONFIG,
        demos=demo_registry,
        messaging=runtime_ns.messaging,
        llm=llm_client,
        speaker=speaker,
        ctx_provider=runtime_ns.t1_memory,
    )

    # 3) Singleton zuweisen und zurückgeben
    _runtime_singleton = runtime_ns
    globals()["_runtime_singleton"] = _runtime_singleton
    return _runtime_singleton