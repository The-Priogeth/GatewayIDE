"""
Zep Memory integration for AutoGen.
Facade that composes ZepThreadMemory + ZepGraphAdmin to keep a clean structure,
while preserving the public API expected by AutoGen:
  - add(), add_episode(), query(), update_context(), clear(), close()
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from autogen_core import CancellationToken
from autogen_core.memory import (
    Memory,
    MemoryContent,
    MemoryMimeType,
    MemoryQueryResult,
    UpdateContextResult,
)
from autogen_core.model_context import ChatCompletionContext
from autogen_core.models import SystemMessage
from zep_cloud.client import AsyncZep

from backend.memory.memory_zep_thread import ZepThreadMemory
from backend.memory.memory_zep_graph import ZepGraphAdmin

class ZepMemory(Memory):
    def __init__(
        self,
        client: AsyncZep, 
        user_id: str, 
        thread_id: Optional[str] = None, 
        **kwargs: Any
        ) -> None:
        if not isinstance(client, AsyncZep):
            raise TypeError("client must be an instance of AsyncZep")
        if not user_id:
            raise ValueError("user_id is required")
        self._client: AsyncZep = client
        self._user_id: str = user_id
        self._config = kwargs
        self._logger = logging.getLogger(__name__)
        # Teil-Fassaden (nur hier verwalten wir die thread_id):
        self._thread = ZepThreadMemory(self._client, self._user_id, thread_id=thread_id)
        self._graph = ZepGraphAdmin(self._client, user_id=self._user_id)

    # Properties, damit diag/health etwas sehen:
    @property
    def thread_id(self) -> str | None:
        return getattr(self._thread, "thread_id", None)
    
    @property
    def user_id(self) -> str | None:
        return self._user_id

    def adopt_thread_id(self, thread_id: str) -> None:
        if getattr(self, "_thread", None) is not None:
            self._thread.set_thread(thread_id)

    async def ensure_thread(self) -> str:
        # No-Op: Thread wird beim Bootstrap erzeugt, nicht im Request-Pfad.
        # Behalten für Kompatibilität – gibt die bekannte ID zurück oder fällt lokal zurück.
        tid = getattr(self._thread, "thread_id", None) or getattr(self, "_thread_id", None)
        if tid:
            return tid
        local_tid = f"local_{self._user_id}"
        if hasattr(self._thread, "set_thread"):
            self._thread.set_thread(local_tid)
        setattr(self, "_thread_id", local_tid)
        return local_tid

    async def add(
        self, content: MemoryContent, cancellation_token: CancellationToken | None = None, *args, **kwargs
    ) -> None:
        supported = {MemoryMimeType.TEXT, MemoryMimeType.MARKDOWN, MemoryMimeType.JSON}
        if content.mime_type not in supported:
            raise ValueError(
                f"Unsupported mime type: {content.mime_type}. "
                f"ZepMemory only supports: {', '.join(str(mt) for mt in supported)}"
            )

        meta = content.metadata.copy() if content.metadata else {}
        content_type = meta.get("type", "data")

        # Route "message" → Thread
        if content_type == "message":
            role = meta.get("role", "user")
            name = meta.get("name")
            text = str(content.content)
            if role == "assistant":
                await self._thread.add_assistant_message(text, name=name)
            elif role == "system":
                await self._thread.add_system_message(text, name=name)
            else:
                await self._thread.add_user_message(text, name=name)
            return

        # wenn local_* → kein Zep-Graph-Write
        if self._thread.is_local:
            return None

        # Route strukturierte/plain Daten → User-Graph
        if content_type == "data":
            mime_to_type = {
                MemoryMimeType.TEXT: "text",
                MemoryMimeType.MARKDOWN: "text",
                MemoryMimeType.JSON: "json",
            }
            data_type = mime_to_type.get(content.mime_type, "text")
            await self._graph.add_raw_data(user_id=self._user_id, data_type=data_type, data=str(content.content))
            return

        raise ValueError(f"Unsupported metadata type: {content_type}. Supported: 'message', 'data'")

    async def add_episode(self, content: str, source: str = "agent", role: str | None = None, **attributes: Any) -> None:
        """Compat sugar: persist a structured 'episode' into the user's graph."""
        from datetime import datetime
        payload = {
            "kind": "episode",
            "content": content,
            "source": source,
            "role": role,
            "ts": datetime.utcnow().isoformat(),
            **attributes,
        }
        await self.add(
            MemoryContent(
                content=payload,
                mime_type=MemoryMimeType.JSON,
                metadata={"type": "data"},
            )
        )

    async def query(
        self,
        query: str | MemoryContent,
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> MemoryQueryResult:
        if isinstance(query, MemoryContent):
            q = str(query.content)
        else:
            q = query

        # ---- Erlaubte/typisierte Such-Parameter aus kwargs holen
        raw_limit = kwargs.pop("limit", 5)
        raw_scope = kwargs.pop("scope", None)
        raw_filters = kwargs.pop("search_filters", None)
        raw_min_rating = kwargs.pop("min_fact_rating", None)
        raw_reranker = kwargs.pop("reranker", None)
        raw_center_uuid = kwargs.pop("center_node_uuid", None)
        # Alles andere ignorieren (verhindert Positions-/Typ-Drift)

        # Typguards (Pylance-freundlich)
        limit: int = int(raw_limit) if isinstance(raw_limit, (int, float, str)) and str(raw_limit).isdigit() else 5
        scope: str | None = raw_scope if isinstance(raw_scope, str) else None
        search_filters: dict[str, Any] | None = raw_filters if isinstance(raw_filters, dict) else None
        min_fact_rating: float | None = float(raw_min_rating) if isinstance(raw_min_rating, (int, float)) else None
        reranker: str | None = raw_reranker if isinstance(raw_reranker, str) else None
        center_node_uuid: str | None = raw_center_uuid if isinstance(raw_center_uuid, str) else None

        results: list[MemoryContent] = []

        try:
            # Nur gültige Keys setzen → kein falscher Typ in die Signatur
            search_args: dict[str, Any] = {"query": q, "limit": limit}
            if scope is not None:
                search_args["scope"] = scope
            if search_filters is not None:
                search_args["search_filters"] = search_filters
            if min_fact_rating is not None:
                search_args["min_fact_rating"] = min_fact_rating
            if reranker is not None:
                search_args["reranker"] = reranker
            if center_node_uuid is not None:
                search_args["center_node_uuid"] = center_node_uuid

            graph_results = await self._graph.search(
                query=q,
                limit=limit,
                scope=scope,
                search_filters=search_filters,
                min_fact_rating=min_fact_rating,
                reranker=reranker,
                center_node_uuid=center_node_uuid,
            )

            # ---- Edges → MemoryContent
            for edge in (getattr(graph_results, "edges", []) or []):
                results.append(
                    MemoryContent(
                        content=getattr(edge, "fact", ""),
                        mime_type=MemoryMimeType.TEXT,
                        metadata={
                            "source": "user_graph",
                            "edge_name": getattr(edge, "name", None),
                            "edge_attributes": getattr(edge, "attributes", {}) or {},
                            "created_at": getattr(edge, "created_at", None),
                            "expired_at": getattr(edge, "expired_at", None),
                            "valid_at": getattr(edge, "valid_at", None),
                            "invalid_at": getattr(edge, "invalid_at", None),
                        },
                    )
                )

            # ---- Nodes → MemoryContent
            for node in (getattr(graph_results, "nodes", []) or []):
                results.append(
                    MemoryContent(
                        content=f"{getattr(node, 'name', '')}:\n {getattr(node, 'summary', '')}",
                        mime_type=MemoryMimeType.TEXT,
                        metadata={
                            "source": "user_graph",
                            "node_name": getattr(node, "name", None),
                            "node_attributes": getattr(node, "attributes", {}) or {},
                            "created_at": getattr(node, "created_at", None),
                        },
                    )
                )

            # ---- Episodes → MemoryContent
            for episode in (getattr(graph_results, "episodes", []) or []):
                results.append(
                    MemoryContent(
                        content=getattr(episode, "content", ""),
                        mime_type=MemoryMimeType.TEXT,
                        metadata={
                            "source": "user_graph",
                            "episode_type": getattr(episode, "source", None),
                            "episode_role": getattr(episode, "role", None),
                            "created_at": getattr(episode, "created_at", None),
                        },
                    )
                )

        except Exception as e:
            self._logger.error(f"Error querying Zep memory: {e}")

        return MemoryQueryResult(results=results)




    async def update_context(self, model_context: ChatCompletionContext) -> UpdateContextResult:
        try:
            # Ohne Zugriff auf model_context.get_messages() – vermeidet .get()-Fehler
            if not self._thread.thread_id:
                return UpdateContextResult(memories=MemoryQueryResult(results=[]))

            block = await self._thread.build_context_block(include_recent=True, recent_limit=10)
            memory_contents = []
            if block:
                memory_contents.append(
                    MemoryContent(
                        content=block,
                        mime_type=MemoryMimeType.TEXT,
                        metadata={"source": "thread_context"},
                    )
                )
                # Best effort – falls ein Modellkontext das nicht unterstützt, nicht crashen
                try:
                    await model_context.add_message(SystemMessage(content=block))
                except Exception as ie:
                    self._logger.debug(f"Context injection skipped: {ie}")

            return UpdateContextResult(memories=MemoryQueryResult(results=memory_contents))
        except Exception as e:
            self._logger.error(f"Error updating context with Zep memory: {e}")
            return UpdateContextResult(memories=MemoryQueryResult(results=[]))

    async def clear(self) -> None:
        try:
            if self._thread.thread_id:
                await self._client.thread.delete(thread_id=self._thread.thread_id)
        except Exception as e:
            self._logger.error(f"Error clearing Zep memory: {e}")
            raise

    async def close(self) -> None:
        # client lifecycle is managed by caller
        pass


# --- NEU in class ZepMemory ---------------------------------

    def adopt_graph_id(self, graph_id: str) -> None:
        """Setzt den Ziel-Graph für Reads/Writes. Entfernen per None."""
        self._graph_id = str(graph_id).strip() if graph_id else None

    async def get_context(
        self,
        include_recent: bool = True,
        graph: bool = False,
        graph_filters: dict[str, Any] | None = None,
        recent_limit: int = 10,
    ) -> str:
        """Baut einen kompakten Kontextstring: Thread-Block (+ optional Graph-Snippet)."""
        parts: list[str] = []

        # Thread-Kontext
        try:
            if include_recent and self._thread:
                block = await self._thread.build_context_block(
                    include_recent=True, recent_limit=recent_limit
                )
                if block:
                    parts.append(block)
        except Exception as e:
            self._logger.debug(f"thread-context skipped: {e}")

        # Optional: Graph-Snippet
        if graph and getattr(self, "_graph", None):
            try:
                params: dict[str, Any] = {"limit": 5}
                if graph_filters:
                    params.update(graph_filters)

                target_graph_id = getattr(self, "_graph_id", None)
                if target_graph_id:
                    ga = ZepGraphAdmin(self._client, graph_id=target_graph_id)
                else:
                    ga = ZepGraphAdmin(self._client, user_id=self._user_id)

                res = await ga.search(query="*", **params)

                lines: list[str] = []
                for e in (getattr(res, "edges", []) or [])[:5]:
                    lines.append(f"- {getattr(e, 'fact', '')}".strip())
                for n in (getattr(res, "nodes", []) or [])[:3]:
                    nm = getattr(n, "name", "")
                    sm = getattr(n, "summary", "") or ""
                    lines.append(f"- {nm}: {sm}".strip())
                if lines:
                    parts.append("Memory graph (compact):\n" + "\n".join(lines))
            except Exception as e:
                self._logger.debug(f"graph-context skipped: {e}")


        ctx = "\n\n".join([p for p in parts if p and p.strip()]) or ""
        return ctx

    async def add_message(
        self,
        role: str,
        text: str,
        name: str | None = None,
        *,
        also_graph: bool = False,
    ) -> None:
        """Einheitlicher Schreibpfad für Speaker/Demos (Thread-first, optional Graph-Duplikat)."""
        r = (role or "user").lower().strip()
        if r == "assistant":
            await self._thread.add_assistant_message(text, name=name)
        elif r == "system":
            await self._thread.add_system_message(text, name=name)
        else:
            await self._thread.add_user_message(text, name=name)

        # Optionales Duplikat in Graph (bewusst „später“ nutzbar)
        if also_graph and not self._thread.is_local:
            try:
                # Ziel-Admin passend binden (graph_id bevorzugt, sonst user_id)
                target_graph_id = getattr(self, "_graph_id", None)
                if target_graph_id:
                    ga = ZepGraphAdmin(self._client, graph_id=target_graph_id)
                else:
                    ga = ZepGraphAdmin(self._client, user_id=self._user_id)

                await ga.add_raw_data(
                    user_id=self._user_id,
                    data_type="text",
                    data=str(text),
                )
            except Exception as e:
                self._logger.debug(f"graph-add skipped: {e}")

# Convenience re-exports (optional)
try:
    from backend.memory.memory_tools import (
        search_memory,
        add_graph_data,
        create_search_graph_tool,
        create_add_graph_data_tool,
    )
except Exception:
    pass
