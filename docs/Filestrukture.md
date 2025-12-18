**Gateway** ist eine modulare KI-Agentenplattform, die FastAPI, Autogen 2 Ziel ist ein orchestriertes Agentensystem mit WebSocket- und REST-Schnittstellen zur Live-Interaktion mit realen oder simulierten Systemen (z.B. UE5).

Gateway/
├── .git/
├── .venv/
├── .vs/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── bootstrap.py
│   ├── reset_utils.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── memory.py
│   │   ├── graph_api.py
│   │   ├── graph_utils.py
│   │   ├── memory_utils.py
│   │   ├── manager.py
│   │   └── memory_tools.py
│   ├── ag2/
│   ├── agent_core/
│   │   ├── __init__.py
│   │   ├── agents.py
│   │   ├── demo_adapter.py
│   │   ├── llm_adapter.py
│   │   ├── messaging.py
│   │   ├── tool_reg.py
│   │   ├── managers/
│   │   │   ├── __init__.py
│   │   │   ├── librarian.py
│   │   │   ├── taskmanager.py
│   │   │   └── trainer.py
│   │   ├── # agents/
│   │   └── hma/
│   │       ├── __init__
│   │       ├── hma_config.py
│   │       ├── hma.py
│   └── routes/
│       ├── __init__.py
│       ├── chat_api.py
│       ├── # memory_api.py
│       ├── agents.py
│       ├── # status_api.py
│       ├── # library_api.py
│       ├── # settings.py
│       └── websocket.py
├── logs/
│   ├── watchdog
│   └── server
├── builds/
│   ├── client/
│   └── server/
├── deploy/
│   ├── scripts/
│   │   └── Dockerfile.ai
│   └── gateway-compose.yaml
├── protos/
│   └── ai_service.proto
├── services/
│   └── GatewayAI/
│       └── ai_service/
│           ├── __init__
│           ├── requirements.txt
│           └── server.py
└── GatewayIDE.App/
    ├── Services/
    │   ├── AI/
    │   │   └── AIClientService C#
    │   └── Processes/
    │       └── DockerService C#
    ├── ViewModels/
    │   ├── DelegateCommand C#
    │   └──  MainWindowViewModel C#
    ├── App.axaml
    ├── App.axaml C#
    ├── Converters C#
    ├── GatewayIDE.App C#
    ├── MainWindow.axaml
    ├── MainWindow.axaml C#
    └── Program C#

├── .env
├── .gitattributes
├── .gitignore
├── build-win.bat
├── demoenv
├── pyproject.toml
├── README.md
├── uv.lock