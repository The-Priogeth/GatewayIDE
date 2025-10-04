# backend/agents/base.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Protocol, Sequence, cast
import os
from loguru import logger

class Agent(Protocol):
    """Kleines, neutrales Agent-Interface für V3."""
    role: str
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erwartetes Resultat:
          {
            "content": str,          # Haupttext des Agenten
            "actions": list,         # optionale Aktionen (Side-Effects, Tools)
            "signals": dict,         # Metadaten (Scores, confidences, etc.)
          }
        """
        ...

def _llm_chat(messages: Sequence[dict], model: Optional[str] = None) -> Optional[str]:
    """
    Dünne LLM-Bridge:
    - Unterstützt openai>=1.x (OpenAI()) und openai<1.x (openai.ChatCompletion)
    - Respektiert OPENAI_MODEL / OPENAI_BASE_URL / OPENAI_API_KEY
    - Kein Retry/Budget – bewusst simpel (V3-Policy macht das später)
    """
    mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base = os.getenv("OPENAI_BASE_URL")
    key  = os.getenv("OPENAI_API_KEY", "")

    def _dbg(where: str, e: Exception):
        if os.getenv("LLM_DEBUG") == "1":
            logger.warning("LLM call failed in {}: {}", where, repr(e))

    try:
        from openai import OpenAI  # type: ignore
        kwargs: Dict[str, Any] = {}
        if base: kwargs["base_url"] = base
        if key:  kwargs["api_key"]  = key
        resp = OpenAI(**kwargs).chat.completions.create(
            model=mdl, messages=cast(Any, messages), temperature=0.5
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        _dbg("new-sdk", e)

    try:
        import openai  # type: ignore
        if base: openai.api_base = base  # type: ignore[attr-defined]
        if key:  openai.api_key  = key   # type: ignore[attr-defined]
        resp = openai.ChatCompletion.create(  # type: ignore[attr-defined]
            model=mdl, messages=messages, temperature=0.5
        )
        ch = resp["choices"][0]
        content = ch.get("message", {}).get("content") or ch.get("text")
        return (content or "").strip()
    except Exception as e:
        _dbg("old-sdk", e)

    return None

class LLMEnabledAgent:
    """
    Bequeme Basisklasse für LLM-gestützte Agenten:
    - optionale Systemnachricht
    - einfacher `user_tpl`
    """
    role = "assistant"
    sys_prompt: Optional[str] = None
    user_tpl: str = "{goal}"

    def _build(self, goal: str, ctx: Dict[str, Any]) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = []
        if self.sys_prompt:
            msgs.append({"role": "system", "content": self.sys_prompt})
        msgs.append({"role": "user", "content": self.user_tpl.format(goal=goal)})
        return msgs

    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        out = _llm_chat(self._build(goal, ctx)) or ""
        return {"content": out.strip(), "actions": [], "signals": {}}
