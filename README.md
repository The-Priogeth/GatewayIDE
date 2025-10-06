## GatewayIDE

### Projektbeschreibung
GatewayIDE ist ein plattformunabhängiges Frontend- und Build-System zur Steuerung eines modularen KI-Gateways. Es basiert auf **Autogen (AG2)**, **FastAPI**, **gRPC** und dem **Zep-Memory-Service**. Das Projekt besteht aus drei Hauptkomponenten:

1. **Avalonia-Desktop-App** – Benutzeroberfläche mit integriertem Terminal und Multi-Tab-System.
2. **Python-Backend** – Verwaltung der KI-Dienste, Prozesssteuerung und gRPC-Kommunikation.
3. **Docker-Compose-Umgebung** – Einheitliche Laufzeitumgebung für Backend, Speicher und optionale Services.


### Features
* **Modernes GUI-Frontend:**
  * Entwickelt mit Avalonia (.NET 8, MVVM-Struktur)
  * Tabs, Terminalausgaben, Prozesssteuerung und Docker-Interaktion in Echtzeit.

* **Interaktiver Chat (manuell steuerbar):**
  * gRPC-Client (AIClientService) zur Kommunikation mit dem Backend.
  * Chatverläufe und Systemlogs werden asynchron in der UI aktualisiert.




#### Voraussetzungen
* **.NET 8 SDK** (für das Avalonia-Frontend)
* **Python ≥ 3.10** mit den Paketen aus `pyproject.toml`
* **Docker Desktop** mit Compose v2



### Windows-Build
Das Script `build-win.bat` erstellt einen self-contained Release-Build in `dist/win-x64`. Beispiel:


### Ausblick
* **CI/CD:** GitHub Actions für Tests, Builds und automatische Releases.
* **Dokumentation:** docs/legacy in neues Wiki-Format überführen.
* **Modularisierung:** Backend in Services für Autogen, Zep und KI-Tasks trennen.


### Lizenz
Bitte füge eine passende Open-Source-Lizenz hinzu (z. B. MIT oder Apache 2.0).
