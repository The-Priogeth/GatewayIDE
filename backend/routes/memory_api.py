# backend/routes/memory_api.py
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Tuple, Iterable, List
from autogen_core.memory import MemoryContent, MemoryMimeType
from loguru import logger
import json
import re

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────────
# Input-Modelle
# ──────────────────────────────────────────────────────────────────────────────
class AddMemoryIn(BaseModel):
    type: str = Field(..., description='"message" | "episode" | sonst → wird als "data" gespeichert')
    content: Dict[str, Any] | str
    role: Optional[str] = Field(None, description='"user" | "assistant" | "system" (nur für message)')
    name: Optional[str] = None

class SearchIn(BaseModel):
    query: str
    limit: int = 5
    # Passthrough-Parameter (optional)
    scope: Optional[str] = None
    search_filters: Optional[Dict[str, Any]] = None
    min_fact_rating: Optional[float] = None
    reranker: Optional[str] = None
    center_node_uuid: Optional[str] = None

# ──────────────────────────────────────────────────────────────────────────────
# Utils
# ──────────────────────────────────────────────────────────────────────────────
MONTHS = {
    "januar": "01", "februar": "02", "märz": "03", "maerz": "03",
    "april": "04", "mai": "05", "juni": "06", "juli": "07",
    "august": "08", "september": "09", "oktober": "10", "november": "11", "dezember": "12",
}
DATE_RE = re.compile(r"(\d{1,2})\.?\s*(januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember)", re.IGNORECASE)


def _normalize_type_and_role(t: str, role: Optional[str]) -> Tuple[str, Optional[str]]:
    t_l = (t or "").lower()
    if t_l in {"message", "user", "assistant", "system"}:
        r = role or (t_l if t_l in {"user", "assistant", "system"} else "user")
        return "message", r
    return "data", None


def extract_fact_and_tags(text: str) -> tuple[str, list[str], Optional[str]]:
    """
    Gibt (fact, tags, month_day) zurück, z. B.:
      "Lina hat am 3. Februar Geburtstag" -> (.., ["note","date:02-03"], "02-03")
    """
    fact = (text or "").strip()
    tags: List[str] = ["note"]
    month_day: Optional[str] = None
    m = DATE_RE.search(fact)
    if m:
        day = int(m.group(1))
        mon = MONTHS.get(m.group(2).lower())
        if mon:
            month_day = f"{mon}-{day:02d}"
            tags.append(f"date:{month_day}")
    return fact, tags, month_day


async def _fact_exists(mem, fact: str) -> bool:
    """Robuste Dedupe-Prüfung – unterstützt sowohl List- als auch Objekt-Returnwerte."""
    try:
        res = await mem.query(fact, limit=1)
    except Exception:
        return False

    items: Iterable[Any] = getattr(res, "results", res)
    try:
        for r in (items or []):
            if isinstance(r, dict):
                text = (r.get("text") or r.get("content") or "").strip()
            else:
                text = (getattr(r, "text", None) or getattr(r, "content", None) or "").strip()
            if text and text.casefold() == fact.strip().casefold():
                return True
    except Exception:
        return False
    return False


