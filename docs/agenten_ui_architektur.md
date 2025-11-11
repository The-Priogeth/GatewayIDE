# Agenten‑UI & Settings Architektur (Fusion aus Agenten‑Dashboard & Agent‑Settings)

> Konsolidierungsstatus: **aktiv**
> Herkunft: Zusammenführung von `agenten_dashboard_doku.md` und `agent_settings_architektur.md` inkl. Kontextpassagen.
> Zweck: Eine Quelle für UI‑Konzept, Statusdarstellung, JSON‑basierte Settings, API‑Schnittstellen und geplante Erweiterungen.

---

## 1) Zielsetzung & Gesamtüberblick

Diese Datei beschreibt die **UI‑Architektur** des Agenten‑Dashboards sowie die **webbasierte Konfigurationslogik** für Agentenprofile. Sie löst die historisch gewachsenen, teilweise redundanten Textblöcke aus zwei Dokumenten ab und führt sie in einer **kohärenten, frontend‑kompatiblen** und **API‑gestützten** Form zusammen. Der Fokus liegt auf: (a) klarer UI‑Struktur für Anzeige/Interaktion, (b) JSON‑basierten Settings je Agent (inkl. Schema), (c) minimaler, stabiler API und (d) einem Ausblick auf Validierung, Live‑Status und spätere Features.

Kontext: Die bisherigen Tkinter‑Prototypen dienen als **heuristische Grundlage** (Gruppierung, Felder), werden aber nicht 1:1 übernommen. Das Ziel ist eine **moderne Web‑UI**, die mit dem Backend über REST/WS kommuniziert, Agentenprofile in JSON speichert und mittels Schema validiert.

---

## 2) UI‑Bausteine: Dashboard, Modal‑Chat, Settings

### 2.1 Dashboard (Listen‑/Kartenansicht)

* **Header** mit Titel „Agent Dashboard“ und **Tool‑Leiste** (Create, Import, Export).
* **Agentenliste** als dynamisch erzeugte DOM‑Karten (Name, Typ, Status‑Badge, Kurzbeschreibung, Aktionen).
* **Aktionen pro Agent**:

  * **Settings**: öffnet Konfigurations‑Modal (Tabs: Grundlagen, LLM, Verhalten, Codeausführung, Erweitert).
  * **Chat**: öffnet modales Chatfenster (Header: Name+Status; Thread‑Ansicht; Input mit Enter‑Send).
  * **Delete**: löscht Agent aus der Persistenz (`stored_agents.json` bzw. Einzeldatei).
* **Statusdarstellung** per CSS‑Klassen `.agent-status.*` (siehe 2.5).
* **Import/Export** sind vorbereitet (Hooks), tatsächliche Datei‑I/O wird später ergänzt.

**Referenz‑HTML‑Skelett (aus dem Legacy‑Konzept):**

```html
<section id="agent-dashboard">
  <div class="agent-dashboard-header">
    <h2>Agent Dashboard</h2>
    <div class="agent-toolbar">
      <button id="create-agent">Create New Agent</button>
      <button id="import-agent">Import Agent</button>
      <button id="export-agent">Export Agent</button>
    </div>
  </div>
  <div id="agent-list"></div>
</section>
```

### 2.2 Chat‑Dialog (Modal)

* **Overlay** mit Drag‑Funktion (mousedown/mousemove).
* **Header**: Agentenname + Live‑Status.
* **Thread**: Nachrichtenanzeige (User/Agent‑Simulation).
* **Input**: Eingabefeld mit Enter‑Auslösung; später optional Tool‑Buttons (Anhang, Presets, Stop).
* **Persistenz** (später): optionaler Verlaufsspeicher pro Agent (lokal/Server).

### 2.3 Settings‑Modal (Schema‑getrieben)

* Tabs orientieren sich am **Schema** (siehe 4.2):

  1. **Grundlagen** (Name, Typ, Beschreibung)
  2. **LLM** (Modellwahl, Temperatur, Max‑Tokens, Timeout, Provider‑Config)
  3. **Verhalten** (human_input_mode, auto_reply‑Zyklen, Antwortgrenzen)
  4. **Codeausführung** (Docker‑Nutzung, Timeout, Workdir, Dateiname, Sprache)
  5. **Erweitert** (Terminierungsregeln, Spezialflags, Debug, Presets)
* Speicherung: **auto‑save** (onChange) oder **explizit** per „Speichern“ mit Feedback‑Toast.

### 2.4 Tool‑Leiste (global)

* Neben dem Dashboard‑Titel.
* **Create**: legt leeres Profil nach Schema an (Defaultwerte).
* **Import**: JSON‑Upload (Validierung gg. Schema).
* **Export**: selektierte Agenten als JSON (Einzel/Batch).

