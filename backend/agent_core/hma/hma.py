# backend/agent_core/hma.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Callable, Optional, Tuple
from .routing import parse_deliver_to
from .selectors import select_demos, aggregate, build_findings
from backend.agent_core.hma.speaker import Speaker

import inspect

class HMA:
    def __init__(self, *, som_system_prompt: str, templates: Any,
                 demos: Iterable[Any], messaging: Any, llm: Any,
                 speaker: Speaker | None = None, ctx_provider: Any | None = None):
        self._sys = som_system_prompt
        self._tpl = templates
        self._demos = list(demos)
        self._msg = messaging
        self._llm = llm
        self._speaker = speaker
        self._ctx = ctx_provider

    async def run(self, *, user_text: str, context: str = "") -> Dict[str, Any]:
        # 0) Speicher-/Verlaufskontext (z. B. ZepMemory) sicher holen
        ctx_block = ""
        if self._ctx:
            fn: Optional[Callable[..., Any]] = getattr(self._ctx, "get_context", None)
            if callable(fn):
                try:
                    res = fn(include_recent=True, graph=False)
                    ctx_block = (await res) if inspect.isawaitable(res) else (str(res) or "")
                except Exception as e:
                    self._msg.log(f"[Ctx:get_context] {e}", scope="HMA")
                    ctx_block = ""

        # Eingabe-Context und Speicher-Context zusammenführen
        merged_context = f"{context}\n\n{ctx_block}".strip() if (context and ctx_block) else (context or ctx_block)

        # 1) Demos auswählen + inneres Material bauen
        chosen = select_demos(user_text, merged_context, self._demos)
        pairs = self._parallel_demo(chosen, user_text, merged_context)
        inner_material = aggregate(pairs)
        findings = build_findings(pairs)
        if findings:
            inner_material = f"{inner_material}\n\n{findings}"

        # 2) Plan-Block mit realem Kontext
        plan_block = self._tpl.som_plan_template.format(
            user_text=user_text,
            context=merged_context,
            capabilities=self._tpl.capabilities
        )

        # 3) Final-Prompt
        final_prompt = (
            f"{plan_block}\n\n"
            f"# Interner Zwischenstand\n{inner_material}\n\n"
            f"{self._tpl.som_final_template.split('# Interner Zwischenstand')[-1]}"
        )

        # 4) LLM-Aufruf (sync oder async abfangen) + Routing
        llm_out = self._call_llm(final_prompt)
        ich_text = await llm_out if inspect.isawaitable(llm_out) else llm_out
        ich_text = ich_text or ""
        route = parse_deliver_to(ich_text)

        # 5) Speaker übernimmt (normaler Pfad)
        if self._speaker:
            return await self._speaker.deliver(
                out={"ich_text": ich_text, "route": route, "inner": inner_material},
                speaker_name="SOM"
            )

        # 6) Fallback-Envelope (wenn kein Speaker gesetzt)
        resp_items = []
        if inner_material:
            resp_items.append({"agent": "SOM:INNER", "content": inner_material})
        if ich_text:
            resp_items.append({"agent": "SOM", "content": ich_text})

        return {
            "ok": True,
            "final": True,
            "deliver_to": getattr(route, "target", "user"),
            "deliver_to_thread": None,
            "route_args": getattr(route, "args", {}) or {},
            "speaker": "SOM",
            "corr_id": None,
            "packet_id": None,
            "p_snapshot": None,
            "inner": inner_material,
            "responses": resp_items,
        }



    # ---- interne Helfer ----------------------------------------------------
    def _parallel_demo(self, demos: Iterable[Any], user_text: str, context: str) -> list[Tuple[str, str]]:
        results: list[Tuple[str, str]] = []
        for d in demos:
            try:
                name = getattr(d, "name", d.__class__.__name__)
                reply = d.run(user_text=user_text, context=context)
                if reply:
                    results.append((name, str(reply)))
            except Exception as e:
                self._msg.log(f"[DemoError] {d}: {e}", scope="HMA")
        return results

    def _call_llm(self, final_prompt: str) -> str:
        # vereinheitlichter Aufruf mit System-Prompt
        return self._llm.completion(system=self._sys, prompt=final_prompt)
