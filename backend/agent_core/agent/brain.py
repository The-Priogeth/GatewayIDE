# backend/agents/brain.py
from __future__ import annotations

import os
from backend.ag2.autogen.agentchat.assistant_agent import AssistantAgent
#backend\ag2\autogen\agents\experimental\reasoning reasoning_agent
from typing import Any, Dict, Mapping, Optional, List
from typing import TYPE_CHECKING, Literal
from backend.agents.adapters.ag2 import Ag2AssistantAdapter


from typing import Literal

HIM: Literal['TERMINATE'] = 'TERMINATE'


class BrainAgent(AssistantAgent):
    """
    Brain = erster Sprecher im V3-Flow.
    - Formuliert Annahmen/Fragen und schlägt einen nächsten Schritt vor
    - Bleibt intern (ReturnAgent kuratiert die Nutzer-Antwort)
    - Implementiert unser V3-Interface: `await propose(goal, ctx) -> {content, ...}`
    """

    role = "brain"

    def __init__(
        self,
        *,
        system_message: Optional[str] = None,
        llm_model: Optional[str] = None,
        human_input_mode: str = "NEVER",
    ) -> None:
        # 🔧 Modellwahl aus ENV oder Default
        model = llm_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # 🧠 Systemprompt: kurz & auf Brain-Rolle zugeschnitten
        sys_msg = system_message or (
            "Du bist Brain. Fasse Annahmen und offene Fragen knapp zusammen und "
            "schlage den nächsten sinnvollen Schritt vor. Antworte prägnant."
        )

        # ⚙️ Minimal-konfig für AG2-AssistantAgent
        llm_config: Dict[str, Any] = {
            "model": model,
            # hier bewusst schlank; Temperatur, TopP etc. können später übergeben werden
        }

        # Kein Tooling hier – Brain ist rein sprachlich
        function_map: Dict[str, Any] = {}

        # 👇 echter AG2-Assistent (vendored)
        super().__init__(
            name="brain",
            system_message=sys_msg,
            llm_config=llm_config,
            human_input_mode=HIM,
            function_map=function_map,
        )

    # ----- Prompt-Building -----------------------------------------------------
    @staticmethod
    def _build_prompt(goal: str, ctx: Dict[str, Any]) -> str:
        """
        Baut eine schlanke User-Nachricht für AG2.
        - Nutzt deliverables/constraints, wenn vorhanden
        - Ergebnis: Bitte um Annahmen/Fragen + Next Step
        """
        dels = ctx.get("deliverables") or []
        cons = ctx.get("constraints") or []

        extra: List[str] = []
        if dels:
            extra.append("Lieferobjekte:\n- " + "\n- ".join(map(str, dels)))
        if cons:
            extra.append("Randbedingungen:\n- " + "\n- ".join(map(str, cons)))

        extra_block = ("\n\n" + "\n\n".join(extra)) if extra else ""

        return (
            f"Ziel:\n{goal}\n"
            f"{extra_block}\n\n"
            "Gib kurz:\n"
            "1) Annahmen/Fragen\n"
            "2) Nächster sinnvoller Schritt"
        )

    # ----- V3-Interface: propose ----------------------------------------------
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Führt EINEN Brain-Turn aus.
        Rückgabeform (V3): {content: str, actions: [], signals: {}}
        """
        # 1) Prompt für den Turn bauen
        prompt = self._build_prompt(goal, ctx)

        # 2) An AG2 übergeben – wir verwenden eine simple user-Message
        messages: List[Dict[str, str]] = [{"role": "user", "content": prompt}]
        try:
            out = self.generate_reply(messages)  # AG2 ist synchron → wir wrappen nur
        except Exception:
            out = None

        # 3) Normalisieren + strukturierte Rückgabe
        text = (out or "").strip() if isinstance(out, str) else str(out or "").strip()
        return {"content": text, "actions": [], "signals": {}}
