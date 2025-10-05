GatewayIDE

GatewayIDE ist ein plattformunabhängiges Frontend und Build‑System zur Steuerung eines KI‑Gateways auf Basis von Autogen (AG2) und Zep‑Memory‑Service. Das Projekt besteht aus einer Avalonia‑Desktop‑App, einem Python‑Backend für den gRPC‑Dienst und einer Docker‑Compose‑Umgebung zur lokalen Ausführung. Dieses Repository bündelt alle Komponenten, damit die Entwicklung und der Betrieb einfacher werden.

Features

Modernes GUI‑Frontend: Die App wurde mit Avalonia umgesetzt und bietet eine saubere MVVM‑Struktur. Im MainWindowViewModel werden diverse UI‑Zustände wie aktive Tabs, die Breite des linken Seitenfensters und Terminal‑Puffer verwaltet
raw.githubusercontent.com
. Über DelegateCommand‑Instanzen werden Benutzeraktionen wie Tab‑Wechsel, Chat‑Senden oder Docker‑Befehle verarbeitet
raw.githubusercontent.com
.

Interaktiver Chat: Ein einfacher gRPC‑Client (AIClientService) sendet Texteingaben an das Backend und gibt die Antworten zurück
raw.githubusercontent.com
. Die Chat‑Verläufe werden in einem StringBuilder gepuffert und asynchron in die UI zurückgeschrieben
raw.githubusercontent.com
.

Terminal & Logging: Für Docker‑ und Prozessausgaben gibt es eigene StringBuilder‑Puffer. Die Methoden HookProcessToBuffers und AttachProcToDockerTerminals koppeln Standard‑Ausgabe und Fehlerausgabe der gestarteten Prozesse an die UI
raw.githubusercontent.com
.

Docker‑Integration: Über den DockerService lassen sich Gateway‑Container aufbauen (StartGateway, StopGateway, BuildNoCache), Logs abrufen und sogar ein kompletter Rebuild durchführen
raw.githubusercontent.com
raw.githubusercontent.com
. Ein zusätzlicher Befehl StartMeganode startet eine optionale Meganode und streamt deren Logs in das Terminal
raw.githubusercontent.com
.

Prozessverwaltung: Der ProcessManager kapselt das Starten externer Prozesse mit korrekter Umleitung der Standard‑Ausgaben
raw.githubusercontent.com
.

Cross‑Platform Build: Für Windows steht ein Batch‑Script zur Verfügung (build-win.bat), das die Anwendung im Release‑Modus baut, ein Self‑Contained‑Executable erstellt und optional eine Verknüpfung im Projektroot erzeugt. Es kann als Vorlage für weitere Plattform‑Builds dienen.

Repository‑Struktur
GatewayIDE/
├── backend/             # Python‑Backend (FastAPI/Autogen/Zep)
├── deploy/              # Docker‑Compose‑Dateien (gateway-compose.yml etc.)
├── protos/              # gRPC‑API‑Definitionen (.proto)
├── services/
│   └── GatewayAI/ai_service  # generierter gRPC‑Client für C#
├── src/
│   └── GatewayIDE.App/  # Avalonia‑Frontend (C#)
│       ├── Services/    # Hilfsdienste (DockerService, ProcessManager etc.)
│       ├── ViewModels/  # MVVM ViewModels (z.B. MainWindowViewModel)
│       ├── App.axaml, MainWindow.axaml  # XAML‑Layouts
│       └── Program.cs   # Einstiegspunkt:contentReference[oaicite:9]{index=9}
├── build-win.bat        # Windows‑Build‑Script
├── GatewayIDE.sln       # Visual‑Studio‑Lösung
├── pyproject.toml       # Python‑Projektmetadata:contentReference[oaicite:10]{index=10}
└── docs/legacy          # Legacy‑Dokumentation (kann später aufgeräumt werden)

Backend (Python)

