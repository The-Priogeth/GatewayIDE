# GatewayIDE – Projektstatus (08.11.2025)

> **Konsolidierungsstatus:** aktiv  
> **Herkunft:** Ursprüngliche Datei `GatewayIDE.txt` (Status-Snapshot & Vision)  
> **Zweck:** Archivierter, aber fortschreibbarer Projektstatus mit vollständigem Kontext, ohne Kürzungen.  
> **Pfad:** `docs/status/GatewayIDE_2025-11-08.md`

---

## 🧭 1) Zweck & Rolle im Gesamtsystem

* **Mission Control der Innenwelt**: sicht- und steuerbare Orchestrierung **deiner** SoM-/HMA-Architektur (T1–T6), inkl. Dialog, Planung, Speicher, Tasks.  
* **Entwicklungs-Cockpit**: Logs, Terminals, Docker-Kontrolle, Build/Run-Pfade.  
* **Basis für Erweiterungen**: spätere Module (Education/Exodus, Mini-Games/Tamagotchi, Blockchain-Megaknoten, UE-Anbindungen).

---

## ⚙️ 2) Architektur (heutiger Stand)

* **Frontend**: Avalonia (.NET 8, Windows-Ziel). Mehrere Tabs/Ansichten (Dashboard, KI-System, Docker, Projekt, Blockchain).  
* **Backend**: Python 3.11 + FastAPI + WebSocket-Kanäle (HMA/SOM-Prozess, Router, Speaker, Demo-Agents).  
* **Kommunikation**: HTTP/WS; gRPC war/ist erwogen.  
* **Speicher/Memories**: Zep Graph Memory (bekannte Limitierung: Persist-Fehler bei > 2 500 Zeichen pro Nachricht).  
* **Build/Repo**: .sln-Struktur, App-Projekt (Avalonia), Backend-Ordner (agent_core, routes, main, etc.).  
* **Docker-Compose** für Backend.

---

## 🧩 3) UI/UX-Status

**Tabs & Layout:**
- **Dashboard**: Systemstatus/Überblick (rudimentär).  
- **KI-System**: Chat-Surface + Visualisierung interner Stränge (teils noch textuell/logzeilenbasiert).  
- **Docker**: Start/Stop, Log-Einsicht, zwei Fenster/Pane-Bereiche.  
- **Projekt**: erste Dateiansichten/Platzhalter für spätere App-Creation-Flows.  
- **Blockchain**: UI-Skelett für Mega-Node-Steuerung.

**Behobene Bugs:**
- UI-Layout-Sprung: gefixt.  
- Expand/Collapse-Buttons: gefixt.

**Bekannte UI-Stellen mit Historie:**
- Grid/Bindings (Top-/Bottom-Pane, Row/Col-Heights).  
- Sichtbarkeits-Kopplung zwischen Tabs (früher: Docker-Pane schob anderes Layout).

---

## 🧠 4) Agenten / HMA / SoM

* **Leitidee:** Society-of-Mind mit HMA (Haupt-Meta-Agent) als „Ich-Stimme“ (SOM-Core), die plant & finalisiert.  
* **Threads T1–T6:**  
  - **T1** Dialog (User-Kanal)  
  - **T2** Innere Stimme / parallele Demos  
  - **T3** Meta-Entscheidung / Router / Speaker  
  - **T4** Librarian (Abruf, Einordnung, Wissensspeicher)  
  - **T5** TaskManager (Routing zu Funktionskanälen)  
  - **T6** Trainer/Verbesserung  
* **Router:** wählt Demo-Agents (Critic, Programmer, Strategist …) je Kontext.  
* **Speaker:** formt finalen Output + `deliver_to` (user | task | lib | trn).  
* **Konfig-Bausteine:** `HMAConfig` (System-Prompt, Templates für Plan/Final, Capabilities, max_parallel_targets).

---

## 🧰 5) Backend-Status

* **FastAPI Uvicorn-Stack** läuft; Logs zeigen sauberen Startup + Watcher für Codepfade.  
* **WebSocket-Route** für Live-Events/Logs aktiv.  

**Problemhistorik:**
- Exceptions (h11_impl / Starlette/ASGI Tracebacks) traten in Vorversionen auf.  
- **Zep Persist:** `400 bad request: message content exceeds 2500 characters` → weiterhin relevant.  
- **Namensauflösung:** Fall „Du heißt T1_ROOT Channel“ (UI korrekt, KI-System-Tab teils inkonsistent).  
- **Using/Namespace-Fehler** (`AIClientService`-Referenzen) beim App-Build.

