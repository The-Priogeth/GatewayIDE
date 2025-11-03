from __future__ import annotations
from fastapi import APIRouter, Request
from pydantic import BaseModel
from autogen_core.memory import MemoryContent, MemoryMimeType

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str

@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    rt = request.app.state.runtime
    t1_mem = rt.t1_memory
    ctxprov = rt.ctx_provider
    hma = rt.hma

    # 1) Prompt -> T1
    await t1_mem.add(MemoryContent(
        content=req.prompt,
        mime_type=MemoryMimeType.TEXT,
        metadata={"type":"message","role":"user","name":"User","thread":"T1"},
    ))

    # 2) Kontext
    if hasattr(ctxprov, "refresh"):
        await ctxprov.refresh()
    ctx = ctxprov.get() if hasattr(ctxprov, "get") else None

    # 3) HMA-Zyklus → Envelope (Speaker ist intern)
    envelope = await hma.run_inner_cycle(req.prompt, ctx)
    return envelope