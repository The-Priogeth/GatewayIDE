# backend/agent_core/konstruktor.py
from __future__ import annotations
from typing import Any, Iterable, Dict, List, Tuple, Optional, cast
from concurrent.futures import ThreadPoolExecutor
import re, json
from loguru import logger

from backend.ag2.autogen.agentchat import ConversableAgent, GroupChat, GroupChatManager
from backend.ag2.autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent
from backend.agent_core.hma_config import HMAConfig
from backend.agent_core.messaging import MessagingRouter, DeliverTo


def _to_text(reply) -> str:
    if isinstance(reply, (list, tuple)):
        return "" if not reply else str(reply[-1])
    return str(reply)

def _normalize_reply(out) -> str:
    """
    Akzeptiert sowohl:
      - (ok: bool, rep: Any)
      - rep: Any
    Gibt IMMER einen String zurück.
    """
    try:
        if isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], (bool, type(None))):
            _, rep = out
            return _to_text(rep)
        return _to_text(out)
    except Exception:
        return str(out)


def _extract_last_json(text: str) -> Tuple[str, Dict[str, Any]]:
    matches = list(re.finditer(r"\{.*?\}", text, flags=re.DOTALL))
    if not matches:
        return text.strip(), {}
    last = matches[-1]
    block = text[last.start(): last.end()]
    try:
        data = json.loads(block)
    except Exception:
        return text.strip(), {}
    cleaned = (text[:last.start()] + text[last.end():]).strip()
    return cleaned, data


class HMA_Router:
    """
    - _parallel_demo: fragt Demo-Profile parallel an (Fan-out)
    - run_inner_cycle: sammelt, lässt SOMCore (solo) final synthetisieren (Fan-in → Final)
    """
    def __init__(
        self,
        som_group: SocietyOfMindAgent,
        som_core: ConversableAgent,
        demo_profiles: Optional[Iterable[ConversableAgent]],
        max_workers: int = 4,
    ):
        self.som_group = som_group      # nur für interne Kooperation/“Denken in der Gruppe”, kein Final-Prompt!
        self.som_core  = som_core       # SOLO-Synthese für den finalen Prompt
        self.demos: List[ConversableAgent] = list(demo_profiles or [])
        self.max_workers = max_workers

    def _parallel_demo(self, user_text: str, context: str) -> List[Tuple[str, str]]:
        """Parallel alle Demo-Agents anfragen (innen), Ergebnisliste (name, reply_text)."""
        if not self.demos:
            return []

        def ask(agent: ConversableAgent) -> Tuple[str, str]:
            # KURZER inhaltlicher Input, KEIN JSON, KEIN Routing
            prompt = (
                f"{user_text}\n\n"
                f"# Kontext\n{context}\n\n"
                "Gib mir bitte in 1–3 Sätzen deinen kompakten Beitrag (ohne Listen, ohne JSON, ohne Routing, kein Smalltalk)."
            )
            out = agent.generate_reply(
                messages=[{"role": "user", "content": prompt}],
                sender=self.som_group
            )
            return agent.name, _normalize_reply(out)

        results: List[Tuple[str, str]] = []
        worker_count = max(1, min(self.max_workers, len(self.demos)))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futs = {a.name: pool.submit(ask, a) for a in self.demos}
            for name, fut in futs.items():
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.warning(f"[DEMO:{name}] Fehler: {e}")
                    results.append((name, ""))
        return results

    def run_inner_cycle(self, user_text: str, context: str, som_final_template: str) -> tuple[str, DeliverTo, str]:
        """
        1) DEMO parallel → sammeln
        2) SOLO-Synthese (SOMCore): erzeugt freien Ich-Text + am Ende {"deliver_to": "..."}
           (Final-Prompt geht NICHT mehr in den GroupChat)
        """
        demo_pairs = self._parallel_demo(user_text, context)

        aggregate_parts: List[str] = []
        for n, r in demo_pairs:
            if r:
                aggregate_parts.append(f"## {n}\n{r}")
        inner_material = "\n\n".join(aggregate_parts) if aggregate_parts else "(keine internen Beiträge)"

        final_prompt = som_final_template.format(user_text=user_text, aggregate=inner_material)

        # WICHTIG: Solo-Agent, KEIN GroupChat → keine “Next speaker…”-Logs, keine Demo-JSONs
        out = self.som_core.generate_reply(
            messages=[{"role": "user", "content": final_prompt}],
            sender=None
        )
        full = _normalize_reply(out)

        ich_text, route_json = _extract_last_json(full)
        dt = "user"
        if isinstance(route_json, dict):
            try:
                dt = str(route_json.get("deliver_to", "user")).lower()
            except Exception:
                dt = "user"
        if dt not in {"user", "task", "lib", "trn"}:
            dt = "user"
        deliver_to: DeliverTo = cast(DeliverTo, dt)

        return ich_text.strip(), deliver_to, inner_material


