# Root‑Kontext — Gebrauch & Regeln
Diese Datei beschreibt für jede Quell‑Datei einen eigenen Kontextblock. Jeder Block beginnt mit einer Überschrift der Form `#backend/<pfad/zur/datei.py>` und enthält einen kompakten Fließtext, der Zweck, Datenfluss, Abhängigkeiten und Änderungsregeln erläutert. Zum Arbeiten suchst du den relevanten Block, liest den Zusammenhang und **überschreibst ausschließlich diesen Block** mit aktualisiertem Fließtext. Keine Hilfsmarker, keine Zitat‑Blöcke, keine losen TODOs. Blöcke dürfen kleiner werden, wenn sich der Umfang der Datei reduziert. Der Chat‑Pfad bleibt auf `autogen_core.memory` und `ZepMemory`; der Orchestrator‑Adapter ist bewusst „thin“ und optional schaltbar. Im Runner‑Container adressierst du Dienste über `http://gateway:8080/…`, auf Host/Server über `http://localhost:8080/…`. bitte den inhalt der blöcke als einzeiler schreiben.

# .env
.env liefert Laufzeit-Konfig für Compose/Backend: OPENAI_API_KEY (per set_openai_key_interactive() aus run.py schreib-/persistierbar), OPENAI_PROJECT_ID, OPENAI_ORG_ID, PYTHONPATH=., ZEP_API_KEY, ZEP_USER_ID=Aaron, Logging (LOG_PATH, LOG_ROTATION, LOG_RETENTION, LOG_DIAGNOSE), CORS (CORS_ALLOW_ORIGINS, CORS_ALLOW_CREDENTIALS), Bootstrap/Runtime (BOOTSTRAP_THREAD=true, ZEP_FALLBACK_LOCAL=false, THREAD_MODE=isolated), Orchestrator (ORCH_ENABLED=true, ORCH_NESTED=false, ORCH_PERSIST_ORCH=graph, ORCH_PERSIST_WORKCELL=inmem, ORCH_PERSIST_AGENT_ST=inmem), Endpunkte (GATEWAY_API_URL=http://gateway:8080/api/chat, ORCH_API_URL=http://gateway:8080/api/orch), sowie LOG_LEVEL=INFO, HEALTH_DEEP_ENABLED=true; sensible Werte bleiben lokal (VCS-safe).

# run.py
Docker-Dev-CLI run.py (Gateway) mit menu() als Einstieg und Aktionen quick_start() (docker compose up -d→time.sleep(2)→open_logs_window()→enter_container_shell()→"System Started."), full_rebuild() (ruft wipe_all()→build --no-cache→up -d+2s; entfernt u. a. Netzwerke gateway_default/gateway-net via docker network rm und räumt mit docker system prune -af), rebuild_image(), stop_container(), restart_gateway(force_recreate=True), set_openai_key_interactive() (persistiert OPENAI_API_KEY in ENV_FILE=Path('.env') über _write_env_file_var und setzt os.environ), Helfer/Globals COMPOSE_FILE, SERVICE_NAME='gateway', CONTAINER_NAME='gateway-container', _compose_bin() (bevorzugt docker-compose), _run(), _has_any(), _is_windows(), _to_text(), open_logs_window(), enter_container_shell(), print_docker_overview(); Logs/Shell unter Windows in separaten cmd-Fenstern, sonst via bash.

# Dockerfile
Python‑3.11‑Image mit Basis‑Tools (git, curl, procps, lsof, net‑tools, python3‑venv). Arbeitsverzeichnis `/app`, kopiert `pyproject.toml` und installiert Abhängigkeiten einmalig via `pip` + `uv sync`. Setzt `PATH` aufs venv (`/app/.venv/bin`) und `PYTHONPATH=/app`. Danach `COPY . .` der gesamten App. Exposed Port **8000**.


# docker-compose.yml
services.gateway: build.context=. + build.network=host, image=gateway, container_name=gateway-container, working_dir=/app, command=/app/.venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8080, ports=8080:8080, dns=[1.1.1.1,9.9.9.9,192.168.178.1], extra_hosts=["api.getzep.com:172.66.40.150"], volumes=./backend:/app/backend ./utils:/app/utils ./src:/app/src ./config:/app/config:ro /etc/localtime:/etc/localtime:ro /etc/timezone:/etc/timezone:ro, networks=gateway-net(bridge), env_file=.env, environment: OPENAI_API_KEY OPENAI_PROJECT_ID OPENAI_ORG_ID PYTHONPATH=/app GATEWAY_API_URL=http://gateway:8080/api/chat, restart=no, volumes.zep_state={}.


# backend/main.py
FastAPI-App mit lifespan(lifespan)→ensure_runtime(); setzt app.state.{zep_client,user_id,thread_id,lobby,memory,hub,persist_cfg,orch_nested,adapter}, TZ via os.environ["TZ"]="Europe/Berlin" + Loguru (LOG_PATH,LOG_ROTATION,LOG_RETENTION,LOG_DIAGNOSE), CORS über CORS_ALLOW_ORIGINS/CORS_ALLOW_CREDENTIALS, startet start_watcher("backend/"), bindet Routen agents_router,conference_router,settings_router,websocket_router,system_router,chat_router/memory_router unter /api, aliasiert /_chat_alias→orch_chat auf POST /api/chat, optional orch_router unter /api/orch wenn ORCH_ENABLED, und schließt Watcher/ZEP-Client sauber beim Shutdown.


# backend/agent_core/bootstrap.py
ensure_runtime() initialisiert AsyncZep(api_key=ZEP_API_KEY, base_url=_sanitized_base()), erzwingt User/Thread via _ensure_user()/_ensure_thread(), baut ZepThreadMemory(...).ensure_thread(), liest ORCH_NESTED + persist_cfg={ORCH_PERSIST_WORKCELL,ORCH_PERSIST_ORCH,ORCH_PERSIST_AGENT_ST} und THREAD_MODE (→ thread_mode: Literal["isolated","shared"]), erstellt targets: Dict[str,PersistTarget], baut ZepMemoryAdapter(zep_facade=mem, thread_mode, targets), lädt router_obj=RealRouter(load_default_spokes()) (Fallback _NullRouter), konstruiert CaptainHub(router, memory=mem_adapter, policy=HubPolicy(persist_workcell=targets["workcell"])) + hub_lobby=hub.build_chat_facade(zep_facade=mem, user_id, thread_id), aktiviert optional hub.chat_reply_sync, cached als _RUNTIME=RuntimeState{zep_client,user_id,thread_id,lobby,memory,hub,orch_nested,persist_cfg} und gibt zurück.


# backend/memory/memory.py
ZepMemory(Memory) kapselt ZepThreadMemory (self._thread) + ZepGraphAdmin (self._graph) und bietet AutoGen-API add()/add_episode()/query()/update_context()/clear()/close(); add() routed metadata.type=="message" → Thread (add_user_message|add_assistant_message|add_system_message) und "data" → Graph (add_raw_data), unterstützt MemoryMimeType.{TEXT,MARKDOWN,JSON}, adopt_thread_id(), ensure_thread() (Fallback local_<user_id>), update_context() injiziert SystemMessage in ChatCompletionContext, query() vereinheitlicht Graph-Suche zu MemoryQueryResult(results=[MemoryContent(...), ...]).


# backend/memory/memory_zep_graph.py
ZepGraphAdmin ist ein dünner Wrapper um client.graph mit Zielauflösung via target_kwargs() (user_id/graph_id) und CRUD/Provisioning (create_graph/list_graphs/update_graph/clone_graph/set_ontology/add_node/add_fact_triple(get_edge)/get_node/get_edge/get_node_edges/delete_edge/delete_episode/add_raw_data); search(query, limit=10, scope, search_filters, min_fact_rating, reranker, center_node_uuid, **kwargs) baut params und ruft client.graph.search(**params).


# backend/memory/memory_zep_thread.py
ZepThreadMemory verwaltet thread_id (Local-Erkennung via Prefix local_) und garantiert sie mit ensure_thread(force_check=False) (client.thread.get_or_create); Nachrichten via add_user_message/add_assistant_message/add_system_message → _add_message() mit 2-Versuch-Strategie (bei ApiError 404 einmal self._thread_id=None und Retry), Kontext-APIs list_recent_messages(limit), get_user_context(mode), build_context_block(include_recent=True, recent_limit=10) (kombiniert Memory context: + „Recent conversation“).


<!-- # backend/routes/chat_api.py
HTTP‑Oberfläche für den core2‑Chat. POST /api/chat nimmt {prompt} entgegen, ruft req.app.state.lobby.converse auf und liefert {reply, steps}. Empfohlener Bootstrap beim ersten Aufruf: Zep‑User (ZEP_USER_ID) sicherstellen und – falls memory.thread_id leer ist – einen Thread erzeugen und in Memory/Lobby setzen; danach persistiert converse ohne 404‑Fehler. GET /api/health/zep meldet 503 solange kein Thread existiert und danach {ok:true, thread}. Zep‑Fehler werden als HTTP 502 mit detail {status, body} durchgereicht; im Runner‑Container sind Aufrufe über http://gateway:8080/, auf Host/Server über http://localhost:8080/ zu richten. -->


# backend/routes/memory_api.py
FastAPI router=APIRouter() mit POST /memory/add (Model AddMemoryIn, Normalisierung via _normalize_type_and_role, schreibt "episode" über mem.add_episode(...), sonst mem.add(MemoryContent(..., mime_type=MemoryMimeType.JSON|TEXT, metadata={"type","role","name"}))) und POST /memory/search (Model SearchIn, ruft mem.query(query, limit, scope, search_filters, min_fact_rating, reranker, center_node_uuid) und gibt {"results":[{"text": r.content, "meta": r.metadata}]} zurück).


# backend/routes/orch_api.py
FastAPI router=APIRouter() mit In-Memory Registry _RUNS: Dict[str, Dict[str, Any]], Helper _has_any_spokes(hub), Models StartIn|ChatIn, Routes: POST /start (baut run_id, Ticket, OrchestrationRun, startet hub.run_ticket im BackgroundTasks-Thread _do()), GET /status (liest _RUNS[run_id]), GET /_diag (liefert has_hub,user_id,persist,has_memory,memory_type,adapter.thread_mode,adapter.targets), POST /chat (wenn router.candidates(...)→Pipeline hub.run_ticket via run_in_threadpool, sonst hub.chat_reply_sync/hub.chat.reply|converse/lobby.converse, finaler Fallback; Response enthält reply, steps, optional workcell_space_id).

<!-- # backend/chat.py
Kommandozeilen‑Client für den Chat‑Endpoint. Wrapt `stdout/stderr` UTF‑8‑sicher, ermittelt die API‑URL aus `GATEWAY_API_URL` oder testet Kandidaten (`/api/chat`) per Probe‑POST auf Erreichbarkeit. Startbanner, dann Event‑Loop: Eingaben lesen, `exit/quit` beenden, `health|/health|:health|hc` ruft einen GET auf `/health/zep` (Basis aus `/api/chat` abgeleitet) und druckt Status/Thread. Normale Prompts werden als `{"prompt": ...}` an den Chat gepostet; Antwort wird als Schrittfolge (`steps` → `[agent,text]`) oder als `reply` ausgegeben. Robuste Fehlerbehandlung via `httpx` (HTTP‑Status, sonstige Exceptions). Einstiegspunkt `run_cli()`. -->

<!-- # backend/agent_core/core2.py
Minimaler 2‑Agenten‑Chat‑Orchestrator mit AutoGen (AG2) und ZepMemory. Die Pipeline lautet: Nutzertext wird als MemoryContent (TEXT) im Zep‑Thread persistiert, anschließend erzeugt der Researcher einen knappen Plan und der Coder die finale Antwort; beide Ergebnisse werden ebenfalls gespeichert. _msg_text extrahiert robust Agent‑Text, UserProxy hält Zep‑Client und IDs, und Lobby.converse spiegelt die tatsächlich verwendete thread_id sowie die Schritte in last_turn_steps zurück. build_lobby(client, user_id, thread_id|None) verdrahtet ZepMemory und erzeugt Researcher/Coder (OpenAIChatCompletionClient); falls thread_id None ist, legt ZepThreadMemory.ensure_thread beim ersten Write automatisch einen Thread an. -->

# backend/captain_hub.py
Orchestrierungskern mit _llm_chat(messages, model) (unterstützt OPENAI_MODEL,OPENAI_BASE_URL,OPENAI_API_KEY,LLM_DEBUG sowie OpenAI SDK ≥1.x und <1.x), Protokollen Memory|Impl|Spoke|Router, Datentypen HubPolicy|TicketStatus|Ticket|OrchestrationRun, leichter Chat-Bridge HubChatFacade._build_messages()/converse() (persistiert via zep.add_user_message()/add_assistant_message()), und CaptainHub(router, memory) mit optionalem Hook chat_reply_sync, Auswahl _match_spokes()/ _choose_planner/_coder/_critic, Pipeline run_ticket() (nutzt WorkcellIO.open()/start()/step_out()/close() und Prompts render_planner/render_implement/render_review, Fallback mit _try_chat_reply und Anti-Rekursion _in_chat_facade), plus Template coder_step(...).

# backend/captain_spoke_nested.py
CaptainHubNested(CaptainHub) ersetzt nur die Coder-Strategie: _choose_coder(tags) bevorzugt builder_captain-Spokes gegenüber coder, und coder_step(...) ruft bei CaptainSpoke.run_nested(memory, run_id, ticket_id, parent_workcell_space_id, tags) eine geschachtelte Orchestrierung auf und spiegelt impl/review optional in memory.write_message(space_id=st_ids["coder"/"critic"], ...), sonst Fallback via super().coder_step(...).

# captain_spoke_registry.py
RealRouter(Router) hält eine einfache spokes: Dict[str, List[Spoke]]-Registry und liefert mit candidates(role, tags) Kandidatenlisten; load_default_spokes() initialisiert leer (planner/coder/critic: []) und loggt via logger.info(...).

# backend/workcell_io.py
WorkcellIO(memory: Memory) (mini-I/O-Fassade) mit open(ticket_id, workcell_space_id=None)→legt Workcell-Space kind="workcell" + ST-Spaces planner|coder|critic an und set_status(...,"running"), start(workcell_sid, payload)→Event "start", step_out(workcell_sid, st_ids, role, content, prompt=None)→write_message in Workcell und Spiegelung in ST (st_ids[role]), close(workcell_sid, review="OK", impl_ok=True, do_gc=True)→set_status(...,"done")+Event "done"+optional gc; nutzt WorkcellOpenResult und ein schlankes Memory-Protocol (create_space|write_message|write_event|set_status|gc).

# backend/orchestration/zep_adapter.py
ZepMemoryAdapter(zep_facade, thread_mode: Literal["isolated","shared"]="isolated", targets={"workcell":"inmem","orch":"graph","agent_st":"inmem"}) stellt ein synchrones Minimal-Memory für CaptainHub bereit: _Space(dataclass) als In-Memory-Ablage (messages,events), create_space(kind,name,parent_id)->space_id, write_message(space_id, role, content, metadata=None), write_event(*, space_id, type, payload), set_status(space_id, status), gc(space_id); Diag: thread_mode, targets(), space_snapshot(space_id); ZEP-Spiegelung ist als TODO vorgesehen.

<!-- # backend/prompts.py
Schlanke Template‑Klasse (PromptTemplates) mit drei Textbausteinen: planner, implement, review. Deutsche Default‑Prompts erzeugen knappe, schrittfokussierte Ausgaben. Helfer _join(...) formatiert Listen. Convenience‑Funktionen render_planner/implement/review setzen die Templates mit Ziel, Deliverables und Constraints. -->