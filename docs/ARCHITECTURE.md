# ARCHITECTURE.md – Vollständige Systembeschreibung (Detaillierte Fassung)

> Diese Fassung beschreibt den vollständigen Ablauf des Gateway-Backends mit allen Funktionsaufrufen, Datenflüssen und Zuständigkeiten. Sie orientiert sich am tatsächlichen Codeaufbau (`main.py`, `bootstrap.py`, `konstruktor.py`, `messaging.py`) und folgt dem Stil einer technischen Laufzeitbeschreibung.

---

# 1) App-Start (FastAPI Lifespan)

1. `main.py` startet, ruft in `lifespan()` → `await bootstrap.ensure_runtime()`.
2. `bootstrap.ensure_runtime()`

   * Lädt `.env` (Model, API-Keys, Zep-Konfiguration).
   * Baut **Zep-Client** und legt **Threads** an (jeweils via `_setup_thread(...)` mit neuem `user_id` und `thread_id`, inkl. zugehöriger `ZepUserMemory`-Instanz):

     * **T1** → Dialog (User ↔ System) → `t1_thread_id`, `t1_memory`
     * **T2** → Innerer Prozess → `t2_thread_id`, `t2_memory`
     * **T3** → Meta-Kommunikation → `t3_thread_id`, `t3_memory`
     * **T4** → Librarian intern → `t4_thread_id`, `t4_memory`
     * **T5** → TaskManager intern → `t5_thread_id`, `t5_memory`
     * **T6** → Trainer intern → `t6_thread_id`, `t6_memory`
   * Erzeugt `ContextProvider` (liefert später `get()` als Gesprächszusammenfassung) und ruft initial `refresh()` auf.
   * Definiert `memory_logger(role, name, content)`:

     * Schreibt asynchron **nur User-Events** in **T1** (Dialogspur User↔System),
     * aktualisiert nach jedem Write die Summary via `ctx_provider.refresh()`.
   * Initialisiert **MemorySink**-Instanzen **für T1–T3** und den **PBuffer**:

     * `sink_t1 = MemorySink(thread_id=t1_thread_id, memory=t1_memory)`
     * `sink_t2 = MemorySink(thread_id=t2_thread_id, memory=t2_memory)`
     * `sink_t3 = MemorySink(thread_id=t3_thread_id, memory=t3_memory)`
     * **Hinweis zu T4–T6:** Es werden **keine separaten MemorySink-Wrapper** angelegt; Schreibzugriffe erfolgen **direkt** auf `t4_memory`/`t5_memory`/`t6_memory` über die Transport-Hilfsfunktion `_call_agent_and_persist(...)`.
   * Erstellt den **MessagingRouter** mit Parametern:

     * `sink_t1`, `sink_t2`, `sink_t3`, `pbuffer`, `transport`
   * Verdrahtet **Transport-Routen** (Outbound an Subsysteme):

     * `to_user(text)` (derzeit ohne Persistenz; Persistenz der Finaltexte übernimmt Egress/Messaging),
     * `to_task(text)` → `MetaAgentTaskManager` auf **T5** mittels `_call_agent_and_persist(meta_task, mem=t5_memory, ...)`,
     * `to_lib(text)`  → `MetaAgentLibrarian`   auf **T4** mittels `_call_agent_and_persist(meta_lib,  mem=t4_memory, ...)`,
     * `to_trn(text)`  → `MetaAgentTrainer`     auf **T6** mittels `_call_agent_and_persist(meta_trn,  mem=t6_memory, ...)`.
   * Ruft `build_hma(messaging, ctx_provider, memory_logger)` und erstellt den **Haupt-Meta-Agenten (HMA)**.
   * Speichert `hma` und `ctx_provider` in `app.state`.

---

# 2) `/chat` Endpoint (main.py)

**Dekorationen & Modelle**

