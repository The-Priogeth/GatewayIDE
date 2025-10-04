import os
import json
from backend.ag2.autogen import ConversableAgent, UserProxyAgent, GroupChat, GroupChatManager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
LOBBY_HISTORY = BASE_DIR / "history" / "conferences" / "main_lobby.json"
LOBBY_INIT = CONFIG_DIR / "lobby_init.json"
LOBBY_HISTORY.parent.mkdir(parents=True, exist_ok=True)

# Singleton Manager
lobby_manager = None

def initialize_lobby():
    global lobby_manager

    # 1. Lade initiale Nachrichten aus lobby_init.json
    if LOBBY_INIT.exists():
        with open(LOBBY_INIT, encoding="utf-8") as f:
            lobby_init = json.load(f)
        messages = lobby_init.get("messages", [])
    else:
        messages = [{"role": "system", "content": "Lobby gestartet", "name": "system"}]
    print("Loading Lobby")
    # 2. Admin laden
    with open(CONFIG_DIR / "admin.json", encoding="utf-8") as f:
        admin_config = json.load(f)
    admin_agent = ConversableAgent(
        name=admin_config["name"],
        system_message=admin_config["system_message"],
        description=admin_config.get("description"),
        human_input_mode=admin_config.get("human_input_mode", "NEVER"),
        default_auto_reply=admin_config.get("default_auto_reply"),
        max_consecutive_auto_reply=admin_config.get("max_consecutive_auto_reply"),
        llm_config=admin_config["llm_config"],
        code_execution_config=admin_config.get("code_execution_config"),
    )

    # 3. User laden
    with open(CONFIG_DIR / "user.json", encoding="utf-8") as f:
        user_config = json.load(f)
    is_termination_msg = user_config.get("is_termination_msg")
    if isinstance(is_termination_msg, str):
        is_termination_msg = eval(is_termination_msg)
    user_agent = UserProxyAgent(
        name=user_config["name"],
        description=user_config.get("description"),
        is_termination_msg=is_termination_msg
    )
    print("ADMIN:", type(admin_agent))
    print("USER:", type(user_agent))
    # 4. GroupChat & Manager erzeugen
    groupchat = GroupChat(
        agents=[admin_agent, user_agent],
        messages=messages,  # <---- Hier landen die initialen Nachrichten!
        max_round=10,
        speaker_selection_method="auto"
    )
    lobby_manager = GroupChatManager(
        groupchat=groupchat,
        name="LobbyManager",
        llm_config=admin_config["llm_config"],
        human_input_mode="NEVER",
        system_message="Dies ist der zentrale Lobby-Manager."
    )

    return lobby_manager


# core.py
def get_lobby_manager():
    global lobby_manager
    if lobby_manager is None:
        lobby_manager = initialize_lobby()
    return lobby_manager


def sync_lobby_manager_to_json():
    global lobby_manager
    if lobby_manager is None:
        return
    messages = lobby_manager.groupchat.messages
    with open(LOBBY_HISTORY, "w", encoding="utf-8") as f:
        json.dump({"messages": messages}, f, indent=2)

def get_lobby():
    if LOBBY_HISTORY.exists():
        with open(LOBBY_HISTORY, encoding="utf-8") as f:
            return json.load(f)
    else:
        return {"messages": []}

def get_lobby_history():
    lobby = get_lobby()
    return lobby.get("messages", [])

def load_agent_profile():
    print()
def build_user_proxy():
    print()
def build_admin(): 
    print()
def build_manager_config():
    print()


#################################################
#################################################

# # "process_message_before_send"#
# # This hook is the only hook not in ConversableAgent's generate_reply method and is designed to intercept a message before it is sent to another agent.
# # You can change the message with the hook and the change will be permanent. This is because this hook is called before a message is displayed or added to the message list.
# # Signature:
# my_agent.register_hook("THE_HOOK_NAME", my_function)
# def your_function_name(
#     sender: ConversableAgent,
#     message: Union[dict[str, Any], str],
#     recipient: Agent,
#     silent: bool) -> Union[dict[str, Any], str]:

# # "update_agent_state"#
# # The first of three hooks that run in the ConversableAgent.generate_reply method before the reply functions are evaluated.
# # This hook is designed to be used to update an agent's state, typically their system message, before replying.
# # As the system message is a key message for an LLM to consider, it's useful to be able to make sure that pertinent information is there.
# # A couple of examples of where it is used: - DocAgent to update the internal summary agent's system message with the context from the ingestions and queries. - Swarms to hide/show conditional hand-offs.
# # Signature:
# def my_update_function(
#     agent: ConversableAgent,
#     messages: list[dict[str, Any]]
#     ) -> None:

# # "process_last_received_message"#
# # This is the second of the three hooks that run in the ConversableAgent.generate_reply method before the reply functions are evaluated.
# # This hook is used to process the last message in the messages list (as opposed to all messages, handled by the next hook).
# # If the last message is a function call or is "exit" then it will not execute the associated function.
# # Changing the message will result in permanent changes to the chat messages of the agent with the hook, but not other agents. So, changes to the messages will be present in future generate_reply calls for the agent with the hook, but not other agent's calls to generate_reply.
# # A couple of examples of where it is used: - The Teachability capability appends any relevant memos to the last message. - The Vision capability will update the last message if it contains an image with a caption for the image using an LLM call.
# Signature:
# def my_processing_function(
#     content: Union[str, list[dict[str, Any]]]
#     ) -> str:

# # "process_all_messages_before_reply"#
# # The final hook that runs in the ConversableAgent.generate_reply method before the reply functions are evaluated.
# # This hook is used to work on all messages before replying.
# # The changes to these messages will be used for the replying but will not persist beyond the generate_reply call.
# # An example of the use of this hook is the TransformMessages capability where it carries out all transforms (such as limiting the number messages, filtering sensitive information, truncating individual messages) on messages before an agent replies.
# # Signature:
# def your_function_name(
#     messages: list[dict[str, Any]]
#     ) -> list[dict[str, Any]]:

