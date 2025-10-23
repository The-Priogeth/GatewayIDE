# backend/agent_core/konstruktor.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, Dict, List, Tuple, Optional, Protocol, cast
from concurrent.futures import ThreadPoolExecutor
import re, json
from loguru import logger
from backend.ag2.autogen.agentchat import LLMConfig
from backend.ag2.autogen.agentchat import ConversableAgent, GroupChat, GroupChatManager
from backend.ag2.autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent
from backend.agent_core.hma_config import HMAConfig
from backend.agent_core.messaging import MessagingRouter, DeliverTo
from backend.agent_core.messaging import compose_inner_combined

# ==== Routing-Konstanten / Parser ====
ROUTE_MARKER = "ROUTE_JSON:"
VALID_ROUTES = {"user", "task", "lib", "trn"}

__all__ = [
    "IntakeEnvelope",
    "ThreadProvider", "NullThreadProvider",
    "DemoSelectorPolicy", "HeuristicSelector", "LearnedSelector",
    "HMA_Router", "HMA_IchFlow", "HMA_Speaker",
    "HauptMetaAgent", "build_hma",
]

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

def _extract_last_json(text: str) -> tuple[str, dict]:
    """
    Extrahiert die letzte ROUTE-Zeile und liefert (cleaned_text, data_dict).
    - Entfernt die Marker-Zeile vollständig aus dem Text.
    - Liefert bei leerem/invalidem Payload {"deliver_to":"user"}.
    - Hat einen Fallback, der am Textende explizit nach deliver_to-JSON sucht.
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    # von unten nach oben: letzte ROUTE-Zeile finden
    for i in range(len(lines) - 1, -1, -1):
        ln = lines[i].strip()
        if ln.startswith(ROUTE_MARKER):
            payload = ln[len(ROUTE_MARKER):].strip()
            cleaned = "\n".join(lines[:i]).strip()
            if payload:
                try:
                    data = json.loads(payload)
                    # normalize + guard hier schon
                    dt = str(data.get("deliver_to", "user")).lower()
                    if dt not in VALID_ROUTES:
                        dt = "user"
                    return cleaned, {"deliver_to": dt}
                except Exception:
                    # ungültiges JSON hinter dem Marker
                    return cleaned, {"deliver_to": "user"}
            # Marker ohne Payload -> Default
            return cleaned, {"deliver_to": "user"}

    # Fallback: explizit nach deliver_to-JSON AM ENDE suchen
    m = re.search(r'(\{[^{}]*"deliver_to"\s*:\s*"(user|task|lib|trn)"[^{}]*\})\s*$',
                  text or "", flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            block = m.group(1)
            data = json.loads(block)
            cleaned = (text[:m.start()] + text[m.end():]).strip()
            dt = str(data.get("deliver_to", "user")).lower()
            if dt not in VALID_ROUTES:
                dt = "user"
            return cleaned, {"deliver_to": dt}
        except Exception:
            pass

    # nichts gefunden
    return (text or "").strip(), {}

# ==== Intake-Envelope (einheitlicher Umschlag pro Nachricht) ====
@dataclass
class IntakeEnvelope:
    text: str                       # die eingegangene Nachricht
    origin: str                     # "external" | "internal"
    origin_label: str               # z.B. "user", "meta:TaskManager", "SOMCore"
    corr_id: Optional[str] = None   # Korrelations-ID für End-to-End-Verfolgung

# ==== Thread-Provider (für spätere pro-Agent-Kontexte/Threads) ====
class ThreadProvider(Protocol):
    def get_thread(self, agent_name: str) -> Optional[str]: ...

class NullThreadProvider:
    def get_thread(self, agent_name: str) -> Optional[str]:
        return None

# ==== Trainierbare Auswahl-Policy (Heuristik jetzt, Lernen später) ====
class DemoSelectorPolicy(Protocol):
    def select(self, *, user_text: str, context: str, demos: List[ConversableAgent]) -> List[ConversableAgent]: ...
    def update(self, *, features: Dict[str, Any], chosen: List[str], outcome: Dict[str, Any]) -> None: ...

class HeuristicSelector:
    """Drop-in-Ersatz für die bisherige select_demos-Logik – aber als Policy."""
    def __init__(self, topk: int = 3):
        self.topk = topk

    def select(self, *, user_text: str, context: str, demos: List[ConversableAgent]) -> List[ConversableAgent]:
        text = f"{user_text} {context}".lower()
        buckets = {
            "demoprogrammer": ["code","class","def","function","bug","error","exception","stack trace","stacktrace","traceback",
                               "python","c#","java","build","compile","cs0246","avln3000","nullreference","np exception"],
            "demostrategist": ["plan","strategie","architektur","design","konzept","roadmap","struktur","spezifikation","milestone"],
            "democritic":     ["prüfe","review","kritik","qualität","bewerte","analyse","risiko","edge case","test","regression"],
            "demotherapist":  ["hilfe","unsicher","sorge","konflikt","ich fühle","überfordert","angst","stress","frust"]
        }
        def score(agent_name: str) -> int:
            base = (agent_name or "").lower()
            for key, kws in buckets.items():
                if base.startswith(key):
                    return sum(1 for k in kws if k in text)
            return 0
        scored = [(a, score(getattr(a, "name", ""))) for a in demos]
        top = [a for a, s in sorted(scored, key=lambda t: t[1], reverse=True) if s > 0][: self.topk]
        if not top:
            # Fallback: Strategist + Critic (wenn vorhanden)
            top = [a for a in demos if getattr(a, "name","").lower().startswith(("demostrategist","democritic"))][:2]
        return top

    def update(self, *, features: Dict[str, Any], chosen: List[str], outcome: Dict[str, Any]) -> None:
        # Heuristik lernt nicht – Platzhalter für spätere Stats/Logs
        pass

class LearnedSelector(HeuristicSelector):
    """Gerüst für ein lernendes Modell (Ranking/Klassifikation).
    Aktuell identisch zur Heuristik; später: model.predict(...), model.update(...)."""
    def __init__(self, topk: int = 3, model: Any = None):
        super().__init__(topk=topk)
        self.model = model
    # Überschreibe select/update, sobald ein Modell bereitsteht.

# ==== Neuer Router: NUR Auswahl (Start) & finale Entscheidung (Schluss) ====
class HMA_Router:
    """
    Verantwortungen:
    - select_internal(...): bestimmt interne Demos (Beginn der Pipeline)
    - decide_external(...): wählt finales deliver_to (Schluss der Pipeline)
    """
    def __init__(
        self,
        som_group: SocietyOfMindAgent,
        som_core: ConversableAgent,
        demo_profiles: Optional[Iterable[ConversableAgent]],
        max_workers: int = 4,
        selector: Optional[DemoSelectorPolicy] = None,
    ):
        self.som_group = som_group
        self.som_core  = som_core
        self.demos: List[ConversableAgent] = list(demo_profiles or [])
        self.max_workers = max_workers
        self.selector = selector or HeuristicSelector(topk=3)

    # 1) interne Auswahl (Beginn)
    def select_internal(self, env: IntakeEnvelope, context: str) -> List[ConversableAgent]:
        return self.selector.select(user_text=env.text, context=context, demos=self.demos)

    # 2) externe Zielwahl (Schluss)
    def decide_external(self, ich_recommendation: DeliverTo, env: IntakeEnvelope, aggregate: str) -> DeliverTo:
        if ich_recommendation in VALID_ROUTES:
            return cast(DeliverTo, ich_recommendation)
        return "user"

# ==== Ich-Flow: Fan-Out (parallel) + Solo-Synthese (SOMCore) ====
class HMA_IchFlow:
    def __init__(self, som_group: SocietyOfMindAgent, som_core: ConversableAgent, max_workers: int = 4,
                 thread_provider: Optional[ThreadProvider] = None):
        self.som_group = som_group
        self.som_core  = som_core
        self.max_workers = max_workers
        self.thread_provider = thread_provider or NullThreadProvider()

    def fanout(self, env: IntakeEnvelope, context: str, agents: List[ConversableAgent]) -> List[Tuple[str, str]]:
        if not agents:
            return []
        def ask(agent: ConversableAgent) -> Tuple[str, str]:
            _ = self.thread_provider.get_thread(agent.name)  # Hook für späteren per-Agent-Kontext
            prompt = (
                f"{env.text}\n\n# Kontext\n{context}\n\n"
                "Gib mir bitte in 1–3 Sätzen deinen kompakten Beitrag "
                "(ohne Listen, ohne JSON, ohne Routing, kein Smalltalk)."
            )
            out = agent.generate_reply(messages=[{"role": "user", "content": prompt}], sender=self.som_group)
            return agent.name, _normalize_reply(out)

        results: List[Tuple[str, str]] = []
        worker_count = max(1, min(self.max_workers, len(agents)))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futs = {a.name: pool.submit(ask, a) for a in agents}
            for name, fut in futs.items():
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.warning(f"[DEMO:{name}] Fehler: {e}")
                    results.append((name, ""))
        return results

    def synthesize(self, env: IntakeEnvelope, aggregate: str, template: str) -> Tuple[str, DeliverTo]:
        final_prompt = template.format(user_text=env.text, aggregate=aggregate)
        out = self.som_core.generate_reply(messages=[{"role": "user", "content": final_prompt}], sender=None)
        full = _normalize_reply(out)
        ich_text, route_json = _extract_last_json(full)
        deliver_to: DeliverTo = cast(DeliverTo, (route_json or {}).get("deliver_to", "user"))
        return ich_text.strip(), deliver_to

# ==== Speaker: formuliert & verschickt adressierte Nachrichten ====
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


# ==== Optional: LLM-Config-Provider (für spätere pro-Agent-Keys/Modelle) ====
class LLMConfigProvider(Protocol):
    def get_config(self, agent_name: str, role: str) -> dict: ...

class StaticLLMConfigProvider:
    """Einfacher Provider: default_cfg + optionale per_agent-Overrides."""
    def __init__(self, default_cfg: dict, per_agent: Optional[Dict[str, dict]] = None):
        self.default_cfg = default_cfg or {}
        self.per_agent = per_agent or {}

    def get_config(self, agent_name: str, role: str) -> dict:
        return self.per_agent.get(agent_name) or self.default_cfg


# ==== Haupt-Meta-Agent mit neuem Orchestrierungs-Flow ====
class HauptMetaAgent:
    """
    Verantwortlichkeiten:
    - Router wählt interne Demos (Start) und entscheidet externes Ziel (Schluss)
    - IchFlow macht Fan-Out (parallel) + Solo-Synthese (SOMCore)
    - Speaker formuliert & verschickt
    """
    def __init__(
        self,
        *,
        llm_config: Any,
        demo_profiles: Iterable[ConversableAgent] | None,
        hma_config: HMAConfig,
        messaging: MessagingRouter,
        som_rounds: int = 3,
        memory_context_provider=None,
        memory_logger=None,
        llm_config_provider: Optional[LLMConfigProvider] = None,
    ):
        self.llm_config = llm_config
        self.llm_config_provider = llm_config_provider or StaticLLMConfigProvider(default_cfg=llm_config)
        self.memory_context_provider = memory_context_provider
        self.memory_logger = memory_logger
        self.cfg = hma_config
        self.messaging = messaging

        # Demos ggf. mit per-Agent-LLM-Config „patchen“
        patched_demos: List[ConversableAgent] = []
        for a in list(demo_profiles or []):
            try:
                cfg_any = self.llm_config_provider.get_config(getattr(a, "name", "demo"), role="demo")
                # Pylance: ConversableAgent.llm_config erwartet LLMConfig | Literal[False]
                a.llm_config = cast(Any, cfg_any)  # type: ignore[assignment]
                # a.llm_config = cast("LLMConfig | Literal[False]", cfg_any)  # type: ignore[assignment]
            except Exception:
                pass
            patched_demos.append(a)

        # Innerer GroupChat NUR als „Kooperationsraum“ für Demos
        inner_gc = GroupChat(
            agents=cast(List[Any], patched_demos),
            messages=[],
            max_round=max(1, som_rounds),
            allow_repeat_speaker=True,
        )
        inner_mgr = GroupChatManager(groupchat=inner_gc, llm_config=self.llm_config)

        # SOM-Gruppe (Kontext), nicht für finalen Prompt
        self.som_group = SocietyOfMindAgent(
            name="SOM",
            chat_manager=inner_mgr,
            llm_config=self.llm_config_provider.get_config("SOM", role="group"),
            human_input_mode="NEVER",
        )
        if hasattr(self.som_group, "update_system_message"):
            try:
                self.som_group.update_system_message(self.cfg.som_system_prompt)
            except Exception:
                pass

        # SOLO-Synthese-Agent (finale Ich-Antwort + ROUTE_JSON)
        self.som_core = ConversableAgent(
            name="SOMCore",
            system_message=self.cfg.som_system_prompt,
            llm_config=self.llm_config_provider.get_config("SOMCore", role="core"),
            human_input_mode="NEVER",
        )

        # Bausteine
        self.router = HMA_Router(
            som_group=self.som_group,
            som_core=self.som_core,
            demo_profiles=patched_demos,
            max_workers=4,
            selector=None,  # HeuristicSelector als Default
        )
        self.ichflow = HMA_IchFlow(
            som_group=self.som_group,
            som_core=self.som_core,
            max_workers=4,
        )
        self.speaker = HMA_Speaker(self.messaging)

    # --- interne Hilfen ---
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

    # --- zentraler Durchlauf ---
    def step(self, incoming_text: str) -> Dict[str, Any]:
        ctx = self._ctx()
        self._log("user", "INPUT", incoming_text)
        env = IntakeEnvelope(text=incoming_text, origin="external", origin_label="user")

        # 1) Router wählt interne Demos
        selected_agents = self.router.select_internal(env, ctx or "(kein zusätzlicher Kontext)")

        # 2) Fan-Out (parallel)
        demo_pairs = self.ichflow.fanout(env, ctx or "(kein zusätzlicher Kontext)", selected_agents)
        parts = [f"## {n}\n{r}" for n, r in demo_pairs if r]
        inner_material = "\n\n".join(parts) if parts else "(keine internen Beiträge)"

        # 3) Solo-Synthese (Ich) mit ROUTE_JSON-Empfehlung
        ich_text, ich_route = self.ichflow.synthesize(env, inner_material, self.cfg.som_final_template)

        # 4) Router entscheidet finale externe Route
        final_route = self.router.decide_external(ich_route, env, inner_material)

        # 5) Persistieren/Loggen kombinierten inneren Textes
        self._log("assistant", "SOM:ich", f"{ich_text[:200]}{'...' if len(ich_text)>200 else ''} | deliver_to={final_route}")
        try:
            snapshot = self.messaging.log_som_internal_t2(aggregate=inner_material, ich_text=ich_text)
        except Exception as e:
            logger.warning(f"[SOM:T2] Persist-Problem: {e}")
            snapshot = None
        inner_combined = compose_inner_combined(inner_material, ich_text)

        # 6) Senden über Speaker
        result = self.speaker.speak(from_name="HMA", to=final_route, ich_text=ich_text)

        return {
            "final": True,
            "deliver_to": final_route,
            "speaker": "HMA",
            "content": ich_text,
            "envelope": result.get("envelope"),
            "snapshot": snapshot or result.get("snapshot"),
            "inner_combined": inner_combined,
            "selected": [a.name for a in selected_agents],
        }


# ==== Fabrik: baut HMA (API bleibt kompatibel) ====
def build_hma(
    llm_config,
    demo_profiles,
    hma_config: HMAConfig,
    messaging: MessagingRouter,
    **kwargs
) -> dict[str, Any]:
    hma = HauptMetaAgent(
        llm_config=llm_config,
        demo_profiles=demo_profiles,
        hma_config=hma_config,
        messaging=messaging,
        **kwargs,
    )
    return {
        "hma": hma,
        "context_provider": hma.memory_context_provider,
    }
