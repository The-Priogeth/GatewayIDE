from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Callable, Tuple, Literal, cast
import asyncio
import inspect
import json
import re

from autogen_core.memory import MemoryContent, MemoryMimeType

Target = Literal["user", "task", "lib", "trn"]


@dataclass
class Route:
    target: Target
    args: dict[str, Any]


@dataclass(frozen=True)
class HMAConfig:
    # Concurrency-Limit für Demo-Ausführung
    max_parallel_targets: int = 3


DEFAULT_HMA_CONFIG = HMAConfig()
# ---- Demo-Selection / Aggregation (ehemals selectors.py) --------------------
_CLAIM_PATTERNS: list[tuple[str, str]] = [
    ("name",        r"\b(hei[ßs]e?\s+ich|mein\s+name\s+ist|du\s+hei[ßs]t)\b.+"),
    ("entscheidung", r"\b(sollte|muss|werde|wir\s+werden|plane)\b.+"),
    ("ort",         r"\b(in|bei|aus)\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)*"),]

def select_demos(user_text: str, context: str, demos: Iterable[Any]) -> list[Any]:
    t = f"{user_text}\n{context}".lower()
    def _find(name: str) -> Any | None:
        for d in demos:
            if getattr(d, "name", "").lower() == name.lower():
                return d
        return None

    # Keyword-Regeln pro Demo-Agent
    keyword_rules: list[tuple[list[str], str]] = [
        (
            [
                "error",
                "traceback",
                "stack",
                "compile",
                "build",
                "docker",
                "compose",
                "code",
                "funktion",
                "methode",
                "klasse",
            ],
            "DemoProgrammer",
        ),
        (
            ["plan", "strategie", "priorisiere", "roadmap", "ziel", "meilenstein"],
            "DemoStrategist",
        ),
        (["prüfe", "review", "kritik", "kritisiere", "gegencheck"], "DemoCritic"),
        (
            ["ich fühle", "überfordert", "angst", "hilfe", "therapie", "emotional"],
            "DemoTherapist",
        ),
    ]

    chosen: list[Any] = []
    pa = _find("PersonalAgent")
    if pa:
        chosen.append(pa)
    for d in demos:
        try:
            fn = getattr(d, "accept", None)
            if callable(fn) and fn(user_text, context):
                if d not in chosen:
                    chosen.append(d)
        except Exception:
            pass

    # 2) Keyword-basierte Zusatz-Selektion
    for keywords, agent_name in keyword_rules:
        if any(k in t for k in keywords):
            agent = _find(agent_name)
            if agent and agent not in chosen:
                chosen.append(agent)

    return chosen or ([pa] if pa else [])


def build_inner_material(pairs: list[Tuple[str, str]]) -> str:
    if not pairs:
        return "(keine internen Beiträge)"
    seen: set[tuple[str, str]] = set()
    blocks: list[str] = []
    votes: dict[str, dict[str, int]] = {}
    for name, reply in pairs:
        name_s = (name or "").strip()
        reply_s = (reply or "").strip()
        key = (name_s, reply_s)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(f"## {name_s}\n{reply_s}")
        for kind, rx in _CLAIM_PATTERNS:
            m = re.search(rx, reply_s, flags=re.IGNORECASE)
            if m:
                kind_votes = votes.setdefault(kind, {})
                val = m.group(0).strip()
                kind_votes[val] = kind_votes.get(val, 0) + 1
    if not votes:
        return "\n\n".join(blocks)
    lines = ["# Findings (kompakt)"]
    for kind, counts in votes.items():
        best = max(counts.items(), key=lambda kv: kv[1])
        lines.append(f"- **{kind}**: {best[0]}")
    return "\n\n".join(blocks + ["\n".join(lines)])


# ---- Routing-Marker / Regex -------------------------------------------------
_ROUTE_BLOCK = re.compile(
    r"<<<ROUTE>>>\s*(\{.*?\})\s*<<<END>>>",
    flags=re.DOTALL,)

def _strip_code_fences(text: str) -> str:
    return re.sub(
        r"```(?:json)?\s*([\s\S]*?)```",
        r"\1",
        text,
        flags=re.IGNORECASE,)

def strip_route_markers(text: str) -> str:
    if not text:
        return ""
    txt = _strip_code_fences(text)
    return _ROUTE_BLOCK.sub("", txt).strip()

