from __future__ import annotations

from typing import Any, Optional, List, Dict, Literal, Set
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
from zep_cloud.core.api_error import ApiError
# from zep_cloud.graph import (
#     SearchResult,
#     AddDocumentRequest,
#     AddNodeRequest,
#     AddEdgeRequest,
# )
# from zep_cloud.thread import Message, Role
from datetime import datetime
import logging
logger = logging.getLogger(__name__)


# -------------------------------
# Embedded: ZepThreadMemory
# -------------------------------
class ZepThreadMemory:
    def __init__(
        self,
        client: AsyncZep,
        user_id: str,
        thread_id: Optional[str] = None,
        *,
        default_context_mode: Literal["basic", "summary"] = "basic",
    ) -> None:
        self._client: Any = client
        self._user_id = user_id
        self._thread_id = thread_id
        self._default_context_mode = default_context_mode

    # -------------------------
    # Properties / accessors
    # -------------------------

    @property
    def thread_id(self) -> Optional[str]:
        return self._thread_id

    def set_thread(self, thread_id: Optional[str]) -> None:
        self._thread_id = thread_id

    @property
    def _is_local(self) -> bool:
        tid = self._thread_id or ""
        return str(tid).startswith("local_")

    # -------------------------
    # Core helpers
    # -------------------------
    async def ensure_thread(self, force_check: bool = False) -> str:
        if not self._thread_id:
            t = await self._client.thread.create(user_id=self._user_id)  # type: ignore[call-arg]
            tid = getattr(t, "thread_id", None) or getattr(t, "uuid", None) or getattr(t, "id", None)
            if not tid:
                raise RuntimeError("ZEP thread.create returned no id")
            self._thread_id = str(tid)
            return self._thread_id

        if force_check:
            try:
                await self._client.thread.get(thread_id=self._thread_id)
            except ApiError as e:
                if getattr(e, "status_code", None) == 404:
                    t = await self._client.thread.create(user_id=self._user_id, thread_id=self._thread_id)
                    tid = getattr(t, "thread_id", None) or getattr(t, "uuid", None) or getattr(t, "id", None)
                    self._thread_id = str(tid) if tid else self._thread_id
                else:
                    raise
        return self._thread_id
    

    # -------------------------
    # Message writers
    # -------------------------

    async def add_user_message(self, content: str, *, name: Optional[str] = None) -> None:
        await self._add_message("user", content, name)

    async def add_assistant_message(self, content: str, *, name: Optional[str] = None) -> None:
        await self._add_message("assistant", content, name)

    async def add_system_message(self, content: str, *, name: Optional[str] = None) -> None:
        await self._add_message("system", content, name)

    async def _add_message(self, role: str, content: str, name: str | None = None) -> None:
        thread_id = await self.ensure_thread(force_check=True)
        msg: dict[str, Any] = {"role": role, "content": content}
        if name:
            msg["name"] = name

        try:
            await self._client.thread.add_messages(thread_id=thread_id, messages=[msg])  # type: ignore[arg-type]
            return
        except ApiError as e:
            if getattr(e, "status_code", None) == 404:
                # einmal explizit anlegen & retry
                t = await self._client.thread.create(user_id=self._user_id, thread_id=thread_id)
                tid = getattr(t, "thread_id", None) or getattr(t, "uuid", None) or getattr(t, "id", None) or thread_id
                self._thread_id = str(tid)
                await self._client.thread.add_messages(thread_id=self._thread_id, messages=[msg])
                return
            raise

    # -------------------------
    # Readers / helpers
    # -------------------------

    async def list_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._thread_id or self._is_local:
            return []
        try:
            resp = await self._client.thread.get(thread_id=self._thread_id)
            raw = getattr(resp, "messages", None) or []
            out: List[Dict[str, Any]] = []
            for m in raw[-limit:]:
                if isinstance(m, dict):
                    role = m.get("role") or ""
                    content = m.get("content") or ""
                    ts = m.get("created_at") or m.get("ts")
                else:
                    role = getattr(m, "role", "") or getattr(m, "type", "")
                    content = getattr(m, "content", "") or getattr(m, "text", "")
                    ts = getattr(m, "created_at", None)
                if not content:
                    continue
                out.append({"role": str(role), "content": str(content), "ts": ts})
            return out
        except Exception:
            return []

    async def search_text(
        self,
        query: str,
        *,
        limit: int = 5,
        roles: Optional[List[str]] = None,
        exclude_notes: bool = False,
        dedupe: bool = True,
        max_scan: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Einfache Thread-Volltextsucht:
        - Holt die letzten `max_scan` Nachrichten des Threads
        - Filtert NEUESTE → ÄLTERE nach `query`
        - Optional: Rollenfilter, „Merke:“ ausblenden, Dedupe
        Rückgabe: [{"role","content","ts"}, ...]
        """
        if not self._thread_id or self._is_local:
           return []
        qcf = (query or "").strip().casefold()
        try:
            resp = await self._client.thread.get(thread_id=self._thread_id)
            raw = getattr(resp, "messages", None) or []
        except Exception:
            raw = []

        msgs = raw[-max_scan:] if max_scan else raw
        want_roles: Optional[Set[str]] = {r.lower() for r in roles} if roles else None
        results: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        for m in reversed(msgs):  # neueste → ältere
            if isinstance(m, dict):
                role = str(m.get("role") or "")
                text = str(m.get("content") or "")
                ts = m.get("created_at") or m.get("ts")
            else:
                role = str(getattr(m, "role", "") or getattr(m, "type", ""))
                text = str(getattr(m, "content", "") or getattr(m, "text", ""))
                ts = getattr(m, "created_at", None)
            if not text:
                continue
            if want_roles and role.lower() not in want_roles:
                continue
            if exclude_notes and text.strip().lower().startswith("merke:"):
                continue
            if qcf and qcf not in text.casefold():
                continue
            key = text.strip().casefold()
            if dedupe and key in seen:
                continue
            seen.add(key)
            results.append({"role": role or "user", "content": text, "ts": ts})
            if len(results) >= limit:
                break
        return results

    async def get_user_context(self, mode: Optional[str] = None) -> str:
        if not self._thread_id or self._is_local:
            return ""
        try:
            ctx = await self._client.thread.get_user_context(
                thread_id=self._thread_id, mode=mode or self._default_context_mode
            )
            return str(getattr(ctx, "context", "") or "")
        except Exception:
            return ""

    async def build_context_block(self, *, include_recent: bool = True, recent_limit: int = 10) -> str:
        parts: List[str] = []
        ctx = await self.get_user_context()
        if ctx:
            parts.append(f"Memory context: {ctx}")
        if include_recent:
            recent = await self.list_recent_messages(limit=recent_limit)
            if recent:
                lines: List[str] = []
                for m in recent:
                    role = (m.get("role") or "").strip() if isinstance(m, dict) else ""
                    content = (m.get("content") or "").strip() if isinstance(m, dict) else ""
                    if not content:
                        continue
                    content = str(content).strip()
                    if len(content) > 2000:
                        content = content[:2000] + " …"
                    lines.append(f"{role}: {content}")
                if lines:
                    parts.append("Recent conversation:\n" + "\n".join(lines))
        return "\n\n".join(parts)



# -------------------------------
# Embedded: ZepGraphAdmin
# -------------------------------
class ZepGraphAdmin:
    def __init__(
        self,
        client: AsyncZep,
        *,
        user_id: Optional[str] = None,
        graph_id: Optional[str] = None,
    ) -> None:
        self._client: Any = client
        self._user_id = user_id
        self._graph_id = graph_id

    # Internal helper
    def _gid(self, graph_id: Optional[str]) -> str:
        gid = graph_id or self._graph_id
        if not gid:
            raise ValueError("graph_id required")
        return gid
    
    # Target selection
    def set_user(self, user_id: str) -> None:
        self._user_id = user_id

    def set_graph(self, graph_id: str) -> None:
        self._graph_id = graph_id

    def target_kwargs(self) -> Dict[str, Any]:
        if self._graph_id:
            return {"graph_id": self._graph_id}
        if self._user_id:
            return {"user_id": self._user_id}
        raise ValueError("Neither graph_id nor user_id is set for ZepGraphAdmin")

    # Provisioning
    async def create_graph(self, graph_id: str) -> Any:
        return await self._client.graph.create(graph_id=graph_id)

    async def list_graphs(self) -> List[Any]:
        return await self._client.graph.list()

    async def update_graph(self, graph_id: str, **kwargs: Any) -> Any:
        return await self._client.graph.update(graph_id=graph_id, **kwargs)

    async def clone_graph(self, src_graph_id: str, new_label: str) -> Any:
        return await self._client.graph.clone(graph_id=src_graph_id, new_label=new_label)

    async def set_ontology(self, graph_id: Optional[str], schema: Dict[str, Any]) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.set_ontology(graph_id=gid, schema=schema)

    async def add_node(self, name: str, *, summary: Optional[str] = None,
                       attributes: Optional[Dict[str, Any]] = None,
                       graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.add_node(graph_id=gid, name=name,
                                                 summary=summary, attributes=attributes or {})

    async def add_fact_triple(self, head_uuid: str, relation: str, tail_uuid: str, *,
                              attributes: Optional[Dict[str, Any]] = None,
                              rating: Optional[float] = None,
                              graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.add_edge(
            graph_id=gid, head_uuid=head_uuid, relation=relation, tail_uuid=tail_uuid,
            attributes=attributes or {}, rating=rating
        )

    async def get_node(self, node_uuid: str, *, graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.get_node(graph_id=gid, node_uuid=node_uuid)

    async def get_edge(self, edge_uuid: str, *, graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.get_edge(graph_id=gid, edge_uuid=edge_uuid)

    async def get_node_edges(self, node_uuid: str, *, graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.get_node_edges(graph_id=gid, node_uuid=node_uuid)

    async def delete_edge(self, edge_uuid: str, *, graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.delete_edge(graph_id=gid, edge_uuid=edge_uuid)

    async def delete_episode(self, episode_uuid: str, *, graph_id: Optional[str] = None) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.delete_episode(graph_id=gid, episode_uuid=episode_uuid)

    async def add_raw_data(self, *, user_id: Optional[str], data_type: str, data: str) -> Any:
        """
        Schreibt bevorzugt in den explizit gesetzten Graph (graph_id).
        Fällt zurück auf den User-Graph, wenn kein graph_id konfiguriert ist.
        """
        if getattr(self, "_graph_id", None):
            return await self._client.graph.add(graph_id=self._graph_id, type=data_type, data=data)
        # Fallback: User-Graph
        uid = user_id or self._user_id
        if not uid:
            raise ValueError("user_id required for add_raw_data when no graph_id is set")
        return await self._client.graph.add(user_id=uid, type=data_type, data=data)
 

    # Unified Search
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        scope: Optional[str] = None,
        search_filters: Optional[Dict[str, Any]] = None,
        min_fact_rating: Optional[float] = None,
        reranker: Optional[str] = None,
        center_node_uuid: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        target = self.target_kwargs()
        params: Dict[str, Any] = {**target, "query": query, "limit": limit}
        if scope is not None: params["scope"] = scope
        if search_filters is not None: params["search_filters"] = search_filters
        if min_fact_rating is not None: params["min_fact_rating"] = min_fact_rating
        if reranker is not None: params["reranker"] = reranker
        if center_node_uuid is not None: params["center_node_uuid"] = center_node_uuid
        params.update(kwargs)
        return await self._client.graph.search(**params)



# -------------------------------
# Hauptklasse: ZepMemory
# -------------------------------
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
        # Thread-Fassade (thread_id wird nur hier verwaltet):
        self._thread = ZepThreadMemory(self._client, self._user_id, thread_id=thread_id)

    # --- zentraler, zustandsloser Graph-Helper ---
    def _get_graph(self) -> ZepGraphAdmin:
        """
        Liefert stets einen korrekt gebundenen ZepGraphAdmin:
        - bevorzugt graph_id (falls per adopt_graph_id gesetzt)
        - sonst user_id
        Hinweis: ZepGraphAdmin ist leichtgewichtig → wir instanzieren on-demand.
        """
        target_graph_id = getattr(self, "_graph_id", None)
        if target_graph_id:
            return ZepGraphAdmin(self._client, graph_id=target_graph_id)
        return ZepGraphAdmin(self._client, user_id=self._user_id)

    @property
    def thread_id(self) -> Optional[str]:
        return self._thread.thread_id
    
    @property
    def user_id(self) -> str | None:
        return self._user_id

    def set_thread(self, thread_id: Optional[str]) -> None:
        self._thread.set_thread(thread_id)

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
        _ = cancellation_token; _ = args; _ = kwargs  # silence unused
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
            also_graph = bool(meta.get("also_graph", False))
            text = str(content.content)
            if role == "assistant":
                await self._thread.add_assistant_message(text, name=name)
            elif role == "system":
                await self._thread.add_system_message(text, name=name)
            else:
                await self._thread.add_user_message(text, name=name)
            # Optionales Duplikat im Graph beibehalten (ersetzt früheres add_message(also_graph=True))
            if also_graph and not self._thread._is_local:
                try:
                    # Ziel-Admin passend binden (graph_id bevorzugt, sonst user_id)
                    target_graph_id = getattr(self, "_graph_id", None)
                    ga = ZepGraphAdmin(self._client, graph_id=target_graph_id, user_id=None if target_graph_id else self._user_id)
                    await ga.add_raw_data(user_id=None, data_type="text", data=str(text))
                except Exception as e:
                    self._logger.debug(f"graph-add skipped: {e}")
            return

        # wenn local_* → kein Zep-Graph-Write
        if self._thread._is_local:
            return None

        # Route strukturierte/plain Daten → User-Graph
        if content_type == "data":
            mime_to_type = {
                MemoryMimeType.TEXT: "text",
                MemoryMimeType.MARKDOWN: "text",
                MemoryMimeType.JSON: "json",
            }
            data_type = mime_to_type.get(content.mime_type, "text")
            await self._get_graph().add_raw_data(user_id=self._user_id, data_type=data_type, data=str(content.content))
            return

        raise ValueError(f"Unsupported metadata type: {content_type}. Supported: 'message', 'data'")


    async def add_episode(self, content: str, source: str = "agent", role: str | None = None, **attributes: Any) -> None:
        """Compat sugar: persist a structured 'episode' into the user's graph."""
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


    async def search(
        self,
        query: str,
        *,
        k: int = 10,
        tags: Optional[list[str]] = None,
    ) -> list[MemoryContent]:
        _ = tags  # reserved for future use; avoids unused-variable warning

        try:
            results = await self._get_graph().search(query=query, limit=k)
        except Exception as e:
            self._logger.warning(f"graph.search failed: {e}")
            return []

        out: list[MemoryContent] = []

        for r in results:
            # created_at robust wandeln
            created_raw = getattr(r, "created_at", None)
            if created_raw is None:
                created_val = None
            else:
                iso_fn = getattr(created_raw, "isoformat", None)
                if callable(iso_fn):
                    created_val = iso_fn()
                else:
                    created_val = str(created_raw)


            out.append(
                MemoryContent(
                    content=getattr(r, "content", "") or "",
                    mime_type=MemoryMimeType.TEXT,
                    metadata={
                        "source": "graph",
                        "uuid": getattr(r, "uuid", None),
                        "type": getattr(r, "type", None),
                        "created_at": created_val,
                        "score": getattr(r, "score", None),
                    },
                )
            )

        return out



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




    async def query(
        self,
        query: str | MemoryContent,
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> MemoryQueryResult:
        _ = cancellation_token
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
            graph_results = await self._get_graph().search(
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
        # Hinweis: Bei lokalen Threads (local_*) niemals Graph-Kontext ziehen.
        #          Das verhindert inkonsistente Zustände im Offline-/Fallback-Modus.
        if graph and not self._thread._is_local:
            try:
                params: dict[str, Any] = {"limit": 5}
                if graph_filters:
                    params.update(graph_filters)

                res = await self._get_graph().search(query="*", **params)

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

    def adopt_graph_id(self, graph_id: Optional[str]) -> None:
        """Setzt den Ziel-Graph für Reads/Writes. Entfernen per None/''."""
        self._graph_id = (str(graph_id).strip() or None) if graph_id is not None else None