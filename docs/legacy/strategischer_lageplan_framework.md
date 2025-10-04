## Strategischer Lageplan: Agentenbasiertes Entwicklungsframework

### 0. Einleitung – Zielsetzung & Übersicht
In zunehmend komplexen Entwicklungsumgebungen braucht es strukturierte, skalierbare und nachvollziehbare Prozesse, um den gesamten Lebenszyklus eines Projekts von der Idee bis zur Umsetzung effizient zu steuern. Dieses Dokument beschreibt ein agentenbasiertes Framework zur Projektentwicklung, das die Arbeit in klar abgegrenzte Phasen aufteilt und jeder Phase dedizierte Rollen mit spezifischen Aufgaben zuweist.

Im Mittelpunkt steht ein KI-gestütztes Konferenzsystem, das über spezialisierte Agenten interagiert, Informationen verarbeitet, Rückfragen stellt und in iterativen Schleifen konsensbasierte Entscheidungen trifft. Von der Anforderungserhebung über technische Spezifikation, Subtask-Zerlegung bis zur Ausführung sind alle Schritte modular strukturiert. 

Ziel des Frameworks ist es, sowohl menschliche wie maschinelle Teilnehmer:innen in einem konsistenten Ablauf zu vereinen – mit eindeutigen Schnittstellen, standardisierten Rollenprofilen und adaptiven Kommunikationsstrukturen.

---

### 1. Konfigurations- & Systemgrundlagen
Der technische Unterbau dieses Frameworks basiert auf einer modularen und deklarativ steuerbaren Architektur, die vollständig auf agentenbasierten Abläufen beruht. Zentrales Element ist die Initialisierung über eine globale Konfigurationsdatei, welche mittels der Funktion `config_list_from_json` geladen wird. Diese Konfiguration definiert sowohl die beteiligten Agenten als auch deren Kommunikationsparameter.

Für die interne Kommunikation wird ein `GroupChat`-Objekt verwendet, das in Kombination mit einem `GroupChatManager` die gesamte Gesprächs- und Interaktionslogik zwischen den Agenten koordiniert. Die Kommunikation erfolgt dabei synchron oder asynchron, gestützt durch systematische Nachrichtenzustände, automatische Antwortgrenzen sowie Rückfragenlogik.

Das System unterscheidet verschiedene Agententypen mit klaren Zuständigkeiten: Der `ProjectManager` orchestriert den gesamten Ablauf, der `UserProxyAgent` übernimmt die Schnittstelle zur Nutzerinteraktion, während `TaskAgents` für die Bearbeitung einzelner Aufgaben zuständig sind. Ein `Mediator` sorgt zusätzlich für Konsensbildung und Konfliktlösung im Entscheidungsprozess.

Gesteuert wird der Gesamtprozess über eine zentrale Instanz namens `ConferenceRoom`. Diese ruft unter anderem Methoden wie `start_conference`, `check_consensus` oder `ask_for_task_and_initialize_conference` auf, um den Ablauf zu starten, iterativ zu steuern und – wenn nötig – Feedback vom Benutzer einzuholen.

Zusätzlich stehen allen Agenten zahlreiche Methoden zur Verfügung, um Aufgaben zu übernehmen, Nachrichten zu verarbeiten, Konversationen zu archivieren oder Code auszuführen. Diese Vielseitigkeit erlaubt eine feingranulare Prozesssteuerung und eine transparente Protokollierung aller relevanten Interaktionen.


---

### Anhang A – Wichtige Methoden für Agenteninteraktion
Für die systeminterne Steuerung stehen den Agenten eine Vielzahl an Methoden zur Verfügung. Diese bilden die Grundlage für Kommunikation, Aufgabenbearbeitung, Interaktion mit Menschen und technische Kontexteingriffe. Der folgende Überblick fasst die wichtigsten Methoden in tabellarischer Form:

| Methode | Funktion |
|--------|----------|
| `send`, `receive` | Nachrichten an andere Agenten senden / empfangen |
| `generate_reply`, `generate_oai_reply` | Antworten basierend auf Konversation oder OAI generieren |
| `run_code`, `execute_code_blocks` | Code bzw. mehrere Codeblöcke ausführen |
| `get_human_input`, `a_get_human_input` | Menschliche Eingaben synchron oder asynchron einholen |
| `register_reply` | Dynamisches Reaktionsverhalten definieren (z. B. Trigger, Rollen) |
| `clear_history`, `reset` | Kontext bzw. Agentenzustand vollständig zurücksetzen |
| `can_execute_function`, `function_map` | Prüfen oder darstellen, welche Funktionen verfügbar sind |
| `update_max_consecutive_auto_reply` | Antwortzyklen für bestimmte Sender begrenzen |

