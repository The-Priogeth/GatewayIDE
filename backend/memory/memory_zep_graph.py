"""
ZepGraphAdmin (async-only)
--------------------------
Thin wrappers around the Zep Graph API for provisioning, CRUD, and search.
Only one unified `search()` is exposed.
"""
from __future__ import annotations
from typing import Any, Optional, Dict, List

class ZepGraphAdmin:
    def __init__(self, client, *, user_id: Optional[str] = None, graph_id: Optional[str] = None) -> None:
        self._client = client
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
    async def create_graph(self, label: str, ontology: Optional[Dict[str, Any]] = None) -> Any:
        return await self._client.graph.create(label=label, ontology=ontology)

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

    # Raw add (parity with source)
    async def add_raw_data(self, *, user_id: Optional[str], data_type: str, data: str) -> Any:
        if not user_id and not self._user_id:
            raise ValueError("user_id required for add_raw_data")
        uid = user_id or self._user_id
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