# import autogen

# # Registering your own reply functions#
# # If you are creating a new type of agent, it's useful to create a reply function that triggers your agent's internal workflow and returns the result back into the conversation.
# # ConversableAgent's register_reply method is used to register a function as a reply function on the agent.
# # As the reply functions are evaluated in a specific order, if you want your reply function to be triggered first you can make sure it's the last one to be added (reply functions registered later will be checked earlier by default) or you can remove all other reply functions when you register yours, ensuring your one will be the only one called.
# # Your reply function should return a Tuple that includes whether the reply is final (True if final, otherwise it will continue evaluating the following reply functions) and the message dictionary with your agent's reply.
# # Signature of reply function:
# def my_reply_function(
#     agent: ConversableAgent,
#     messages: Optional[list[dict[str, Any]]] = None,
#     sender: Optional[Agent] = None,
#     config: Optional[OpenAIWrapper] = None,
# ) -> tuple[bool, dict[str, Any]]:
    

# import json, os, uuid
# from typing import Annotated
# from autogen import LLMConfig
# from autogen.agentchat import (
#     Agent,
#     AssistantAgent,
#     ChatResult,
#     ConversableAgent,
#     GroupChat,
#     GroupChatManager,
#     LLMAgent,
#     UpdateSystemMessage,
#     UserProxyAgent,
#     a_initiate_chats,
#     a_initiate_group_chat,
#     a_initiate_swarm_chat,
#     a_run_group_chat,
#     a_run_swarm,
#     gather_usage_summary,
#     initiate_chats,
#     initiate_group_chat,
#     register_function,
#     run_group_chat,
#     run_swarm,
# )
# from autogen.agentchat.contrib.captainagent import CaptainAgent, AgentBuilder, ToolBuilder, format_ag2_tool, get_full_tool_description
# from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent

# from autogen.agentchat.group.patterns import (
#     DefaultPattern,
#     AutoPattern,
#     ManualPattern,
#     RandomPattern,
#     RoundRobinPattern,
#     )
# from autogen.agentchat.group import (
#     AgentNameTarget,
#     AgentTarget,
#     AskUserTarget,
#     ContextExpression,
#     ContextStr,
#     ContextStrLLMCondition,
#     ContextVariables,
#     ExpressionAvailableCondition,
#     ExpressionContextCondition,
#     GroupChatConfig,
#     GroupChatTarget,
#     Handoffs,
#     NestedChatTarget,
#     OnCondition,
#     OnContextCondition,
#     ReplyResult,
#     RevertToUserTarget,
#     SpeakerSelectionResult,
#     StayTarget,
#     StringAvailableCondition,
#     StringContextCondition,
#     StringLLMCondition,
#     TerminateTarget,
#     )

# # HANDOFFS REGISTRATION
# # Coordinator Agent handoffs to specialists
# coordinator_agent.handoffs.add_many(
#     [
#         # Conditional handoffs to specialists based on what information is needed
#         OnContextCondition( # Example of Context Variable-based transfer, this happens automatically without LLM
#             target=AgentTarget(DokumentenAgent),
#             condition=ExpressionContextCondition(ContextExpression("${weather_info_needed} == True and ${weather_info_completed} == False")),
#             available=StringAvailableCondition("query_analyzed")
#         ),
#     ]
# )
# # Revert to user when finished
# coordinator_agent.handoffs.set_after_work(RevertToUserTarget())
# # Each specialist always returns to the coordinator
# DokumentenAgent.handoffs.set_after_work(AgentTarget(coordinator_agent))
# TerminAgent.handoffs.set_after_work(AgentTarget(coordinator_agent))
# TaskManager.handoffs.set_after_work(AgentTarget(coordinator_agent))



# # ========================
# # SPECIALIST FUNCTIONS
# # ========================
# def function_context_info(function_context_content: str, context_variables: ContextVariables) -> ReplyResult:
#     """function_context"""
#     context_variables["function_contextr_info"] = function_context_content
#     context_variables["function_context_info_completed"] = True
#     return ReplyResult(
#         message="function_context",
#         context_variables=context_variables,
#         target=AgentTarget(coordinator_agent)  # Always return to the coordinator
#     )

# # Hook zum Speichern der User-Nachricht & Kontext-Abruf
# # Hooks registrieren für alle relevanten Agenten
# # for agent in [coordinator_agent, DokumentenAgent, TerminAgent, TaskManager]:
#     # agent.register_hook("update_agent_state")


# # # Create pattern for the group chat
# # pattern = AutoPattern(
# #     initial_agent=coordinator_agent,                   # Start with the finance bot
# #     agents=[DokumentenAgent, TerminAgent, TaskManager],           # All agents in the group chat
# #     user_agent=user_proxy,                            # Provide our human-in-the-loop agent
# #     group_manager_args={"llm_config": llm_config},  # Config for group manager
# #     "is_termination_msg": is_termination_msg
# # )
# # # Initialize the group chat
# # result, context_variables, last_agent = initiate_group_chat(
# #     pattern=pattern,
# #     messages=user_msg,                     # Initial request with transactions
# # )
# # Process the workflow

# # def is_termination_msg(msg: dict[str, Any]) -> bool:
# #     content = msg.get("content", "")
# #     return (content is not None) and "==== SUMMARY GENERATED ====" in content



# from pydantic import BaseModel
# # 1. Define your structured output model with Pydantic
# class ResponseModel(BaseModel):
#     field1: str
#     field2: int
#     field3: list[str]
