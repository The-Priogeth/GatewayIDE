# backend/agent_core/llm_adapter.py
from __future__ import annotations

from typing import Any


class LLMAdapter:
    """
    Dünner Wrapper um einen ConversableAgent, der als Ich-Agent fungiert.

    Erwartetes Verhalten des Ich-Agenten (per system_message konfiguriert):
    - Er erhält als Input einen Prompt mit:
        - Plan-Block
        - "# Interner Zwischenstand" mit allen Demo-Antworten
    - Er formt daraus eine kurze Ich-Antwort in der 1. Person Singular,
      deren erstes Wort "Ich" ist.
    - Am Ende fügt er GENAU EIN Routing-Tag an:
        <<<ROUTE>>> {"deliver_to":"user"|"task"|"lib"|"trn","args":{}} <<<END>>>
    - Er gibt sonst nichts zusätzlich aus.
    """

    def __init__(self, agent: Any) -> None:
        """
        agent: z. B. ein AG2-ConversableAgent mit passender system_message.
        """
        self.agent = agent

    def completion(self, *, system: str, prompt: str) -> str:
        """
        HMA-Interface:
        - 'system' ist der SOM-Systemprompt (som_system_prompt)
        - 'prompt' ist der komplette Final-Prompt (Plan + Interner Zwischenstand + Aufgabe)

        Wir reichen beides als Nachrichten an den Ich-Agenten durch:
        - zusätzliche system-Nachricht
        - user-Nachricht mit dem kompletten Prompt
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        out = self.agent.generate_reply(messages=messages, sender=None)

        # AG2 gibt manchmal (ok, text) oder direkt text zurück
        if isinstance(out, tuple) and len(out) == 2:
            _, text = out
        else:
            text = out

        return str(text).strip()
