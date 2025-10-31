# backend/main.py — FastAPI entrypoint (Slim-HMA kompatibel)
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import cast
import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger

# Zep Memory (autogen-core)
from autogen_core.memory import MemoryContent, MemoryMimeType

# Projekt-Imports
from backend import bootstrap
from backend.routes.websocket import start_watcher


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
    description="Modulare KI-Agentenplattform (Slim-HMA mit SOM und Routing)",
    version="3.0",
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

    # Slim-HMA: direkte Instanz (kein dict!)
    hma = rt.hma

    # 1) User-Prompt in T1 schreiben
    await t1_mem.add(
        MemoryContent(
            content=req.prompt,
            mime_type=MemoryMimeType.TEXT,
            metadata={"type": "message", "role": "user", "name": "User", "thread": "T1"},
        )
    )

    # 2) Kontext beschaffen (falls vorhanden)
    if hasattr(ctxprov, "refresh"):
        await ctxprov.refresh()
    ctx = ctxprov.get() if hasattr(ctxprov, "get") else None
    # 3) HMA aufrufen (Slim API)
    # Rückgabeformat: {"ich_text": str, "route": Route(target, args)}
    out = await hma.run_inner_cycle(req.prompt, ctx)
    route   = out["route"]
    content = out.get("ich_text", "") or "" # finale Ich-Antwort (SOM)
    inner   = (out.get("inner") or "").strip()
    # 3a) Snapshot (leichtgewichtiger Audit-Trail)
    corr_id = str(uuid.uuid4())
    try:
        rt.messaging.snapshot(content, to=route.target, corr_id=corr_id)
    except Exception:
        pass

    # 3b) Inner in T2 persistieren
    inner = (out.get("inner") or "").strip()
    if inner:
        try:
            await rt.t2_memory.add(
                MemoryContent(
                    content=inner,
                    mime_type=MemoryMimeType.TEXT,
                    metadata={"type": "message", "role": "system", "name": "SOM:inner", "thread": "T2"},
                )
            )
        except Exception:
            pass

    # 3c) WICHTIG: Inner auch ans UI schicken (T2-Panel)
    # Dein ViewModel matched "SOM:INNER" (case-insensitive via ToUpperInvariant)
    resp_items = []
    if inner:
        resp_items.append({"agent": "SOM:INNER", "content": inner})

    # 4) Responses für das Frontend aufbauen
    if route.target == "user" and content:
        # ... (dein bestehender T1-Persist bleibt unverändert)
        await t1_mem.add(
            MemoryContent(
                content=content,
                mime_type=MemoryMimeType.TEXT,
                metadata={"type": "message", "role": "assistant", "name": "SOM", "thread": "T1"},
            )
        )
        resp_items.append({"agent": "SOM", "content": content})
    else:
        # --- Delegation mini: schreibe Auftrag in T4/T5/T6 Memory,
        #     damit die Threads wieder "leben" (ohne große Manager)
        target = (route.target or "task").lower()
        mem = None
        thread_label = ""
        if target == "lib":
            mem, thread_label = rt.t4_memory, "T4"
        elif target == "task":
            mem, thread_label = rt.t5_memory, "T5"
        elif target == "trn":
            mem, thread_label = rt.t6_memory, "T6"

        if mem and content:
            try:
                await mem.add(
                    MemoryContent(
                        content=content,
                        mime_type=MemoryMimeType.TEXT,
                        metadata={"type": "message", "role": "assistant", "name": "HMA", "thread": thread_label, "kind": "delegation", "corr_id": corr_id},
                    )
                )
            except Exception:
                pass
        # Optional: kleine Rückmeldung für das UI
        resp_items.append({"agent": "HMA", "content": f"→ Delegation an {target.upper()} übergeben."})


    # 5) Minimale, stabile Antwortstruktur (IDE-ViewModel-kompatibel)
    return {
        "ok": True,
        "final": True,                    # Slim-HMA ohne Streaming
        "deliver_to": route.target,       # "user" | "task" | "lib" | "trn"
        "speaker": "SOM",
        "corr_id": None,
        "packet_id": None,
        "p_snapshot": None,
        "inner": inner,  
        "responses": resp_items,          # Liste der darstellbaren Nachrichten
    }


# -----------------------------------------------------------------------------#
# 🏠 Root
# -----------------------------------------------------------------------------#
@app.get("/")
def root():
    return {"status": "ok", "message": "Gateway Backend (Slim-HMA) läuft."}