* **Lifespan-Contextmanager**: `@asynccontextmanager` auf `lifespan(app: FastAPI)`; wird in `FastAPI(lifespan=lifespan, ...)` registriert. Innerhalb von `lifespan` ruft die App `await bootstrap.ensure_runtime()` auf und legt alle Artefakte in `app.state.*` ab (u. a. `runtime`, `zep_client`, `t1_memory`, `t2_thread_id`, `ctx_provider`, `hma`, `messaging`, `pbuffer_dir`).
* **Pydantic-Requestmodell**: `class ChatRequest(BaseModel): prompt: str`.
* **Endpoint-Dekorator**: `@app.post("/chat")` für den zentralen Chat-Endpunkt.

**Ablauf (Schritt für Schritt)**

1. **Request annehmen**: FastAPI mappt den Body auf `ChatRequest` (Feld `prompt`).
2. **Ingress-Persistenz**: Die User-Eingabe wird sofort in **T1** persistiert via `t1_memory.add(MemoryContent(..., metadata={"role":"user","thread":"T1"}))`, damit sie im UI unmittelbar sichtbar ist.
3. **Kontext aktualisieren**: Über `zep.thread.get_user_context(thread_id=t1_thread_id, mode="summary")` wird die T1-Zusammenfassung geholt und per `ctx_provider.update(...)` in den ContextProvider gespiegelt.
4. **HMA ausführen**: `result = hma.step(req.prompt)` triggert Fan-Out/Fan-In, Ich-Synthese und `deliver_to`-Entscheidung.
5. **Response-Items bauen**:

   * Wenn vorhanden: `inner_combined = result["inner_combined"].strip()` → `{agent: "SOM:inner", content: inner_combined}` (für **T2**-Anzeige im UI).
   * Falls `deliver_to == "user"` und `content` gesetzt: `{agent: "SOM", content: content}` (für **T1**-Anzeige im UI).
6. **Antwortstruktur** (vereinfacht):

   ```json
   {
     "ok": true,
     "final": true,
     "deliver_to": "user|task|lib|trn",
     "speaker": "HMA",
     "corr_id": "<uuid>",
     "packet_id": "<uuid>",
     "p_snapshot": "<path-or-none>",
     "responses": [ {"agent":"SOM:inner","content":"..."}, {"agent":"SOM","content":"..."} ]
   }
   ```

**Signaturen (Kurzreferenz)**

```python
@asynccontextmanager
async def lifespan(app: FastAPI): ...

app: FastAPI = FastAPI(lifespan=lifespan, title=..., description=..., version="2.12")

class ChatRequest(BaseModel):
    prompt: str

@app.post("/chat")
async def chat(req: ChatRequest): ...
```

---

# 3) HMA-Aufbau (bootstrap.py)

1. **HMA-Erzeugung** erfolgt über `build_hma(...)` in `bootstrap.ensure_runtime()`.

   * Übergabewerte: `llm_config`, `demo_profiles`, `lobby_agents`, `hma_config`, `memory_context_provider`, `memory_logger`, `messaging`.
   * Rückgabe: HMA-Paket/Objekt (`hma`), das intern Router, SOMCore und Speaker kapselt.

2. **Konkrete Meta-Agenten (äußerer Bereich)** werden vor dem HMA gebaut und als `lobby_agents` injiziert:

   * `MetaAgentLibrarian(name="Librarian",   llm_config=llm_cfg, human_input_mode="NEVER")` → **T4** (Recherche/Fakten)
   * `MetaAgentTaskManager(name="TaskManager", llm_config=llm_cfg, human_input_mode="NEVER")` → **T5** (Plan/Koordination)
   * `MetaAgentTrainer(name="Trainer",     llm_config=llm_cfg, human_input_mode="NEVER")` → **T6** (Lernen/Coaching)
   * Jeder Meta-Agent besitzt einen eigenen Zep-Thread (`t4_thread_id`, `t5_thread_id`, `t6_thread_id`) und eine eigene `ZepUserMemory`-Instanz (`t4_memory`, `t5_memory`, `t6_memory`).

