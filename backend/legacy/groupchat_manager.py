# backend/groupchat_manager.py
"""
GroupChat-Manager (V3-Vorbereitung)
- Übergangsmodul: ehemals CaptainHub, nun neutral benannt
- Beinhaltet Kompatibilitäts-Alias `CaptainHub` für V2
- Memory-Integration & Chat-Facade bleiben 1:1 erhalten
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, cast, Sequence, Mapping, Protocol
import os
from loguru import logger
import asyncio

# ── LLM Bridge ────────────────────────────────────────────────────────────────
def _llm_chat(messages: Sequence[dict[str, Any]], model: str | None = None) -> str | None:
    """
    Versucht zuerst neues OpenAI-SDK (>=1.x), dann altes (<1.x).
    Unterstützt OPENAI_BASE_URL (z.B. Azure, LM Studio, Ollama Gateway).
    Setze LLM_DEBUG=1 für Fehlerlogs.
    """
    mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base = os.getenv("OPENAI_BASE_URL") 
    key  = os.getenv("OPENAI_API_KEY", "")

    def _dbg(exc: Exception, where: str):
        if os.getenv("LLM_DEBUG") == "1":
            logger.warning("LLM call failed in {}: {}", where, repr(exc))

    # Neues SDK (openai>=1.x)
    try:
        from openai import OpenAI  # type: ignore
        kwargs: dict[str, Any] = {}
        if base:
            kwargs["base_url"] = base
        if key:
            kwargs["api_key"] = key
        client = OpenAI(**kwargs)  # type: ignore[arg-type]
        resp = client.chat.completions.create(
            model=mdl,
            messages=cast(Any, messages),  # Pylance beruhigen
            temperature=0.7,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        _dbg(e, "new-sdk")



# ── Protokolle & einfache Datentypen ─────────────────────────────────────────
class MemoryLike(Protocol):
    # exakt das, was der Manager braucht
    async def add_user_message(self, content: str, *, name: Optional[str] = None) -> None: ...
    async def add_assistant_message(self, content: str, *, name: Optional[str] = None) -> None: ...
    async def add_system_message(self, content: str, *, name: Optional[str] = None) -> None: ...
    async def build_context_block(self, *, include_recent: bool = True, recent_limit: int = 10) -> str: ...
    @property
    def thread_id(self) -> Optional[str]: ...

@dataclass
class HubPolicy:
    # V3: Wer spricht zuerst? Default: 'brain', sonst erstes Agent-Objekt
    def pick_first(self, agents: Mapping[str, Any], *, ctx: Dict[str, Any]) -> Any:
        speaker = agents.get("brain")
        if speaker is not None:
            return speaker
        # Fallback: erstes Element
        try:
            return next(iter(agents.values()))
        except StopIteration:
            raise RuntimeError("No agents registered in GroupChatManager")

# ── Chat-Fassade (ZEP-Thread) ────────────────────────────────────────────────
class HubChatFacade:
    """
    Schlanke Chat-Fassade über GroupChatManager.
    - Persistiert User/Assistant im ZEP-Thread
    - Ruft direkt ein LLM mit ZEP-Kontext 
    - Liefert {reply, steps} ähnlich core2 zurück
    """
    def __init__(self, hub, zep_facade, user_id: str, thread_id: str):
        self.hub = hub
        self.zep = zep_facade
        self.user_id = user_id
        self.thread_id = thread_id

    async def _build_messages(self, prompt: str) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = []
        ctx = None
        try:
            if hasattr(self.zep, "build_context_block"):
                ctx = await self.zep.build_context_block(include_recent=True, recent_limit=8)  # type: ignore
        except Exception:
            ctx = None
        if ctx:
            msgs.append({"role": "system", "content": f"Nutze folgenden kompakten Kontext:\n{ctx}"})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    async def converse(self, prompt: str) -> dict:
        try:
            await self.zep.add_user_message(prompt)  # type: ignore
        except Exception:
            pass

        reply: str | None = None
        try:
            messages = await self._build_messages(prompt)
            reply = _llm_chat(messages)
        except Exception:
            reply = None
        if not reply:
            reply = f"Ich habe dich gehört: „{prompt}“ (LLM nicht verfügbar)."

        try:
            await self.zep.add_assistant_message(reply)  # type: ignore
        except Exception:
            pass

        steps = [["assistant", reply]]
        return {"reply": reply, "steps": steps}


class _AgentProto(Protocol):
    role: str
    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]: ...


# ── GroupChat-Manager (ex-CaptainHub) ────────────────────────────────────────
class GroupChatManager:
    def __init__(
        self,
        *,
        memory: MemoryLike,
        policy: Optional[HubPolicy] = None,
        agents: Optional[Mapping[str, _AgentProto]] = None,
        
    ) -> None:
        self.memory = memory
        self.policy = policy or HubPolicy()

        if agents is None:
            raise RuntimeError("GroupChatManager: no agents injected (avoid circular imports).")
        # Mapping ➜ lokale Kopie als dict (mutierbar)
        self.agents: Dict[str, _AgentProto] = cast(Dict[str, _AgentProto], dict(agents))

    def build_chat_facade(self, *, zep_facade, user_id: str, thread_id: str) -> HubChatFacade:
        facade = HubChatFacade(self, zep_facade, user_id, thread_id)
        setattr(self, "chat", facade)  # für bootstrap: hub.chat verfügbar
        return facade



    # ── V3-Hook: Ein-Turn GroupChat (Stub) ────────────────────────────────────
    async def group_once(
        self,
        *,
        goal: str,
        deliverables: list[str] | None = None,
        constraints:  list[str] | None = None,
        extra_ctx: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ein Turn des GroupChats.

        Ablauf:
        1) Policy wählt den ersten Sprecher (Default: 'brain').
        2) Manager "sendet" Ziel/Kontext an den Sprecher.
        3) Sprecher liefert genau *eine* Antwort (one-shot).
        4) (Optional) Debug-Trace zeigt Datenfluss: choose → send → (nested?) → reply.

        Eingabe (ctx-Flags):
        - debug: bool                → Trace mitsenden
        - show_manager_step: bool    → Manager-Entscheidung als Step in 'steps' sichtbar machen
        - timeout_s: float           → timeout für den Sprecherturn (Sekunden)

        Rückgabe:
        {
            "reply": str,                    # finale Antwort an den User
            "steps": list[[role, text]],     # sichtbare Schritte (z. B. [["brain", "..."]])
            "status": "final",
            "trace": [ {...}, ... ]          # nur falls debug=True; objekte mit from/to/type/data
        }
        """
        # ──────────────────────────────────────────────────────────────────────
        # 0) Kontext konsolidieren (nicht-mutierend gegenüber Caller)
        # ──────────────────────────────────────────────────────────────────────
        ctx: Dict[str, Any] = {
            "deliverables": list(deliverables or []),
            "constraints":  list(constraints  or []),
        }
        if extra_ctx:
            ctx.update(extra_ctx)

        debug: bool = bool(ctx.get("debug"))
        show_mgr_step: bool = bool(ctx.get("show_manager_step"))
        timeout_s: Optional[float] = (
            float(ctx["timeout_s"]) if isinstance(ctx.get("timeout_s"), (int, float)) else None
        )

        # ──────────────────────────────────────────────────────────────────────
        # A) Thread-Kontext (kompakt) aus Memory beziehen und anhängen
        #    → erhöht Antwortqualität, bleibt aber bewusst klein
        # ──────────────────────────────────────────────────────────────────────
        try:
            if hasattr(self.memory, "build_context_block"):
                context_block = await self.memory.build_context_block(
                    include_recent=True, recent_limit=8
                )
                if context_block:
                    ctx["context_block"] = context_block
        except Exception:
            # Kontext ist "nice-to-have" – Fehler hier sollen den Turn nicht stoppen
            pass

        # ──────────────────────────────────────────────────────────────────────
        # B) User-Prompt im Thread persistieren (für Folgeturns/Recall)
        # ──────────────────────────────────────────────────────────────────────
        # User persistieren nur, wenn wir einen Agentenpfad nutzen (kein Fallback).
        _persist_user_before = True

        # Strukturierter Trace für Debug-Ansicht im Frontend
        # Schema pro Event: {"from": <str>, "to": <str>, "type": <str>, "data": <any>, "nested": <bool?>}
        trace: List[Dict[str, Any]] = []

        # ──────────────────────────────────────────────────────────────────────
        # 1) Sprecherwahl per Policy
        # ──────────────────────────────────────────────────────────────────────
        try:
            speaker = self.policy.pick_first(self.agents, ctx=ctx)
        except Exception:
            speaker = None

        if speaker is None:
            chat = getattr(self, "chat", None)
            if chat and hasattr(chat, "converse"):
                out = await chat.converse(goal)
                # Normalisieren: immer {"reply": str, "steps": [[role, text], ...], "status": "final"}
                if isinstance(out, dict):
                    reply = (out.get("reply") or "").strip()
                    steps  = out.get("steps") or [["assistant", reply]]
                elif isinstance(out, tuple):
                    reply = (out[0] or "").strip()
                    steps  = out[1] if len(out) > 1 else [["assistant", reply]]
                else:
                    reply = (str(out) if out is not None else "").strip()
                    steps  = [["assistant", reply]]

                res: Dict[str, Any] = {"reply": reply, "steps": steps, "status": "final"}
                if debug:
                    res["trace"] = [{
                        "from": "manager", "to": "chat-facade",
                        "type": "fallback", "data": {"reason": "no-agents"}
                    }]
                return res
            if _persist_user_before:
                try:
                    if hasattr(self.memory, "add_user_message"):
                        await self.memory.add_user_message(goal)
                except Exception:
                    pass

            # Gar nichts verfügbar → neutraler Echo-Reply (defensiv)
            res: Dict[str, Any] = {"reply": goal, "steps": [["manager", "noop"]], "status": "final"}
            if debug:
                res["trace"] = [{
                    "from": "manager", "to": "∅",
                    "type": "fallback", "data": {"reason": "no-agents"}
                }]
            return res

        role = getattr(speaker, "role", "assistant")

        if debug:
            compact_ctx = {
                "goal": goal,
                "deliverables": len(ctx.get("deliverables") or []),
                "constraints":  len(ctx.get("constraints") or []),
                "extra_keys":   sorted(k for k in ctx.keys() if k not in ("deliverables","constraints","debug","show_manager_step","timeout_s")),
            }
            trace.append({"from": "manager", "to": role, "type": "send", "data": compact_ctx})


        # ──────────────────────────────────────────────────────────────────────
        # 2) Ein Turn mit optionalem Timeout
        # ──────────────────────────────────────────────────────────────────────
        text: str = ""
        try:
            # Erwartetes Agent-Interface:
            #   async def propose(goal, ctx) -> {"content": str, "signals": {...}} | str
            coro = speaker.propose(goal, ctx)
            out = await (asyncio.wait_for(coro, timeout=timeout_s) if timeout_s else coro)

            if isinstance(out, dict):
                text = (out.get("content") or "").strip()
                sig = out.get("signals") or {}
                signals = sig if isinstance(sig, dict) else {}
                # Nested Trace anflanschen (vom Adapter/verschachtelten Managern)
                nested = signals.get("trace")
                if debug and isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            trace.append({
                                "from": str(item[0]), "to": role, "type": "note",
                                "data": str(item[1]), "nested": True
                            })
                        elif isinstance(item, dict):
                            it = dict(item); it["nested"] = it.get("nested", True)
                            trace.append(it)
            else:
                # Adapter/Agent hat reinen String zurückgegeben
                text = str(out or "").strip()

        except asyncio.TimeoutError:
            text = "(error) Timeout while waiting for agent response"
        except Exception as e:
            text = f"(error) {type(e).__name__}: {e}"

        if debug:
            # Wir loggen nur eine Vorschau, damit die Trace nicht ausartet
            trace.append({
                "from": role, "to": "manager", "type": "reply",
                "data": {"preview": text[:240], "truncated": len(text) > 240}
            })
        # ──────────────────────────────────────────────────────────────────────
        # C) Assistant-Antwort persistieren (Thread-Memory)
        # ──────────────────────────────────────────────────────────────────────
        try:
            if text and hasattr(self.memory, "add_assistant_message"):
                await self.memory.add_assistant_message(text, name=role)
        except Exception:
            pass

        # ──────────────────────────────────────────────────────────────────────
        # 3) Steps bauen (sichtbar für den Client)
        # ──────────────────────────────────────────────────────────────────────
        steps: List[List[str]] = []
        if show_mgr_step:
            steps.append(["manager", f"chose:{role}"])
        # Immer: Sprecher + finaler Text (User will wissen, „wer hat’s gesagt?“)
        steps.append([role, text])

        result: Dict[str, Any] = {"reply": text, "steps": steps, "status": "final"}
        if debug:
            result["trace"] = trace
        return result


# ── Übergangs-Alias (bricht keine existierenden Importe) ──────────────────────
CaptainHub = GroupChatManager

__all__ = ["GroupChatManager", "HubPolicy", "CaptainHub", "_llm_chat"]