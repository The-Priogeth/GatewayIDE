# backend/reset_utils.py
from typing import Optional, Any, cast
from loguru import logger
import uuid
from zep_cloud.client import AsyncZep


# ------------------------------------------------------------------------------
# Delete Thread (standardisiert)
# ------------------------------------------------------------------------------
async def delete_thread_if_exists(zep: AsyncZep, thread_id: Optional[str]) -> None:
    """
    Löscht einen bestehenden Thread, falls thread_id existiert.
    Nutzt Zep.memory.a_delete_thread (asynchron).
    Loggt Events per Loguru.
    """
    if not thread_id:
        logger.debug("🔄 [Reset] Kein Thread zu löschen: thread_id=None")
        return

    try:
        memory_client = cast(Any, zep).memory
        await memory_client.a_delete_thread(thread_id)
        logger.info(f"🗑️ [Reset] Thread gelöscht: {thread_id}")
    except Exception as e:
        logger.warning(f"⚠️ [Reset] Thread konnte nicht gelöscht werden: {thread_id} ({e})")


# ------------------------------------------------------------------------------
# Delete Graph
# ------------------------------------------------------------------------------
async def delete_graph_if_exists(graph_api: Any, graph_id: Optional[str]) -> None:
    """
    Löscht einen Graphen aus Zep, falls er existiert.
    """
    if not graph_id:
        logger.debug("🔄 [Reset] Kein Graph zu löschen: graph_id=None")
        return

    try:
        await graph_api.delete_graph(graph_id)
        logger.info(f"🗑️ [Reset] Graph gelöscht: {graph_id}")
    except Exception as e:
        logger.warning(f"⚠️ [Reset] Graph konnte nicht gelöscht werden: {graph_id} ({e})")


# ------------------------------------------------------------------------------
# ID Generator
# ------------------------------------------------------------------------------
def generate_new_id(prefix: str = "") -> str:
    """
    Erzeugt eine kurze UUID-ID, optional mit Prefix.
    """
    core = uuid.uuid4().hex[:8]
    value = f"{prefix}_{core}" if prefix else core
    logger.debug(f"🔧 [Reset] Neue ID generiert: {value}")
    return value