3. **Transport-Routen & Messaging-Einbindung**

   * In `ensure_runtime()` werden Outbound-Routen definiert und dem `Transport` übergeben:

     * `to_user(text)` → **Stub** (keine Persistenz hier; Finaltexte schreibt ausschließlich der **Egress/MessagingRouter** in **T1**).
     * `to_task(text)` → ruft `_call_agent_and_persist(meta_task, mem=t5_memory, agent_name="TaskManager", thread_label="T5")` (Persistenz **direkt** nach **T5**).
     * `to_lib(text)`  → ruft `_call_agent_and_persist(meta_lib,  mem=t4_memory, agent_name="Librarian",   thread_label="T4")` (Persistenz **direkt** nach **T4**).
     * `to_trn(text)`  → ruft `_call_agent_and_persist(meta_trn,  mem=t6_memory, agent_name="Trainer",     thread_label="T6")` (Persistenz **direkt** nach **T6**).
   * Diese `Transport`-Instanz wird zusammen mit `sink_t1`, `sink_t2`, `sink_t3` und `pbuffer` an den `MessagingRouter` übergeben. Somit kann der **Egress** (über `send_addressed_message(...)`) final entscheiden:

     * `deliver_to == "user"` → **T1**-Persistenz (Final-Dialog) + Transport `to_user`.
     * `deliver_to in {task, lib, trn}` → **T3**-Persistenz (**Envelope only**) + Transport zur jeweiligen Route; Payload liegt im **P-Buffer**.

4. **HMA interne Struktur** (durch `build_hma(...)`):

   * **Router** (Ingress/Egress): wählt Demo-Agenten (Fan-Out), sammelt Antworten (Fan-In) und leitet abhängig von `deliver_to` den Egress ein (Persistenz via `MessagingRouter`).
   * **SOMCore**: orchestriert die Ich-Synthese auf Basis der Demo-Antworten und des `ContextProvider.get()`-Strings.
   * **Speaker**: formatiert den Ich-Text zur adressierten Ansprache und gibt sie an den Messaging/Egress weiter.

5. **Thread-Nutzung durch HMA**

   * **T1** → sichtbarer Dialog (User ↔ HMA, Finaltexte),
   * **T2** → innerer Prozess (Demo-Snippets, Aggregat, Ich-Referenz),
   * **T3** → Meta-Kommunikation (Envelope only).

---

# 4) Innerer Prozess (konstruktor.py)

Dieser Abschnitt beschreibt die **konkrete Ausführungskette** in `konstruktor.py` – von der Demo-Parallelausführung über die Solo-Synthese des SOM bis hin zur T2-Persistenz und der finalen Egress-Übergabe.

## 4.1 Hilfsfunktionen (Normalisierung & JSON-Extraktion)

* `_to_text(reply) -> str`

  * Akzeptiert Agent-Antworten in unterschiedlichen Formen (`list/tuple/str`).
  * Gibt stets **den letzten String** zurück (bei Sequenzen), sonst `str(reply)`.

* `_normalize_reply(out) -> str`

  * Verträgt beide Varianten der Autogen-Rückgaben: `(ok: bool, rep: Any)` **oder** `rep: Any`.
  * Vereinheitlicht auf **Plain-Text** (ruft intern `_to_text` auf). Ziel: robuste Textbasis ohne Kontrollfluss über Return-Typen.

* `_extract_last_json(text: str) -> Tuple[str, Dict[str, Any]]`

  * Sucht **letzten** JSON-Block (`{...}`) im String (DOTALL-RegEx),
  * versucht `json.loads(...)`; bei Erfolg wird der JSON **entfernt** und als Dict zurückgegeben,
  * Rückgabe: `(bereinigter_text, json_dict)`; bei Fehlern: `(text, {})`.
  * Zweck: Am Ende des Ich-Textes eingebettetes Routing JSON (z. B. `{ "deliver_to": "user" }`) **verlustfrei** abtrennen.

## 4.2 Router-Logik (Fan-Out → Fan-In)

### 4.2.1 Konstruktor

