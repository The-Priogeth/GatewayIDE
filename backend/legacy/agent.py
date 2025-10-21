"""
agent.py — Factories für THINK/PLAN/EXECUTE (CaptainAgent) + interne Subagenten (THOUGHT, RETURN)
- Jeder Captain (THINK, PLAN, EXECUTE) kann intern ein kleines Team besitzen:
  { "<CAP>.THOUGHT", "<CAP>.RETURN" } — ohne eigene Zep-Threads.
- Dein gepatchter captainagent.py kann `captain._internal_team` verwenden, um intern erst
  THOUGHT laufen zu lassen und optional an RETURN zu übergeben, bevor der Captain-FINAL entsteht.
"""
from __future__ import annotations

from typing import Callable, Dict, Any
from backend.ag2.autogen.agentchat import ConversableAgent
from backend.ag2.autogen.agentchat.contrib.captainagent import CaptainAgent
from backend.ag2.autogen.agentchat import GroupChat, GroupChatManager
from backend.zep_autogen import ZepUserMemory
# ============================================================
# Kontext-Provider (für Zep-Kontext-Injektion vor jedem Run)
# ============================================================
class ContextProvider:
    """Einfacher Kontext-Provider, den die CaptainAgents via memory_context_provider aufrufen."""
    def __init__(self) -> None:
        self._text: str = ""

    def update(self, text: str) -> None:
        self._text = text or ""

    def __call__(self) -> str:
        return self._text


# ============================================================
# LLM-Konfiguration (Captain-kompatibel: config_list vorhanden)
# ============================================================


def build_llm_config(model: str, api_key: str) -> Dict[str, Any]:
    """
    Gibt eine dict-basierte llm_config zurück (vermeidet LLMConfig-Klassen-Mismatch).
    """
    return {
        "config_list": [
            {
                "model": model,
                "api_key": api_key,
                # Optional:
                # "temperature": 0.2,
                # "api_base": os.getenv("OPENAI_BASE_URL"),
                # "organization": os.getenv("OPENAI_ORG"),
            }
        ],
        # Globale Defaults (optional):
        # "temperature": 0.2,
    }


# ============================================================
# Optionaler Lokalspeicher (nur letzte Antwort pro Rolle)
# Persistenz nach Zep macht chat.py, nicht der Logger!
# ============================================================
def _collector(responses: Dict[str, str], label: str) -> Callable[[str, str, str], None]:
    def _log(role: str, name: str, content: str) -> None:
        if role == "assistant":
            responses[label] = content
    return _log


# ============================================================
# Captain-Fabriken (Top-Level)
# ============================================================
def create_captain_agents(
    llm_cfg: Dict[str, Any],
    context_provider: ContextProvider,
    responses: Dict[str, str],
) -> Dict[str, CaptainAgent]:
    """Erzeugt drei CaptainAgents (THINK, PLAN, EXECUTE) mit Hooks."""
    sys_think = (
        "Rolle: THINK. Antworte auf Deutsch. Denke tiefgründig, identifiziere Annahmen, Risiken, "
        "Alternativen. Antworte ausschließlich mit einem Block: 'THINK:\n<Inhalt>'."
    )
    sys_plan = (
        "Rolle: PLAN(THINK,...). Antworte auf Deutsch. Erzeuge einen konkreten, überprüfbaren Plan "
        "basierend auf THINK. Antworte ausschließlich mit: 'PLAN:\n<Inhalt>'."
    )
    sys_exec = (
        "Rolle: EXECUTE(THINK,...). Antworte auf Deutsch. Führe den Plan gedanklich aus, simuliere "
        "Ergebnisse, nenne offene Punkte. Antworte ausschließlich mit: 'EXECUTE:\n<Inhalt>'."
    )

    agent_think = CaptainAgent(
        name="THINK",
        system_message=sys_think,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
        memory_context_provider=context_provider,
        memory_logger=_collector(responses, "THINK"),
    )
    agent_plan = CaptainAgent(
        name="PLAN",
        system_message=sys_plan,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
        memory_context_provider=context_provider,
        memory_logger=_collector(responses, "PLAN"),
    )
    agent_exec = CaptainAgent(
        name="EXECUTE",
        system_message=sys_exec,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
        memory_context_provider=context_provider,
        memory_logger=_collector(responses, "EXECUTE"),
    )
    return {"THINK": agent_think, "PLAN": agent_plan, "EXECUTE": agent_exec}

