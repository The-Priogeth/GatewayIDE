# backend/routes/chat_api.py
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["chat"])

@router.post("/chat")
async def chat(request: Request) -> JSONResponse:
    # JSON lesen
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)

    # Back-compat: text/message -> prompt
    if "prompt" not in payload:
        for k in ("text", "message"):
            if isinstance(payload.get(k), str):
                payload["prompt"] = payload.pop(k)
                break
    if not isinstance(payload.get("prompt"), str):
        return JSONResponse({"detail": "Missing 'prompt' (or 'text')"}, status_code=400)

    # Manager ziehen
    hub = getattr(request.app.state, "hub", None)
    if not hub:
        return JSONResponse({"detail": "Hub not available"}, status_code=503)

    # Ein Turn, brain-first; Debug via payload.debug
    res = await hub.group_once(
        goal=payload["prompt"],
        deliverables=payload.get("deliverables"),
        constraints=payload.get("constraints"),
        extra_ctx={"debug": bool(payload.get("debug"))},
    )
    return JSONResponse(content=res, status_code=200)
