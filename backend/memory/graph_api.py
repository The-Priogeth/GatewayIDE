# backend/memory/graph_api.py
from __future__ import annotations
from typing import Any, Dict, List, Literal, Callable
from zep_cloud.client import AsyncZep

from dataclasses import dataclass, asdict
from .memory import ZepGraphAdmin  # Low-Level only; Normierung erfolgt hier


# ---------------------------------------------------------------------------------
# Einzige Quelle für Normalisierung/Mapping (Edge/Node/Episode) → dict
# ---------------------------------------------------------------------------------
@dataclass
class _EdgeInfo:
    uuid: str | None
    name: str | None
    fact: str | None
    score: float | None
    attributes: dict[str, Any]
    created_at: Any | None
    valid_at: Any | None
    invalid_at: Any | None
    expired_at: Any | None
    source_node_uuid: str | None = None
    target_node_uuid: str | None = None
    rating: float | None = None
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self); d["type"] = "edge"; d["content"] = self.fact
        return d

def _edge_from_zep(obj: Any) -> _EdgeInfo:
    return _EdgeInfo(
        uuid=getattr(obj, "uuid", None),
        name=getattr(obj, "name", None),
        fact=getattr(obj, "fact", None),
        score=getattr(obj, "score", None),
        attributes=(getattr(obj, "attributes", {}) or {}),
        created_at=getattr(obj, "created_at", None),
        valid_at=getattr(obj, "valid_at", None),
        invalid_at=getattr(obj, "invalid_at", None),
        expired_at=getattr(obj, "expired_at", None),
        source_node_uuid=getattr(obj, "source_node_uuid", None),
        target_node_uuid=getattr(obj, "target_node_uuid", None),
        rating=getattr(obj, "rating", None),
    )

@dataclass
class _NodeInfo:
    uuid: str | None
    name: str | None
    summary: str | None
    score: float | None
    attributes: dict[str, Any]
    labels: list[str]
    created_at: Any | None
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self); d["type"] = "node"
        d["content"] = f"{self.name}: {self.summary}".strip(": ")
        return d

def _node_from_zep(obj: Any) -> _NodeInfo:
    return _NodeInfo(
        uuid=getattr(obj, "uuid", None),
        name=getattr(obj, "name", None),
        summary=(getattr(obj, "summary", "") or ""),
        score=getattr(obj, "score", None),
        attributes=(getattr(obj, "attributes", {}) or {}),
        labels=(getattr(obj, "labels", []) or []),
        created_at=getattr(obj, "created_at", None),
    )

@dataclass
class _EpisodeInfo:
    uuid: str | None
    content: str | None
    role: str | None
    source: str | None
    score: float | None
    created_at: Any | None
    thread_id: str | None = None
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self); d["type"] = "episode"
        return d

def _episode_from_zep(obj: Any) -> _EpisodeInfo:
    return _EpisodeInfo(
        uuid=getattr(obj, "uuid", None),
        content=(getattr(obj, "content", "") or ""),
        role=getattr(obj, "role", None),
        source=getattr(obj, "source", None),
        score=getattr(obj, "score", None),
        created_at=getattr(obj, "created_at", None),
        thread_id=getattr(obj, "thread_id", None),
    )

