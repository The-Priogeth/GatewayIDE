from .exceptions import ZepDependencyError

try:
    from .graph_memory import ZepGraphMemory
    from .memory import ZepUserMemory
    from .tools import (create_add_graph_data_tool,
                        create_search_graph_tool,
                        search_memory,
                        add_graph_data,)

    __all__ = [
        "ZepUserMemory",
        "ZepGraphMemory",
        "create_search_graph_tool",
        "create_add_graph_data_tool",
        "ZepDependencyError",
        "search_memory",
        "add_graph_data",
    ]

except ImportError as e:
    raise ZepDependencyError(framework="AutoGen", install_command="pip install zep-autogen") from e
