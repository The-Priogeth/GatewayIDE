from __future__ import annotations
from typing import Any, Iterable, Literal, cast, Tuple, Union, TypedDict

from backend.ag2.autogen.agentchat import ConversableAgent, GroupChat, GroupChatManager
from loguru import logger

# ==== Typdefinitionen ====

class MessageDict(TypedDict):
    role: str
    name: str
    content: str

Reply = Union[str, MessageDict]
ReplyReturn = Tuple[bool, Reply]
LLMCfg = Any


# ==== Hauptklasse ====

class MetaAgentTaskManager(ConversableAgent):
    def __init__(
        self,
        name: str = "TaskManager",
        *,
        llm_config: LLMCfg,
        human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER",
        memory_context_provider=None,
        memory_logger=None,
        inner_profiles: Iterable[ConversableAgent] | None = None,
    ):
        super().__init__(
            name=name,
            system_message="Koordiniert Aufgaben & Gates.",
            llm_config=llm_config,
            human_input_mode=human_input_mode,
        )
        self._mem_ctx = memory_context_provider
        self._mem_log = memory_logger

        # --- Inneres Team (mindestens ein Captain) ---
        profs: list[ConversableAgent] = list(inner_profiles) if inner_profiles else [
            ConversableAgent(
                name=f"{name}-Captain",
                system_message="Orchestriert Team.",
                llm_config=llm_config,
                human_input_mode="NEVER",
            )
        ]

        # 🔧 Harte Absicherung: Captain.generate_reply überschreiben,
        # damit EIN MessageDict (kein Tuple) zurückkommt.
        def _captain_generate_reply(self_ag: ConversableAgent, messages=None, sender=None, **kwargs):
            # letzten User-Text aus der übergebenen Historie ziehen
            txt = ""
            try:
                if messages:
                    last = messages[-1]
                    txt = (last.get("content", "") or "")
            except Exception:
                pass

            content = (txt or "ready.").strip()
            msg: MessageDict = {"role": "assistant", "name": self_ag.name, "content": content}
            # WICHTIG: KEIN (True, msg) zurückgeben!
            return msg

        for ag in profs:
            try:
                ag.default_auto_reply = False  # falls vorhanden
            except Exception:
                pass
            ag.generate_reply = _captain_generate_reply.__get__(ag, ConversableAgent)  # type: ignore[assignment]

        self._gc = GroupChat(
            agents=cast(list, profs),
            messages=[],
            max_round=4,
            allow_repeat_speaker=True,
        )  # type: ignore[arg-type]

        self._mgr = GroupChatManager(groupchat=self._gc, llm_config=llm_config)

        # === Reply-Handler des TaskManagers (liefert Tuple wie von Autogen erwartet) ===
        def _reply(agent, messages, sender, config) -> ReplyReturn:
            msg = self._process_and_build_msg(messages)
            return True, msg

        self.register_reply(".*", _reply)

    # ==== Hilfsfunktionen ====

    def _process_and_build_msg(self, messages) -> MessageDict:
        """Extrahiert User-Text, ruft inneren Chat, loggt und baut MessageDict."""
        user_text = ""
        try:
            if messages:
                last = messages[-1]
                user_text = (last.get("content", "") or "")
        except Exception:
            pass

        # inneren Mini-GroupChat laufen lassen
        reply_raw = self._run_inner(str(user_text))
        reply = self._normalize_reply(reply_raw)

        if callable(self._mem_log):
            try:
                self._mem_log("assistant", self.name, reply)
            except Exception:
                pass

        msg: MessageDict = {
            "role": "assistant",
            "name": self.name,
            "content": reply,
        }
        return msg

    def _run_inner(self, content: str) -> str:
        """Führt den inneren Mini-GroupChat aus."""
        # defensiv resetten
        for a in self._gc.agents:
            if hasattr(a, "reset"):
                try:
                    a.reset()  # type: ignore[attr-defined]
                except Exception:
                    pass
        if hasattr(self._mgr, "reset"):
            try:
                self._mgr.reset()
            except Exception:
                pass

        # internes Mini-GroupChat-Spiel
        self._mgr.send(
            {"role": "user", "name": self.name, "content": content},
            self._gc.agents[0],
            request_reply=True,
        )
        return self._gc.messages[-1].get("content", "") if self._gc.messages else ""

    def _normalize_reply(self, reply) -> str:
        """Normalisiert verschiedene Antwortformate zu String."""
        try:
            if isinstance(reply, str):
                return reply
            if isinstance(reply, dict):
                return str(reply.get("content", "")) or str(reply)
            if isinstance(reply, (list, tuple)):
                parts = []
                for x in reply:
                    if isinstance(x, dict):
                        parts.append(x.get("content", "") or str(x))
                    else:
                        parts.append(str(x))
                return " ".join(p for p in parts if p).strip() or str(reply)
            return str(reply)
        except Exception:
            return str(reply)

    # ==== Fallback (methodenbasierter Pfad) ====

    def generate_reply(self, messages=None, sender=None, **kwargs) -> Reply:
        """Wird genutzt, falls kein expliziter Reply-Handler greift (äußerer Pfad)."""
        if messages is None and sender is not None:
            try:
                messages = self.chat_messages[sender]
            except Exception:
                messages = []

        msg = self._process_and_build_msg(messages)
        # WICHTIG: GroupChatManager.run_chat erwartet hier KEIN (final, reply)-Tuple,
        # sondern direkt den Reply (str | dict). Also NUR das MessageDict zurückgeben.
        return msg
