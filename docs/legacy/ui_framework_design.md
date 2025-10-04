## UI Framework Dokumentation – Konferenzsystem (Workforce Project)

### 1. Zielsetzung
Das UI dient als zentrale Schnittstelle zwischen Nutzern und einem agentenbasierten KI-System zur Projektentwicklung. Es erlaubt die strukturierte Kommunikation, Steuerung und Visualisierung aller Phasen im strategischen Lageplan. Die Benutzeroberfläche wird modular aufgebaut und soll sowohl Konferenzlogik als auch Agenteninteraktion visuell abbilden.

---

### 2. Hauptkomponenten (Layout-Basiselemente)
- **Top-Menüleiste:**


- **Konferenzraum-Panel:**


- **Agenten-Dashboard (rechts):**


- **Workspace (unten):**
  - Anzeige & Bearbeitung von:
    - Code
    - Subtasks
    - Markdown-Phasenpläne

- **Dateiexplorer (unten rechts):**
  - Baumstruktur der Projektdateien
  - Zugriff auf `task_repository`, `logs`, `execution`



#### Neue Anforderungen
- Jeder Agent erhält eigenes Chat-Fenster (Popup/Dialog)
  - Öffnet sich via "Chat"-Button neben dem Settings-Button
  - Der Button leuchtet, wenn eine direkte Anfrage an den User vorliegt

### 4. Backend-Verschiebung
- **Flask-Module:**
  - `agents_routes.py`
  - `chat_routes.py`
  - `status_routes.py`

- **Frontend-Logik:**
  - Agentenanzeige als dynamisches Grid
  - Konferenzfenster mit echtem Threading
  - Input/Output über Websocket (für spätere Live-Kommunikation)

---
