**Gateway** ist eine modulare KI-Agentenplattform, die FastAPI, Autogen 2 Ziel ist ein orchestriertes Agentensystem mit WebSocket- und REST-Schnittstellen zur Live-Interaktion mit realen oder simulierten Systemen (z.B. UE5).

Gateway/
├── README.md
├── .dockerignore
├── .gitignore
├── .env
├── demoenv
├── pyproject.toml
├── ARCHITECTURE.dm
├── build-win.bat
├── uv.lock
├── .git/
├── .venv/
├── .vs/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── bootstrap.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── memory.py
│   │   ├── memory_wrapper.py
│   │   └── memory_tools.py
│   ├── ag2/
│   ├── agent_core/
│   │   ├── __init__.py
│   │   ├── messaging.py
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
│   │       ├── routing.py
│   │       ├── selector.py
│   │       └── speaker.py
│   └── routes/
│       ├── __init__.py
│       ├── chat_api.py
│       ├── # memory_api.py
│       ├── agents.py
│       ├── # status_api.py
│       ├── # library_api.py
│       ├── # settings.py
│       └── websocket.py
├── docs/
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