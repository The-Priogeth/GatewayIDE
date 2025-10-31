**Gateway** ist eine modulare KI-Agentenplattform, die FastAPI, Autogen 2 Ziel ist ein orchestriertes Agentensystem mit WebSocket- und REST-Schnittstellen zur Live-Interaktion mit realen oder simulierten Systemen (z.B. UE5).

Gateway/
├── README.md
├── LICENSE
├── CHANGELOG
├── .dockerignore
├── .gitignore
├── .env
├── demo.env
├── docker-compose.yml
├── Dockerfile
├── run.py # runs docker, builds image, starts container, opens cmd,starts app
├── pyproject.toml
├── .git/
├── .venv/
├── .vscode/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── bootstrap.py
│   ├── agent.py -> muss noch angepassst werden und in agent_core verschoben werden
│   ├── tools.py -> wird ersetzt sehe captainagent tools
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── memory.py
│   │   ├── memory_zep_graph.py
│   │   ├── memory_zep_thread.py
│   ├── ag2/
│   ├── zep_autogen/
│   ├── agent_core/
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── managers/
│   │   ├── agents/
│   ├── history/
│       ├── __init__.py
│   │   ├── chats/
│   └── routes/
│       ├── __init__.py
│       ├── chat_api.py
│       ├── memory_api.py
│       ├── agents.py
│       ├── status_api.py
│       ├── library_api.py
│       ├── agents.py
│       ├── settings.py
│       ├── # system.py
│       └── ws_utils.py
├── config/
│   ├── admin.json
│   ├── default.json
│   ├── llm_config.json
│   ├── manager.json
│   ├── lobby_init.json
│   └── user.json
├── docs/
├── logs/
│   ├── watchdog
│   ├── server
├── builds/
│   ├── client/
│   └── server/