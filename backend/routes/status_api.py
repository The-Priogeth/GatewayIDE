# backend/routes/status_api.py
from __future__ import annotations
import os
from typing import Any, Dict, List
from fastapi import APIRouter, Request, HTTPException

# Prefix kommt aus main.py → hier nur /status
router = APIRouter(prefix="/status", tags=["status"])

def _mask(s: str, head: int = 6, tail: int = 4) -> str:
    """Hilfsfunktion: API-Key-Fingerprint ohne Geheimnisse."""
    if not s:
        return "<empty>"
    if len(s) <= head + tail:
        return "*" * len(s)
    return f"{s[:head]}…{s[-tail:]}"

@router.get("")
async def status_root(request: Request) -> Dict[str, Any]:
    """
    Kompakter Status-Snapshot.
    - Keine Fallbacks: wenn Kernkomponenten fehlen → 503.
    - Nur vorhandene, V3-relevante States werden ausgewiesen.
    """
    st = request.app.state
    # Harte Anforderungen (sonst 503)
    if not getattr(st, "hub", None):
        raise HTTPException(status_code=503, detail="manager (hub) not initialized")
    if not getattr(st, "mem_thread", None):
        raise HTTPException(status_code=503, detail="thread memory not initialized")
    if not getattr(st, "zep_client", None):
        raise HTTPException(status_code=503, detail="zep client not initialized")

    # Leichte Felder
    user_id   = getattr(st, "user_id", None)
    thread_id = getattr(st, "thread_id", None)
    hub       = getattr(st, "hub", None)
    mem_thr   = getattr(st, "mem_thread", None)

    # Agents-Übersicht (nur, was real registriert ist)
    agents_summary: List[Dict[str, Any]] = []
    agents = getattr(hub, "agents", {}) or {}
    for role, obj in agents.items():
        agents_summary.append({
            "role": role,
            "type": type(obj).__name__,
        })

    return {
        "ok": True,
        "manager": type(hub).__name__,
        "user_id": user_id,
        "thread_id": thread_id,
        "zep_client": True,
        "agents": agents_summary,
    }

@router.get("/diag")
async def status_diag(request: Request) -> Dict[str, Any]:
    """
    Tiefergehende Diagnose (aber leichtgewichtig):
    - Policy-Info + Entscheidung für ersten Sprecher (ohne den Chat auszuführen)
    - Maskierte ENV/Model-Info
    - Keine externen Aufrufe, kein Fallback
    """
    st = request.app.state
    hub = getattr(st, "hub", None)
    if not hub:
        raise HTTPException(status_code=503, detail="manager (hub) not initialized")

    # Policy & First-Speaker (rein deterministische Wahl, kein Netz/LLM)
    first_speaker = None
    policy_name   = type(getattr(hub, "policy", None)).__name__ if getattr(hub, "policy", None) else None
    try:
        picker = getattr(hub, "policy", None)
        if picker and hasattr(picker, "pick_first"):
            agent_obj = picker.pick_first(getattr(hub, "agents", {}) or {}, ctx={})
            first_speaker = getattr(agent_obj, "role", type(agent_obj).__name__)
    except Exception:
        first_speaker = None  # keine Fallback-Tricks

    # ENV/Model-Facts (maskiert)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_model = os.getenv("OPENAI_MODEL", None)
    zep_base = os.getenv("ZEP_BASE_URL", os.getenv("ZEP_API_BASE_URL", None))

    return {
        "ok": True,
        "manager": {
            "type": type(hub).__name__,
            "policy": policy_name,
            "first_speaker": first_speaker,
            "agent_count": len(getattr(hub, "agents", {}) or {}),
        },
        "memory": {
            "has_thread": bool(getattr(st, "mem_thread", None)),
            "has_full": bool(getattr(st, "memory", None)),
            "user_id": getattr(st, "user_id", None),
            "thread_id": getattr(st, "thread_id", None),
        },
        "env": {
            "openai_key_fp": _mask(openai_key),
            "openai_model": openai_model,
            "zep_base_url": zep_base,
        },
    }

@router.get("/agents")
async def status_agents(request: Request) -> Dict[str, Any]:
    """
    Detailansicht zu registrierten Agents (nur Metadaten).
    Kein Fallback – wenn kein Manager existiert, 503.
    """
    st = request.app.state
    hub = getattr(st, "hub", None)
    if not hub:
        raise HTTPException(status_code=503, detail="manager (hub) not initialized")

    out: List[Dict[str, Any]] = []
    for role, obj in (getattr(hub, "agents", {}) or {}).items():
        # Mindest-Metadaten; keine geheimen Prompt-Inhalte o.ä.
        meta: Dict[str, Any] = {"role": role, "type": type(obj).__name__}
        # freiwillig: verschachtelte Manager als solche markieren
        if hasattr(obj, "manager"):
            meta["nested"] = type(getattr(obj, "manager")).__name__
        out.append(meta)

    return {"ok": True, "agents": out}


@router.get("/diag/env")
def diag_env():
    key = os.getenv("OPENAI_API_KEY", "")
    fp  = f"{key[:6]}…{key[-4:]}" if key else "<empty>"
    return {
        "openai_api_key_fp": fp,
        "openai_model": os.getenv("OPENAI_MODEL"),
        "openai_project_id": os.getenv("OPENAI_PROJECT_ID"),
        "openai_org_id": os.getenv("OPENAI_ORG_ID"),
    }

@router.get("/diag/runtime")
def diag_runtime(request: Request):
    st = request.app.state
    return {
        "user_id": getattr(st, "user_id", None),
        "thread_id": getattr(st, "thread_id", None),
        "zep_client": bool(getattr(st, "zep_client", None)),
        "mem_thread": bool(getattr(st, "mem_thread", None)),
        "hub": type(getattr(st, "hub", None)).__name__ if getattr(st, "hub", None) else None,
    }
