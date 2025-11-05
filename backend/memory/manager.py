# backend/memory/manager.py (neu, dünne Fassade)
from typing import Optional
from autogen_core.memory import MemoryContent, MemoryMimeType
from .memory import ZepMemory

class MemoryManager:
    def __init__(self, zep_memory: ZepMemory) -> None:
        self.mem = zep_memory

    async def add_message(self, role: str, text: str, name: Optional[str] = None, also_graph: bool = False) -> None:
        await self.mem.add_message(role, text, name=name, also_graph=also_graph)

    async def get_context(self, include_recent: bool = True, graph: bool = False, recent_limit: int = 10) -> str:
        return await self.mem.get_context(include_recent=include_recent, graph=graph, recent_limit=recent_limit)

    async def search(self, query: str, **kwargs):
        return await self.mem.query(query, **kwargs)

    async def add_data(self, text: str, data_type: str = "text"):
        mc = MemoryContent(content=text, mime_type=MemoryMimeType.TEXT if data_type=="text" else MemoryMimeType.JSON, metadata={"type":"data"})
        await self.mem.add(mc)
