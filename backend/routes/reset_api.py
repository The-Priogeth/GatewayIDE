# backend/routes/reset_api.py
from fastapi import APIRouter, Request
from backend.bootstrap import ensure_runtime
from backend.reset_utils import generate_new_id
router = APIRouter()

@router.post("/reset/chat")
async def reset_chat(request: Request):
    """
    Startet eine neue Konversation (Soft oder Hard).
    POST-Body (optional):
    {
        "new_thread": true  # oder false (default)
    }
    """
    body = await request.json()
    new_thread = bool(body.get("new_thread", False))

    runtime = await ensure_runtime()
    runtime.memory.start_new_chat(new_thread=new_thread)

    return {"status": "started", "mode": "new_thread" if new_thread else "soft"}

@router.post("/reset/hard")
async def hard_reset_chat(request: Request):
    """
    Führt einen Hard-Reset durch:
    - Löscht den alten Thread
    - Erstellt einen neuen Thread
    - Setzt neue Thread-ID
    """
    runtime = await ensure_runtime()

    old_id = runtime.memory.thread_id
    try:
        # nutzt die MemoryManager-Logik, die intern Zep-Thread löscht
        await runtime.memory.clear()
    except Exception as e:
        runtime.logger.warning(f"Thread delete failed: {e}")

    # neue Thread-ID mit zentraler Helper-Funktion
    new_id = generate_new_id("thread_hardreset")
    runtime.memory.set_thread(new_id)

    return {"status": "restarted", "old_id": old_id, "new_id": new_id}
