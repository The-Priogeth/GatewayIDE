## Dokumentation: Agenten-Dashboard UI (Workforce Project)

### 1. Zielsetzung
Das Agenten-Dashboard ist eine zentrale Benutzeroberfläche zur Verwaltung, Interaktion und Beobachtung von KI-Agenten im Rahmen des Workforce-Konferenzsystems. Ziel ist eine kompakte, funktionale und erweiterbare Ansicht, die sowohl viele Agenten gleichzeitig abbildet als auch spezifische Interaktionen wie Chat, Settings oder Statusmanagement erlaubt.

---

### 2. Funktionsübersicht

#### 2.1 Agentenanzeige


#### 2.2 Aktionen pro Agent
- **Settings:** vorbereitet für spätere Konfiguration (noch leer)
- **Chat:** öffnet modales Fenster mit Agentenname und Status
- **Delete:** löscht Agent aus persistenter JSON-Datei (`stored_agents.json`)

#### 2.4 Chat-Dialog
- **Modal:** Overlay-Fenster mit Drag-Funktion
- **Header:** Agentenname + Status
- **Thread:** Nachrichtenanzeige (User/Agent-Simulation)
- **Input:** Eingabefeld mit Enter-Auslösung

#### 2.5 Statusdarstellung (farbig)
Status sind über CSS-Klassen wie `.agent-status.idle`, `.agent-status.reading`, etc. abgebildet und visuell hervorgehoben.

#### 2.6 Tool-Leiste
- Direkt neben "Agent Dashboard" platziert
- Buttons: `Create`, `Import`, `Export` (Import/Export: vorbereitet)

---

### 3. Technische Umsetzung

#### 3.1 HTML-Struktur
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

#### 3.2 Persistenz (Backend)
- Datei: `stored_agents.json`
- Endpunkte:
  - `/api/agents/status` (GET)
  - `/api/agents/create` (POST)
  - `/api/agents/delete/<name>` (DELETE)

#### 3.3 Frontend (JS)
- Datei: `main.js`
- Dynamische DOM-Erzeugung der Agentenkarten
- Eventlistener für Chat, Delete, Create
- Drag-Funktion für Chatfenster über `mousedown`/`mousemove`

#### 3.4 Styling
- Datei: `style.css`
- Kompakt: `.agent-card`, `.agent-status`, `.chat-modal`
- Farb- und Layoutdefinitionen für alle Statusvarianten

---

### 4. Statusübersicht (Standardisiert)
| Status         | Farbe (CSS)     |
|----------------|-----------------|
| idle           | #888            |
| reading        | #2196f3         |
| writing        | #4caf50         |
| listening      | #ff9800         |
| answering      | #00bcd4         |
| waiting        | #ffc107         |
| searching      | #9c27b0         |
| thinking       | #ff5722         |
| executing      | #f44336         |
| planning       | #3f51b5         |
| summarizing    | #009688         |
| translating    | #795548         |
| reviewing      | #673ab7         |
| error          | #f00            |
| offline        | #555 (durchgestrichen) |

---

### 5. Ausblick / Nächste Schritte
- Agenten-Konfiguration (Settings) editierbar machen
- Chatverlauf speichern (temporär oder persistent)
- Import/Export-Funktionalität für Agentenprofile (JSON)
- WebSocket-basierte Live-Kommunikation
- Verlinkung mit Konferenzlogik und Rollensteuerung

---

### 6. Verknüpfte Dateien
- `base.html` → Struktur
- `main.js` → Logik
- `style.css` → Layout
- `agents_routes.py` → Backend
- `stored_agents.json` → Datenspeicher


> Letzte Änderung: nach erfolgreicher Integration des modalen Chatfensters mit Drag & Statusanzeige. Import/Export und Settings in Vorbereitung.

Im Zuge der Weiterentwicklung des agentenbasierten Frameworks wird eine moderne, webbasierte Konfigurationslogik für Agentenprofile eingeführt. Ziel ist es, die bislang in Tkinter realisierten Konfigurationsansichten in eine strukturierte, skalierbare und frontendkompatible Form zu überführen, ohne jedoch die Logik vergangener Prototypen direkt zu übernehmen. Vielmehr dienen diese als heuristische Grundlage für die semantische und funktionale Gruppierung der Konfigurationselemente.

Jeder Agent im System erhält eine eigene JSON-basierte Konfigurationsdatei, die zentral unter stored_agents.json oder als Einzeldokument gespeichert wird. Die Kernstruktur dieser Agentenprofile umfasst neben Basisfeldern wie Name, Typ und Beschreibung auch LLM-spezifische Einstellungen (z. B. Modellwahl, Prompt, Temperatur), Interaktionsverhalten (Input-Modus, Antwortgrenzen), optionale Codeausführungsparameter (Docker, Timeout) sowie Terminierungsregeln. Ein dediziertes Schema in agent_schema.json definiert Typen, Pflichtfelder, Standardwerte und die zugehörige UI-Komponente (Input, Dropdown, Checkbox etc.).

Die Modellwahl wird über model_defaults.json gesteuert, welches alle gängigen Modellnamen (z. B. gpt-3.5-turbo, gpt-4-1106-preview, whisper-1 etc.) samt zugehöriger Parameter (z. B. Tokenlimit, Temperaturbereich, API-Spezifikationen) zentral verwaltet. Dadurch lässt sich die Dropdown-Auswahl im UI automatisch generieren und validieren.

Frontendseitig wird das Agenten-Dashboard um einen "Settings"-Button erweitert. Dieser öffnet ein modales Fenster mit Tabs für verschiedene Konfigurationsgruppen: Grundlagen, LLM, Verhalten, Codeausführung, Erweitert. Die Formularfelder orientieren sich an der Schema-Definition. Die Speicherung erfolgt entweder automatisch bei jeder Eingabe oder manuell über einen „Speichern“-Button mit Bestätigungsfeedback.

Die API-Endpunkte sind minimal gehalten:

GET /api/agents/settings/<name> liefert die gespeicherte Agentenkonfiguration oder fällt auf das Schema zurück.

POST /api/agents/settings/<name> speichert die übermittelte Konfiguration und validiert sie gegen das Schema.

Perspektivisch kann diese Architektur um Funktionen wie Preset-Auswahl, Schema-basierte Validierung im Frontend, Undo-Stacks oder Live-Vorschau erweitert werden. Entscheidend ist, dass sie die Übergabe an die „agent_core“-Module sauber abbildet und die Personalisierung sowie das Debugging einzelner Agenten erheblich erleichtert. Die Übergangslogik zwischen Settings-UI, Konferenzlogik und aktiver Agentenausführung bildet damit einen elementaren Baustein des geplanten Produktionssystems.