Diese Methodentabelle kann später direkt für API-Dokumentation, Systemmonitoring oder UI-Debugging genutzt werden.
---

### 2. Development Plan Team – Strategische Planung
Die Arbeit des Development Plan Teams bildet das strategische Fundament des gesamten Entwicklungsprozesses. Ziel dieser Phase ist es, aus einer meist vagen Projektidee eine präzise und technisch anschlussfähige Beschreibung abzuleiten. Der Prozess beginnt mit der Erfassung eines Ausgangstasks durch die NLP-Schnittstelle „Leona“, welche in der Rolle einer dialogorientierten Benutzeroberfläche Rückfragen stellt, Vorschläge sammelt und die Kontexteingabe formalisiert.

In enger Abstimmung mit der Benutzerseite wird daraufhin ein strukturierter Anforderungskatalog erstellt, den der Project Manager in ein erstes Entwicklungsgerüst übersetzt. Dabei werden technische Aspekte geprüft, erste Lösungsansätze skizziert und innovative Perspektiven durch spezialisierte Rollen wie den „Innovator“ eingebracht.

Ein zentrales Element dieser Phase ist die Risikoabschätzung durch den Risk Assessor, der Schwachstellen, Zielkonflikte und externe Abhängigkeiten identifiziert. Parallel prüft der Requirements Analyst die Konsistenz der Anforderungen, hinterfragt gegebenenfalls Formulierungen und sucht über Web-Schnittstellen ergänzende Informationen.

Sämtliche Bewertungen, Vorschläge und Einschätzungen werden in iterativen Schleifen gebündelt, durch einen Mediator moderiert und schließlich in einen abgestimmten Plan überführt. Dieser Plan wird in dokumentierte Phasen überführt und dient als Übergabepunkt für das nachfolgende Development Phase Team.

**Phasen:**
1. Task-Erfassung durch NLP-Schnittstelle (Leona)
2. Anforderungspräzisierung mit User
3. Initialplan durch Project Manager
4. Technikprüfung (Tech-Rolle)
5. Innovationseinwurf
6. Abgleich mit Anforderungen (Requirements Analyst)
7. Risikoabschätzung (Risk Assessor)
8. Planverfeinerung (PM + Mediator)
9. Phasenbildung & Dokumentation


Während der Ablauf formal linear strukturiert ist, können bestimmte Arbeitsschritte – etwa technische Analyse und Innovationsbeiträge – auch parallel durchgeführt werden. Diese parallele Interaktion erhöht die Effizienz, ohne die klare Struktur der späteren Zusammenführung zu gefährden.

**Rollen:** Requirements Analyst, Architect, Risk Assessor** Requirements Analyst, Architect, Risk Assessor

---

### 3. Development Phase Team – Technische Dekomposition
Das Development Phase Team übernimmt die Übergabe aus der strategischen Planungsphase und überführt sie in eine detaillierte technische Architektur. Ziel dieser Phase ist es, aus dem vorliegenden Entwicklungsplan konkrete technische Strukturen, Abläufe und Abhängigkeiten abzuleiten. Zu Beginn sichtet der zuständige Projektmanager die eingegangenen Phasenpläne, verteilt diese an die jeweiligen Expert:innen und stellt sicher, dass das Team einen gemeinsamen Überblick über Umfang und Zielsetzung hat.

Der Systems Designer entwickelt daraufhin eine konzeptionelle Systemarchitektur, in der Module, Schnittstellen und technische Abhängigkeiten klar beschrieben sind. In parallel geführten Teilprozessen können – je nach Projektanforderung – zusätzlich ein UI/UX-Design und eine Datenbankstruktur entwickelt werden. Diese Designanteile werden mit Skizzen, Diagrammen und Tabellen formalisiert und fließen in die Gesamtdokumentation ein.

