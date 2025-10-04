# backend/main.py — FastAPI entrypoint (Lobby/Manager driven chat)
from __future__ import annotations

import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Callable, Awaitable, cast
from loguru import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import bootstrap
from backend.routes.websocket import start_watcher
from backend.ag2.autogen.agentchat import UserProxyAgent

# -----------------------------------------------------------------------------
# Environment basics
# -----------------------------------------------------------------------------
os.environ.setdefault("TZ", "Europe/Berlin")
# Avoid static attribute access (Pylance: time.tzset may not exist on Windows)
_tzset = getattr(time, "tzset", None)
if callable(_tzset):
    _tzset()

LOG_PATH = os.getenv("LOG_PATH", "logs")
LOG_ROTATION = os.getenv("LOG_ROTATION", "25 MB")
LOG_RETENTION = os.getenv("LOG_RETENTION")  # None → keep forever
LOG_DIAGNOSE = os.getenv("LOG_DIAGNOSE", "true").lower() == "true"

CORS_ALLOW_ORIGINS_RAW = os.getenv("CORS_ALLOW_ORIGINS", "*")
if CORS_ALLOW_ORIGINS_RAW.strip() == "*":
    CORS_ALLOW_ORIGINS = ["*"]
    CORS_ALLOW_CREDENTIALS = False  # Wildcard + credentials is not allowed by spec
else:
    CORS_ALLOW_ORIGINS = [o.strip() for o in CORS_ALLOW_ORIGINS_RAW.split(",") if o.strip()]
    CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

# File logging sink (best effort)
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
    # Logging should never block startup
    pass

# -----------------------------------------------------------------------------
# Lifespan: initialize once (runtime, captains, lobby manager) and cleanup on exit
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = await bootstrap.ensure_runtime()

    # Make runtime easily accessible to routes
    app.state.runtime = runtime
    app.state.zep_client = runtime.zep_client
    app.state.user_id = runtime.user_id
    app.state.thread_id = runtime.thread_id
    app.state.lobby = runtime.lobby
    app.state.memory = runtime.memory
    app.state.mem_thread = runtime.mem_thread
    


    logger.info("ready: user={} thread={}", app.state.user_id, app.state.thread_id)

    # Dev watcher (robust path regardless of Docker mount)
    watcher = None
    try:
        backend_dir = str(Path(__file__).resolve().parent)
        watcher = start_watcher(path=backend_dir)
        yield
    finally:
        try:
            if watcher is not None:
                if hasattr(watcher, "stop"):
                    watcher.stop()
                if hasattr(watcher, "join"):
                    watcher.join(timeout=5)
        except Exception:
            pass

        # Close ZEP client if it exposes an async close (type-safe for Pylance)
        try:
            zep = getattr(app.state, "zep_client", None)
            aclose_f = cast(Optional[Callable[[], Awaitable[None]]], getattr(zep, "aclose", None))
            if aclose_f is not None:
                await aclose_f()
        except Exception:
            pass

        logger.info("shutdown: ok")

# -----------------------------------------------------------------------------
# App factory & middleware
# -----------------------------------------------------------------------------
app: FastAPI = FastAPI(
    lifespan=lifespan,
    title="Gateway API",
    description="Modulare KI-Agentenplattform (Lobby/Manager-Chat)",
    version="0.5",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve minimal HTML UI at /ui (if present)
static_dir = os.path.join("backend", "static")
if os.path.isdir(static_dir):
    app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

# -----------------------------------------------------------------------------
# Chat API (Manager-driven): feed prompt into the lobby and let the manager route
# -----------------------------------------------------------------------------
class ChatRequest(BaseModel):
    prompt: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    runtime = app.state.runtime
    zep = runtime.zep_client

    lobby = runtime.hub["lobby"]
    manager = lobby["manager"]
    root_memory = runtime.lobby["root_memory"]

    # 1) Persist user prompt into the root thread (the shared user/groupchat thread)
    from autogen_core.memory import MemoryContent, MemoryMimeType

    await root_memory.add(
        MemoryContent(
            content=req.prompt,
            mime_type=MemoryMimeType.TEXT,
            metadata={"type": "message", "role": "user", "name": "User"},
        )
    )

    # 2) Refresh high-level context (summary) into the ContextProvider
    ctx = await zep.thread.get_user_context(thread_id=runtime.thread_id, mode="summary")
    runtime.hub["context_provider"].update((ctx.context or "").strip())

    # 3) Kick off the conversation via manager (auto pattern: THINK/PLAN/EXECUTE/RETURN decided by manager)
    #    UserProxyAgent is just the starter; no human input loop here.
    user = UserProxyAgent(name="User", human_input_mode="NEVER", code_execution_config=False)
    user.initiate_chat(manager, message=req.prompt)

    # 4) Collect latest assistant messages from all lobby agents (conservative)
    out: list[dict[str, str]] = []
    for agent in lobby["groupchat"].agents:
        try:
            key = next(iter(agent.chat_messages.keys()))
            msgs = agent.chat_messages[key]
            # pick last assistant message authored by the agent
            for m in reversed(msgs):
                if m.get("role") == "assistant" and m.get("name") == agent.name:
                    out.append({"agent": agent.name, "content": m.get("content", "")})
                    break
        except Exception:
            # best-effort: skip agents without messages
            pass

    # 5) Optionally persist RETURN into the root thread (so the shared chat has the final answer)
    try:
        ret_msg = next((r["content"] for r in out if r["agent"] == "RETURN"), None)
        if ret_msg:
            await root_memory.add(
                MemoryContent(
                    content=ret_msg,
                    mime_type=MemoryMimeType.TEXT,
                    metadata={"type": "message", "role": "assistant", "name": "RETURN"},
                )
            )
    except Exception:
        pass

    return {"responses": out}

# -----------------------------------------------------------------------------
# Local run (production runs through uvicorn CLI in Docker)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    logger.info("serve: http://0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
