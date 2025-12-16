# backend/main.py — FastAPI entrypoint
from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4
from time import perf_counter
import os
import sys

from fastapi import FastAPI, Request
from loguru import logger

# Loguru-Konfiguration: Standard INFO, per ENV überschreibbar
LOG_LEVEL = os.getenv("GATEWAY_LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL)

# Projekt-Imports
from backend import bootstrap
from backend.routes.websocket import start_watcher
from backend.routes.chat_api import router as chat_router
from backend.routes import reset_api


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
    logger.info("🚀 [Lifespan] Starte Gateway Backend – initialisiere Runtime…")

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

    app.state.hma          = runtime.hma            # direkte HMA-Instanz
    app.state.messaging    = runtime.messaging
    app.state.pbuffer_dir  = runtime.pbuffer_dir

    logger.info(
        "✅ [Lifespan] Runtime ready | T1={} T2={} T3={} T4={} T5={} T6={}",
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
        logger.info("👀 [Lifespan] Watcher gestartet für: /app/backend")
    except Exception as e:
        logger.warning(f"⚠️ [Lifespan] Watcher konnte nicht gestartet werden: {e}")

    try:
        yield
    finally:
        logger.info("🧹 [Lifespan] FastAPI shutting down.")


# -----------------------------------------------------------------------------#
# 🚀 App
# -----------------------------------------------------------------------------#
app = FastAPI(
    lifespan=lifespan,
    title="Gateway API",
    version="3.2",
)

app.include_router(chat_router, tags=["chat"])
app.include_router(reset_api.router)


# -----------------------------------------------------------------------------#
# 🧾 Middleware: Correlation-Id & Request-Logging
# -----------------------------------------------------------------------------#
@app.middleware("http")
async def add_corr_id(request: Request, call_next):
    cid = request.headers.get("x-corr-id") or uuid4().hex
    token = bootstrap.corr_id_var.set(cid)
    start = perf_counter()

    method = request.method
    path = request.url.path

    logger.info(
        "➡️ [HTTP] {method} {path} cid={cid}",
        method=method,
        path=path,
        cid=cid,
    )

    try:
        response = await call_next(request)
    except Exception as e:
        # Fehler im Request-Pfad zentral loggen
        logger.exception(
            "💥 [HTTP] Unhandled error for {method} {path} cid={cid}: {err}",
            method=method,
            path=path,
            cid=cid,
            err=e,
        )
        bootstrap.corr_id_var.reset(token)
        raise

    # Correlation-Id-Kontext zurücksetzen
    bootstrap.corr_id_var.reset(token)

    duration_ms = (perf_counter() - start) * 1000.0
    logger.info(
        "⬅️ [HTTP] {status} {method} {path} cid={cid} ({ms:.1f} ms)",
        status=response.status_code,
        method=method,
        path=path,
        cid=cid,
        ms=duration_ms,
    )

    response.headers["x-corr-id"] = cid
    return response


# -----------------------------------------------------------------------------#
# 🏠 Root
# -----------------------------------------------------------------------------#
@app.get("/")
def root():
    logger.debug("🏠 [Root] Healthcheck aufgerufen.")
    return {"status": "ok", "message": "Gateway Backend läuft."}