---

## 📜 6) Logs & Terminals

* **Docker-Log-Anzeige:** zwei getrennte Fenster/Pane, Live-Feed.  
* **In-App-Terminal-Feeling:** vorgesehen; heute v. a. Logviews + Buttons (Start/Stop/Build).  
* **Watcher:** Backend meldete „Watcher gestartet“ (Verzeichnis-Überwachung).

---

## 🧹 7) Code-Gesundheit & Refactoring

* **Ziel:** ~ 30 % Code-Volumen bei gleicher Wirkung (Entfernung redundanter Logik, Fallbacks).  
* **Status:** begonnen; Nebenwirkung: vieles verschwunden/kaputt (bekannt, wird bewusst neu geordnet).  

**Hotspots:**
- Doppelte Logik (Router/HMA in mehreren Schichten).  
- UI-Bindings (GridLength ↔ String).  
- Commands ohne Hook im ViewModel.  
- Unklare Sichtbarkeitssteuerung zwischen Tabs.

---

## ✅ 8) Qualitätsmerkmale / Definition of Ready

- **Stabile UI-Pane-Logik** (kein Durchschlagen zwischen Tabs).  
- **Eindeutige Zuständigkeiten** (Router ≠ Speaker ≠ TaskManager).  
- **Sichere Memory-Schnittstellen** (Chunking, Längenbegrenzung, saubere Persistenz).  
- **Fehlerarme Build-Pipelines** (.csproj-Referenzen, Namespaces, Restore → Build → Run).  
- **Observability** (einheitliche Log-Formate, Prefix je Thread T1–T6).

---

## 🌍 Vision – Entwicklungsperspektiven

### 1) Kurzfristig: Innenwelt-Reife
- **Transparente SoM-Visualisierung:** T1–T6 als Streams (Plan → Entscheidung → Output).  
- **Task-Flows:** Klar trennbar (user/task/lib/trn) mit auditierbaren Spuren (wer hat was entschieden, auf Basis welcher Kontexte).  
- **Robuste Speicheranbindung:** Chunking, Summarizer, Limits im UI sichtbar.  
- **Sauberes Code-Skelett:** minimal, erweiterbar, testbar.

### 2) Mittelfrist: Ökosystem-Andockpunkte
- **Projekt-Tab:** Creation-Hub (Boilerplates, Mini-Games, Skript-Templates).  
- **Blockchain-Tab:** Mega-Node-Start, Monitoring, Statusmetriken, eventuelle Backpressure-Signale ins HMA.  
- **Wissensflächen:** Librarian-Ansicht (Quellen, Snippets, Zep-Graph-Ausschnitte), kuratierte Memory-Einspeisung.

### 3) Langfrist: Gesamtvision
- **Exodus-Integration:** Lernwelten, globale Identität (Zugangs-/Rechte-Layer).  
- **S.A.A.I.-Pfad:** Simulation & Training mit UE-Anbindung, Echtzeit-Signale zwischen Engine und HMA-Threads.  
- **Welt-Konsole:** IDE als Leitstand für Bildung/Ökonomie/Kommunikation im GSE-Konzept — mit klarer Trennung von Innenwelt (Denken/Planen) und Außenwelt (Liefern/Wirken).

---

## 🧷 Offene Punkte (Loose Ends)

- **Persist-Strategie** für lange Nachrichten (Zep-Limits → Chunking/Summarize-Pfade).  
- **Namensraum/Referenzen** in der App (`AIClientService` etc.).  
- **Thread-Transparenz** im UI (Filter, Timeline, Zustandswechsel).  
- **Sichtbarkeit/State-Management** (Tabs beeinflussen sich nicht).  
- **Minimal-Core nach Refactoring** (stabile Baseline vor Erweiterungen).

---

## 🧩 TL;DR

**GatewayIDE** ist der **Innenwelt-Leitstand**: Denken, Planen, Orchestrieren, Beobachten.  
**Aktueller Stand:** UI-Kern funktioniert; kritische Bugs (Layout/Expand) behoben; Refactoring auf 30 % läuft, hat aber Substanz entfernt → geplanter Neuaufbau/Sortierung.  
**Vision:** SoM-Transparenz, robuste Speicher-/Task-Pipelines, anschließende Erweiterungen (Projekt-Creation, Mega-Node, Exodus, S.A.A.I.).

---

> _Hinweis: Ursprünglich als Stand-Dokument vorgesehen; Erweiterung um Checklisten ist möglich._  
> _Nächste geplante Versionierung: nach Abschluss der Agent-HQ-Integration._