```python
class HMA_Router:
    def __init__(self, som_group, som_core, demo_profiles, max_workers=4):
        self.som_group = som_group   # GroupChat-Kontext, kein Final-Prompt
        self.som_core  = som_core    # SOLO-Agent für finale Synthese
        self.demos     = list(demo_profiles or [])
        self.max_workers = max_workers
```

### 4.2.2 Parallele Demo-Anfrage: `_parallel_demo(user_text, context)`

* Baut **pro Demo-Agent** einen **knappen Prompt** (1–3 Sätze, **ohne JSON/Listen/Routing**).
* Übergibt dem jeweiligen Agenten die Nachricht über `agent.generate_reply(..., sender=self.som_group)` – der `sender` ist die SOM-Gruppe (für konsistente Stimmführung im inneren Raum).
* Verwendet `ThreadPoolExecutor` mit `max_workers = min(len(demos), 4)`.
* Fehlerbehandlung: Exceptions je Demo werden **pro Agent geloggt** und als leere Antwort `(name, "")` aufgenommen (kein Abbruch der Gesamtauswertung).
* Rückgabeformat: `List[Tuple[name: str, reply: str]]`.

### 4.2.3 Aggregation: `run_inner_cycle(...).`

* Ruft `_parallel_demo(...)` auf, baut daraus ein **Markdown-Aggregat**:

  ```
  ## <DemoName>
  <Kurzbeitrag>
  ```
* Ist die Liste leer, wird `(keine internen Beiträge)` gesetzt.
* Erzeugt das **Finalprompt** aus `som_final_template.format(user_text=..., aggregate=...)`.

## 4.3 Solo-Synthese (SOMCore) & Routing-Ermittlung

* **Wichtig:** Die finale Synthese läuft **nicht** über den GroupChat, sondern **solo** über `som_core.generate_reply(messages=[{"role":"user","content":final_prompt}], sender=None)`.
* Das Ergebnis (`full`) wird über `_normalize_reply` in Text gegossen.
* `_extract_last_json(full)` trennt den eigentlichen Ich-Text (`ich_text`) vom optionalen letzten JSON.
* **`deliver_to`-Normalisierung**:

  * Default `"user"`.
  * Wenn JSON ein Feld `deliver_to` hat, wird dessen Wert (`.lower()`) in die Menge `{"user","task","lib","trn"}` projiziert; unbekannte Werte fallen auf `"user"` zurück (defensive Safety).

## 4.4 Übergabe an Messaging (T2-Persistenz)

* `HauptMetaAgent.step(...)` ruft nach der Synthese `messaging.log_som_internal_t2(aggregate=inner_material, ich_text=ich_text)` auf.

  * **Persistiert** den kombinierten T2-Block asynchron (über `sink_t2`).
  * **Echo**: rekonstruiert denselben kombiniert formatierten Text lokal in `inner_combined`, damit `/chat` ihn **ohne Polling** direkt ans UI liefern kann.

* Parallel wird über `_log("assistant", "SOM:ich", ...)` eine **Kurzfassung** des Ich-Textes (200 Zeichen) protokolliert (Loguru + optionaler `memory_logger`).

## 4.5 Adressierte Ausgabe (Speaker → Messaging/Egress)

* `HMA_Speaker.speak(from_name, to, ich_text, corr_id=None)`:

  * Präfixiert je nach Ziel (`"task"→"@TaskManager: "`, `"lib"→"@Librarian: "`, `"trn"→"@Trainer: "`; `"user"` ohne Präfix).
  * Ruft `messaging.send_addressed_message(frm=from_name, to=to, text=addressed, intent="inform", corr_id=corr_id)`.
  * **Egress-Entscheidung** passiert in `MessagingRouter`:

    * `to=="user"` → **T1-Persistenz** des Finaltexts.
    * `to in {task,lib,trn}` → **T3-Envelope** (Payload liegt im **P-Buffer**), danach Transport zur jeweiligen Outbound-Route.

## 4.6 `HauptMetaAgent.step(...)` – Ablauf im Ganzen

