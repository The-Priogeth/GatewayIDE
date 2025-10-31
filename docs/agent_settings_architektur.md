Im Zuge der Weiterentwicklung des agentenbasierten Frameworks wird eine moderne, webbasierte Konfigurationslogik für Agentenprofile eingeführt. Ziel ist es, die bislang in Tkinter realisierten Konfigurationsansichten in eine strukturierte, skalierbare und frontendkompatible Form zu überführen, ohne jedoch die Logik vergangener Prototypen direkt zu übernehmen. Vielmehr dienen diese als heuristische Grundlage für die semantische und funktionale Gruppierung der Konfigurationselemente.

Jeder Agent im System erhält eine eigene JSON-basierte Konfigurationsdatei, die zentral unter `stored_agents.json` oder als Einzeldokument gespeichert wird. Die Kernstruktur dieser Agentenprofile umfasst neben Basisfeldern wie Name, Typ und Beschreibung auch LLM-spezifische Einstellungen (z. B. Modellwahl, Prompt, Temperatur), Interaktionsverhalten (Input-Modus, Antwortgrenzen), optionale Codeausführungsparameter (Docker, Timeout) sowie Terminierungsregeln. Ein dediziertes Schema in `agent_schema.json` definiert Typen, Pflichtfelder, Standardwerte und die zugehörige UI-Komponente (Input, Dropdown, Checkbox etc.).

Die Modellwahl wird über `model_defaults.json` gesteuert, welches alle gängigen Modellnamen (z. B. gpt-3.5-turbo, gpt-4-1106-preview, whisper-1 etc.) samt zugehöriger Parameter (z. B. Tokenlimit, Temperaturbereich, API-Spezifikationen) zentral verwaltet. Dadurch lässt sich die Dropdown-Auswahl im UI automatisch generieren und validieren.

Frontendseitig wird das Agenten-Dashboard um einen "Settings"-Button erweitert. Dieser öffnet ein modales Fenster mit Tabs für verschiedene Konfigurationsgruppen: Grundlagen, LLM, Verhalten, Codeausführung, Erweitert. Die Formularfelder orientieren sich an der Schema-Definition. Die Speicherung erfolgt entweder automatisch bei jeder Eingabe oder manuell über einen „Speichern“-Button mit Bestätigungsfeedback.

Die API-Endpunkte sind minimal gehalten:
- `GET /api/agents/settings/<name>` liefert die gespeicherte Agentenkonfiguration oder fällt auf das Schema zurück.
- `POST /api/agents/settings/<name>` speichert die übermittelte Konfiguration und validiert sie gegen das Schema.

Perspektivisch kann diese Architektur um Funktionen wie Preset-Auswahl, Schema-basierte Validierung im Frontend, Undo-Stacks oder Live-Vorschau erweitert werden. Entscheidend ist, dass sie die Übergabe an die „agent_core“-Module sauber abbildet und die Personalisierung sowie das Debugging einzelner Agenten erheblich erleichtert. Die Übergangslogik zwischen Settings-UI, Konferenzlogik und aktiver Agentenausführung bildet damit einen elementaren Baustein des geplanten Produktionssystems.

