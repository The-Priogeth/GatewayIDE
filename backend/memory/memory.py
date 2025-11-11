from __future__ import annotations

from typing import Any, Optional, List, Dict, Literal, Set, Tuple, Callable
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
import json
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

class MemoryBackendError(RuntimeError):
    pass




# -------------------------------
# Embedded: ZepThreadMemory
# -------------------------------
class ZepThreadMemory:
    def __init__(self,client: AsyncZep,user_id: str,thread_id: Optional[str] = None,*,default_context_mode: Literal["basic", "summary"] = "basic",) -> None:
        self._client: Any = client
        self._user_id = user_id
        self._thread_id = thread_id
        self._default_context_mode = default_context_mode

    @property
    def thread_id(self) -> Optional[str]:
        return self._thread_id

    def set_thread(self, thread_id: Optional[str]) -> None:
        self._thread_id = thread_id

    @property
    def _is_local(self) -> bool:
        tid = self._thread_id or ""
        return str(tid).startswith("local_")

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
    

    async def add_messages(self, messages: list[dict[str, Any]], *, ignore_roles: list[str] | None = None) -> None:
        from .memory_utils import prepare_message_dict, chunk_messages
        thread_id = await self.ensure_thread(force_check=True)
        ignore = set((ignore_roles or []))
        norm: list[dict[str, Any]] = []
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = (m.get("role") or "user")
            content = (m.get("content") or "")
            name = m.get("name")
            if role in ignore:
                continue
            item = prepare_message_dict(role, content, name=name)
            if item["content"]:
                norm.append(item)
        if not norm:
            return
        # Zep-Limit-Schutz: in Blöcken senden
        try:
            for batch in chunk_messages(norm, max_batch=30):
                await self._client.thread.add_messages(thread_id=thread_id, messages=batch, ignore_roles=ignore_roles or [])
            return
        except ApiError as e:
            if getattr(e, "status_code", None) != 404:
                raise
            t = await self._client.thread.create(
                user_id=self._user_id,
                thread_id=thread_id,)
            tid = (
                getattr(t, "thread_id", None)
                or getattr(t, "uuid", None)
                or getattr(t, "id", None)
                or thread_id)
            self._thread_id = str(tid)
            await self._client.thread.add_messages(
                thread_id=self._thread_id,
                messages=norm,
                ignore_roles=ignore_roles,)

    async def list_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._thread_id or self._is_local:
            return []
        try:
            resp = await self._client.thread.get(thread_id=self._thread_id)
            raw = getattr(resp, "messages", None) or []
            # in einfache Dicts umgießen
            tmp = []
            for m in raw:
                if isinstance(m, dict):
                    tmp.append({"role": m.get("role"), "content": m.get("content"), "created_at": m.get("created_at") or m.get("ts")})
                else:
                    tmp.append({"role": getattr(m, "role", None) or getattr(m, "type", None),
                                "content": getattr(m, "content", None) or getattr(m, "text", None),
                                "created_at": getattr(m, "created_at", None)})
            from .memory_utils import format_message_list
            return format_message_list(tmp, limit=limit)
        except Exception as e:
            logger.error("thread.get failed in list_recent_messages", exc_info=True)
            raise MemoryBackendError(f"thread.get failed: {e}") from e


    async def get_user_context(self, mode: Optional[str] = None) -> str:
        if not self._thread_id or self._is_local:
            return ""
        try:
            ctx = await self._client.thread.get_user_context(
                thread_id=self._thread_id, mode=mode or self._default_context_mode)
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
                # ggf. kürzen pro Zeile (optional)
                lines = []
                for m in recent:
                    content = str(m["content"])
                    if len(content) > 2000:
                        content = content[:2000] + " …"
                    lines.append(f"{m['role']}: {content}")
                parts.append("Recent conversation:\n" + "\n".join(lines))

        return "\n\n".join(parts)



