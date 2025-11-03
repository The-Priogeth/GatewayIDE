# backend/memory/memory_tools.py
"""
Zep AutoGen Tools (offizielle Location).
Tools zum Suchen/Schreiben im Zep-Graph/User-Graph. 
Ehemals backend.zep_autogen.tools – jetzt konsolidiert unter backend.memory.
"""
from __future__ import annotations
import logging
from typing import Annotated, Any
from autogen_core.tools import FunctionTool
from zep_cloud.client import AsyncZep

logger = logging.getLogger(__name__)

async def search_memory(
    client: AsyncZep,
    query: Annotated[str, "The search query to find relevant memories"],
    graph_id: Annotated[str | None, "Graph ID to search in (for generic knowledge graph)"] = None,
    user_id: Annotated[str | None, "User ID to search graph for (for user knowledge graph)"] = None,
    limit: Annotated[int, "Maximum number of results to return"] = 10,
    scope: Annotated[
        str | None,
        "Scope of search: 'edges' (facts), 'nodes' (entities), 'episodes' (for knowledge graph). Defaults to edges",
    ] = "edges",
) -> list[dict[str, Any]]:
    if not graph_id and not user_id:
        raise ValueError("Either graph_id or user_id must be provided")
    if graph_id and user_id:
        raise ValueError("Only one of graph_id or user_id should be provided")
    try:
        results = []
        if graph_id:
            search_results = await client.graph.search(graph_id=graph_id, query=query, limit=limit, scope=scope)
        else:
            search_results = await client.graph.search(user_id=user_id, query=query, limit=limit)
        if getattr(search_results, "edges", None):
            for edge in (getattr(search_results, "edges", []) or []):
                results.append({
                    "content": edge.fact,
                    "type": "edge",
                    "name": edge.name,
                    "attributes": edge.attributes or {},
                    "created_at": edge.created_at,
                    "valid_at": edge.valid_at,
                    "invalid_at": edge.invalid_at,
                    "expired_at": edge.expired_at,
                })
        if getattr(search_results, "nodes", None):
            for node in (getattr(search_results, "nodes", []) or []):
                results.append({
                    "content": f"{node.name}: {node.summary}",
                    "type": "node",
                    "name": node.name,
                    "attributes": node.attributes or {},
                    "created_at": node.created_at,
                })
        if getattr(search_results, "episodes", None):
            for episode in (getattr(search_results, "episodes", []) or []):
                results.append({
                    "content": episode.content,
                    "type": "episode",
                    "source": episode.source,
                    "role": episode.role,
                    "created_at": episode.created_at,
                })
        logger.info(f"Found {len(results)} memories for query: {query}")
        return results
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        return []

async def add_graph_data(
    client: AsyncZep,
    data: Annotated[str, "The data/information to store in the graph"],
    graph_id: Annotated[str | None, "Graph ID to store data in (for graph memory)"] = None,
    user_id: Annotated[str | None, "User ID to store data for (for user memory)"] = None,
    data_type: Annotated[str, "Type of data: 'text', 'json', or 'message'"] = "text",
) -> dict[str, Any]:
    if not graph_id and not user_id:
        raise ValueError("Either graph_id or user_id must be provided")
    if graph_id and user_id:
        raise ValueError("Only one of graph_id or user_id should be provided")
    try:
        if graph_id:
            await client.graph.add(graph_id=graph_id, type=data_type, data=data)
            logger.debug(f"Added data to graph {graph_id}")
            return {"success": True, "message": "Data added to graph memory", "graph_id": graph_id, "data_type": data_type}
        else:
            await client.graph.add(user_id=user_id, type=data_type, data=data)
            logger.debug(f"Added data to user graph {user_id}")
            return {"success": True, "message": "Data added to user graph memory", "user_id": user_id, "data_type": data_type}
    except Exception as e:
        logger.error(f"Error adding memory data: {e}")
        return {"success": False, "message": f"Failed to add data: {str(e)}"}

def create_search_graph_tool(client: AsyncZep, graph_id: str | None = None, user_id: str | None = None) -> FunctionTool:
    if not graph_id and not user_id:
        raise ValueError("Either graph_id or user_id must be provided when creating the tool")
    if graph_id and user_id:
        raise ValueError("Only one of graph_id or user_id should be provided when creating the tool")
    async def bound_search_memory(
        query: Annotated[str, "The search query to find relevant memories"],
        limit: Annotated[int, "Maximum number of results to return"] = 10,
        scope: Annotated[
            str | None,
            "Scope of search: 'edges' (facts), 'nodes' (entities), 'episodes' (for knowledge graph). Defaults to edges",
        ] = "edges",
    ) -> list[dict[str, Any]]:
        return await search_memory(client, query, graph_id, user_id, limit, scope)
    return FunctionTool(bound_search_memory, description=f"Search Zep memory storage for relevant information in {'graph ' + (graph_id or '') if graph_id else 'user ' + (user_id or '')}.")

def create_add_graph_data_tool(client: AsyncZep, graph_id: str | None = None, user_id: str | None = None) -> FunctionTool:
    if not graph_id and not user_id:
        raise ValueError("Either graph_id or user_id must be provided when creating the tool")
    if graph_id and user_id:
        raise ValueError("Only one of graph_id or user_id should be provided when creating the tool")
    async def bound_add_memory_data(
        data: Annotated[str, "The data/information to store in memory"],
        data_type: Annotated[str, "Type of data: 'text', 'json', or 'message'"] = "text",
    ) -> dict[str, Any]:
        return await add_graph_data(client, data, graph_id, user_id, data_type)
    return FunctionTool(bound_add_memory_data, description=f"Add data to Zep memory storage in {'graph ' + (graph_id or '') if graph_id else 'user ' + (user_id or '')}.")
