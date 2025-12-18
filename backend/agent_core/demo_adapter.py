# backend/agent_core/demo_adapter.py

import json
import inspect
from typing import Any, Awaitable, Callable, Optional
import asyncio

class DemoAdapter:
    """
    Adapter für ConversableAgents, die als Demos innerhalb des HMA laufen.
    Variante B:
    - Erlaubt Tool-Calls über einfaches JSON-Protokoll.
    - Nutzt einen zentralen call_tool-Dispatcher.

    Ablauf:
        1) Demo erhält base_prompt (Kontext + Aufgabe)
        2) Demo kann antworten:
            a) normaler Text → direkt an HMA
            b) {"tool": "...", "args": {...}} → Tool wird ausgeführt
        3) Tool-Resultat wird an denselben Demo zurückgegeben
        4) Demo fasst Ergebnis für den HMA zusammen
    """

    def __init__(
        self,
        agent: Any,
        call_tool: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> None:
        self.agent = agent
        self.call_tool = call_tool
        self.name = getattr(agent, "name", agent.__class__.__name__)

    async def run(self, *, user_text: str, context: str) -> str:
        """
        Führt Demo aus:
        - Erstversuch: Demo entscheidet, ob Tool nötig ist
        - Falls Tool genutzt wird: Tool ausführen + Demo zweite Runde geben
        """

        base_prompt = (
            "[Kontext]\n"
            f"{context}\n\n"
            "[Aufgabe]\n"
            f"{user_text}\n\n"
            "Hinweis: Wenn du ein Tool verwenden möchtest, antworte NUR mit einer Zeile JSON.\n"
            'Beispiel: {"tool": "search_graph", "args": {"query": "..."}}.\n'
            "Wenn du kein Tool brauchst, antworte direkt."
        )

        # ---- Runde 1 ----
        first_out = await asyncio.to_thread(
            self.agent.generate_reply,
            messages=[{"role": "user", "content": base_prompt}],
            sender=None,
        )

        first_text = self._normalize_output(first_out)

        # Prüfen: Ist das JSON? Enthält es ein Tool?
        tool_spec = self._try_parse_tool(first_text)

        # Kein Tool → direkt zurück
        if not tool_spec or not self.call_tool:
            return first_text

        # ---- Tool ausführen ----
        tool_name = str(tool_spec["tool"])
        tool_args = tool_spec.get("args") or {}

        try:
            res = self.call_tool(tool_name, **tool_args)
            result = await res if inspect.isawaitable(res) else res
            tool_result_text = f"Tool {tool_name} Ergebnis:\n{result}"
        except Exception as e:
            tool_result_text = f"Tool-Aufruf {tool_name} ist fehlgeschlagen: {e}"

        # ---- Runde 2 ---- Demo fasst das Tool-Resultat zusammen ----
        followup_prompt = (
            "[Kontext]\n"
            f"{context}\n\n"
            "[Aufgabe]\n"
            f"{user_text}\n\n"
            "[Tool-Result]\n"
            f"{tool_result_text}\n\n"
            "Bitte formuliere jetzt eine knappe, klare Antwort für den HMA."
        )

        second_out = await asyncio.to_thread(
            self.agent.generate_reply,
            messages=[
                {"role": "user", "content": base_prompt},
                {"role": "assistant", "content": first_text},
                {"role": "user", "content": followup_prompt},
            ],
            sender=None,
        )

        second_text = self._normalize_output(second_out)
        return second_text

    # ----------------------------------------------
    # Hilfsfunktionen
    # ----------------------------------------------

    def _normalize_output(self, out: Any) -> str:
        """AG2-kompatible Normalisierung: tuple oder plain, alles zu string."""
        if isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], (bool, type(None))):
            _, text = out
        else:
            text = out
        return str(text).strip()

    def _try_parse_tool(self, text: str) -> Optional[dict]:
        """Versucht JSON zu parsen und Tool-Spezifikation zu extrahieren."""
        if not (text.startswith("{") and text.endswith("}")):
            return None
        try:
            parsed = json.loads(text)
        except Exception:
            return None
        if isinstance(parsed, dict) and "tool" in parsed:
            return parsed
        return None
