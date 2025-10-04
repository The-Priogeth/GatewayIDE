
from loguru import logger
import asyncio
from watchfiles import watch
import threading

# Globale Sets zur Client-Verwaltung
reload_clients = set()
chat_clients = set()

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
            asyncio.run(broadcast_reload())

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    logger.info("🧵 Watcher-Thread gestartet.")

# Zugriff von außen ermöglichen
__all__ = ["reload_clients", "chat_clients", "broadcast_reload", "broadcast_chat_message", "start_watcher"]
