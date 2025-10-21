# backend/agent_core/messaging.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal, Callable
import os, uuid, time, json

# --------- Typen ---------
DeliverTo = Literal["user", "task", "lib", "trn"]

@dataclass
class Envelope:
    id: str
    ts: float
    frm: str
    to: DeliverTo | str
    intent: Literal["ask","inform","order","notify"]
    corr_id: str
    parent_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

# --------- P-Buffer (Snapshot vor Versand) ---------
class PBuffer:
    def __init__(self, dirpath: str):
        self.dir = dirpath
        os.makedirs(self.dir, exist_ok=True)

    def snapshot(self, *, corr_id: str, to: str, text: str) -> str:
        path = os.path.join(self.dir, f"{corr_id}_{int(time.time())}_{to}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

# --------- Zep-Senke (ein Thread, ein Memory) ---------
class MemorySink:
    def __init__(self, *, thread_id: str, memory: Any):
        self.thread_id = thread_id
        self.memory = memory  # erwartet add(MemoryContent(...))

    async def write_text(self, *, role: str, name: str, text: str, meta: Dict[str, Any]) -> None:
        from autogen_core.memory import MemoryContent, MemoryMimeType
        await self.memory.add(
            MemoryContent(
                content=str(text),
                mime_type=MemoryMimeType.TEXT,
                metadata={**meta, "role": role, "name": name},
            )
        )

# --------- Transport (tatsächliches Senden) ---------
class Transport:
    """
    Kapselt die konkreten Sendekanäle. Jede Methode ist ein Call, der die jeweilige
    Gegenstelle „erreicht“ (UI/Meta-Agent). Persistenz macht MessagingRouter.
    """
    def __init__(self, *, to_user: Callable[[str], None], to_task: Callable[[str], None],
                 to_lib: Callable[[str], None], to_trn: Callable[[str], None]):
        self._to_user = to_user
        self._to_task = to_task
        self._to_lib  = to_lib
        self._to_trn  = to_trn

    def send(self, *, to: DeliverTo, text: str) -> None:
        if to == "user":
            self._to_user(text)
        elif to == "task":
            self._to_task(text)
        elif to == "lib":
            self._to_lib(text)
        elif to == "trn":
            self._to_trn(text)
        else:
            raise RuntimeError(f"Unknown deliver_to: {to}")

# --------- MessagingRouter (Orchestriert P -> Persistenz -> Transport) ---------
class MessagingRouter:
    def __init__(self, *,
                 pbuffer: PBuffer,
                 sink_t2: MemorySink,        # user-visible Text
                 sink_t3: MemorySink,        # meta-protocol ENVELOPE only
                 transport: Transport):
        self.pbuffer = pbuffer
        self.sink_t2 = sink_t2
        self.sink_t3 = sink_t3
        self.transport = transport

    def _persist_sink(self, *, sink: Any, role: str, name: str, text: str, meta: Dict[str, Any]) -> dict[str, Any]:
        """
        Kleiner Helper für synchrone Persistenz in einen MemorySink.
        Wird in log_som_internal_t2() verwendet.
        """
        try:
            import asyncio
            asyncio.create_task(sink.write_text(role=role, name=name, text=text, meta=meta))
            return {"ok": True, "thread": meta.get("thread"), "name": name}
        except Exception as e:
            return {"ok": False, "error": str(e), "thread": meta.get("thread"), "name": name}

    def log_som_internal_t2(self, *, aggregate: str, ich_text: str, corr_id: str | None = None) -> dict[str, any]:
        """
        Persistiert die interne Denkrunde in T2 als EINEN Eintrag:
        - # Interner Zwischenstand (Demo-Beiträge)
        - # Ich (Finale Ich-Referenz)
        """
        combined = (
            "# Interner Zwischenstand\n"
            f"{(aggregate or '').strip() or '(keine internen Beiträge)'}\n\n"
            "# Ich\n"
            f"{(ich_text or '').strip()}"
        )
        snap = self._persist_sink(
            sink=self.sink_t2,
            role="assistant",
            name="SOM:inner",
            text=combined,
            meta={"thread": "T2", "kind": "inner_combined", "corr_id": corr_id or ""}
        )
        return {"t2_combined": snap}


    def _make_envelope(self, *, frm: str, to: DeliverTo, intent: Literal["ask","inform","order","notify"],
                       corr_id: Optional[str], parent_id: Optional[str], meta: Dict[str, Any]) -> Envelope:
        return Envelope(
            id=str(uuid.uuid4()),
            ts=time.time(),
            frm=frm,
            to=to,
            intent=intent,
            corr_id=corr_id or str(uuid.uuid4()),
            parent_id=parent_id,
            meta=meta or {},
        )

    def _envelope_json(self, env: Envelope) -> str:
        return json.dumps({
            "id": env.id,
            "ts": env.ts,
            "from": env.frm,
            "to": env.to,
            "intent": env.intent,
            "corr_id": env.corr_id,
            "parent_id": env.parent_id,
            "meta": env.meta or {},
        }, ensure_ascii=False)

    def send_addressed_message(self, *, frm: str, to: DeliverTo, text: str,
                               intent: Literal["ask","inform","order","notify"]="inform",
                               corr_id: Optional[str]=None, parent_id: Optional[str]=None,
                               meta: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
        """
        1) Snapshot in P (Paketinhalt als Datei)
        2) Persistenz:
           - deliver_to == user  → T2: TEXT
           - deliver_to in {task,lib,trn} → T3: ENVELOPE (ohne Payload)
        3) Transport (tatsächliches Senden)
        Rückgabe enthält Envelope-JSON und Snapshot-Pfad.
        """
        env = self._make_envelope(frm=frm, to=to, intent=intent, corr_id=corr_id, parent_id=parent_id, meta=meta or {})
        # 1) P-Snapshot (immer Text, simple File Copy)
        snapshot_path = self.pbuffer.snapshot(corr_id=env.corr_id, to=to, text=text)

        # 2) Persistenz (asynchron via Zep)
        #    - user → T2 schreibt den TEXT (user-visible)
        #    - meta → T3 schreibt NUR die ENVELOPE
        if to == "user":
            # keine Persistenz in T2 – Chat-Antwort geht direkt an T1 (Transport)
            pass
        else:
            # T3: ENVELOPE ONLY
            try:
                import asyncio
                asyncio.create_task(self.sink_t3.write_text(role="system", name="PROTO", text=self._envelope_json(env),
                                                            meta={"channel": "meta", "corr_id": env.corr_id}))
            except Exception:
                pass

        # 3) Transport ausführen (one-way, bare-bones)
        self.transport.send(to=to, text=text)

        return {
            "envelope": {
                "json": self._envelope_json(env),
                "id": env.id,
                "corr_id": env.corr_id,
            },
            "snapshot": snapshot_path,
        }
