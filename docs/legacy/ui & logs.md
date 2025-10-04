Workforce Manager – Logging & UI Überblick

1. Architekturüberblick

Die Anwendung besteht aus drei Hauptteilen:

UI (app.pyw)

Erstellt das Tkinter-Fenster

Zwei Log-Ausgabefelder:

Output Box (links, grün): Standard-Logs (z.B. Build-Prozess)

Error Box (rechts, rot): Fehler-Logs und Tracebacks

Buttons:

🔨 Build Image

♻️ Rebuild Image

▶️ Start Container

🔁 Restart Container

⏹ Shutdown Container

🌐 Open UI

📝 Show Logs

Logger (utils/logger.py)

log_to_gui(message): Schreibt in Logdatei und Queue

log_to_error(message): Schreibt in Logdatei (Warning) und direkt ins Error-Feld

poll_log_queue(output_box, window): Holt Nachrichten aus Queue

set_error_output_box(box): Initialisiert das Error-Feld

Docker Control (utils/docker_control.py)

Alle Docker-Befehle:

build_image()

rebuild_image()

start_container()

restart_container()

shutdown_container()

show_logs()

Wenn der Container nicht läuft, wird automatisch show_logs() ausgeführt.

2. Ablauf Container-Erstellung

Beispiel:

Build Image:

docker build ausführen

Zeilen erscheinen live in Output-Box

Start Container:

docker run -d oder docker start

Prüfung:

Läuft Container?

Existiert backend/main.py?

Ist Port 5000 erreichbar?

Falls Container nicht läuft:

Automatisch Logs anzeigen im Error-Feld