1. **Kontext holen**: `ctx = self._ctx()` (ruft `memory_context_provider()`; leer bei Fehlern).
2. **Eingang loggen**: `_log("user", "INPUT", incoming_text)`.
3. **Innerer Zyklus**: `ich_text, deliver_to, inner_material = router.run_inner_cycle(user_text=incoming_text, context=ctx or "(kein zusätzlicher Kontext)", som_final_template=self.cfg.som_final_template)`.
4. **Ich-Log**: `_log("assistant", "SOM:ich", f"{ich_text[:200]}... | deliver_to={deliver_to}")`.
5. **T2-Persistenz + Echo**: `log_som_internal_t2(...)` + Aufbau von `inner_combined` ("# Interner Zwischenstand... # Ich...").
6. **Egress**: `result = speaker.speak(from_name="HMA", to=deliver_to, ich_text=ich_text)`.
7. **Rückgabe an `/chat`**:

   ```python
   {
     "final": True,
     "deliver_to": deliver_to,
     "speaker": "HMA",
     "content": ich_text,
     "envelope": result.get("envelope"),
     "snapshot": result.get("snapshot"),
     "inner_combined": inner_combined,
   }
   ```

## 4.7 Randfälle & Robustheit

* **Leere/fehlerhafte Demo-Antworten** werden toleriert; die Aggregation setzt nur nicht-leere Beiträge.
* **JSON-Parsing-Fehler** im Ich-Text führen **nicht** zum Abbruch; es wird auf `deliver_to="user"` zurückgefallen.
* **Kontextausfall** (`memory_context_provider` wirft Exception) resultiert in leerem Kontextstring – der Prozess läuft weiter.
* **Persistenzfehler T2** werden geloggt (`[SOM:T2] Persist-Problem: ...`), beeinträchtigen aber nicht den Egress.
* **Threading**: Fan-Out ist über `ThreadPoolExecutor` limitiert; deadlocks werden durch reinen CPU-Bound-Textaufbau vermieden.

---

# 5) Messaging & Transport (messaging.py)

Dieser Abschnitt dokumentiert die **konkreten Typen, Klassen und Methoden** in `backend/agent_core/messaging.py` und deren Ablauf (Snapshot → Persistenz → Transport). Er bildet die verbindliche Referenz für Egress und T2-Persistenz.

## 5.1 Typen & Datentransport

* **`DeliverTo = Literal["user","task","lib","trn"]`**
  Zieladressen für Egress. Jeder andere Wert ist ungültig und führt zu `RuntimeError` im Transport.

* **`@dataclass Envelope`**

  ```python
  class Envelope:
      id: str                # eindeutige Paket-ID (uuid4)
      ts: float              # Epoch-Timestamp (time.time())
      frm: str               # Absender, z. B. "HMA"
      to: DeliverTo | str    # Ziel ("user"|"task"|"lib"|"trn")
      intent: Literal["ask","inform","order","notify"]
      corr_id: str           # Korrelations-ID (uuid4, für End-to-End-Tracking)
      parent_id: Optional[str] = None
      meta: Optional[Dict[str, Any]] = None
  ```

  Wird durch `_make_envelope(...)` erzeugt und mit `_envelope_json(...)` für T3 serialisiert.

## 5.2 Puffer & Senken

* **`class PBuffer`**

  ```python
  def snapshot(self, *, corr_id: str, to: str, text: str) -> str
  ```

  Schreibt **vor** dem Versand einen **Plaintext-Snapshot** der Payload in das Puffer-Verzeichnis (`<corr_id>_<epoch>_<to>.txt`) und gibt den **Pfad** zurück. Dient als revisionssicherer Versand-Snapshot ("copy to file reicht schon").

* **`class MemorySink`**
  Wrapper für Zep-Threads.

  ```python
  async def write_text(self, *, role: str, name: str, text: str, meta: Dict[str, Any]) -> None
  ```

  Erwartet `memory.add(MemoryContent(...))`. `meta` wird unverändert als `metadata` gespeichert (z. B. `{thread:"T1", kind:"final", corr_id:"..."}`).

