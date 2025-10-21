# backend/router.py
from __future__ import annotations
from typing import Any, Dict, Optional
from backend.agent_core.speaker import HMASpeaker

class HMARouter:
    """
    Optional: dünner Wrapper, falls du HMA.step(...) und Speaker trennen willst.
    """
    def __init__(self, *, hma: Any, speaker: HMASpeaker) -> None:
        self.hma = hma
        self.speaker = speaker

    async def handle(self, user_text: str, *, corr_id: Optional[str] = None) -> Dict[str, Any]:
        result = self.hma.step(user_text)  # {"final":True,"deliver_to":...,"content":...}
        deliver_to = result.get("deliver_to", "user")
        content = result.get("content", "")
        info = await self.speaker.speak(deliver_to=deliver_to, content=content, corr_id=corr_id)
        return {"final": True, "deliver_to": deliver_to, "speaker": "HMA", "content_len": len(content), **info}
