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
    Regeln:
    - PersonalAgent IMMER dabei (Name/Profil, leichte Smalltalks).
    - Programmer nur bei Code/Fehler/Logs.
    - Strategist bei Planung, Struktur, Roadmaps.
    - Critic bei 'prüfe', 'kritisiere', 'review'.
    - Therapist bei 'ich fühle', 'stress', 'überfordert', 'hilfe' etc.
    Falls ein Demo eine accept(user_text, context) anbietet → das überschreibt die Heuristik für dieses Demo.
    """
    t = f"{user_text}\n{context}".lower()

    def has(name: str) -> Any | None:
        for d in demos:
            if getattr(d, "name", "").lower() == name.lower():
                return d
        return None

    chosen: list[Any] = []
    pa = has("PersonalAgent")
    if pa: chosen.append(pa)

    # Hooks der Demos respektieren
    for d in demos:
        try:
            fn = getattr(d, "accept", None)
            if callable(fn) and fn(user_text, context):
                if d not in chosen:
                    chosen.append(d)
        except Exception:
            pass

    # Heuristische Ergänzungen
    if any(k in t for k in ["error", "traceback", "stack", "compile", "build", "docker", "compose", "code", "funktion", "methode", "klasse"]):
        dp = has("DemoProgrammer")
        if dp and dp not in chosen:
            chosen.append(dp)

    if any(k in t for k in ["plan", "strategie", "priorisiere", "roadmap", "ziel", "meilenstein"]):
        ds = has("DemoStrategist")
        if ds and ds not in chosen:
            chosen.append(ds)

    if any(k in t for k in ["prüfe", "review", "kritik", "kritisiere", "gegencheck"]):
        dc = has("DemoCritic")
        if dc and dc not in chosen:
            chosen.append(dc)

    if any(k in t for k in ["ich fühle", "überfordert", "angst", "hilfe", "therapie", "emotional"]):
        dt = has("DemoTherapist")
        if dt and dt not in chosen:
            chosen.append(dt)

    # Fallback: mindestens PersonalAgent
    return chosen or ([pa] if pa else list(demos))


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

# am Ende von backend/agent_core/selectors.py

def selector1(user_text: str, context: str, demos) -> list:
    """
    Upstream-Auswahl (leichtgewichtig; dein Wunsch: gpt-3.5 möglich).
    Für jetzt: nutze bestehende Heuristik, identisch zu select_demos.
    """
    return select_demos(user_text, context, demos)

def selector2(ich_text: str) -> str:
    """
    Downstream-Auswahl des Adressaten.
    Hier könnten wir später LLM-Kriterien / Regelwerke nutzen.
    Für jetzt: Route-Parsing bleibt im HMA; selector2 ist Hook.
    Gibt 'user'|'task'|'lib'|'trn' zurück (kompatibel zu routing.py).
    """
    # Minimal: wir lassen routing.parse_deliver_to im HMA entscheiden
    # und nutzen diesen Hook künftig, sobald du Regeln definierst.
    # Für jetzt geben wir einen Dummy zurück (wird nicht verwendet).
    return "user"