Der File Manager erstellt auf dieser Grundlage eine konkrete Datei- und Ordnerstruktur inklusive Namenskonventionen, während der Function Manager die enthaltenen Funktionen identifiziert, benennt und mit semantischer Beschreibung versieht. Es folgt eine detaillierte Analyse der internen Abhängigkeiten: Der Connector dokumentiert die Verknüpfungen zwischen Funktionen, Modulen und ggf. externen APIs oder Bibliotheken.

Abschließend sorgt der Integration Specialist für die Konsolidierung aller Entwürfe zu einem konsistenten und funktionsfähigen Gesamtbild, das dann durch den Documentation Specialist umfassend verschriftlicht wird. Dabei entsteht ein strukturierter Output aus Phasenplänen, Diagrammen, Schnittstellenbeschreibungen und technischen Richtlinien, der die Grundlage für die nachfolgende Subtask-Phase bildet.

**Schritte:**
1. Phase-Empfang & Verteilung
2. Systemdesign
3. UI/UX-Design (optional)
4. Datenbankschema (optional)
5. Dateistruktur & Namenskonventionen
6. Funktionsidentifikation
7. Abhängigkeitsanalyse
8. Integrationscheck
9. Technische Dokumentation

**Rollen:** Systems Designer, UI/UX Expert, Database Expert, File Manager, Function Manager, Connector, Integration Specialist, QualityAssuranceSpecialist** Systems Designer, UI/UX Expert, Database Expert, File Manager, Function Manager, Connector, Integration Specialist, QualityAssuranceSpecialist

---

### 4. Subtask Team – Feinkörnige Aufgabenzerlegung
Sobald die technischen Entwicklungsphasen spezifiziert vorliegen, übernimmt das Subtask Team die Aufbereitung in klar definierte, operative Arbeitseinheiten. Ziel ist es, die Phase in kleinste sinnvolle Aufgaben (Subtasks) zu zerlegen, die jeweils in kurzer Zeit – idealerweise innerhalb eines Tages – abgeschlossen werden können.

Der Subtask Supervisor eröffnet den Prozess mit einer kontextuellen Einweisung für das Team. Anschließend beginnt der Task Identifier mit der systematischen Aufschlüsselung der Entwicklungsphasen in logische Einzelaufgaben. Diese werden durch den Task Describer mit verständlichen, praxisnahen Beschreibungen versehen, sodass eine spätere Ausführung auch ohne tiefere Rückfragen möglich ist.

In einem weiteren Schritt analysiert der Task Sequencer Abhängigkeiten zwischen den Subtasks und stellt sicher, dass notwendige Reihenfolgen korrekt dokumentiert werden. Parallel dazu übernimmt der Resource Allocator die Zuordnung von benötigten Werkzeugen, Technologien oder Expertisen. Dadurch wird bereits frühzeitig sichergestellt, dass alle erforderlichen Voraussetzungen bekannt sind.

Besonderes Augenmerk liegt in dieser Phase auf der Risikoanalyse auf Mikroebene: Der Risk Forecaster identifiziert potenzielle Fallstricke pro Subtask, beschreibt Herausforderungen und schlägt präventive Maßnahmen vor. Abschließend prüft der Subtask Validator die Qualität, Konsistenz und Umsetzbarkeit der erstellten Subtasks. Bei Bedarf wird in die vorherigen Rollen zurückgeschleift, um Korrekturen vorzunehmen.

Erst nach dieser Validierung erfolgt die Übergabe an den Documentation Specialist, der sämtliche Ergebnisse systematisch verschriftlicht. Das Resultat ist ein vollständiger, sauber dokumentierter Subtask-Katalog, der als unmittelbare Arbeitsgrundlage für das Execution Team dient.

Der gesamte Prozess ist rückkopplungsfähig aufgebaut – jeder Schritt kann im Bedarfsfall erneut durchlaufen werden, um Unklarheiten, Überschneidungen oder Abweichungen frühzeitig zu korrigieren.

**Schritte:**
1. Einführung & Kontextverständnis
2. Zerlegung in logische Einheiten
3. Beschreibung der Subtasks
4. Abhängigkeits- und Sequenzplanung
5. Tool- und Ressourcen-Zuordnung
6. Risiko- und Hürdenabschätzung
7. Validierung & Rückkopplung
8. Dokumentation

