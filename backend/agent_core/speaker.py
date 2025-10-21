# backend/speaker.py
from __future__ import annotations
from typing import Optional, Dict, Any
from backend.agent_core.messaging import MetaBus

class HMASpeaker:
    """
    Nimmt den finalen Ich-Text und liefert ihn (über den MetaBus) an das Ziel aus.
    - P-Snapshot + Persistenz erledigt der Bus.
    """
    def __init__(self, *, bus: MetaBus) -> None:
        self.bus = bus

    async def speak(self, *, deliver_to: str, content: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        return await self.bus.send(to=deliver_to, text=content, corr_id=corr_id, intent="inform")
