# backend/agent_core/tool_reg.py
from __future__ import annotations

import os
import asyncio
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List

from zep_cloud.client import AsyncZep
from autogen_core.tools import FunctionTool

from ..memory.graph_api import GraphAPIProvider
from ..memory.memory import ZepGraphAdmin
from ..memory.memory_tools import (
    create_search_graph_tool,
    create_add_graph_data_tool,
    create_set_ontology_tool,
    create_add_node_tool,
    create_add_edge_tool,
    create_clone_graph_tool,
    create_clone_user_graph_tool,
    create_get_graph_item_tool,
    create_get_node_edges_tool,
    create_delete_edge_tool,
    create_delete_episode_tool,
)


async def setup_tools(
    *,
    zep: AsyncZep,
    base_user: str | None,
    graph_id: str | None = None,
) -> SimpleNamespace:
    """
    Zentrales Tool-Setup für den Gateway-Hauptgraphen.

    Responsibilities:
    - Graph anlegen (falls nötig)
    - GraphAPIProvider + get_api erzeugen
    - Alle FunctionTools registrieren
    - call_tool(name, **kwargs) bereitstellen

    Rückgabe: SimpleNamespace mit:
        graph_api_provider
        get_api
        tools
        tool_registry
        call_tool
    """
    graph_id = graph_id or os.getenv("ZEP_GRAPH_ID", "gateway_main")
    if not base_user:
        # Fallback, sollte aber im Normalfall gesetzt sein (T1_USER_ID oder ZEP_USER_ID)
        base_user = "gateway_base_user"

    # --- Graph-Admin: einmaliger Graph-Create-Call --------------------------
    admin = ZepGraphAdmin(client=zep, user_id=base_user, graph_id=graph_id)

    try:
        await admin.create_graph(
            graph_id=graph_id,
            name="Gateway Main",
            description="GatewayIDE globaler Hauptgraph",
        )
    except Exception as e:
        # Soft-Fail: Wenn der Graph schon existiert, bekommen wir meist 4xx → nur Hinweis loggen.
        print(f"[tool_reg] Hinweis: create_graph('{graph_id}') fehlgeschlagen: {e!r}")

    # --- Provider + Tools ----------------------------------------------------
    provider = GraphAPIProvider(client=zep, graph_id=graph_id, user_id=base_user)
    get_api = provider.get_api

    tools: List[FunctionTool] = [
        create_search_graph_tool(get_api),
        create_add_graph_data_tool(get_api),
        create_set_ontology_tool(get_api),
        create_add_node_tool(get_api),
        create_add_edge_tool(get_api),
        create_clone_graph_tool(get_api),
        create_clone_user_graph_tool(get_api),
        create_get_graph_item_tool(get_api),
        create_get_node_edges_tool(get_api),
        create_delete_edge_tool(get_api),
        create_delete_episode_tool(get_api),
    ]
    tool_registry: Dict[str, FunctionTool] = {t.name: t for t in tools}

    async def call_tool(name: str, /, **kwargs: Any) -> Any:
        """
        Einheitlicher Aufruf für registrierte FunctionTools.
        Nutzt bevorzugt .func (async), fällt auf .invoke(**kwargs) zurück.
        """
        tool = tool_registry.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        fn = getattr(tool, "func", None)
        if callable(fn):
            res = fn(**kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        inv = getattr(tool, "invoke", None)
        if callable(inv):
            res = inv(kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        raise RuntimeError(f"Tool {name} has neither async func nor invoke")

    return SimpleNamespace(
        graph_api_provider=provider,
        get_api=get_api,
        tools=tools,
        tool_registry=tool_registry,
        call_tool=call_tool,
    )
