# backend/memory/memory_tools.py
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Callable
from autogen_core.tools import FunctionTool
from .graph_api import GraphAPI

GetAPI = Callable[[], GraphAPI]

def create_clone_user_graph_tool(get_api: GetAPI) -> FunctionTool:
    async def clone_user_graph(
        source_user_id: Annotated[str, "Source user ID"],
        target_user_id: Annotated[str, "Target user ID"],
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.clone_user_graph(source_user_id=source_user_id, target_user_id=target_user_id)
    return FunctionTool(
        func=clone_user_graph,
        name="clone_user_graph",
        description="Clone a complete user graph from source_user_id to target_user_id.",)

def create_set_ontology_tool(get_api: GetAPI) -> FunctionTool:
    async def bound_set_ontology(
        schema: Annotated[Dict[str, Any], "Ontology schema dict (entity_types, edge_types, etc.)"],
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.set_ontology(schema)
    return FunctionTool(bound_set_ontology, name="set_ontology", description="Set ontology for the current graph scope.")

def create_add_node_tool(get_api: GetAPI) -> FunctionTool:
    async def bound_add_node(
        name: Annotated[str, "Entity name"],
        summary: Annotated[str | None, "Optional summary/description"] = None,
        attributes: Annotated[Dict[str, Any] | None, "Optional attributes dict"] = None,
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.add_node(name=name, summary=summary, attributes=attributes or {})
    return FunctionTool(bound_add_node, name="add_node", description="Add node to the current graph scope.")

def create_add_edge_tool(get_api: GetAPI) -> FunctionTool:
    async def add_graph_edge(
        head_uuid: Annotated[str, "Source node UUID"],
        relation: Annotated[str, "Edge/Relation type (name)"],
        tail_uuid: Annotated[str, "Target node UUID"],*,
        fact: Annotated[str | None, "Optional human-readable fact text"] = None,
        rating: Annotated[float | None, "Optional relevance rating 0.0–1.0"] = None,
        attributes: Annotated[Dict[str, Any] | None, "Optional key-value attributes"] = None,
        valid_at: Annotated[str | None, "ISO8601 valid_from timestamp"] = None,
        invalid_at: Annotated[str | None, "ISO8601 valid_until timestamp"] = None,
        expired_at: Annotated[str | None, "ISO8601 expiration timestamp"] = None,
        graph_id: Annotated[str | None, "Graph ID (omit for user graph ops)"] = None,
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.add_edge(
            head_uuid=head_uuid, relation=relation, tail_uuid=tail_uuid,
            fact=fact, rating=rating, attributes=attributes,
            valid_at=valid_at, invalid_at=invalid_at, expired_at=expired_at,
            graph_id=graph_id)
    return FunctionTool(
        func=add_graph_edge,
        name="add_graph_edge",
        description="Create an edge/fact between two nodes, with optional fact text, rating, and validity window.",)

def create_clone_graph_tool(get_api: GetAPI) -> FunctionTool:
    async def bound_clone_graph(
        src_graph_id: Annotated[str, "Source graph ID"],
        new_label: Annotated[str, "New label for cloned graph"],
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.clone_graph(src_graph_id=src_graph_id, new_label=new_label)
    return FunctionTool(bound_clone_graph, name="clone_graph", description="Clone a Zep graph with a new label.")

def create_search_graph_tool(get_api: GetAPI) -> FunctionTool:
    async def search_memory(
        query: Annotated[str, "The search query to find relevant memories"],*,
        scope: Annotated[Literal["edges", "nodes", "episodes"] | None, "What to search (edges=default)"] = None,
        limit: Annotated[int | None, "Max number of results (<=50)"] = None,
        search_filters: Annotated[Dict[str, Any] | None, "Filter: node_labels/edge_types/..."] = None,
        reranker: Annotated[str | None, "rrf|mmr|node_distance|episode_mentions|cross_encoder"] = None,
        center_node_uuid: Annotated[str | None, "Needed for node_distance reranker"] = None,
        mmr_lambda: Annotated[float | None, "Diversity/relevance tradeoff for mmr"] = None,
        min_fact_rating: Annotated[float | None, "Minimum fact rating filter (edges)"] = None,
        bfs_origin_node_uuids: Annotated[List[str] | None, "Limit search to BFS from these nodes"] = None,
        graph_id: Annotated[str | None, "Custom graph scope"] = None,
        user_id: Annotated[str | None, "User graph scope"] = None,
        extra: Annotated[Dict[str, Any] | None, "Additional params passed to Zep search as-is"] = None,
    ) -> List[Dict[str, Any]]:
        api = get_api()
        params: Dict[str, Any] = {
            "query": query,
            "limit": limit,
            "scope": scope,
            "search_filters": search_filters,
            "reranker": reranker,
            "center_node_uuid": center_node_uuid,
            "mmr_lambda": mmr_lambda,
            "min_fact_rating": min_fact_rating,
            "bfs_origin_node_uuids": bfs_origin_node_uuids,
            "graph_id": graph_id,
            "user_id": user_id,
        }
        if extra:
            for k, v in extra.items():
                if v is not None and (k not in params or params[k] is None):
                    params[k] = v
        return await api.search(**{k: v for k, v in params.items() if v is not None})
    return FunctionTool(
        func=search_memory,
        name="search_graph",
        description="Search the Zep graph (edges/nodes/episodes) with optional filters, rerankers, and pass-through params.",)

def create_add_graph_data_tool(get_api: GetAPI) -> FunctionTool:
    async def bound_add_memory_data(
        data: Annotated[str, "The data/information to store in memory"],
        data_type: Annotated[Literal["text","json","message"], "Type of data: 'text', 'json', or 'message'"] = "text",
        source: Annotated[str | None, "Logical source tag (e.g. 'text'|'message'|'import')"] = None,
        role: Annotated[str | None, "Speaker role for episode content (e.g. 'user'|'assistant')"] = None,
        metadata: Annotated[Dict[str, Any] | None, "Arbitrary metadata dict to attach"] = None,
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.add_data(data=data, data_type=data_type, role=role, source=source, metadata=metadata or {})
    return FunctionTool(bound_add_memory_data, name="add_graph_data", description="Add data/episode into current graph scope.")

def create_get_graph_item_tool(get_api: GetAPI) -> FunctionTool:
    async def bound_get_graph_item(kind: Annotated[str, "'node' or 'edge'"], uuid: Annotated[str, "UUID"], *, graph_id: Annotated[str | None, "Graph override"] = None):
        api = get_api()
        if kind == "node":
            return await api.get_node(uuid, graph_id=graph_id)
        elif kind == "edge":
            return await api.get_edge(uuid, graph_id=graph_id)
        raise ValueError("kind must be 'node' or 'edge'")
    return FunctionTool(bound_get_graph_item, name="get_graph_item", description="Get a node or edge from current graph scope.")

def create_get_node_edges_tool(get_api: GetAPI) -> FunctionTool:
    async def get_node_edges(
        node_uuid: Annotated[str, "Node UUID"],
        *,
        direction: Annotated[Literal["out", "in", "both"] | None, "Which edges to return"] = None,
        graph_id: Annotated[str | None, "Graph override"] = None,
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.get_node_edges(node_uuid=node_uuid, direction=direction, graph_id=graph_id)
    return FunctionTool(
        func=get_node_edges,
        name="get_node_edges",
        description="List edges connected to a given node.",)

def create_delete_edge_tool(get_api: GetAPI) -> FunctionTool:
    async def delete_edge(
        edge_uuid: Annotated[str, "Edge UUID"],
        *,
        graph_id: Annotated[str | None, "Graph override"] = None,
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.delete_edge(edge_uuid=edge_uuid, graph_id=graph_id)
    return FunctionTool(
        func=delete_edge,
        name="delete_edge",
        description="Delete an edge by UUID.",)

def create_delete_episode_tool(get_api: GetAPI) -> FunctionTool:
    async def delete_episode(
        episode_uuid: Annotated[str, "Episode UUID"],
        *,
        graph_id: Annotated[str | None, "Graph override"] = None,
    ) -> Dict[str, Any]:
        api = get_api()
        return await api.delete_episode(episode_uuid=episode_uuid, graph_id=graph_id)
    return FunctionTool(
        func=delete_episode,
        name="delete_episode",
        description="Delete an episode (message/text/json) by UUID.",)