def _extract_route_json(raw: Any) -> str | None:
    txt = _strip_code_fences(str(raw)).strip()
    m = _ROUTE_BLOCK.search(txt)
    return m.group(1).strip() if m else None

def parse_deliver_to(raw: Any) -> Route:
    try:
        if isinstance(raw, dict):
            d = raw
        else:
            route_json = _extract_route_json(raw)
            if not route_json:
                return Route(target="user", args={})
            d = json.loads(route_json)
        dt = d.get("deliver_to", "user")
        args = d.get("args") or {}
        if dt not in ("user", "task", "lib", "trn"):
            dt = "user"
        if not isinstance(args, dict):
            args = {}
        return Route(target=cast(Target, dt), args=args)
    except Exception:
        return Route(target="user", args={})


# Mapping zentral halten: Ziel-Thread & Agent-Label pro Target ----------------
# Hinweis: In deinem Modell ist T2 die "Innenwelt" (Leona/inner voice) und T3 die
# "Außenstimme"/Hub (outer voice), der mit Manager-Threads (T4/T5/T6) interagiert.
# Deshalb routen wir "task/lib/trn" zunächst nach T3 (und können später optional
# in die jeweiligen Manager-Threads spiegeln).
_TARGET_META: dict[Target, Tuple[str, str]] = {
    "user": ("T1", "HMA→User"),
    "task": ("T3", "HMA→TaskManager"),
    "lib":  ("T3", "HMA→Librarian"),
    "trn":  ("T3", "HMA→Trainer"),
}

