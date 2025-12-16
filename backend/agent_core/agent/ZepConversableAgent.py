from __future__ import annotations
from backend.ag2.autogen.agentchat.conversable_agent  import ConversableAgent
from zep_cloud.client import AsyncZep
from backend.memory.memory import ZepMemory as Memory

class ZepConversableAgent(ConversableAgent):  # Agent with Zep memory
    """A custom ConversableAgent that integrates with Zep for long-term memory."""

    def __init__(
        self,
        name: str,
        system_message: str,
        llm_config: dict,
        function_map: dict,
        human_input_mode: str,
        zep_thread_id: str,
        zep_client: AsyncZep,
        min_fact_rating: float,
        memory: Memory,
    ):
        super().__init__(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            human_input_mode=human_input_mode,
            function_map=function_map,
        )
        self.zep_thread_id = zep_thread_id
        self.zep_client = zep_client
        self.min_fact_rating = min_fact_rating
        # Store the original system message as we will update it with relevant facts from Zep
        self.original_system_message = system_message
        self.memory = memory



from typing import Any, Dict, List
from .base import Agent


class ZepConversableAgentAdapter(Agent):
    """
    Adapter: macht einen autogen.ConversableAgent (deine alte Demo) V3-kompatibel.
    Erwartet ein Objekt mit .generate_reply(messages) o.ä.
    """
    role: str = "assistant"

    def __init__(self, wrapped, role: str = "assistant"):
        self.wrapped = wrapped
        self.role = role

    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = [{"role": "user", "content": goal}]
        # Je nach API deiner Demo ggf. anpassen:
        try:
            out = self.wrapped.generate_reply(messages)  # sync in autogen
        except Exception:
            out = None
        text = (out or "").strip()
        return {"content": text, "actions": [], "signals": {}}
    
#backend.ag2.autogen.types.py
#backend.ag2.autogen.token_count_util.py
#backend.ag2.autogen.runtime_logging.py
#backend.ag2.autogen.llm_config.py
#backend.ag2.autogen.import_utils.py
#backend.ag2.autogen.exception_utils.py

#backend.ag2.autogen.agentchat.agent
#backend.ag2.autogen.agentchat.assistant_agent
#backend.ag2.autogen.agentchat.conversable_agent
#backend.ag2.autogen.agentchat.groupchat
#backend.ag2.autogen.agentchat.user_proxy_agent

#img_utils.py
#math_user_proxy_agent.py
#society_of_mind_agent.py
#swarm_agent.py
#text_analyzer_agent.
#web_surfer.py
#agent_builder.py
#captainagent.py
#tool_retriever.py
#deep_research.py
#discord.py
#reasoning_agent.py
#wikipedia.py
#
#
#