Im Ordner backend liegt eine FastAPI‑basierte Anwendung, die über gRPC eine Echo‑Funktion (EchoAsync) bereitstellt
raw.githubusercontent.com
. Die pyproject.toml beschreibt das Paket und listet alle Abhängigkeiten auf. Da die Anwendung stark im Fluss ist, lassen wir die Backend‑Struktur vorerst unangetastet. Wichtig ist, dass das Backend per Docker ausgeführt wird und an die gRPC‑Client‑Bibliothek in src/Services/GatewayAI angebunden ist.

Build & Ausführung
Voraussetzungen

.NET 8 SDK für die Avalonia‑App.

Python ≥ 3.10 sowie alle im pyproject.toml definierten Abhängigkeiten
raw.githubusercontent.com
.

Docker Desktop inklusive Docker Compose (Version 2).

Nodejs ist nicht erforderlich; alle Frontend‑Assets sind in C# eingebettet.

Backend starten
# aus dem Projektstammverzeichnis
cd backend
python -m uvicorn main:app --reload

Oder alternativ via Docker:
cd deploy
docker compose -f gateway-compose.yml up -d gateway

Frontend (Avalonia) starten
# aus dem Projektstammverzeichnis
cd src/GatewayIDE.App
# Restore Abhängigkeiten
dotnet restore
# Start im Debug‑Modus
dotnet run

Windows‑Build

Das Script build-win.bat automatisiert den Buildprozess für Windows. Es erstellt einen self‑contained Release‑Build inklusive .exe und legt die Artefakte in den Ordner dist\win-x64 ab. Falls Sie das Zielverzeichnis ändern möchten, passen Sie die Variable OUTDIR im Script an. Eine beispielhafte Anpassung könnte so aussehen:
REM Publish target in a unified dist folder
set "OUTDIR=%~dp0dist\win-x64"

Damit werden Binär‑ und Objektdateien nicht mehr im Repository abgelegt, sondern in einem separaten dist‑Ordner erzeugt.

Aufräumen & .gitignore‑Anpassungen

Um das Repository schlank zu halten, sollten nur benötigte Quellen versioniert werden. Folgende Dateien/Ordner können entfernt oder ignoriert werden:

.vs/ – Visual Studio‑Arbeitsverzeichnis. Wird automatisch generiert.

GatewayIDE-crash.log – Crash‑Logs der IDE; nicht versionieren.

GatewayIDE.lnk – Windows‑Shortcut; wird vom Build‑Script erzeugt.

docs/legacy – Altlasten; können archiviert oder gelöscht werden.

deploy/bin, deploy/obj und andere Build‑Artefakte aus dotnet und python.

Die vorhandene .gitignore enthält bereits viele Regeln. Ergänzen Sie bei Bedarf folgende Einträge, damit nur relevante Dateien eingecheckt werden:
# Eigene Ergänzungen
# Avalonia/AvalonDock Cache
*.axaml.cs.*.cache
# Crash‑Logs
GatewayIDE-crash.log
# Windows‑Shortcuts
*.lnk
# Visual Studio
.vs/
# Legacy‑Dokumentation ausblenden
/docs/legacy/
# Docker‑Artefakte
**/deploy/**/logs/

Damit bleibt der Commit‑Verlauf übersichtlich und die Projektgröße schlank.

Ausblick

CI/CD: Einrichtung eines GitHub‑Actions‑Workflows, der Backend‑Tests ausführt, die C#‑App baut und ein Release erstellt.

Documentation: Das docs/legacy‑Verzeichnis sollte überarbeitet oder durch aktuelle Dokumentation ersetzt werden. Hier kann die README später detailliertere Anleitungen enthalten.

Backend‑Refactoring: Der Python‑Teil könnte modulare Services für Autogen, Speicher (Zep) und gRPC Server enthalten. Dies sollte in einem separaten Task modernisiert werden.

Lizenz

Aktuell liegt keine Lizenzdatei bei. Bitte füge eine passende Open‑Source‑Lizenz hinzu, z. B. MIT oder Apache 2.0.