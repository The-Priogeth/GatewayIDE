from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os, json

from backend.agent_core.core import build_user_proxy, build_admin, build_manager_config
from backend.ag2.autogen import GroupChat, GroupChatManager

router = APIRouter()

HISTORY_PATH = Path(__file__).resolve().parent / ".." / "history" / "conferences" / "main_lobby.json"
HISTORY_DIR = HISTORY_PATH.resolve()

conference_managers: dict[str, GroupChatManager] = {}

# 🏡 Models
class ConferenceMessage(BaseModel):
    room: str
    message: str

# 🧠 Helferfunktionen
def get_history_path(room: str) -> Path:
    return HISTORY_DIR / f"{room}.json"

def load_conference_history(room: str) -> list:
    path = get_history_path(room)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("messages", [])
    return []

def save_conference_history(room: str, messages: list):
    path = get_history_path(room)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"messages": messages}, f, indent=2)

def get_conference_manager(room: str) -> Optional[GroupChatManager]:
    return conference_managers.get(room)

# 🔄 Konferenz starten
@router.post("/api/conference/start")
def start_conference(request: Request):
    data = request.query_params or request.json()
    room = data.get("room", "debug-conf")

    if room in conference_managers:
        return {"success": False, "message": f"Konferenz '{room}' bereits gestartet."}

    user_proxy = build_user_proxy()
    admin = build_admin()
    messages = load_conference_history(room) or [{"role": "system", "content": "Conference started"}]

    group = GroupChat(agents=[user_proxy, admin], messages=messages, max_round=10)
    manager = GroupChatManager(
        groupchat=group,
        name=f"{room}_manager",
        llm_config=build_manager_config(),
        human_input_mode="NEVER",
        system_message=f"Dies ist der Gruppenmanager für Raum {room}."
    )

    conference_managers[room] = manager
    save_conference_history(room, group.messages)
    return {"success": True, "message": f"Konferenz '{room}' gestartet."}

# 🔣 Nachricht an Konferenz
@router.post("/api/conference/say")
def say_to_conference(msg: ConferenceMessage):
    manager = get_conference_manager(msg.room)
    if not manager:
        raise HTTPException(status_code=404, detail="Konferenz nicht gefunden.")

    reply = manager.run_chat(msg.message)
    save_conference_history(msg.room, manager.groupchat.messages)
    return {"success": True, "reply": reply}

# 📜 Verlauf abrufen
@router.get("/api/conference/history")
def get_conference_history(room: str):
    history = load_conference_history(room)
    return {"success": True, "history": history}

# 📋 Alle Konferenzen listen
@router.get("/api/conference/list")
def list_conferences():
    rooms = [p.stem for p in HISTORY_DIR.glob("*.json")]
    return {"success": True, "rooms": rooms}