### 2.5 Statusübersicht (CSS‑Mapping)

| Status      | CSS‑Farbe (Beispiel) |
| ----------- | -------------------- |
| idle        | #888                 |
| reading     | #2196f3              |
| writing     | #4caf50              |
| listening   | #ff9800              |
| answering   | #00bcd4              |
| waiting     | #ffc107              |
| searching   | #9c27b0              |
| thinking    | #ff5722              |
| executing   | #f44336              |
| planning    | #3f51b5              |
| summarizing | #009688              |
| translating | #795548              |
| reviewing   | #673ab7              |
| error       | #f00                 |
| offline     | #555 (strikethrough) |

> Hinweis: Farben sind Platzhalter und können zentral über CSS‑Variablen/Theming definiert werden.

---

## 3) Backend‑Persistenz & Endpunkte

### 3.1 Speicherorte

* **Zentraldatei**: `stored_agents.json` (Schnellstart, einfache Persistenz).
* **Alternative**: **Einzeldokumente** pro Agent (`/data/agents/<name>.json`) – erleichtert Git‑Diffs und Merges.
* **Schema‑Dateien**:

  * `agent_schema.json` (Felder, Typen, Pflichtwerte, UI‑Komponenten‑Hints).
  * `model_defaults.json` (Modellnamen, Tokenlimits, Temperaturbereiche, API‑Spezifika).

### 3.2 Minimal‑API

* `GET /api/agents/status` → Liste laufender/registrierter Agenten (für Dashboard).
* `POST /api/agents/create` → legt Agent mit Default‑Profil an.
* `DELETE /api/agents/delete/<name>` → entfernt Agent aus Persistenz.
* `GET /api/agents/settings/<name>` → lädt gespeicherte Konfiguration **oder** fällt auf Schema‑Defaults zurück.
* `POST /api/agents/settings/<name>` → speichert übermittelte Konfiguration, **validiert** gegen Schema; gibt Normalform zurück.

> Prinzip: **schlank** bleiben. Weitere Endpunkte (Import/Export, Presets, Batch‑Updates) erst nach Stabilisierung.

---

## 4) Settings‑Architektur (JSON, Schema, Defaults)

### 4.1 Grundidee

Jeder Agent hat ein **JSON‑Profil**: Basisfelder (name, type, description), **LLM‑Konfiguration** (Modell, Temperatur, max_tokens, timeout), **Interaktionsverhalten** (human_input_mode, auto‑reply), **optionale Codeausführung** (Docker, timeout, work_dir, filename, lang) sowie **Terminierungsregeln**. Diese Struktur ist **Schema‑geführt**, damit UI und Backend deterministisch und valide bleiben.

### 4.2 `agent_schema.json` (Beispielstruktur)

* **Typen & Pflichtfelder**: name (string, required), agent_type (enum: assistant, tool, user_proxy, …), description (string), human_input_mode (enum: NEVER/TERMINATE/ALWAYS), max_consecutive_auto_reply (int ≥0), default_auto_reply (string), is_termination_msg (string/regex),
* **LLM**: model (enum aus `model_defaults.json`), temperature (0..2), max_tokens (≥1), timeout (s), provider‑config (api_key‑Ref, base_url, api_type, api_version),
* **Codeausführung**: use_docker (bool), timeout (s), work_dir (string), filename (string), lang (enum),
* **UI‑Hints**: component (input, textarea, dropdown, checkbox, slider), group (Grundlagen/LLM/…)

### 4.3 `model_defaults.json`

* Aggregiert **zulässige Modellnamen** (z. B. `gpt‑4.1‑mini`, `gpt‑4.1`, `whisper‑1`, …) inkl. **Parameterrahmen** (max_tokens, temperature‑Range) und etwaiger **Provider‑Spezifika**.
* UI generiert **Dropdowns** aus dieser Datei und validiert Eingaben schon **clientseitig**.

### 4.4 Validierungsfluss

1. UI lädt Schema + Defaults (Cache).
2. Eingaben werden **live** gegen Schema geprüft (Fehlermeldung neben Feld).
3. `POST /settings/<name>` führt **Server‑Validierung** aus (Single Source of Truth), normalisiert Werte und persistiert.
4. Serverantwort aktualisiert UI‑State (Optimistic UI optional, aber nachziehen mit Server‑Payload).

---

## 5) Frontend‑Implementierung (Referenz)

### 5.1 Dateien & Verantwortlichkeiten

