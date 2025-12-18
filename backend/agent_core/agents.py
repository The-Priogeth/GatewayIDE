from __future__ import annotations

import os
from typing import Any, Callable, List, Tuple

from ..ag2.autogen.agentchat import ConversableAgent
from .demo_adapter import DemoAdapter
from .llm_adapter import LLMAdapter
from .hma.hma_config import HMAConfig, DEFAULT_HMA_CONFIG


def build_agents(
    *,
    model_name: str,
    call_tool: Callable[..., Any],
    config: HMAConfig = DEFAULT_HMA_CONFIG,
) -> Tuple[List[DemoAdapter], LLMAdapter]:
    """
    Baut die inneren Demo-Agenten und den Ich-Agenten.
    agents.py enthält KEINE Prompt-Wahrheit mehr.
    """

    # ------------------------------------------------------------------
    # Hard-Fail: Demo-Prompts müssen vollständig in der Config vorhanden sein
    # ------------------------------------------------------------------
    demo_msgs = config.demo_system_messages

    required_demos = [
        "PersonalAgent",
        "DemoTherapist",
        "DemoProgrammer",
        "DemoStrategist",
        "DemoCritic",
    ]

    missing = [
        name for name in required_demos
        if name not in demo_msgs or not str(demo_msgs[name]).strip()
    ]

    if missing:
        raise ValueError(
            f"HMAConfig.demo_system_messages missing or empty keys: {missing}"
        )

    # ------------------------------------------------------------------
    # Demos (AG2)
    # ------------------------------------------------------------------
    llm_cfg: dict[str, Any] = {"model": model_name}

    raw_demos: List[ConversableAgent] = [
        ConversableAgent(
            name="PersonalAgent",
            system_message=demo_msgs["PersonalAgent"],
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoTherapist",
            system_message=demo_msgs["DemoTherapist"],
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoProgrammer",
            system_message=demo_msgs["DemoProgrammer"],
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoStrategist",
            system_message=demo_msgs["DemoStrategist"],
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
        ConversableAgent(
            name="DemoCritic",
            system_message=demo_msgs["DemoCritic"],
            llm_config=llm_cfg,
            human_input_mode="NEVER",
        ),
    ]

    demo_registry: List[DemoAdapter] = [
        DemoAdapter(agent, call_tool=call_tool)
        for agent in raw_demos
    ]

    # ------------------------------------------------------------------
    # Hard-Fail: Ich-Systemprompt MUSS vorhanden sein
    # ------------------------------------------------------------------
    ich_prompt = config.ich_system_message
    if not ich_prompt or not ich_prompt.strip():
        raise ValueError(
            "HMAConfig.ich_system_message is empty or missing (hard fail)."
        )

    ich_model_name = os.getenv("ICH_MODEL", model_name)
    ich_llm_cfg: dict[str, Any] = {"model": ich_model_name}

    ich_agent = ConversableAgent(
        name="IchAgent",
        system_message=ich_prompt,
        llm_config=ich_llm_cfg,
        human_input_mode="NEVER",
    )

    ich_llm = LLMAdapter(agent=ich_agent)

    return demo_registry, ich_llm
