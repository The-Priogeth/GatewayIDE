from __future__ import annotations
from typing import Any, Iterable, Literal, cast
from backend.ag2.autogen.agentchat import ConversableAgent, GroupChat, GroupChatManager
from loguru import logger

LLMCfg = Any


class MetaAgentLibrarian(ConversableAgent):
    def __init__(
        self,
        name: str = "Librarian",
        *,
        llm_config: LLMCfg,
        human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER",
        memory_context_provider=None,
        memory_logger=None,
        inner_profiles: Iterable[ConversableAgent] | None = None,
    ):
        super().__init__(
            name=name,
            system_message="Findet/ordnet Wissen & Artefakte.",
            llm_config=llm_config,
            human_input_mode=human_input_mode,
        )
        self._mem_ctx = memory_context_provider
        self._mem_log = memory_logger

        profs: list[ConversableAgent] = list(inner_profiles) if inner_profiles else [
            ConversableAgent(
                name=f"{name}-Curator",
                system_message="Kuratierte Quellen, kurze Zitate.",
                llm_config=llm_config,
                human_input_mode="NEVER",
            )
        ]
        self._gc  = GroupChat(agents=cast(list, profs), messages=[], max_round=3, allow_repeat_speaker=True)  # type: ignore[arg-type]
        self._mgr = GroupChatManager(groupchat=self._gc, llm_config=llm_config)

    def _run_inner(self, content: str) -> str:
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

        self._mgr.send(
            {"role": "user", "name": self.name, "content": content},
            self._gc.agents[0],
            request_reply=True,
        )
        return self._gc.messages[-1].get("content", "") if self._gc.messages else ""

    def generate_reply(self, messages=None, sender=None, config=None):
        # Sichtbarer Test: bestätigt Hot-Reload und Agent-Routing
        logger.warning("📚 [LIBRARIAN] generate_reply() ACTIVE")

        if messages is None and sender is not None:
            try:
                messages = self.chat_messages[sender]
            except Exception:
                messages = []

        user_text = ""
        if messages:
            last = messages[-1]
            user_text = (last.get("content", "") or "")

        reply = self._run_inner(str(user_text))

        if callable(self._mem_log):
            try:
                self._mem_log("assistant", self.name, reply)
            except Exception:
                pass

        logger.warning(f"📚 [LIBRARIAN] reply_type={type(reply).__name__}")

        # WICHTIG: KEIN (True, reply) – sondern direkt ein Message-Dict zurückgeben
        return {"role": "assistant", "name": self.name, "content": reply}
