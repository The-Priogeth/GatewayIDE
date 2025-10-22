# backend/main.py — FastAPI entrypoint (HMA v2 kompatibel)
from __future__ import annotations
import os, time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import cast
from loguru import logger
from fastapi import FastAPI
from pydantic import BaseModel

from autogen_core.memory import MemoryContent, MemoryMimeType

from backend import bootstrap
from backend.routes.websocket import start_watcher


# -----------------------------------------------------------------------------#
# 🌍 Environment / Logging Setup
# -----------------------------------------------------------------------------#
os.environ.setdefault("TZ", "Europe/Berlin")
_tzset = getattr(time, "tzset", None)
if callable(_tzset):
    _tzset()

LOG_PATH = os.getenv("LOG_PATH", "logs")
LOG_ROTATION = os.getenv("LOG_ROTATION", "25 MB")
LOG_RETENTION = os.getenv("LOG_RETENTION")  # None → keep forever
LOG_DIAGNOSE = os.getenv("LOG_DIAGNOSE", "true").lower() == "true"

try:
    os.makedirs(LOG_PATH, exist_ok=True)
    logger.add(
        os.path.join(LOG_PATH, "server.log"),
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION if LOG_RETENTION else None,
        backtrace=False,
        diagnose=LOG_DIAGNOSE,
        enqueue=True,
    )
except Exception:
    pass


# -----------------------------------------------------------------------------#
# ⚙️ Lifespan: Runtime initialisieren
# -----------------------------------------------------------------------------#
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialisiert beim App-Start das gesamte Laufzeitsystem:
    - Lädt Keys & Modelle über bootstrap.ensure_runtime()
    - Erstellt Zep-Client, Threads T1..T6, HMA, ContextProvider, Messaging
    - Startet Dateiwächter für Hot-Reload (optional)
    """
    runtime = await bootstrap.ensure_runtime()

    # Gemeinsamer App-State für alle Endpoints
    app.state.runtime       = runtime
    app.state.zep_client    = runtime.zep_client

    # Threads/Memories (Naming aus bootstrap.ensure_runtime)
    app.state.t1_thread_id  = runtime.t1_thread_id
    app.state.t1_memory     = runtime.t1_memory
    app.state.t2_thread_id  = runtime.t2_thread_id
    app.state.t3_thread_id  = runtime.t3_thread_id
    app.state.t4_thread_id  = runtime.t4_thread_id
    app.state.t5_thread_id  = runtime.t5_thread_id
    app.state.t6_thread_id  = runtime.t6_thread_id

    app.state.ctx_provider  = runtime.ctx_provider
    app.state.hma_pack      = runtime.hma               # dict: {"hma": HauptMetaAgent, "context_provider": ...}
    app.state.messaging     = runtime.messaging
    app.state.pbuffer_dir   = runtime.pbuffer_dir

    logger.info(
        "✅ Runtime ready | T1={} T2={} T3={} T4={} T5={} T6={}",
        app.state.t1_thread_id, app.state.t2_thread_id, app.state.t3_thread_id,
        app.state.t4_thread_id, app.state.t5_thread_id, app.state.t6_thread_id
    )

    watcher_thread = watcher_stop = None
    try:
        backend_dir = str(Path(__file__).resolve().parent)
        watcher_thread, watcher_stop = start_watcher(path=backend_dir)
        yield
    finally:
        try:
            if watcher_stop: watcher_stop.set()
            if watcher_thread: watcher_thread.join(timeout=5)
        except Exception:
            pass
        logger.info("🧹 Shutdown complete.")


# -----------------------------------------------------------------------------#
# 🚀 FastAPI App-Definition
# -----------------------------------------------------------------------------#
app: FastAPI = FastAPI(
    lifespan=lifespan,
    title="Gateway API",
    description="Modulare KI-Agentenplattform (HMA mit innerem SOM und direkter Funktionsansprache)",
    version="2.12",
)


# -----------------------------------------------------------------------------#
# 💬 /chat — Zentrale Schnittstelle für User-Eingaben aus der IDE
# -----------------------------------------------------------------------------#
class ChatRequest(BaseModel):
    prompt: str


@app.post("/chat")
async def chat(req: ChatRequest):
    rt = app.state.runtime
    zep = rt.zep_client
    t1_mem = rt.t1_memory
    ctxprov = rt.ctx_provider
    hma = rt.hma["hma"]  # HauptMetaAgent-Instanz

    # 1) User-Prompt in T1 schreiben
    await t1_mem.add(
        MemoryContent(
            content=req.prompt,
            mime_type=MemoryMimeType.TEXT,
            metadata={"type": "message", "role": "user", "name": "User", "thread": "T1"},
        )
    )

    # 2) Context aktualisieren (Summary aus T1)
    try:
        ctx = await zep.thread.get_user_context(thread_id=cast(str, rt.t1_thread_id), mode="summary")
        if hasattr(ctxprov, "update"):
            ctxprov.update((ctx.context or "").strip())
    except Exception:
        pass

    # 3) HMA-Schritt (DEMO parallel → Ich → deliver_to → Speaker/Messaging)
    result = hma.step(req.prompt)
    # result enthält: final, deliver_to, speaker, content, envelope, snapshot
    # Kompat mit IDE: responses für die Chatliste füllen
    resp_items = []
    to = result.get("deliver_to")
    content = result.get("content", "")
    # 3a) Innerer Prozess (immer mitsenden, wenn vorhanden)
    inner = (result.get("inner_combined") or "").strip()
    if inner:
        resp_items.append({"agent": "SOM:inner", "content": inner})
    # 3b) Finale Ich-Antwort an den User
    if to == "user" and content:
        resp_items.append({"agent": "SOM", "content": content})

    return {
        "ok": True,
        "final": result.get("final", True),
        "deliver_to": to,
        "speaker": result.get("speaker"),
        "corr_id": (result.get("envelope") or {}).get("corr_id"),
        "packet_id": (result.get("envelope") or {}).get("id"),
        "p_snapshot": result.get("snapshot"),
        "responses": resp_items,   # 👈 wichtig für dein ViewModel
    }


@app.get("/")
def root():
    return {"status": "ok", "message": "Gateway Backend mit HMA läuft."}