**Rollen:** Subtask Supervisor, Task Identifier, Task Describer, Task Sequencer, Resource Allocator, Risk Forecaster, Subtask Validator, Documentation Specialist2

---

### 5. Execution Team – Umsetzung & Testing
Nachdem die einzelnen Aufgaben klar strukturiert und dokumentiert sind, übernimmt das Execution Team die operative Umsetzung. Diese Phase ist maßgeblich für die tatsächliche Realisierung des Produkts und erfordert ein hohes Maß an Präzision, Testabdeckung und Koordination.

Zu Beginn sichtet der Execution Supervisor die übergebenen Subtasks, prüft ihre Ausführbarkeit und verteilt sie an spezialisierte Mitglieder des Teams. Der Task Executor beginnt mit der eigentlichen Umsetzung der beschriebenen Aufgaben – entweder in Form von Code, Konfiguration oder anderen operativen Elementen.

Um sicherzustellen, dass alle technischen Abhängigkeiten korrekt integriert sind, überwacht der Dependency Manager die Einbindung externer Libraries, Datenzugriffe und Schnittstellen. Nach Abschluss der Erstimplementierung folgen erste Tests: Der Preliminary Tester identifiziert funktionale Probleme oder Fehlverhalten direkt nach Fertigstellung eines Subtasks.

Wenn Probleme erkannt werden, greift der Refinement Expert gezielt ein, überarbeitet kritische Stellen und verbessert Struktur oder Funktionalität. Danach erfolgt der Integrationstest, bei dem das neu geschaffene Modul im Gesamtsystem getestet wird. Der Integration Tester prüft dabei Kompatibilität, Stabilität und Systemverhalten im Verbund.

Optional wird ein User Acceptance Test durchgeführt, um sicherzustellen, dass das Ergebnis den Nutzeranforderungen entspricht. Erkenntnisse daraus fließen in eine finale Überarbeitung ein. Abschließend übernehmen der Code Commenter und der Documentation Specialist3 die Aufgabe, den Code verständlich zu kommentieren, alle Schritte zu dokumentieren und gegebenenfalls begleitende Nutzer- oder Entwicklerdokumentationen zu erstellen.

**Schritte:**
1. Subtask-Empfang & Verteilung
2. Codierung / Task-Durchführung
3. Abhängigkeitsmanagement
4. Vorabtests
5. Fehleranalyse & Korrektur
6. Integrationstest
7. UAT (User Acceptance Test)
8. Finalisierung
9. Code-Kommentierung & Dokumentation

**Rollen:** Execution Supervisor, Task Executor, Dependency Manager, Preliminary Tester, Refinement Expert, Integration Tester, UAT Tester, Documentation Specialist3

---

### 6. Kommunikation & Iteration (Konferenzstruktur)
Der reibungslose Ablauf zwischen den Teams und Phasen wird durch eine zentral organisierte Kommunikations- und Iterationsstruktur gewährleistet, die auf dem Prinzip eines digitalen Konferenzraums basiert. Im Zentrum steht ein kontinuierlicher Austausch zwischen spezialisierten Agenten, Nutzer:innen und – perspektivisch – einer UI-gestützten Darstellung dieser Konferenzen in Echtzeit.

Das Grundprinzip dieser Konferenzstruktur ist der sogenannte „GroupChat“ – eine gemeinsame Kommunikationsinstanz, in der alle beteiligten Rollen (z. B. TaskAgents, ProjectManager, Mediator, UserProxy) synchronisiert zusammenarbeiten. Jeder Task oder Themenbereich erhält dabei eine eigene Threadstruktur, um kontextuelles Durcheinander zu vermeiden. Neben Threading erlaubt das System Priorisierungen, Markierungen und Archivierung.

Nach Eingabe eines Tasks durch den User (über UI oder Spracheingabe) startet eine Initialrunde, in der alle zuständigen Agenten ihren ersten Input liefern. Falls externe Informationen notwendig sind, erfolgt in dieser Phase auch eine koordinierte Websuche durch speziell konfigurierte Agenten mit Suchberechtigung. Diese liefern kontextreiche Erweiterungen, die wiederum in eine erste Konsensrunde münden.

