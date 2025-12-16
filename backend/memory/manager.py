# backend/memory/manager.py (neu, dünne Fassade)
from typing import Optional, Any, Dict, List, Callable
from autogen_core.memory import MemoryContent, MemoryMimeType
from .memory import ZepMemory
from .graph_api import GraphAPI

GetAPI = Callable[[], GraphAPI]

class MemoryManager:
    """
    Zentrale High-Level-Abstraktion für:
      - Thread/Message Memory (ZepThread)
      - Graph Memory (GraphAPI/ZepGraphAdmin)
    """
    def __init__(self, zep_memory: ZepMemory, get_api: GetAPI) -> None:
        self.mem = zep_memory
        self._get_api = get_api
        self._reset_after: Optional[float] = None  # Zeitstempel als Epoch-Seconds

    def start_new_chat(self, new_thread: bool = False) -> None:
        if hasattr(self.mem, "start_new_chat"):
            self.mem.start_new_chat(new_thread=new_thread)

    def reset_context(self):
        """
        Soft-Reset: Nur Episoden nach diesem Moment werden in get_context() berücksichtigt.
        """
        import time
        self._reset_after = time.time()

    async def add_message(self, role: str, text: str, name: Optional[str] = None,
                          also_graph: bool = False,
                          ignore_roles: list[str] | None = None) -> None:
        """
        Nachricht in den Thread schreiben; optional auch in den Graph duplizieren.
        Rollen-Policy (assistant/system) hier anwenden, statt über metadata zu signalisieren.
        """
        r = (role or "user").lower()
        deny = set(ignore_roles or ["assistant", "system"])
        if r in deny:
            return
        # Fallback: altes add()-Routing (ohne also_graph-Unterstützung)
        mc = MemoryContent(
            content=text,
            mime_type=MemoryMimeType.TEXT,
            metadata={"type": "message", "role": r, "name": name},
        )
        await self.mem.add(mc)

    async def get_context(
        self,
        include_recent: bool = True,
        graph: bool = False,
        recent_limit: int = 10,
        graph_filters: dict | None = None,
    ) -> str:
        ctx = await self.mem.get_context(
            include_recent=include_recent,
            graph=graph,
            recent_limit=recent_limit,
            graph_filters=graph_filters,
        )

        # Filter: wenn reset_after gesetzt ist → alte Episoden entfernen
        if self._reset_after:
            import re
            import time

            cutoff = self._reset_after
            blocks = re.split(r"\n(?=# )", ctx.strip())
            fresh_blocks = []
            for block in blocks:
                m = re.search(r'"created_at":\s*"(.*?)"', block)
                if not m:
                    fresh_blocks.append(block)
                    continue
                try:
                    ts = m.group(1)
                    epoch = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
                    if epoch >= cutoff:
                        fresh_blocks.append(block)
                except Exception:
                    fresh_blocks.append(block)
            return "\n".join(fresh_blocks).strip()
        return ctx

    async def search(self, query: str, **kwargs):
        return await self.mem.query(query, **kwargs)

    async def add_data(self, text: str, data_type: str = "text") -> None:
        mime = MemoryMimeType.TEXT if data_type == "text" else MemoryMimeType.JSON
        mc = MemoryContent(content=text, mime_type=mime, metadata={"type": "data"})
        await self.mem.add(mc)


    # ------------- High-Level Graph API -------------
    async def add_node(self, name: str, *, summary: str | None = None, attributes: Dict[str, Any] | None = None) -> Dict[str, Any]:
        api = self._get_api()
        return await api.add_node(name=name, summary=summary, attributes=attributes or {})

    async def add_edge(
        self,
        *,
        head_uuid: str,
        relation: str,
        tail_uuid: str,
        fact: str | None = None,
        rating: float | None = None,
        attributes: Dict[str, Any] | None = None,
        valid_at: str | None = None,
        invalid_at: str | None = None,
        expired_at: str | None = None,
        graph_id: str | None = None,
    ) -> Dict[str, Any]:
        api = self._get_api()
        return await api.add_edge(
            head_uuid=head_uuid,
            relation=relation,
            tail_uuid=tail_uuid,
            fact=fact,
            rating=rating,
            attributes=attributes,
            valid_at=valid_at,
            invalid_at=invalid_at,
            expired_at=expired_at,
            graph_id=graph_id,
        )

    async def search_nodes(
        self,
        query: str,
        *,
        limit: int = 25,
        search_filters: Dict[str, Any] | None = None,
        reranker: str | None = None,
        center_node_uuid: str | None = None,
        mmr_lambda: float | None = None,
        graph_id: str | None = None,
        user_id: str | None = None,
        **extra: Any,
    ) -> List[Dict[str, Any]]:
        """
        Convenience: Nur Nodes zurückgeben, andere Typen werden gefiltert.
        """
        api = self._get_api()
        items = await api.search(
            query=query,
            limit=limit,
            scope="nodes",
            search_filters=search_filters,
            reranker=reranker,
            center_node_uuid=center_node_uuid,
            mmr_lambda=mmr_lambda,
            graph_id=graph_id,
            user_id=user_id,
            **extra,
        )
        return [it for it in items if isinstance(it, dict) and it.get("type") == "node"]

    # ------------- Per-Demo Graph-Scopes -------------
    def for_graph(self, graph_id: str) -> "GraphScopedManager":
        """
        Liefert ein Handle, dessen Graph-Operationen automatisch im gegebenen graph_id-Namespace laufen.
        Thread/Message-Operationen werden 1:1 an dieselbe ZepMemory-Instanz delegiert.
        """
        def _scoped_api() -> GraphAPI:
            base = self._get_api()
            return base.with_graph(graph_id)
        return GraphScopedManager(self.mem, _scoped_api)


class GraphScopedManager(MemoryManager):
    """
    Scoped-Variante: nutzt dieselbe Thread-Memory, aber Graph-Calls sind auf `graph_id` fixiert.
    """
    def __init__(self, zep_memory: ZepMemory, get_api: GetAPI) -> None:
        super().__init__(zep_memory, get_api)