* `base.html` → statische Grundstruktur und Container (Dashboard‑Section, Modals).
* `main.js` → dynamische DOM‑Erzeugung (Agentenkarten), Event‑Handling (Chat/Settings/Delete/Create), Drag‑Logik für Modals, API‑Calls, State‑Management (in‑memory Cache der Agenten).
* `style.css` → Layout, Farbthemen, Status‑Badges, Modal‑Styling, responsive Anpassungen.

### 5.2 Zustandsmodell (UI)

* `agents[]`: Liste der Agenten inkl. `status` (idle/…);
* `selectedAgent`: aktuell geöffnetes Settings‑ oder Chat‑Modal;
* `schema`, `modelDefaults`: basis für Formular‑Generierung;
* `dirtyFlags`: pro Feld/Tab zur Steuerung von Save‑Buttons und Warnungen.

### 5.3 Interaktionsabläufe

* **Create** → (1) GET Schema/Defaults → (2) POST Create → (3) Push in `agents[]` → (4) optional Settings‑Modal öffnen.
* **Edit** → (1) GET Settings → (2) UI‑Form füllt Felder → (3) onChange: validate + mark dirty → (4) Save: POST Settings → (5) UI normalisiert.
* **Chat** → (1) Modal öffnen → (2) Thread laden (optional) → (3) Eingabe senden → (4) Antwort anzeigen; WebSocket später.
* **Delete** → (1) Confirm → (2) DELETE → (3) aus `agents[]` entfernen.

---

## 6) Live‑Status & WebSocket (Ausblick)

* **WS‑Kanal**: Echtzeit‑Updates zu `status` (reading/writing/…); Dashboard‑Badges aktualisieren.
* **Undo‑Stack**: Feldänderungen in Settings rückgängig machen (lokal, optional serverseitig).
* **Live‑Vorschau**: geänderte Settings als „Simulation“ (z. B. veränderte Temperatur) in einem Test‑Prompt ausprobieren.

---

## 7) Import/Export & Presets (Ausblick)

* **Import**: JSON‑Upload, Validierung gg. Schema, Normalisierung, Merge‑Strategie (Konfliktlösung nach Feld).
* **Export**: Einzel‑/Sammel‑Export (Datei pro Agent oder Bundle).
* **Presets**: wiederverwendbare Profile (z. B. „Programmer‑Strict“, „Critic‑Gentle“), auswählbar im Settings‑Modal.

---

## 8) Übergabe an agent_core

* Settings werden **read‑only** an die `agent_core`‑Module übergeben; keine Geschäftslogik in der UI.
* Einheitlicher **Adapter** (z. B. `AgentSettingsProvider`) liefert validierte Konfigurationen.
* Debugging: UI zeigt die tatsächlich **wirksame** Konfig (nach Server‑Normalisierung) an.

---

## 9) Sicherheit, Versionierung, Governance

* **Config‑Scope**: sensible Werte (API‑Keys) nicht im Agentenprofil speichern → nur **Ref‑Keys**/Placeholders; tatsächliche Secrets in `.env`/Secret‑Store.
* **Schema‑Version**: `schema_version` pro Agent; Migrationspfad definieren (Server hebt alte Profile).
* **Audit‑Trail**: optional Änderungslog (wer/was/wann), nützlich für Debug/Compliance.

---

## 10) Test‑ & Abnahmekriterien (DoR/DoD)

* **Form‑Validierung**: Client/Server stimmen überein (Fehlerfälle abgedeckt).
* **Status‑Badges**: alle definierten Zustände rendern korrekt.
* **API**: 200/400/404‑Pfade, saubere Fehlertexte, Idempotenz bei Create.
* **Persistenz**: Round‑trip Create→Read→Update→Read liefert stabile Normalform.
* **Accessibility**: Tastatur‑Nutzung der Modals, ARIA‑Labels, Kontrast.
* **Performance**: 200 Agenten listen & filtern ohne Layout‑Jank.

---

## 11) Glossar

* **Agentenprofil**: JSON‑Objekt mit Feldern zu Verhalten, LLM, Tools etc.
* **Schema**: JSON‑Schema‑ähnliche Definition (Typen, Pflicht, UI‑Hints).
* **Defaults**: externe Datei mit zulässigen Modellnamen und Parameter‑Ranges.
* **Normalisierung**: Server setzt fehlende Defaults, korrigiert Wertebereiche, gibt konsistente Form zurück.

---

## 12) Changelog

* **v0.1 (heute)**: Fusion `agenten_dashboard_doku.md` + `agent_settings_architektur.md`.
* **v0.2 (geplant)**: Ergänzung Import/Export‑Flow, Presets, WS‑Eventspezifikation.
