# backend/routes/library_api.py
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.bibliothek import BibliothekService

router = APIRouter(tags=["catalog"])

class RememberIn(BaseModel):
    path: str
    text: str
    role: Optional[str] = "assistant"

class RecallIn(BaseModel):
    path: str
    query: str
    k: int = 5

def _service(req: Request) -> BibliothekService:
    zc = getattr(req.app.state, "zep_client", None)
    uid = getattr(req.app.state, "user_id", None)
    if not zc or not uid:
        raise HTTPException(status_code=503, detail="ZEP or user not initialized")
    return BibliothekService(zep_client=zc, user_id=uid)

@router.get("/_diag")
async def catalog_diag(path: str, request: Request):
    srv = _service(request)
    tid = await srv.ensure_file_thread(path)
    return {"path": path, "thread_id": tid}

@router.post("/remember")
async def catalog_remember(body: RememberIn, request: Request):
    srv = _service(request)
    ok = await srv.remember(path=body.path, text=body.text, role=(body.role or "assistant"))
    return {"ok": bool(ok)}

@router.post("/recall")
async def catalog_recall(body: RecallIn, request: Request):
    srv = _service(request)
    hits = await srv.recall(path=body.path, query=body.query, k=body.k)
    return {"results": hits}