class HMA:
    def __init__(
        self,
        *,
        som_system_prompt: str,
        templates: Any,
        demos: Iterable[Any],
        messaging: Any,
        llm: Any,  # LLMAdapter → Any, um Import-Zirkus zu vermeiden
        ctx_provider: Any | None = None,  # MemoryManager, ZepMemory etc.
        runtime: Any | None = None,  # SimpleNamespace aus bootstrap.ensure_runtime
        config: HMAConfig = DEFAULT_HMA_CONFIG,
    ) -> None:
        self._cfg: HMAConfig = config
        self._sys = som_system_prompt
        self._tpl = templates
        self._demos = list(demos)
        self._msg = messaging
        self._llm = llm
        self._ctx = ctx_provider
        self._rt = runtime

    # -------------------------------------------------------------------------
    # kleine Utility: ggf. awaiten
    # -------------------------------------------------------------------------
    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        return await value if inspect.isawaitable(value) else value

    async def _build_context(self, context: str) -> str:
        ctx_block = ""
        if self._ctx:
            fn: Optional[Callable[..., Any]] = getattr(self._ctx, "get_context", None)
            if callable(fn):
                try:
                    res = fn(include_recent=True, graph=True)
                    raw_ctx = str(await self._maybe_await(res) or "")
                    # Persistierte SOM-Summary-Blöcke ("# Interner Zwischenstand ... # Ich-Antwort ...")
                    # NICHT noch einmal in den Prompt geben – sonst wiederholt das LLM alte Ich-Antworten
                    # wie z.B. "Ich wähle die Zahl 7.".
                    ctx_block = re.sub(
                        r"# Interner Zwischenstand[\s\S]*?# Ich-Antwort[\s\S]*?(?=$|\n# |\Z)",
                        "",
                        raw_ctx,
                        flags=re.IGNORECASE,
                    ).strip()
                except Exception as e:
                    if self._msg:
                        self._msg.log(f"[Ctx:get_context] {e}", scope="HMA")
                    ctx_block = ""
        if context and ctx_block:
            return f"{context}\n\n{ctx_block}".strip()
        return context or ctx_block

    async def run(self, *, user_text: str, context: str = "", corr_id: str | None = None) -> Dict[str, Any]:
        merged_context = await self._build_context(context)
        # Demos sehen denselben Kontext wie das SOM-LLM
        chosen = select_demos(user_text, merged_context, self._demos)
        pairs = await self._parallel_demo(chosen, user_text, merged_context)
        inner_material = build_inner_material(pairs)

        # Prompt-Bau komplett über die Config-Templates
        final_prompt = self._tpl.som_plan_template.format(
            user_text=user_text,
            context=merged_context,
            capabilities=self._tpl.capabilities,
            aggregate=inner_material,
        ) + self._tpl.som_final_template
        llm_out = self._call_llm(final_prompt)
        ich_text_raw = await self._maybe_await(llm_out)
        ich_text = str(ich_text_raw or "")
        route = parse_deliver_to(ich_text)
        return await self._deliver(
            ich_text=ich_text,
            inner_material=inner_material,
            route=route,
            speaker_name="SOM",
            corr_id=corr_id,)

    # ---- interne Helfer ----------------------------------------------------
    async def _add_memory(
        self,
        *,
        mem_attr: str,
        content: str,
        role: str,
        name: str,
        thread: str,
        extra_meta: Dict[str, Any] | None = None,
    ) -> None:
        if not content or self._rt is None:
            return
        try:
            mem = getattr(self._rt, mem_attr, None)
            if mem is None:
                return
            meta: Dict[str, Any] = {
                "type": "message",
                "role": role,
                "name": name,
                "thread": thread,}
            if extra_meta:
                meta.update(extra_meta)
            await mem.add(
                MemoryContent(
                    content=content,
                    mime_type=MemoryMimeType.TEXT,
                    metadata=meta,))
        except Exception:pass

    async def _deliver(
        self,
        *,
        ich_text: str,
        inner_material: str,
        route: Route,
        speaker_name: str = "SOM",
        corr_id: str | None = None,
    ) -> Dict[str, Any]:
        target: Target = route.target
        route_args: Dict[str, Any] = route.args or {}
        inner = strip_route_markers(inner_material or "")
        ich_core = strip_route_markers(ich_text or "")
        summary = ""
        if inner or ich_core:
            summary = (
                "# Interner Zwischenstand\n"
                f"{inner}\n\n"
                "# Ich-Antwort\n"
                f"{ich_core}"
            ).strip()
            await self._add_memory(
                mem_attr="t2_memory",
                content=summary,
                role="system",
                name="SOM:inner",
                thread="T2",
                extra_meta={"corr_id": corr_id} if corr_id else None,)
        target_thread, who = _TARGET_META.get(target, ("T3", "HMA"))
        if ich_core:
            if self._msg:
                try:
                    self._msg.snapshot(ich_core, to=target, corr_id=corr_id)
                except Exception:pass
            await self._add_memory(
                mem_attr=f"{target_thread.lower()}_memory",
                content=ich_core,
                role="assistant",
                name=speaker_name,
                thread=target_thread,
                extra_meta=None,)
        resp_items: list[dict[str, str]] = []
        if summary:
            resp_items.append({"agent": "SOM:INNER", "content": summary})
        if ich_core:
            resp_items.append({"agent": who, "content": ich_core})
        return {
            "ok": True,
            "final": True,
            "deliver_to": target,
            "deliver_to_thread": target_thread,
            "route_args": route_args,
            "speaker": speaker_name,
            "corr_id": corr_id,
            "packet_id": None,
            "p_snapshot": None,
            "responses": resp_items,}

    async def _parallel_demo(
        self, demos: Iterable[Any], user_text: str, context: str
    ) -> list[Tuple[str, str]]:
        demos_list = list(demos)
        limit = max(1, int(self._cfg.max_parallel_targets))
        sem = asyncio.Semaphore(limit)

        async def _run_one(idx: int, d: Any) -> tuple[int, tuple[str, str] | None]:
            name = getattr(d, "name", d.__class__.__name__)
            try:
                async with sem:
                    res = d.run(user_text=user_text, context=context)
                    reply = await self._maybe_await(res)
                if reply:
                    return idx, (name, str(reply))
                return idx, None
            except Exception as e:
                if self._msg:
                    self._msg.log(f"[DemoError] {name}: {e}", scope="HMA")
                return idx, None

        tasks = [asyncio.create_task(_run_one(i, d)) for i, d in enumerate(demos_list)]
        done = await asyncio.gather(*tasks, return_exceptions=False)

        # preserve original order deterministically
        done.sort(key=lambda x: x[0])
        results: list[Tuple[str, str]] = []
        for _, item in done:
            if item:
                results.append(item)
        return results


    def _call_llm(self, final_prompt: str) -> Any:
        return self._llm.completion(system=self._sys, prompt=final_prompt)