# ============================================================
# Interne Subagenten pro Captain (THOUGHT & RETURN)
# ============================================================
def create_thought_agent(llm_cfg: Dict[str, Any], owner_label: str) -> ConversableAgent:
    """Subagent 'THOUGHT' für einen Captain (z. B. THINK.THOUGHT, PLAN.THOUGHT, EXECUTE.THOUGHT)."""
    sys_msg = (
        f"Rolle: THOUGHT for {owner_label}. Antworte auf Deutsch. Reflektiere präzise, "
        "liste Annahmen, Risiken, Alternativen. Antworte ausschließlich mit: 'THOUGHT:\n<Inhalt>'."
    )
    return ConversableAgent(
        name=f"{owner_label}.THOUGHT",
        system_message=sys_msg,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
    )


def create_internal_return_agent(llm_cfg: Dict[str, Any], owner_label: str) -> ConversableAgent:
    """Subagent 'RETURN' für einen Captain (finalisiert interne Zwischenergebnisse)."""
    sys_msg = (
        f"Rolle: RETURN for {owner_label}. Antworte auf Deutsch. Fasse die Zwischenergebnisse des internen "
        "Teams prägnant zusammen. Antworte ausschließlich mit: 'RETURN:\n<Inhalt>'."
    )
    return ConversableAgent(
        name=f"{owner_label}.RETURN",
        system_message=sys_msg,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
    )


def attach_internal_team(captain: CaptainAgent, thought: ConversableAgent, ret: ConversableAgent) -> None:
    """Hängt dem Captain eine interne Team-Definition an (wird von deinem captainagent.py gelesen)."""
    setattr(captain, "_internal_team", {"THOUGHT": thought, "RETURN": ret})
    try:
        desc = (getattr(captain, "description", None) or "").strip()
        add = (
            "\n\n# Internal Team\n"
            f"- {captain.name}.THOUGHT: liefert THOUGHT:...\n"
            f"- {captain.name}.RETURN:  liefert RETURN:...\n"
            "Nutze zuerst THOUGHT, und gib erst an RETURN ab, wenn ein interner Abschluss erreicht ist."
        )
        setattr(captain, "description", (desc + add) if desc else add)
    except Exception:
        pass


def create_captains_with_internal_team(
    llm_cfg: Dict[str, Any],
    context_provider: ContextProvider,
    zep_client,
    memory_map: Dict[str, ZepUserMemory],
    thread_map: Dict[str, str],
) -> tuple[Dict[str, CaptainAgent], Dict[str, Any]]:
    """
    Wie create_captain_agents, aber mit je einem internen THOUGHT + RETURN pro Captain vorbereitet.
    Gibt (captains, internal_map) zurück, wobei internal_map[label] = {"THOUGHT": ..., "RETURN": ...}.
    """
    # responses fürs Logging erzeugen (optional, aber praktisch)
    responses: Dict[str, str] = {"THINK": "", "PLAN": "", "EXECUTE": ""}

    captains = create_captain_agents(llm_cfg, context_provider, responses)
    internal_map: Dict[str, Dict[str, ConversableAgent]] = {}
    for label, cap in captains.items():
        t = create_thought_agent(llm_cfg, label)
        r = create_internal_return_agent(llm_cfg, label)
        attach_internal_team(cap, t, r)
        internal_map[label] = {"THOUGHT": t, "RETURN": r}
    return captains, internal_map


def create_top_level_return_agent(llm_cfg: Dict[str, Any]) -> ConversableAgent:
    """Top-Level RETURN für die Lobby (finalisiert die Gesamtunterhaltung)."""
    sys_msg = (
        "Rolle: RETURN (Top-Level). Antworte auf Deutsch. "
        "Falls die Konversation aus Sicht von THINK/PLAN/EXECUTE ausreichend ist, "
        "schließe sie mit 'TERMINATE' ab. Antworte ausschließlich mit: 'RETURN:\\n<Inhalt>'."
    )
    return ConversableAgent(
        name="RETURN",
        system_message=sys_msg,
        human_input_mode="NEVER",
        llm_config=llm_cfg,
    )

# ============================================================
# Lobby = GroupChat(THINK, PLAN, EXECUTE, RETURN) + Manager
# ============================================================
def create_lobby(llm_cfg: Dict[str, Any], captains: Dict[str, CaptainAgent]) -> dict[str, Any]:
    """
    Erstellt die Lobby mit Auto-Pattern:
      - Agents: THINK, PLAN, EXECUTE, RETURN (Top-Level)
      - GroupChatManager entscheidet, wer spricht (kein fixes Sequencing).
    """
    ret = create_top_level_return_agent(llm_cfg)
    agent_list = [captains["THINK"], captains["PLAN"], captains["EXECUTE"], ret]
    gc = GroupChat(
        agents=agent_list,
        messages=[],
        # Du kannst Wiederholungen begrenzen/erlauben:
        allow_repeat_speaker=agent_list,   # frei für Manager
        max_round=8,
    )
    manager = GroupChatManager(groupchat=gc, llm_config=llm_cfg)
    return {"groupchat": gc, "manager": manager, "return": ret}