Darauf folgen mehrere iterative Feedback-Schleifen, in denen Erkenntnisse integriert, Hypothesen geprüft und Vorschläge angepasst werden. Jeder Iterationszyklus endet mit einem Meilenstein-Checkpoint, an dem entschieden wird, ob:
- der aktuelle Erkenntnisstand ausreicht,
- eine weitere Iteration notwendig ist oder
- die Übergabe an das nächste Team erfolgen kann.

Integriert ist auch ein expliziter User-Feedback-Zyklus. Zu definierten Punkten – z. B. nach einer Iteration oder einem Meilenstein – wird gezielt Feedback der Nutzer:innen eingeholt. Dies stellt sicher, dass technische Ausarbeitungen auf realen Anforderungen und Erwartungen basieren.

Am Ende eines jeden Konferenzzyklus steht die Finalisierung: Der Mediator sammelt Ergebnisse, überprüft Konsens oder fordert eine Nutzerentscheidung ein. Anschließend wird ein strukturierter Übergabebrief für das Folgeteam erstellt – inklusive Entscheidungskontext, offener Fragen und verlinkter Informationshistorie.

Diese Architektur ist nicht nur funktional, sondern bildet auch die Grundlage für eine zukünftige UI-Komponente. Diese könnte sämtliche Konferenzaktivitäten visuell abbilden: mit Threads, Rollenübersicht, Interaktionslogs und Entscheidungspunkten. Ziel ist ein Interface, das sowohl Debugging als auch Echtzeitverfolgung für Menschen erlaubt – als Brücke zwischen KI und menschlicher Steuerung.


**Offene Systemfrage:**
Wie kann verhindert werden, dass sich Wiederholungsschleifen endlos ausweiten – gerade dann, wenn sie ab einem bestimmten Punkt keinen zusätzlichen Erkenntnisgewinn mehr liefern? 

**Temporäre Lösung:** Für jede Konferenzinstanz kann eine maximale Anzahl zulässiger Iterationen festgelegt werden (z. B. 3–5 Runden pro Aufgabe). Diese Grenze kann manuell konfiguriert oder adaptiv durch den Mediator überwacht werden, um eine Balance zwischen Tiefe und Effizienz zu gewährleisten.
- Zentrales Brainstorming-Forum
- Initialrunde & Verstehen
- Websuche & externe Integration
- Iterative Schleifen mit Meilensteinprüfungen
- Userfeedback einholen
- Konsolidierung aller Daten
- Briefing für Übergabe an nächstes Team

---

### 7. Rollenprofil-Katalog (für Matching & Agentenerstellung)
Die differenzierte Beschreibung der beteiligten Rollen ist ein zentraler Baustein dieses Frameworks, denn sie ermöglicht sowohl menschliches Verständnis als auch eine maschinelle Abbildung in KI-Systemen. Jede Rolle ist so formuliert, dass sie eindeutige Zuständigkeiten, charakterliche Merkmale und technisches Wissen umfasst. Diese Struktur schafft die Grundlage für automatische Rollenzuweisung, Agentensimulation oder Matchingprozesse in Multi-Agentensystemen.

In der strategischen Planungsphase (Development Plan) finden sich Rollen wie der Requirements Analyst – analytisch, geduldig, detailverliebt – mit Erfahrung in Nutzerzentrierung und Anforderungserhebung. Ergänzt wird dieses Profil durch den Architect (strategisch, visionär) mit Kenntnissen in Architekturmustern und Systemdenken, sowie durch den Risk Assessor, der Risiken vorausschauend identifiziert und Maßnahmen vorschlägt.

Im technischen Design (Development Phase) dominieren Rollen wie der Systems Designer (strukturiert, kreativ), der UI/UX Expert (empathisch, benutzerzentriert), der Database Expert (logisch, datengetrieben) und der Integration Specialist (adaptiv, kooperationsstark). Sie tragen die Verantwortung für die Umsetzung technischer Standards, die Strukturierung des Daten- und Anwendungsraums sowie die Entwicklung integrationsfähiger Module.

In der Subtask-Phase rücken operative Rollen in den Vordergrund: etwa der Module Lead mit tiefem Fachwissen und Führungsstärke, der QA Expert mit hoher Genauigkeit und systematischem Vorgehen oder der Documentation Specialist, dessen Fokus auf Nachvollziehbarkeit und exakter Dokumentation liegt.

