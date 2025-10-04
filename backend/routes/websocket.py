
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from watchfiles import watch
import threading
from .ws_utils import reload_clients, chat_clients, broadcast_reload, broadcast_chat_message, start_watcher


router = APIRouter()
reload_clients = set()
chat_clients = set()

@router.websocket("/ws/reload")
async def reload_socket(websocket: WebSocket):
    await websocket.accept()
    reload_clients.add(websocket)
    logger.info("🔌 Neuer Reload-Client verbunden.")
    try:
        while True:
            data = await websocket.receive_text()
            if data.lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        reload_clients.discard(websocket)
        logger.info("❌ Reload-Client getrennt.")

@router.websocket("/ws/conference")
async def conference_socket(websocket: WebSocket):
    await websocket.accept()
    chat_clients.add(websocket)
    logger.info("💬 Neuer Konferenz-Client verbunden.")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"💭 Eingehende Nachricht (Konferenz WS): {data}")
            await broadcast_chat_message(data)
    except WebSocketDisconnect:
        chat_clients.discard(websocket)
        logger.info("❌ Konferenz-Client getrennt.")

async def broadcast_reload():
    for client in reload_clients.copy():
        try:
            await client.send_text("reload")
        except Exception:
            reload_clients.discard(client)
            logger.warning("⚠️ Fehler beim Senden an Reload-Client – entfernt.")

async def broadcast_chat_message(message: str):
    for client in chat_clients.copy():
        try:
            await client.send_text(message)
        except Exception:
            chat_clients.discard(client)
            logger.warning("⚠️ Fehler beim Senden an Konferenz-Client – entfernt.")

def start_watcher(path="backend/"):
    def watcher():
        logger.info(f"👀 Watcher gestartet für: {path}")
        for changes in watch(path):
            logger.info(f"📦 Änderung erkannt: {changes}")
            import asyncio
            asyncio.run(broadcast_reload())

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    logger.info("🧵 Watcher-Thread gestartet.")
