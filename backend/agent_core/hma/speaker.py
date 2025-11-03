# backend/agent_core/hma/speaker.py
from __future__ import annotations
from typing import Any, Dict
from autogen_core.memory import MemoryContent, MemoryMimeType
from backend.agent_core.hma.routing import (
    map_target_to_thread, to_target, parse_deliver_to, strip_route_markers, Target
)

class Speaker:
    """
    Formuliert die Ich-Antwort als Ansprache an den vom Selector gewählten Adressaten
    UND persistiert sie in den Ziel-Thread. Kapselt außerdem Snapshot & T2-Inner-Persist.
    """
    def __init__(self, runtime):
        self.rt = runtime
        self.messaging = getattr(runtime, "messaging", None)

    async def _persist_inner(self, inner: str) -> None:
        if not inner:
            return
        try:
            await self.rt.t2_memory.add(MemoryContent(
                content=inner,
                mime_type=MemoryMimeType.TEXT,
                metadata={"type":"message","role":"system","name":"SOM:inner","thread":"T2"},
            ))
        except Exception:
            pass

    async def _snapshot(self, text: str, to: str, corr_id: str | None = None) -> None:
        if not text or not self.messaging:
            return
        try:
            self.messaging.snapshot(text, to=to, corr_id=corr_id)
        except Exception:
            pass

    async def _persist_final(self, target_thread: str, content: str, speaker_name: str) -> None:
        if not content:
            return
        mem = None
        if target_thread == "T1":
            mem = self.rt.t1_memory
        elif target_thread == "T4":
            mem = self.rt.t4_memory
        elif target_thread == "T5":
            mem = self.rt.t5_memory
        elif target_thread == "T6":
            mem = self.rt.t6_memory
        else:
            mem = self.rt.t1_memory
        await mem.add(MemoryContent(
            content=content,
            mime_type=MemoryMimeType.TEXT,
            metadata={"type":"message","role":"assistant","name":speaker_name,"thread":target_thread},
        ))

    async def deliver(self, *, out: Dict[str, Any], speaker_name: str = "SOM") -> Dict[str, Any]:
        # route defensiv entpacken + ggf. parsen
        route = out.get("route")
        if not getattr(route, "target", None):
            # route kann dict/str/None sein → robust parsen
            route = parse_deliver_to(route)

        # Target typ-sicher machen
        raw_target = getattr(route, "target", None)
        target: Target = to_target(raw_target)
        route_args: Dict[str, Any] = getattr(route, "args", {}) or {}

        # Texte holen und ROUTE-Marker zuverlässig entfernen
        inner = strip_route_markers(out.get("inner") or "")
        ich_core = strip_route_markers(out.get("ich_text") or "")

        # 1) Inner persistieren (T2), Fehler nicht UI-blockierend
        if inner:
            try:
                await self._persist_inner(inner)
            except Exception:
                pass

        # 2) Thread bestimmen
        target_thread = map_target_to_thread(target)

        # 3) Snapshot (Audit)
        try:
            await self._snapshot(ich_core, to=target, corr_id=None)
        except Exception:
            pass

        # 4) Finale Ansprache
        anschrift = ich_core

        # 5) Persist finale Antwort
        try:
            await self._persist_final(
                target_thread=target_thread,
                content=anschrift,
                speaker_name=speaker_name
            )
        except Exception:
            pass

        # 6) UI-Envelope (optional inner kürzen)
        trimmed_inner = inner if len(inner) <= 4000 else inner[:4000] + "…"
        resp_items = []
        if trimmed_inner:
            resp_items.append({"agent": "SOM:INNER", "content": trimmed_inner})

        who = "SOM" if target == "user" else f"HMA→{target.upper()}"
        if anschrift:
            resp_items.append({"agent": who, "content": anschrift})

        return {
            "ok": True,
            "final": True,
            "deliver_to": target,
            "deliver_to_thread": target_thread,
            "route_args": route_args,
            "speaker": speaker_name,
            "corr_id": None,
            "packet_id": None,
            "p_snapshot": None,
            "inner": trimmed_inner,
            "responses": resp_items,
        }