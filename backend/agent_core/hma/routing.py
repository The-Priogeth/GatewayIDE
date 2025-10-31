# backend/agent_core/hma/routing.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Any
import json
import re

# -------------------------------------------------------------
# Typen
# -------------------------------------------------------------
Target = Literal["user", "task", "lib", "trn"]

@dataclass
class Route:
    target: Target
    args: dict[str, Any]

# -------------------------------------------------------------
# Marker / Regex
# -------------------------------------------------------------
# Bevorzugte Marker-Zeile vom LLM
_ROUTE_LINE = re.compile(
    r"<<<ROUTE>>>\s*(\{.*?\})\s*<<<END>>>",
    flags=re.DOTALL,
)

# Fallback: letztes JSON mit "deliver_to"
_ROUTE_JSON_FALLBACK = re.compile(
    r"\{[^{}]*\"deliver_to\"\s*:\s*\"(?:user|task|lib|trn)\"[^{}]*\}",
    flags=re.DOTALL,
)

# -------------------------------------------------------------
# Hilfsfunktionen
# -------------------------------------------------------------
def _strip_code_fences(text: str) -> str:
    """Entfernt Markdown-Codeblöcke ```json ... ``` oder ``` ... ```"""
    return re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text, flags=re.IGNORECASE)

def _extract_route_json(raw: str) -> str | None:
    """
    Versucht, den JSON-Block aus dem Modelltext zu extrahieren:
      1) Marker-Zeile: <<<ROUTE>>> {...} <<<END>>>
      2) Fallback: letztes JSON mit "deliver_to"
    """
    txt = _strip_code_fences(raw).strip()
    m = _ROUTE_LINE.search(txt)
    if m:
        return m.group(1).strip()
    ms = list(_ROUTE_JSON_FALLBACK.finditer(txt))
    if ms:
        return ms[-1].group(0).strip()
    return None

# -------------------------------------------------------------
# Hauptfunktion
# -------------------------------------------------------------
def parse_deliver_to(raw: Any) -> Route:
    """
    Robuster Parser mit sanftem Fallback:
      - bevorzugt Marker-Zeile
      - sonst letztes JSON mit "deliver_to"
      - bei Fehlern/Unklarheit → Route(target="user", args={})
    """
    try:
        if isinstance(raw, dict):
            d = raw
        else:
            s = str(raw)
            route_json = _extract_route_json(s)
            if not route_json:
                return Route(target="user", args={})
            d = json.loads(route_json)

        # akzeptiere deliver_to oder target
        dt   = d.get("deliver_to") or d.get("target") or "user"
        args = d.get("args", {}) or {}

        if dt not in ("user", "task", "lib", "trn"):
            dt = "user"
        if not isinstance(args, dict):
            args = {}

        return Route(target=dt, args=args)

    except Exception:
        # Letzter Fallschirm: niemals crashen
        return Route(target="user", args={})

# -------------------------------------------------------------
# Thread-Mapping
# -------------------------------------------------------------
def map_target_to_thread(target: Target) -> str:
    """Zuordnung Ziel → Thread-ID (T1–T6)"""
    return {
        "user": "T1",  # Dialog
        "lib":  "T4",  # Librarian
        "task": "T5",  # TaskManager
        "trn":  "T6",  # Trainer
    }.get(target, "T1")
