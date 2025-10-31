# backend/agent_core/hma.py
from __future__ import annotations
from typing import Any, Iterable, Tuple
from .routing import parse_deliver_to, Route
from .selectors import select_demos, aggregate, build_findings

class HMA:
    """
    Haupt-Meta-Agent (SOM-Kern):
    - Fächert zu Demos auf (parallel/sequenziell – hier einfach gehalten).
    - Baut Final-Prompt, ruft LLM, parst deliver_to.
    - Gibt {"ich_text", "route"} zurück. Keine Fallbacks.
    """
    def __init__(self, *, som_system_prompt: str, templates: Any,
                 demos: Iterable[Any], messaging: Any, llm: Any):
        self._sys = som_system_prompt
        self._tpl = templates
        self._demos = list(demos)
        self._msg = messaging
        self._llm = llm  # injizierter LLM-Client/Wrapper

    # ---- externes API --------------------------------------------------------
    async def run_inner_cycle(self, user_text: str, context: str) -> dict[str, Any]:
        """
        Führt den inneren Zyklus aus (Slim-Variante, async).
        """
        chosen = select_demos(user_text, context, self._demos)
        pairs = self._parallel_demo(chosen, user_text, context)
        inner_material = aggregate(pairs)
        findings = build_findings(pairs)
        if findings:
            inner_material = f"{inner_material}\n\n{findings}"

        final_prompt = self._tpl.som_final_template.format(
            user_text=user_text,
            aggregate=inner_material,
        )

        ich_text = self._call_llm(final_prompt)
        route: Route = parse_deliver_to(ich_text)

        # 👉 In T2 persistieren
        try:
            from backend.bootstrap import _runtime_singleton as _rt
            t2_mem = getattr(_rt, "t2_memory", None)
            if t2_mem:
                await self._msg.log_som_internal_t2(
                    t2_memory=t2_mem,
                    aggregate=inner_material,
                    ich_text=ich_text,
                )
        except Exception as e:
            self._msg.log(f"[SOM:T2] Persist-Problem: {e}", scope="HMA")

        return {"ich_text": ich_text, "route": route, "inner": inner_material}



    # ---- interne Helfer ------------------------------------------------------
    def _parallel_demo(self, demos: Iterable[Any], user_text: str, context: str) -> list[Tuple[str, str]]:
        results: list[Tuple[str, str]] = []
        # Für Slim: sequenziell + try/except (leicht parallelisierbar)
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
        # Einheitlicher Aufruf; Systemprompt aus _sys
        return self._llm.completion(system=self._sys, prompt=final_prompt)