class GraphAPI:
    """
    Dünne, zentrale Fassade. Hält *eine* ZepGraphAdmin-Instanz
    und bietet eine einheitliche, normalisierte API für Tools & Module.
    """
    def __init__(self, client: AsyncZep, *, graph_id: str | None = None, user_id: str | None = None) -> None:
        # Merke dir den Client für spätere Scopes
        self._client = client
        self._admin = ZepGraphAdmin(client=client, graph_id=graph_id, user_id=user_id)

    # Neue Helper: aktuelle Targets & Scopes
    def current_target(self) -> Dict[str, Any]:
        return self._admin.target_kwargs()

    def with_graph(self, graph_id: str) -> "GraphAPI":
        """Neues GraphAPI mit gleichem Client, aber anderem graph_id."""
        target = self._admin.target_kwargs()
        user_id = target.get("user_id")
        return GraphAPI(self._client, graph_id=graph_id, user_id=user_id)

    # ---- Mutierende Aktionen -------------------------------------------------
    async def set_ontology(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        target = self._admin.target_kwargs()
        await self._admin.set_ontology(target.get("graph_id"), schema)
        return {"ok": True, "data": {"message": "ontology:set", **target}}

    async def add_node(self, name: str, *, summary: str | None = None, attributes: Dict[str, Any] | None = None) -> Dict[str, Any]:
        node = await self._admin.add_node(name=name, summary=summary, attributes=attributes or {})
        return {"ok": True, "data": {"node": _node_from_zep(node).to_dict()}}

    async def add_edge(self, *, head_uuid: str, relation: str, tail_uuid: str,
                       fact: str | None = None, rating: float | None = None,
                       attributes: Dict[str, Any] | None = None,
                       valid_at: str | None = None, invalid_at: str | None = None,
                       expired_at: str | None = None, graph_id: str | None = None) -> Dict[str, Any]:
        res = await self._admin.add_fact_triple(
            head_uuid=head_uuid, relation=relation, tail_uuid=tail_uuid,
            fact=fact, attributes=attributes, rating=rating,
            valid_at=valid_at, invalid_at=invalid_at, expired_at=expired_at,
            graph_id=graph_id)
        return {"ok": True, "data": {"edge": _edge_from_zep(res).to_dict()}}

    async def add_data(self, *, data: str, data_type: Literal["text","json","message"] = "text",
                       role: str | None = None, source: str | None = None,
                       metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from .memory_utils import split_long_text
        parts = split_long_text(data, max_len=10_000)
        last = None
        for chunk in parts:
            last = await self._admin.add_raw_data(
                user_id=None, data_type=data_type, data=chunk,
                role=role, source=source, metadata=metadata or {})
        return {"ok": True, "data": {"episode": _episode_from_zep(last).to_dict() if last else None}}

    # Alias für bestehenden Call-Site-Namen aus P0 (Memory.add → api.add_raw_data)
    async def add_raw_data(self, *, user_id: str | None, data_type: Literal["text","json","message"] = "text", data: str,
                           role: str | None = None, source: str | None = None,
                           metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from .memory_utils import split_long_text
        parts = split_long_text(data, max_len=10_000)
        last = None
        for chunk in parts:
            last = await self._admin.add_raw_data(
                user_id=user_id, data_type=data_type, data=chunk,
                role=role, source=source, metadata=metadata or {})
        return {"ok": True, "data": {"episode": _episode_from_zep(last).to_dict() if last else None}}

    async def delete_edge(self, edge_uuid: str, *, graph_id: str | None = None) -> Dict[str, Any]:
        await self._admin.delete_edge(edge_uuid=edge_uuid, graph_id=graph_id)
        return {"ok": True, "data": {"edge_uuid": edge_uuid}}

    async def delete_episode(self, episode_uuid: str, *, graph_id: str | None = None) -> Dict[str, Any]:
        await self._admin.delete_episode(episode_uuid=episode_uuid, graph_id=graph_id)
        return {"ok": True, "data": {"episode_uuid": episode_uuid}}

    async def clone_graph(self, *, src_graph_id: str, new_label: str) -> Dict[str, Any]:
        await self._admin.clone_graph(src_graph_id=src_graph_id, new_label=new_label)
        return {"ok": True, "data": {"src_graph_id": src_graph_id, "new_label": new_label}}

    async def clone_user_graph(self, *, source_user_id: str, target_user_id: str) -> Dict[str, Any]:
        await self._admin.clone_user_graph(source_user_id=source_user_id, target_user_id=target_user_id)
        return {"ok": True, "data": {"source_user_id": source_user_id, "target_user_id": target_user_id}}

    # ---- Lesende Aktionen ----------------------------------------------------
    async def search(self, **params: Any) -> List[dict[str, Any]]:
        """
        Liefert direkt die normalisierte Ergebnisliste (Edge/Node/Episode → dict).
        Kein Wrapper-Objekt mehr, damit Call-Sites (z. B. ZepMemory) sofort Listen verarbeiten.
        """
        raw = await self._admin.search(**params)
        results: list[dict[str, Any]] = []
        for e in (getattr(raw, "edges", []) or []):   results.append(_edge_from_zep(e).to_dict())
        for n in (getattr(raw, "nodes", []) or []):   results.append(_node_from_zep(n).to_dict())
        for ep in (getattr(raw, "episodes", []) or []): results.append(_episode_from_zep(ep).to_dict())
        return results

    async def get_node(self, node_uuid: str, *, graph_id: str | None = None) -> Dict[str, Any]:
        obj = await self._admin.get_node(node_uuid=node_uuid, graph_id=graph_id)
        return {"ok": True, "data": {"node": _node_from_zep(obj).to_dict()}}

    async def get_edge(self, edge_uuid: str, *, graph_id: str | None = None) -> Dict[str, Any]:
        obj = await self._admin.get_edge(edge_uuid=edge_uuid, graph_id=graph_id)
        return {"ok": True, "data": {"edge": _edge_from_zep(obj).to_dict()}}

    async def get_node_edges(self, node_uuid: str, *, direction: str | None = None, graph_id: str | None = None) -> Dict[str, Any]:
        res = await self._admin.get_node_edges(node_uuid=node_uuid, direction=direction, graph_id=graph_id)
        edges = [_edge_from_zep(e).to_dict() for e in (res or [])]
        return {"ok": True, "data": {"edges": edges}}


class GraphAPIProvider:
    """
    Sehr schlanke Factory/DI: liefert *eine* GraphAPI-Instanz pro Scope.
    Tools bekommen nur noch get_api() injiziert – keine Admin-News.
    """
    def __init__(self, client: AsyncZep, *, graph_id: str | None = None, user_id: str | None = None) -> None:
        self._client = client
        self._api = GraphAPI(client=client, graph_id=graph_id, user_id=user_id)

    def get_api(self) -> GraphAPI:
        return self._api

    def scoped(self, graph_id: str) -> "GraphAPIProvider":
        """
        Leichtgewichtige Factory für per-Graph Scopes, ohne neuen Zep-Client.
        """
        # user_id vom aktuellen Target übernehmen (falls gesetzt)
        user_id = None
        try:
            user_id = self._api.current_target().get("user_id")
        except Exception:
            pass
        return GraphAPIProvider(self._client, graph_id=graph_id, user_id=user_id)