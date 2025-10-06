
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from watchfiles import watch, Change
import threading

router = APIRouter()
reload_clients = set()

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

def _should_ignore(changes) -> bool:
    for change, path in changes:
        p = str(path).replace("\\", "/")
        if p.endswith("/logs/server.log") or "/logs/" in p:
            return True
    return False


def start_watcher(path="backend/"):
    """
    Startet den Dateiwatcher in einem Daemon-Thread und gibt (thread, stop_event) zurück.
    Mit stop_event.set() lässt er sich sauber beenden.
    """
    stop_event = threading.Event()

    def watcher():
        logger.info(f"👀 Watcher gestartet für: {path}")
        # watchfiles unterstützt stop_event → Iterator endet, wenn Event gesetzt ist
        for changes in watch(path, stop_event=stop_event):
            # optional: zusätzliche Entprellung / Noise-Filter hier einbauen
            if _should_ignore(changes):
                continue
            logger.info(f"📦 Änderung erkannt: {changes}")

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    logger.info("🧵 Watcher-Thread gestartet.")
    return thread, stop_event
