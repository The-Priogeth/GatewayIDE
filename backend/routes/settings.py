# backend/routes/settings.py
from fastapi import APIRouter, HTTPException
from typing import List
import os, json
from pydantic import BaseModel
from loguru import logger

router = APIRouter(prefix="/api/agents", tags=["settings"])

AGENTS_DIR = "./config/agents_config_list"

class AgentStatus(BaseModel):
    name: str
    status: str

class DeleteResponse(BaseModel):
    success: bool
    message: str

class AgentSettings(BaseModel):
    name: str
    status: str
    system_message: str
    llm_config: dict

@router.get("/status", response_model=List[AgentStatus])
async def get_agents_status():
    try:
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
        logger.info(f"📋 {len(agents)} Agentenstatus geladen.")
        return agents
    except Exception as e:
        logger.exception("❌ Fehler beim Laden des Agentenstatus")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete/{name}", response_model=DeleteResponse)
async def delete_agent(name: str):
    try:
        path = os.path.join(AGENTS_DIR, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"🗑 Agent '{name}' gelöscht.")
            return {"success": True, "message": f"Agent {name} gelöscht."}
        else:
            logger.warning(f"🔍 Löschversuch fehlgeschlagen: Agent '{name}' nicht gefunden.")
            raise HTTPException(status_code=404, detail="Agent nicht gefunden.")
    except Exception as e:
        logger.exception(f"❌ Fehler beim Löschen von Agent '{name}'")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings/{name}", response_model=AgentSettings)
async def get_agent_settings(name: str):
    try:
        path = os.path.join(AGENTS_DIR, f"{name}.json")
        if not os.path.exists(path):
            logger.warning(f"⚠️ Agent '{name}' nicht gefunden.")
            raise HTTPException(status_code=404, detail="Agent nicht gefunden")

        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)

        logger.info(f"⚙️ Einstellungen für Agent '{name}' geladen.")
        return config
    except Exception as e:
        logger.exception(f"❌ Fehler beim Laden der Einstellungen für Agent '{name}'")
        raise HTTPException(status_code=500, detail=str(e))