def _episode_from_content(content: Any) -> Tuple[str, list, str]:
    """Normalisiert beliebigen Episoden-Content zu (fact, tags, payload_str)."""
    if isinstance(content, dict):
        fact = (content.get("text") or json.dumps(content, ensure_ascii=False)).strip()
        tags = content.get("tags") or []
        md = next((t.split(":",1)[1] for t in tags if isinstance(t,str) and t.startswith("date:")), None)
        pl = {"text": fact, "tags": tags}
        if md: pl["month_day"] = md
        payload = json.dumps(pl, ensure_ascii=False)
    elif isinstance(content, str):
        fact, tags, md = extract_fact_and_tags(content)
        pl = {"text": fact, "tags": tags}
        if md: pl["month_day"] = md
        payload = json.dumps(pl, ensure_ascii=False)
    else:
        fact = str(content).strip()
        tags = []
        payload = json.dumps({"text": fact, "tags": tags}, ensure_ascii=False)
    return fact, tags, payload


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/memory/add")
async def memory_add(req: Request, body: AddMemoryIn):
    mem = req.app.state.memory

    # a) episode → direkt in den Graph (mit Duplikat-Schutz)
    if body.type.lower() == "episode":
        fact, tags, payload = _episode_from_content(body.content)
        if not await _fact_exists(mem, fact):
            await mem.add_episode(content=payload, source="api", role=body.role or None)
        return {"ok": True}

    # b) message/data → Thread/Store
    t_norm, role = _normalize_type_and_role(body.type, body.role)

    mime = MemoryMimeType.JSON if isinstance(body.content, dict) else MemoryMimeType.TEXT
    meta: Dict[str, Any] = {"type": t_norm}
    if t_norm == "message":
        meta["role"] = role or "user"
        if body.name:
            meta["name"] = body.name

    await mem.add(MemoryContent(content=body.content, mime_type=mime, metadata=meta))

    # c) OPTIONAL: „Merke:“ zusätzlich als Episode spiegeln (Graph), ebenfalls mit Dedupe
    if t_norm == "message" and isinstance(body.content, str):
        ct = body.content.strip()
        if ct.casefold().startswith("merke:"):
            fact_text = ct.split(":", 1)[1].strip() or ct
            fact, tags, md = extract_fact_and_tags(fact_text)
            if not await _fact_exists(mem, fact):
                md = next((t.split(":",1)[1] for t in tags if isinstance(t,str) and t.startswith("date:")), None)
                pl = {"text": fact, "tags": tags}
                if md: pl["month_day"] = md
                payload = json.dumps(pl, ensure_ascii=False)
                try:
                    await mem.add_episode(content=payload, source="api", role=role or None)
                except Exception:
                    pass  # Message-Add soll nicht scheitern

    return {"ok": True}


@router.post("/memory/search")
async def memory_search(req: Request, body: SearchIn):
    from typing import Any, Iterable  # lokal, um Imports oben nicht umzubauen

    # 1) THREAD-SCOPE: strikt, ohne Fallbacks
    if (body.scope or "").lower() == "thread":
        mem_thread = getattr(req.app.state, "mem_thread", None)
        if not mem_thread or not hasattr(mem_thread, "search_text"):
            logger.warning("THREAD SEARCH unavailable: mem_thread missing or lacks search_text()")
            return {"results": []}

        sf = body.search_filters or {}
        roles = [r.strip().lower() for r in sf.get("roles", ["user"])]
        exclude_notes = bool(sf.get("exclude_notes", True))
        dedupe = bool(sf.get("dedupe", True))
        max_scan = int(sf.get("max_scan", max(200, body.limit * 10)))

        try:
            msgs = await mem_thread.search_text(
                body.query,
                limit=body.limit,
                roles=roles,
                exclude_notes=exclude_notes,
                dedupe=dedupe,
                max_scan=max_scan
            )
        except Exception as e:
            logger.error("THREAD SEARCH failed: {}", e)
            return {"results": []}

        return {
            "results": [
                {
                    "text": m.get("content"),
                    "meta": {"source": "thread", "role": m.get("role"), "ts": m.get("ts")},
                }
                for m in (msgs or [])
            ]
        }

    # 2) Standard: Graph/Knowledge-Scope wie bisher
    mem = req.app.state.memory
    kwargs = {
        "limit": body.limit,
        "scope": body.scope,
        "search_filters": body.search_filters,
        "min_fact_rating": body.min_fact_rating,
        "reranker": body.reranker,
        "center_node_uuid": body.center_node_uuid,
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    res = await mem.query(body.query, **kwargs)
    items: Iterable[Any] = getattr(res, "results", res)

    out = []
    for r in (items or []):
        if isinstance(r, dict):
            out.append({"text": r.get("text") or r.get("content"), "meta": r.get("metadata") or r.get("meta")})
        else:
            out.append(
                {
                    "text": getattr(r, "content", None) or getattr(r, "text", None),
                    "meta": getattr(r, "metadata", None),
                }
            )
    return {"results": out}
