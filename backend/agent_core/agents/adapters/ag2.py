# backend/agents/adapters/ag2.py
from __future__ import annotations
from typing import Any, Dict, Callable, Optional, Literal, Protocol, Sequence, cast
import asyncio
import os

from backend.ag2.autogen.agentchat.assistant_agent import AssistantAgent  # noqa: F401
_LLM_BRIDGE_AVAILABLE = False  # Lazy-Import später in propose()

class Agent(Protocol):
    """Minimales Protokoll, das der GroupChatManager erwartet."""
    role: str
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]: ...

def _default_make_prompt(goal: str, ctx: Dict[str, Any]) -> str:
    """Standard: benutze das Ziel 1:1 als Prompt (Manager injiziert Kontext separat)."""
    return goal

class Ag2AssistantAdapter(Agent):
    """
    Adapter: AG2 AssistantAgent -> unser V3-Agent-Interface.
    - Bewahrt eine klare Abtrennung: 'propose(goal, ctx)' liefert {content, signals}.
    - Nutzt AG2, wenn verfügbar; sonst Fallback auf _llm_chat().
    """
    role: str

    def __init__(
        self,
        *,
        role: str,
        system_message: str,
        make_prompt: Callable[[str, Dict[str, Any]], str] | None = None,
        llm_model: Optional[str] = None,
        human_input_mode: Literal['ALWAYS', 'NEVER', 'TERMINATE'] = "NEVER",
        function_map: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.role = role
        self.system_message = system_message                         # <-- für späteren Zugriff
        self.make_prompt = make_prompt or _default_make_prompt

        # Modellwahl zentralisieren
        self.model = llm_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        llm_cfg: Dict[str, Any] = {"model": self.model}
        if llm_config:
            llm_cfg.update(llm_config)

        # Echten AG2-Agenten bauen (funktioniert auch ohne Tools/Functions)
        self.assistant = AssistantAgent(
            name=role,
            system_message=system_message,
            llm_config=llm_cfg,
            human_input_mode=human_input_mode,
            function_map=function_map or {},
        )

    async def _ag2_generate(self, prompt: str) -> Optional[str]:
        """
        Versuche, synchronen AG2-Call nicht-blockierend im Thread auszuführen.
        Viele AG2-Implementierungen sind sync; deshalb Offload in Executor.
        """
        try:
            # AG2-API ist nicht immer identisch; wir versuchen sinnvolle Defaults
            def _call() -> str | None:
                # häufige Varianten:
                #  1) generate_reply(prompt: str) -> str
                #  2) generate_reply(messages=[...]) -> dict/str
                fn = getattr(self.assistant, "generate_reply", None)
                if callable(fn):
                    try:
                        # 1) Prompt-Variante
                        out = fn(prompt)  # type: ignore[call-arg]
                    except TypeError:
                        # 2) Messages-Variante
                        out = fn(messages=[{"content": prompt}])  # type: ignore[call-arg]
                else:
                    # Fallback: manchmal heißt es 'reply' oder ähnlich
                    fn = getattr(self.assistant, "reply", None)
                    if not callable(fn):
                        return None
                    out = fn(prompt)  # type: ignore[call-arg]

                # Normalisieren
                if isinstance(out, str):
                    return out.strip()
                if isinstance(out, dict):
                    txt = (out.get("content") or out.get("reply") or "")
                    return (txt or "").strip()
                return str(out or "").strip()

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _call)
        except Exception:
            return None

    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Liefert genau eine Nachricht (ein Turn).
        Rückgabeformat:
          { "content": <str>, "signals": { "trace": [...optional...] } }
        """
        prompt = self.make_prompt(goal, ctx)

        # Trace nur, wenn der Manager Debug aktiviert hat – hier sammeln wir lokal
        trace: list[list[str]] = []

        # 1) Versuche AG2
        text: Optional[str] = await self._ag2_generate(prompt)
        if text:
            return {"content": text, "signals": {"trace": trace}}

        # 2) Fallback: unsere LLM-Bridge (_llm_chat)
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_message}]
        cb = (ctx.get("context_block") or "").strip()
        if cb:
            messages.append({"role": "system", "content": f"Kontext (kompakt):\n{cb}"})
        messages.append({"role": "user", "content": prompt})

        text2: str = ""
        # Lazy-Import, um Zirkularimporte zu vermeiden (Manager ist zu diesem Zeitpunkt bereits geladen)
        _llm = None
        try:
            from backend.groupchat_manager import _llm_chat as _llm  # type: ignore
        except Exception:
            _llm = None

        if callable(_llm):
            try:
                out = _llm(cast(Sequence[Dict[str, Any]], messages), model=self.model)  # type: ignore[arg-type]
                text2 = (out or "").strip()
            except Exception:
                text2 = ""
        if not text2:
            # Minimaler Notfall-Text, falls weder AG2 noch LLM erreichbar
            text2 = f"(fallback) {prompt}"

        return {"content": text2, "signals": {"trace": trace}}