Im Execution Team treten präzise Rollen wie der Code Generator (schnell, robust, effizient), der Integration Tester (geduldig, technologieaffin), der Unit Tester (systematisch, detailorientiert) und der Deployment Specialist (methodisch, lösungsorientiert) auf. Ihre kombinierte Aufgabe ist die Realisierung, Prüfung und produktive Bereitstellung des geplanten Systems.

Die Rollenprofile sind durch folgende Struktur gegliedert:
- **Zuständigkeit:** Was ist der konkrete Aufgabenbereich dieser Rolle?
- **Persönlichkeitsmerkmale:** Welche Charakterzüge unterstützen die Erfüllung dieser Rolle?
- **Fachliche Vorkenntnisse:** Welches Wissen, welche Erfahrung ist für die Rolle erforderlich?

Dieser Katalog kann als UI-Komponente modular eingebunden werden – z. B. zur Konfiguration eines Agentensystems, zur Schulung oder als dynamischer Auswahlmechanismus für Rollenzuweisung auf Basis verfügbarer Kompetenzen oder Präferenzen.

---

### 8. Adaptive Suchstrategie & Lernlogik
Damit ein agentenbasiertes System nicht blind auf externe Informationsquellen zugreift, sondern diese selektiv, verantwortungsvoll und effizient nutzt, wurde eine abgestufte Such- und Lernlogik integriert. Diese ist sowohl für die Autonomie der Agenten als auch für die spätere Nutzerkontrolle über die UI von zentraler Bedeutung.

Ein erster Mechanismus ist die interne Selbsteinschätzung der Agenten: Bevor ein Websearch ausgelöst wird, prüfen sie anhand eines konfigurierbaren Schwellenwerts ("confidence level"), wie sicher ihre interne Wissensbasis die gestellte Aufgabe abdecken kann. Liegt der Wert über dem Grenzwert, unterbleibt eine Suche. Ergänzend können globale Limits wie "maximal 3 Suchanfragen pro Stunde" gesetzt werden, um Spam oder kostspielige Operationen zu verhindern.

Darüber hinaus folgt die Problembehandlung einer abgestuften Hierarchie:
1. Nutzung interner Wissensbasis
2. Kollaboration mit anderen Agenten (Erfahrungsabgleich)
3. Erst wenn diese Optionen ausgeschöpft sind: gezielte Websuche

Auch die Suchergebnisse selbst werden nicht ungeprüft übernommen. Agenten evaluieren Relevanz und Informationsdichte, um Redundanzen zu vermeiden. Erfolgslose Suchversuche werden registriert und dienen zur Verbesserung künftiger Suchentscheidungen.

Ein zusätzlicher Layer ist die explizite Nutzerinteraktion: Vor allem in frühen Projektphasen oder bei sensiblen Aufgaben kann der Agent die Nutzer:innen fragen: „Ich erwäge, dazu online Informationen zu suchen. Ist das in Ordnung?“ Dieses Verhalten schafft Vertrauen, Transparenz und fördert Verantwortlichkeit.

Schließlich fließt jede Suchaktion in eine langfristige Lernstrategie ein: Wenn bestimmte Suchmuster regelmäßig verwertbare Ergebnisse liefern, werden sie bevorzugt. Fruchtlose Anfragen hingegen werden künftig zurückgestellt. Ziel ist ein System, das nicht nur handelt, sondern aus seiner Suchhistorie lernt – für maximale Effizienz und minimale Ablenkung.

import os

def default_agent_config(name: str):
return {
"name": name,
"class_name": "ConversableAgent",
"agent_type": "assistant",
"status": "idle",
"description": "Autogen-kompatibler Agent.",
"system_message": "You are a helpful assistant.",
"human_input_mode": "TERMINATE",
"max_consecutive_auto_reply": 3,
"default_auto_reply": "Bitte präzisieren Sie Ihre Anfrage.",
"is_termination_msg": "None",
"llm_config": {
"model": "gpt-3.5-turbo",
"temperature": 0.7,
"max_tokens": 2048,
"timeout": 60,
"config_list": [
{
"api_key": "{{global}}",
"base_url": "",
"api_type": "",
"api_version": ""
}
]
},
"code_execution_config": {
"use_docker": True,
"timeout": 30,
"work_dir": "",
"filename": "",
"lang": "python"
}
}

def get_agent_config_path(name: str):
return os.path.join("config", "agents", f"{name}.json")