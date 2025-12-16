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
    # Optionale Anhänge (Bilder, Dateien, Blob-IDs, etc.)
    # Konkrete Struktur später definieren (z. B. {"type": "...", "id": "..."}).
    attachments: list[Any] | None = None


@dataclass
class Address:
    """
    Abstrakte Adressierung für Agenten-Kommunikation.

    origin: Wer sendet? z. B. "HMA", "TASK", "LIB", "TRN", ...
    target: Wohin?      z. B. "user", "task", "lib", "trn"

    Die konkrete Übersetzung (Thread-Mapping, Envelope-Routing)
    erfolgt agent-/kontextspezifisch und NICHT hier.
    """
    origin: str
    target: str

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
# UserProxy – dünne Hülle um HMA für /chat
# ---------------------------------------------------------------------

class UserProxy:
    """
    Nimmt ein Envelope aus der Chat-API entgegen und kümmert sich darum,
    die User-Nachricht in T1 zu persistieren und den HMA auszuführen.

    Später kann diese Klasse erweitert werden (z. B. Envelope-Routing,
    Multi-Thread-Support, Dateien/Bilder behandeln, etc.).
    """

    def __init__(self, *, hma: Any, t1_memory: Any, messaging: Any | None = None) -> None:
        self._hma = hma
        self._t1 = t1_memory
        self._msg = messaging

    async def handle(self, envelope: Envelope) -> dict[str, Any]:
        """
        Aktuelles Verhalten:
        - erwartet eine User-Nachricht (thread "T1")
        - persistiert sie in T1
        - ruft HMA.run(user_text=...) auf
        - gibt das HMA-Ergebnis unverändert zurück
        """
        # Safety: nur T1 für direkten User-Dialog (später erweiterbar)
        thread = envelope.thread or "T1"
        msg = envelope.message

        # 1) User-Prompt in T1 persistieren (so wie bisher direkt in chat_api)
        if self._t1 is not None and msg and msg.text:
            from autogen_core.memory import MemoryContent, MemoryMimeType
            await self._t1.add(
                MemoryContent(
                    content=msg.text,
                    mime_type=MemoryMimeType.TEXT,
                    metadata={"type": "message", "role": msg.role, "name": "User", "thread": thread},
                )
            )

        # 2) HMA kümmert sich um alles Weitere (Kontext, Speaker, Routing)
        result = await self._hma.run(user_text=msg.text, context="")
        return result