* **`class Transport`**
  Kapselt die **Outbound-Routen**; Persistenz macht nicht der Transport, sondern der Router.

  ```python
  def send(self, *, to: DeliverTo, text: str) -> None
  ```

  Delegiert an die beim Bootstrap registrierten Callbacks: `_to_user/_to_task/_to_lib/_to_trn`. Unbekanntes `to` erzeugt `RuntimeError`.

## 5.3 MessagingRouter – öffentliche API & Ablauf

* **Konstruktor**

  ```python
  MessagingRouter(pbuffer: PBuffer, sink_t1: MemorySink, sink_t2: MemorySink, sink_t3: MemorySink, transport: Transport)
  ```

  * `sink_t1` → **T1** (Final-Dialog),
  * `sink_t2` → **T2** (innerer Prozess),
  * `sink_t3` → **T3** (Envelope only),
  * `pbuffer` → Dateisnapshot vor Versand,
  * `transport` → tatsächliches Senden an Zielsysteme.

* **`log_som_internal_t2(aggregate: str, ich_text: str, corr_id: str | None = None) -> dict`**
  Baut einen **kombinierten** Markdown-Block:

  ```
  # Interner Zwischenstand
  ```

<aggregate>

# Ich

<ich_text>

````
Persistiert asynchron nach **T2**:
```python
meta={"thread":"T2","kind":"inner_combined","corr_id": corr_id or ""}
````

Rückgabe: `{ "t2_combined": {"ok": True|False, "thread": "T2", "name": "SOM:inner", ...} }`
(Nutzt intern `_persist_sink(...)` und `asyncio.create_task(...)`).

* **`send_addressed_message(frm, to, text, intent="inform", corr_id=None, parent_id=None, meta=None) -> Dict[str, Any]`**
  **Ablauf in drei Schritten**:

  1. **Snapshot in P**
     `snapshot_path = pbuffer.snapshot(corr_id=env.corr_id, to=to, text=text)`
  2. **Persistenz**

     * `to == "user"`  → **T1-Write** (Assistant→User):

       ```python
       sink_t1.write_text(role="assistant", name=str(frm or "HMA"), text=text,
                          meta={"thread":"T1","kind":"final","corr_id": env.corr_id})
       ```
     * `to in {"task","lib","trn"}` → **T3-Write** (Envelope only):

       ```python
       sink_t3.write_text(role="system", name="PROTO", text=_envelope_json(env),
                          meta={"channel":"meta","corr_id": env.corr_id})
       ```

     Beide Writes laufen **asynchron** via `asyncio.create_task(...)` mit **Best-Effort**-`try/except` (Fehler werden verschluckt, Egress läuft weiter).
  3. **Transport**
     `transport.send(to=to, text=text)` (one-way).
     **Rückgabe** enthält Envelope-Infos und Snapshot-Pfad:

  ```python
  {
    "envelope": {"json": _envelope_json(env), "id": env.id, "corr_id": env.corr_id},
    "snapshot": snapshot_path,
  }
  ```

## 5.4 Interne Helfer

* **`_persist_sink(sink, role, name, text, meta) -> dict`**
  Startet `sink.write_text(...)` per `asyncio.create_task(...)` und gibt ein kleines Status-Dict zurück (`ok`/`error`, `thread`, `name`). Wird für **T2** genutzt.

* **`_make_envelope(frm, to, intent, corr_id, parent_id, meta) -> Envelope`**
  Erzeugt eine **vollständige** `Envelope`-Instanz, setzt `corr_id` falls `None`.

* **`_envelope_json(env: Envelope) -> str`**
  JSON-Serialisierung (schreibt u. a. `id`, `ts`, `from`, `to`, `intent`, `corr_id`, `parent_id`, `meta`). Dieses JSON ist der **einzige Inhalt**, der in **T3** gespeichert wird (Payload verbleibt im **P-Buffer**).

## 5.5 Reihenfolge & Invarianten

1. **Immer** zuerst **P-Snapshot**, danach Persistenz, zuletzt Transport.
2. **T1** enthält ausschließlich Final-Dialog (Assistant→User); **T2** enthält ausschließlich den **inneren Prozess**; **T3** enthält ausschließlich **Envelopes**.
3. **`corr_id`** ermöglicht Thread-übergreifendes Tracking zwischen P-Snapshot, T1/T3-Einträgen und Transport.

## 5.6 Fehler- & Performance-Aspekte

* **Asynchronität**: Persistenz läuft nicht-blockierend (`create_task`), der HTTP-Request wird dadurch nicht verzögert.
* **Fehlerbehandlung**: Persistenzfehler in T1/T3 werden geloggt/ignoriert (Best-Effort), Transport wird trotzdem ausgeführt.
* **Ressourcen**: P-Buffer schreibt kleine Textdateien; Verzeichnisrotation/Retention kann später ergänzt werden.
* **Sicherheit**: Envelope enthält **keine Payload**; sensible Inhalte liegen nur im Pufferfile und ggf. in T1/T2, nie in T3.

---

# 6) Persistenzlogik (Zep)

| Thread | Owner            | Inhalt                         | Schreibquelle              |
| ------ | ---------------- | ------------------------------ | -------------------------- |
| **T1** | Ingress & Egress | User-Dialog & Finaltexte       | `/chat` & MessagingRouter  |
| **T2** | SOM              | Demo-Antworten, Ich-Synthese   | `log_som_internal_t2()`    |
| **T3** | MessagingRouter  | Meta-Kommunikation (Envelopes) | `send_addressed_message()` |

**Ablauf:**

1. User-Eingabe → `main.py` → T1.
2. Innerer Prozess → `messaging.log_som_internal_t2()` → T2.
3. Finale Nachricht → `MessagingRouter.send_addressed_message()` → T1/T3.

---

# 7) ContextProvider & memory_logger

* `ContextProvider.get()` gibt gekürzte Zusammenfassung von T1.
* `memory_logger(role, name, content)`

  * schreibt User-Events nach T1,
  * ignoriert interne SOM/Assistant-Logs.
  * ruft `ctx_provider.refresh()` nach jedem Write.

---

# 8) UI-Verhalten (MainWindowViewModel.cs)

* `AppendAgentReply()` verteilt Nachrichten:

  * `SOM` → ThreadId.T1
  * `SOM:INNER` → ThreadId.T2
  * Keine Finalantworten mehr in T2.
* User-Eingaben erscheinen sofort in T1.
* Optional: Anzeige des internen Prozesses (Fan-In/Out + Ich) im T2-Fenster.

---

# 9) Meta-Kommunikation (T3)

* Wird für System-zu-System-Kommunikation genutzt.
* Nachrichten werden als **Envelope** gespeichert (JSON ohne Payload).
* Payloads liegen im P-Buffer (Dateisystem oder temporärer Speicher).
* Beispiel-Envelope:

  ```json
  {
    "from": "HMA",
    "to": "TaskManager",
    "intent": "order",
    "corr_id": "<uuid>",
    "ts": "2025-10-22T12:00:00Z"
  }
  ```

---

# 10) Fehler- und Wiederherstellungsstrategien

* Fehlerhafte Deliver-To werden geloggt, aber nicht ausgeführt.
* Ungültige JSON-Blöcke werden von SOM ignoriert.
* Abstürze einzelner Agenten (Demos) führen nicht zum Abbruch des Hauptprozesses.
* Logging dokumentiert jedes Event (Eingang, Aggregation, Finalisierung, Versand).

---

# 11) Zusammenfassung

* **Ingress:** `main.py` – User→T1
* **Innerer Prozess:** `konstruktor.py` – Demo→T2
* **Egress:** `messaging.py` – SOM→T1 / Meta→T3
* **UI:** Anzeige in T1 (Final), T2 (innerer Prozess)

Jede dieser Komponenten arbeitet asynchron, modular und mit klarer Verantwortung. Das System ist so ausgelegt, dass alle Aktionen auditierbar und transparent sind.