######################################################################################################
# Embedded: ZepGraphAdmin
######################################################################################################
class ZepGraphAdmin:
    def __init__(self,client: AsyncZep,*,user_id: Optional[str] = None,graph_id: Optional[str] = None,) -> None:
        self._client: Any = client
        self._user_id = user_id
        self._graph_id = graph_id

    @staticmethod
    def _build_search_params(
        *,
        query: str,
        limit: int = 10,
        scope: Optional[str] = None,
        search_filters: Optional[Dict[str, Any]] = None,
        min_fact_rating: Optional[float] = None,
        reranker: Optional[str] = None,
        center_node_uuid: Optional[str] = None,
        mmr_lambda: Optional[float] = None,
        bfs_origin_node_uuids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"query": query, "limit": int(limit)}
        if scope is not None: params["scope"] = scope
        if search_filters is not None: params["search_filters"] = search_filters
        if min_fact_rating is not None: params["min_fact_rating"] = float(min_fact_rating)
        if reranker is not None: params["reranker"] = reranker
        if center_node_uuid is not None: params["center_node_uuid"] = center_node_uuid
        if mmr_lambda is not None:
            try: params["mmr_lambda"] = float(mmr_lambda)
            except Exception: pass
        if bfs_origin_node_uuids: params["bfs_origin_node_uuids"] = [str(x) for x in bfs_origin_node_uuids]
        return params



    def _gid(self, graph_id: Optional[str]) -> str:
        gid = graph_id or self._graph_id
        if not gid:
            raise ValueError("graph_id required")
        return gid
    
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

    def _choose_target(self, graph_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        if graph_id:
            return {"graph_id": graph_id}
        if user_id:
            return {"user_id": user_id}
        return self.target_kwargs()

    async def create_graph(self, graph_id: str, *, name: str | None = None, description: str | None = None) -> Any:
        return await self._client.graph.create(
            graph_id=graph_id, name=name, description=description)


    async def list_graphs(self) -> List[Any]:
        return await self._client.graph.list()

    async def update_graph(self, graph_id: str, **kwargs: Any) -> Any:
        return await self._client.graph.update(graph_id=graph_id, **kwargs)

    async def clone_graph(self, src_graph_id: str, *, target_graph_id: Optional[str] = None, new_label: Optional[str] = None) -> Any:
        if target_graph_id:
            return await self._client.graph.clone(source_graph_id=src_graph_id, target_graph_id=target_graph_id)
        return await self._client.graph.clone(graph_id=src_graph_id, new_label=new_label or "copy")


    async def clone_user_graph(self,source_user_id: str,target_user_id: str,) -> Any:
        return await self._client.graph.clone(
            source_user_id=source_user_id,
            target_user_id=target_user_id,)
    
    async def set_ontology(self, graph_id: Optional[str], schema: Dict[str, Any]) -> Any:
        gid = self._gid(graph_id)
        return await self._client.graph.set_ontology(graph_id=gid, schema=schema)

    async def add_node(self, name: str, *, summary: Optional[str] = None,
                        attributes: Optional[Dict[str, Any]] = None,
                        graph_id: Optional[str] = None, user_id: Optional[str] = None) -> Any:
        target = self._choose_target(graph_id=graph_id, user_id=user_id)
        return await self._client.graph.add_node(**target, name=name, summary=summary, attributes=attributes or {})

    async def add_fact_triple(
        self,
        head_uuid: str,
        relation: str,
        tail_uuid: str,
        *,
        fact: str | None = None,
        attributes: Dict[str, Any] | None = None,
        rating: float | None = None,
        valid_at: str | None = None,
        invalid_at: str | None = None,
        expired_at: str | None = None,
        graph_id: str | None = None,
        user_id: str | None = None,    
    ) -> Any:
        # Payload-Erzeugung zentralisieren
        from .graph_utils import build_edge_payload
        payload: Dict[str, Any] = build_edge_payload(
            head_uuid, relation, tail_uuid,
            fact=fact, attributes=attributes, rating=rating,
            valid_at=valid_at, invalid_at=invalid_at, expired_at=expired_at,
        )
        target = self._choose_target(graph_id=graph_id, user_id=user_id)
        return await self._client.graph.add_edge(**target, **payload)


    async def get_node(self, node_uuid: str, *, graph_id: Optional[str] = None, user_id: Optional[str] = None) -> Any:
        target = self._choose_target(graph_id=graph_id, user_id=user_id)
        return await self._client.graph.get_node(**target, node_uuid=node_uuid)

    async def get_edge(self, edge_uuid: str, *, graph_id: Optional[str] = None, user_id: Optional[str] = None) -> Any:
        target = self._choose_target(graph_id=graph_id, user_id=user_id)
        return await self._client.graph.get_edge(**target, edge_uuid=edge_uuid)

    async def get_node_edges(self,node_uuid: str,*, direction: Optional[str] = None, graph_id: Optional[str] = None,) -> Any:
        gid = self._gid(graph_id)
        if direction is not None:
            return await self._client.graph.get_node_edges(
                graph_id=gid,
                node_uuid=node_uuid,
                direction=direction,)
        return await self._client.graph.get_node_edges(
            graph_id=gid,
            node_uuid=node_uuid,)

    async def delete_edge(self, edge_uuid: str, *, graph_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
        target = self._choose_target(graph_id=graph_id, user_id=user_id)
        await self._client.graph.delete_edge(**target, edge_uuid=edge_uuid)

    async def delete_episode(self, episode_uuid: str, *, graph_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
        target = self._choose_target(graph_id=graph_id, user_id=user_id)
        await self._client.graph.delete_episode(**target, episode_uuid=episode_uuid)

    async def add_raw_data(self,*,user_id: Optional[str],data_type: str,data: str,role: Optional[str] = None,source: Optional[str] = None,metadata: Optional[Dict[str, Any]] = None,) -> Any:
        if getattr(self, "_graph_id", None):
            return await self._client.graph.add(
                graph_id=self._graph_id, type=data_type, data=data,
                role=role, source=source, metadata=metadata or {})
        uid = user_id or self._user_id
        if not uid:
            raise ValueError("user_id required for add_raw_data when no graph_id is set")
        return await self._client.graph.add(
            user_id=uid, type=data_type, data=data,
            role=role, source=source, metadata=metadata or {})

    async def search(self,query: str,*,limit: int = 10,scope: Optional[str] = None,search_filters: Optional[Dict[str, Any]] = None,min_fact_rating: Optional[float] = None,reranker: Optional[str] = None,center_node_uuid: Optional[str] = None,**kwargs: Any,) -> Any:
        target = self.target_kwargs()
        built = self._build_search_params(
            query=query, limit=limit, scope=scope, search_filters=search_filters,
            min_fact_rating=min_fact_rating, reranker=reranker,
            center_node_uuid=center_node_uuid, **kwargs)
        params: Dict[str, Any] = {**target, **built}
        try:
            search_results = await self._client.graph.search(**params)
            return search_results
        except Exception as e:
            logger.error("graph.search failed", exc_info=True)
            raise


######################################################################################################
# Hauptklasse: ZepMemory
######################################################################################################
class ZepMemory(Memory):
    def __init__(self,client: AsyncZep, user_id: str, thread_id: Optional[str] = None, **kwargs: Any) -> None:
        if not isinstance(client, AsyncZep):
            raise TypeError("client must be an instance of AsyncZep")
        if not user_id:
            raise ValueError("user_id is required")
        self._client: AsyncZep = client
        self._user_id: str = user_id
        self._config = kwargs
        self._logger = logging.getLogger(__name__)
        self._thread = ZepThreadMemory(self._client, self._user_id, thread_id=thread_id)
        self._get_api_cb: Optional[Callable[[], Any]] = None

    def set_api(self, get_api: Callable[[], Any]) -> None:
        """Dependency Injection: zentrale GraphAPI-Instanz (pro User-Scope)."""
        self._get_api_cb = get_api

    def _get_api(self):
        if not self._get_api_cb:
            raise RuntimeError("GraphAPI ist nicht injiziert. Bitte via set_api(...) setzen.")
        return self._get_api_cb()



    
    @property
    def thread_id(self) -> Optional[str]:
        return self._thread.thread_id
    
    @property
    def user_id(self) -> str | None:
        return self._user_id

    def set_thread(self, thread_id: Optional[str]) -> None:
        self._thread.set_thread(thread_id)


    async def ensure_thread(self) -> str:
        # Single-Source-Policy: nur ZepThreadMemory kümmert sich um Erstellung/Check
        return await self._thread.ensure_thread(force_check=True)
    
    async def add(self, content: MemoryContent, cancellation_token: CancellationToken | None = None, *args, **kwargs) -> None:
        _ = cancellation_token; _ = args; _ = kwargs  # silence unused
        supported = {MemoryMimeType.TEXT, MemoryMimeType.MARKDOWN, MemoryMimeType.JSON}
        if content.mime_type not in supported:
            raise ValueError(
                f"Unsupported mime type: {content.mime_type}. "
                f"ZepMemory only supports: {', '.join(str(mt) for mt in supported)}")
        meta = content.metadata.copy() if content.metadata else {}
        content_type = meta.get("type", "data")
        if content_type == "message":
            from .memory_utils import prepare_message_dict
            role = meta.get("role", "user")
            name = meta.get("name")
            also_graph = bool(meta.get("also_graph", False))
            text = str(content.content)
            msg = prepare_message_dict(role, text, name=name)
            await self._thread.add_messages([msg], ignore_roles=meta.get("ignore_roles"))
            if also_graph and not self._thread._is_local:
                try:
                    api = self._get_api()
                    await api.add_raw_data(
                        user_id=self._user_id,
                        data_type="message",
                        data=str(text),
                        role=role,
                        source="thread",
                        metadata={"thread_id": self._thread.thread_id},
                    )
                except Exception as e:
                    self._logger.debug(f"graph-add skipped: {e}")
            return
        if self._thread._is_local:
            return None
        if content_type == "data":
            mime_to_type = {
                MemoryMimeType.TEXT: "text",
                MemoryMimeType.MARKDOWN: "text",
                MemoryMimeType.JSON: "json",}
            data_type = mime_to_type.get(content.mime_type, "text")
            api = self._get_api()
            await api.add_raw_data(user_id=self._user_id, data_type=data_type, data=str(content.content))
            return
        raise ValueError(f"Unsupported metadata type: {content_type}. Supported: 'message', 'data'")

    async def add_episode(self, content: str, source: str = "agent", role: str | None = None, **attributes: Any) -> None:
        payload = {
            "kind": "episode",
            "content": content,
            "source": source,
            "role": role,
            "ts": datetime.utcnow().isoformat(),
            **attributes,
        }
        await self.add(MemoryContent(content=payload,mime_type=MemoryMimeType.JSON,metadata={"type": "data"},))

    async def search(self,query: str,*,k: int = 10,tags: Optional[list[str]] = None,**kwargs: Any,) -> list[MemoryContent]:
        _ = tags  # reserved (zukünftige Tag-Filter)
        limit = int(kwargs.pop("limit", k))
        try:
            api = self._get_api()
            # GraphAPI liefert bereits normalisierte Dicts (edge|node|episode)
            items: list[dict[str, Any]] = await api.search(query=query, limit=limit, **kwargs)
        except Exception as e:
            self._logger.warning(f"graph.search failed: {e}")
            return []
        # Einheitlicher, dünner Mapper → MemoryContent (keine eigene Normalisierung)
        out: list[MemoryContent] = []
        for d in items:
            if not isinstance(d, dict):
                continue
            t = str(d.get("type") or "").strip().lower()
            content = str(d.get("content") or "").strip()
            meta = {k: v for k, v in d.items() if k not in ("type", "content")}
            meta.update({"source": "graph", "kind": t or "item"})
            out.append(MemoryContent(content=content, mime_type=MemoryMimeType.TEXT, metadata=meta))
        return out

    async def clear(self) -> None:
        try:
            if self._thread.thread_id:
                await self._client.thread.delete(thread_id=self._thread.thread_id)
        except Exception as e:
            self._logger.error(f"Error clearing Zep memory: {e}")
            raise

    async def close(self) -> None:
        return None
    
    async def query(
        self,
        query: str | MemoryContent,
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> MemoryQueryResult:
        _ = cancellation_token

        raw_limit = kwargs.pop("limit", 5)

        # Union auflösen: Immer als string in search() geben
        if isinstance(query, MemoryContent):
            q_str = str(query.content)
        else:
            q_str = str(query)

        contents = await self.search(q_str, k=raw_limit, **kwargs)
        return MemoryQueryResult(results=contents)

    async def update_context(self, model_context: ChatCompletionContext) -> UpdateContextResult:
        try:
            if not self._thread.thread_id:
                return UpdateContextResult(memories=MemoryQueryResult(results=[]))
            block = await self._thread.build_context_block(include_recent=True, recent_limit=10)
            memory_contents = []
            if block:
                memory_contents.append(
                    MemoryContent(
                        content=block,
                        mime_type=MemoryMimeType.TEXT,
                        metadata={"source": "thread_context"},))
                try:
                    await model_context.add_message(SystemMessage(content=block))
                except Exception as ie:
                    self._logger.debug(f"Context injection skipped: {ie}")
            return UpdateContextResult(memories=MemoryQueryResult(results=memory_contents))
        except Exception as e:
            self._logger.error(f"Error updating context with Zep memory: {e}")
            return UpdateContextResult(memories=MemoryQueryResult(results=[]))

    async def get_context(self,include_recent: bool = True,graph: bool = False,graph_filters: dict[str, Any] | None = None,recent_limit: int = 10,) -> str:
        parts: list[str] = []
        try:
            if include_recent and self._thread:
                block = await self._thread.build_context_block(
                    include_recent=True, recent_limit=recent_limit)
                if block:
                    parts.append(block)
        except Exception as e:
            self._logger.debug(f"thread-context skipped: {e}")
        if graph and not self._thread._is_local:
            try:
                params: dict[str, Any] = {"limit": 5}
                if graph_filters:
                    params.update(graph_filters)
                api = self._get_api()
                items: list[dict[str, Any]] = await api.search(query="*", **params)
                lines: list[str] = []
                # kompaktes Rendering direkt aus normalisierten Items
                for it in items:
                    c = str(it.get("content") or "").strip()
                    if c:
                        lines.append(f"- {c}")
                if lines:
                    parts.append("Memory graph (compact):\n" + "\n".join(lines))
            except Exception as e:
                self._logger.debug(f"graph-context skipped: {e}")
        ctx = "\n\n".join([p for p in parts if p and p.strip()]) or ""
        return ctx

