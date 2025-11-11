# backend/memory/memory_utils.py
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---- Message-Normalisierung -------------------------------------------------
ALLOWED_ROLES = {"user", "assistant", "system"}

def prepare_message_dict(role: str, content: str, name: Optional[str] = None) -> Dict[str, Any]:
    r = (role or "user").strip().lower()
    if r not in ALLOWED_ROLES:
        r = "user"
    c = (content or "").strip()
    item: Dict[str, Any] = {"role": r, "content": c}
    if name:
        item["name"] = str(name)
    return item

def format_message_list(raw: Sequence[Dict[str, Any]], *, limit: int = 10) -> List[Dict[str, Any]]:
    """Gibt Liste mit einheitlichen Keys zurück: role, content, ts (letzte N)."""
    out: List[Dict[str, Any]] = []
    for m in raw[-limit:]:
        role = (m.get("role") or "").strip().lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        ts = m.get("ts") or m.get("created_at")
        out.append({"role": role or "user", "content": content, "ts": ts})
    return out

# ---- Chunking / Splitting ---------------------------------------------------
def chunk_messages(messages: List[Dict[str, Any]], *, max_batch: int = 30) -> List[List[Dict[str, Any]]]:
    if max_batch <= 0:
        return [messages]
    return [messages[i:i+max_batch] for i in range(0, len(messages), max_batch)]

def split_long_text(text: str, *, max_len: int = 10_000) -> List[str]:
    s = text or ""
    if len(s) <= max_len:
        return [s]
    parts: List[str] = []
    i = 0
    while i < len(s):
        parts.append(s[i:i+max_len])
        i += max_len
    return parts