class HMA_Speaker:
    """Formt die Ansprache aus dem Ich-Text und verschickt paketbasiert (P → persist → send)."""
    def __init__(self, messaging: MessagingRouter, style_map: Optional[Dict[str, str]] = None):
        self.messaging = messaging
        self.style_map = style_map or {
            "user": "",
            "task": "@TaskManager: ",
            "lib":  "@Librarian: ",
            "trn":  "@Trainer: "
        }

    def speak(self, *, from_name: str, to: DeliverTo, ich_text: str, corr_id: Optional[str]=None) -> Dict[str, Any]:
        prefix = self.style_map.get(to, "")
        addressed = f"{prefix}{ich_text}".strip()
        return self.messaging.send_addressed_message(frm=from_name, to=to, text=addressed, intent="inform", corr_id=corr_id)


class HauptMetaAgent:
    """
    HMA besteht funktional aus:
    - Router: DEMO parallelisieren, SOLO-Synthese (SOMCore) → Ich-Output + deliver_to
    - Speaker: Ich-Text adressieren & paketbasiert versenden
    """
    def __init__(
        self,
        *,
        llm_config: Any,
        demo_profiles: Iterable[ConversableAgent] | None,
        lobby_agents: Iterable[ConversableAgent] | None,
        hma_config: HMAConfig,
        messaging: MessagingRouter,
        som_rounds: int = 3,
        memory_context_provider=None,
        memory_logger=None,
    ):
        self.llm_config = llm_config
        self.memory_context_provider = memory_context_provider
        self.memory_logger = memory_logger
        self.cfg = hma_config
        self.messaging = messaging

        # GroupChat NUR als “inneres Spielfeld” für die Demos (falls SOM sie als Sender braucht)
        inner_gc = GroupChat(
            agents=list(demo_profiles or []),
            messages=[],
            max_round=max(1, som_rounds),     # 1 reicht i.d.R., wenn Demos nur kurze Inputs geben sollen
            allow_repeat_speaker=True,
        )
        inner_mgr = GroupChatManager(groupchat=inner_gc, llm_config=self.llm_config)

        # SOM-Gruppe (für Kontext), aber NICHT für den finalen Prompt
        self.som_group = SocietyOfMindAgent(
            name="SOM",
            chat_manager=inner_mgr,
            llm_config=self.llm_config,
            human_input_mode="NEVER",
        )
        if hasattr(self.som_group, "update_system_message"):
            try:
                self.som_group.update_system_message(self.cfg.som_system_prompt)
            except Exception:
                pass

        # SOLO-Synthese-Agent für die finale Ich-Antwort + Routing-JSON
        self.som_core = ConversableAgent(
            name="SOMCore",
            system_message=self.cfg.som_system_prompt,
            llm_config=self.llm_config,
            human_input_mode="NEVER",
        )

        self.router = HMA_Router(
            som_group=self.som_group,
            som_core=self.som_core,
            demo_profiles=list(demo_profiles or []),
            max_workers=4,
        )
        self.speaker = HMA_Speaker(self.messaging)

    def _ctx(self) -> str:
        if self.memory_context_provider:
            try:
                return self.memory_context_provider()
            except Exception:
                return ""
        return ""

    def _log(self, role: str, sender: str, content: str):
        logger.info(f"[{sender}] → {role}: {content[:200]}{'...' if len(content) > 200 else ''}")
        if callable(self.memory_logger):
            try:
                self.memory_logger(role, sender, content)
            except Exception:
                pass

    def step(self, incoming_text: str) -> Dict[str, Any]:
        ctx = self._ctx()
        self._log("user", "INPUT", incoming_text)

        ich_text, deliver_to, inner_material = self.router.run_inner_cycle(
            user_text=incoming_text,
            context=ctx or "(kein zusätzlicher Kontext)",
            som_final_template=self.cfg.som_final_template
        )
        self._log("assistant", "SOM:ich", f"{ich_text[:200]}{'...' if len(ich_text)>200 else ''} | deliver_to={deliver_to}")
        # 🔎 NEU: HMA intern nach T2 schreiben (Aggregate + Ich-Referenz)
        try:
            self.messaging.log_som_internal_t2(aggregate=inner_material, ich_text=ich_text)
        except Exception as e:
            logger.warning(f"[SOM:T2] Persist-Problem: {e}")
        result = self.speaker.speak(from_name="HMA", to=deliver_to, ich_text=ich_text)

        return {
            "final": True,
            "deliver_to": deliver_to,
            "speaker": "HMA",
            "content": ich_text,
            "envelope": result.get("envelope"),
            "snapshot": result.get("snapshot"),
        }


def build_hma(
    llm_config,
    demo_profiles,
    lobby_agents,
    hma_config: HMAConfig,
    messaging: MessagingRouter,
    **kwargs
) -> dict[str, Any]:
    hma = HauptMetaAgent(
        llm_config=llm_config,
        demo_profiles=demo_profiles,
        lobby_agents=lobby_agents,
        hma_config=hma_config,
        messaging=messaging,
        **kwargs,
    )
    return {
        "hma": hma,
        "context_provider": hma.memory_context_provider,
    }
