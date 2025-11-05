# backend/agent_core/messaging.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Literal
import os, time, uuid
Role = Literal["user", "assistant", "system"]

@dataclass
class Message:
    role: Role
    text: str
    meta: dict[str, Any] | None = None
    deliver_to: str | None = None  # optional, Rohwert falls SOM-Text enthalten ist

@dataclass
class Envelope:
    thread: str   # "T1"..."T6"
    message: Message

def log(msg: str, scope: str = "sys") -> None:
    # Zentraler Logger (kann an loguru/structlog gebunden werden)
    print(f"{scope} | {msg}")

def store(envelope: Envelope) -> None:
    # Persistiere envelope (hier nur Platzhalter – bei dir an Zep/DB binden)
    log(f"STORE {envelope.thread}: {asdict(envelope)}", scope="store")

def forward(envelope: Envelope) -> None:
    # Transport/Signal – bewusst ohne Geschäftslogik
    log(f"FORWARD {envelope.thread}: {asdict(envelope)}", scope="forward")

def snapshot(text: str, *, to: str = "user", corr_id: str | None = None, dirpath: str | None = None) -> str:
    if os.getenv("SNAPSHOT_ENABLED", "0") not in ("1", "true", "True"):  # <— Opt-in
        return ""
    dirpath = dirpath or os.getenv("PBUFFER_DIR", "/app/pbuffer")
    try:
        os.makedirs(dirpath, exist_ok=True)
    except Exception:
        pass
    corr = corr_id or str(uuid.uuid4())
    fname = f"{int(time.time())}_{to}_{corr}.txt"
    path = os.path.join(dirpath, fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text or "")
    except Exception:
        pass
    return path

# ---------------------------------------------------------------------
# T2 Persistenz (Slim, async)
# ---------------------------------------------------------------------
import asyncio

async def log_som_internal_t2(
    *, t2_memory, aggregate: str, ich_text: str, corr_id: str | None = None
) -> bool:
    """
    Speichert den internen SOM-Zwischenstand (aggregate + ich_text) in Thread T2.
    Erwartet ein ZepUserMemory-Objekt als t2_memory.
    """
    if not t2_memory:
        print("[Messaging:T2] Kein t2_memory übergeben – übersprungen.")
        return False

    from autogen_core.memory import MemoryContent, MemoryMimeType

    content = (
        f"# Interner Zwischenstand\n{aggregate}\n\n"
        f"# Ich-Antwort (Roh)\n{ich_text.strip()}"
    )

    try:
        await t2_memory.add(
            MemoryContent(
                content=content,
                mime_type=MemoryMimeType.TEXT,
                metadata={
                    "type": "message",
                    "role": "system",
                    "name": "SOM:inner",
                    "thread": "T2",
                    "corr_id": corr_id or "no-id",
                },
            )
        )
        print("[Messaging:T2] Persist-OK.")
        return True
    except Exception as e:
        print(f"[Messaging:T2] Persist-Fehler: {e}")
        return False
