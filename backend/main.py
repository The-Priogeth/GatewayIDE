# backend/main.py — FastAPI entrypoint (Slim-HMA kompatibel)
from __future__ import annotations


from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from loguru import logger
from uuid import uuid4
# Projekt-Imports
from backend import bootstrap
from backend.routes.websocket import start_watcher
from backend.routes.chat_api import router as chat_router

# -----------------------------------------------------------------------------#
# 🌱 Lifespan: Init & App-State
# -----------------------------------------------------------------------------#
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialisiert beim App-Start die gesamte Runtime:
    - Lädt Keys/Modelle über bootstrap.ensure_runtime()
    - Erstellt Zep-Client, Threads T1..T6, HMA, ContextProvider, Messaging
    - Startet optional den Dateiwächter (Hot-Reload)
    """
    runtime = await bootstrap.ensure_runtime()

    # Gemeinsamer App-State für alle Endpoints
    app.state.runtime      = runtime
    app.state.zep_client   = runtime.zep_client

    # Threads & Memories (aus bootstrap.ensure_runtime)
    app.state.t1_thread_id = runtime.t1_thread_id
    app.state.t1_memory    = runtime.t1_memory
    app.state.t2_thread_id = runtime.t2_thread_id
    app.state.t3_thread_id = runtime.t3_thread_id
    app.state.t4_thread_id = runtime.t4_thread_id
    app.state.t5_thread_id = runtime.t5_thread_id
    app.state.t6_thread_id = runtime.t6_thread_id

    app.state.ctx_provider = runtime.ctx_provider

    # 🔁 WICHTIG: Slim-HMA legt HMA direkt ab – KEIN dict mehr
    app.state.hma          = runtime.hma            # direkte HMA-Instanz
    app.state.messaging    = runtime.messaging
    app.state.pbuffer_dir  = runtime.pbuffer_dir

    logger.info(
        "✅ Runtime ready | T1={} T2={} T3={} T4={} T5={} T6={}",
        runtime.t1_thread_id,
        runtime.t2_thread_id,
        runtime.t3_thread_id,
        runtime.t4_thread_id,
        runtime.t5_thread_id,
        runtime.t6_thread_id,
    )

    # Optionaler Watcher (Hot-Reload für /app/backend)
    try:
        start_watcher("/app/backend")
        logger.info("👀 Watcher gestartet für: /app/backend")
    except Exception as e:
        logger.warning(f"Watcher konnte nicht gestartet werden: {e}")

    try:
        yield
    finally:
        logger.info("🧹 FastAPI shutting down.")


# -----------------------------------------------------------------------------#
# 🚀 App
# -----------------------------------------------------------------------------#
app = FastAPI(
    lifespan=lifespan,
    title="Gateway API",
    version="3.1",
)

app.include_router(chat_router, tags=["chat"])


@app.middleware("http")
async def add_corr_id(request: Request, call_next):
    cid = request.headers.get("x-corr-id") or uuid4().hex
    token = bootstrap.corr_id_var.set(cid)
    try:
        response = await call_next(request)
    finally:
        bootstrap.corr_id_var.reset(token)
    response.headers["x-corr-id"] = cid
    return response

# -----------------------------------------------------------------------------#
# 🏠 Root
# -----------------------------------------------------------------------------#
@app.get("/")
def root():
    return {"status": "ok", "message": "Gateway Backend (Slim-HMA) läuft."}
