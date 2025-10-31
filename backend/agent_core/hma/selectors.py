# backend/agent_core/selectors.py
from __future__ import annotations
from typing import Iterable, Tuple, Any
import re
from typing import List

_CLAIM_PATTERNS = [
    ("name",       r"\b(hei[ßs]e?\s+ich|mein\s+name\s+ist|du\s+hei[ßs]t)\b.+"),
    ("entscheidung", r"\b(sollte|muss|werde|wir\s+werden|plane)\b.+"),
    ("ort",        r"\b(in|bei|aus)\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)*"),
]

def select_demos(user_text: str, context: str, demos: Iterable[Any]) -> list[Any]:
    """
    Mini-Heuristik:
    - Nimmt alle Demos, die ein optionales Attribut `accept(user_text, context)` True liefern.
    - Falls kein Demo ein accept hat/True ist: nimm alle (deterministisch stabil).
    """
    chosen: list[Any] = []
    for d in demos:
        ok = getattr(d, "accept", None)
        try:
            if callable(ok) and ok(user_text, context):
                chosen.append(d)
        except Exception:
            pass
    if not chosen:
        chosen = list(demos)
    return chosen

def aggregate(pairs: list[Tuple[str, str]]) -> str:
    """
    Minimal-Join: '## Name\\nAntwort' pro Demo, einfache Duplikatentfernung.
    """
    seen = set()
    blocks = []
    for name, reply in pairs:
        key = (name.strip(), reply.strip())
        if key in seen:
            continue
        seen.add(key)
        blocks.append(f"## {name}\n{reply}")
    return "\n\n".join(blocks) if blocks else "(keine internen Beiträge)"

def build_findings(pairs: List[Tuple[str, str]]) -> str:
    if not pairs:
        return ""
    votes = {}
    for _, txt in pairs:
        t = (txt or "").strip()
        for kind, rx in _CLAIM_PATTERNS:
            m = re.search(rx, t, flags=re.IGNORECASE)
            if m:
                votes.setdefault(kind, {})
                key = m.group(0).strip()
                votes[kind][key] = votes[kind].get(key, 0) + 1
    if not votes:
        return ""
    lines = ["# Findings (kompakt)"]
    for kind, counts in votes.items():
        best = max(counts.items(), key=lambda kv: kv[1])
        lines.append(f"- **{kind}**: {best[0]}")
    return "\n".join(lines)