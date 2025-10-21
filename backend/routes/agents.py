# backend/routes/agents.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List
import os
import json

from loguru import logger
# 🔧 Hilfsfunktion importieren (aus agent_core/core.py)
from agent_core.konstruktor import load_agent_profile

router = APIRouter(prefix="/api/agents", tags=["Agents"])

AGENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents_config_list"))

# 📋 Response-Modell
class AgentStatus(BaseModel):
    name: str
    status: str

class CreateAgentRequest(BaseModel):
    name: str
    profile: str = "default"

from typing import Optional

class AgentResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    reply: Optional[str] = None

# 📋 Alle Agenten auflisten
@router.get("/status", response_model=List[AgentStatus])
async def get_agents_status():
    if not os.path.exists(AGENTS_DIR):
        os.makedirs(AGENTS_DIR)

    agents = []
    for filename in os.listdir(AGENTS_DIR):
        if filename.endswith(".json"):
            path = os.path.join(AGENTS_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
                agents.append({
                    "name": config.get("name", filename.replace(".json", "")),
                    "status": config.get("status", "idle")
                })
    return agents

# ➕ Neuen Agenten anlegen
@router.post("/create", response_model=AgentResponse)
async def create_agent(request: CreateAgentRequest):
    try:
        agent_config = load_agent_profile(request.profile)
        if agent_config is None:
            raise HTTPException(status_code=404, detail=f"Profil '{request.profile}' nicht gefunden.")

        agent_config["name"] = request.name
        os.makedirs(AGENTS_DIR, exist_ok=True)
        
        path = os.path.join(AGENTS_DIR, f"{request.name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(agent_config, f, indent=2)

        logger.info(f"➕ Agent '{request.name}' gespeichert mit Profil '{request.profile}'")
        return {"success": True, "message": f"Agent {request.name} gespeichert."}
    except Exception as e:
        logger.exception(f"❌ Fehler beim Erstellen von Agent '{request.name}'")
        raise HTTPException(status_code=500, detail=str(e))


# ❌ Agent löschen
@router.delete("/delete/{name}", response_model=AgentResponse)
async def delete_agent(name: str):
    path = os.path.join(AGENTS_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)
        return {"success": True, "message": f"Agent {name} gelöscht."}
    else:
        raise HTTPException(status_code=404, detail="Agent nicht gefunden.")

# 💬 Agent antwortet
class AgentMessage(BaseModel):
    message: str

@router.post("/respond/{name}", response_model=AgentResponse)
async def respond_agent(name: str, request: AgentMessage):
    path = os.path.join(AGENTS_DIR, f"{name}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Agent nicht gefunden.")

    with open(path, "r", encoding="utf-8") as f:
        agent = json.load(f)

    llm = agent.get("llm_config") or {}
    config_list = llm.get("config_list")
    api_key = ""

    if isinstance(config_list, list) and len(config_list) > 0:
        api_key = config_list[0].get("api_key", "").strip()

    if api_key == "{{global}}" or not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(status_code=403, detail="Kein gültiger API-Key gesetzt.")

    if api_key == "{{global}}" or not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=403, detail="Kein gültiger API-Key gesetzt.")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        logger.info(f"💬 Agent '{name}' antwortet auf: {request.message}")
        response = client.chat.completions.create(
            model=llm.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": agent.get("system_message", "You are a helpful assistant.")},
                {"role": "user", "content": request.message}
            ],
            temperature=llm.get("temperature", 0.7),
            max_tokens=llm.get("max_tokens", 2048)
        )
        reply = response.choices[0].message.content
        logger.info(f"✅ Antwort von Agent '{name}': {reply[:100]}..." if reply else f"⚠️ Keine Antwort erhalten von Agent '{name}'")
        return {"success": True, "reply": reply}
    except Exception as e:
        logger.exception(f"❌ Fehler bei Agentenantwort von '{name}'")
        raise HTTPException(status_code=500, detail=str(e))
    

