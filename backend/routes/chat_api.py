from __future__ import annotations
from fastapi import APIRouter, Request
from pydantic import BaseModel
from backend.agent_core.messaging import Message, Envelope, UserProxy

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str

@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    rt = request.app.state.runtime
    t1_mem = rt.t1_memory
    hma = rt.hma

    # UserProxy – in Zukunft gerne im Runtime-Bootstrap zentral instanzieren.
    user_proxy = getattr(rt, "user_proxy", None)
    if user_proxy is None:
        user_proxy = UserProxy(hma=hma, t1_memory=t1_mem, messaging=getattr(rt, "messaging", None))

    # 1) Request → Envelope (Thread T1, Rolle "user")
    msg = Message(
        role="user",
        text=req.prompt,
        meta=None,
        deliver_to=None,
    )
    env = Envelope(
        thread="T1",
        message=msg,
        attachments=None,  # später: Dateien/Bilder aus dem Request befüllen
    )

    # 2) UserProxy verarbeitet das Envelope und delegiert an HMA
    result = await user_proxy.handle(env)
    return result