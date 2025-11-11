Memory Module – GatewayIDE Backend

Dieses Modul bildet die Speicher-Abstraktion des GatewayIDE-Backends.
Es vereint Thread- (Zep Threads) und Graph-Speicher (Zep Graph API) zu einer konsistenten, erweiterbaren Architektur.


📁 graph_utils.py
Hilfsfunktionen zur konsistenten Erstellung von Edge-Payloads für die Zep-Graph-APIs.

API
build_edge_payload(head_uuid, relation, tail_uuid, *, fact=None, attributes=None, rating=None, valid_at=None, invalid_at=None, expired_at=None) -> Dict[str, Any>

Erzeugt ein standardisiertes Kanten-Payload für graph.add_edge.

Pflichtparameter

head_uuid: Quellknoten-UUID

relation: Beziehungsname / Prädikat

tail_uuid: Zielknoten-UUID

Optionale Felder

fact: Freitext / Begründung zur Kante

attributes: Zusatzattribute (dict)

rating: Gewichtung / Score

valid_at, invalid_at, expired_at: Zeitfenster (ISO 8601 oder datetime)

_iso(dt)

Interne Utility, die datetime → ISO-8601 wandelt, Strings unverändert lässt und None zurückgibt, wenn kein Wert gesetzt ist.

Design-Notizen

Defensive Programmierung: Leere oder fehlerhafte Typen werden ignoriert.

Klarheit: Nur sinnvolle Felder werden gesetzt (z. B. kein leeres Dict).

Zeitfenster: Nur nicht-None-Werte werden eingefügt.


📁 memory_tools.py
Factory-Funktionen zur Erzeugung von Autogen FunctionTools, die Agenten Zugriff auf Graph-Operationen geben.

Grundprinzip

Jede create_*_tool(get_api)-Funktion:

zieht api = get_api()

ruft eine entsprechende GraphAPI-Methode auf
→ keine direkten Zep-Client-Aufrufe.

Wichtige Tools
Tool	Beschreibung
clone_user_graph	Klont kompletten User-Graph.
set_ontology	Setzt Ontologie im aktuellen Graph-Scope.
add_node	Fügt Knoten hinzu (name, optional summary, attributes).
add_graph_edge	Legt Kante an (fact, rating, valid/invalid/expired).
clone_graph	Klont Graph mit neuem Label.
search_graph	Einheitliche Suche (nodes / edges / episodes + Filter, Reranker usw.).
add_graph_data	Fügt Episoden-/Rohdaten ein (`text
get_graph_item	Holt node oder edge per UUID.
get_node_edges	Listet Kanten zu einem Knoten (optional Richtung).
delete_edge / delete_episode	Löschen per UUID.
Design-Notizen

Single Source of Truth: Alle Pfade laufen über GraphAPI.

Kein mehrfaches Instanziieren von Admins.

Saubere Parametrisierung: Nur gesetzte Parameter werden weitergereicht.


📁 manager.py
Hoch-Level-Fassade über Thread-Memory (ZepThread) und Graph-Memory (GraphAPI).
Bietet zentrale Entry-Points für alle Speicheraktionen.

Hauptklasse MemoryManager
Konstruktor
MemoryManager(zep_memory: ZepMemory, get_api: Callable[[], GraphAPI])


Speichert ZepMemory (Thread) und injiziert get_api (Graph).

Methoden
Methode	Beschreibung
add_message(role, text, name=None, also_graph=False, ignore_roles=None)	Schreibt Nachricht in Zep-Thread (optionale Spiegelung in Graph).
get_context(include_recent=True, graph=False, recent_limit=10, graph_filters=None)	Baut kombinierten Kontextblock.
search(query, **kwargs)	Leitet an ZepMemory.query.
add_data(text, data_type="text")	Fügt Daten/Episoden ein.
add_node(...)	Fügt Knoten über GraphAPI hinzu.
add_edge(...)	Legt Kante mit vollem Parametersatz an.
search_nodes(...)	Führt Graph-Suche aus, filtert nur type=="node".
for_graph(graph_id)	Erzeugt GraphScopedManager für festen Graph-Scope.
GraphScopedManager

Erbt von MemoryManager, nutzt dasselbe Thread-Memory, aber fixiert graph_id für alle Graph-Aufrufe.

Design-Notizen

Dependency Injection: get_api ist zentrale Quelle.

Trennung: Thread- vs. Graph-Speicher strikt getrennt.

Scoped Handles: erlauben mehrere parallele Demo-/User-Graphen.


📁 memory_utils.py
Kleine Utilities zur Normalisierung, Chunking und Text-Aufteilung.

API
Funktion	Beschreibung
prepare_message_dict(role, content, name=None)	Validiert Rollen (`user
format_message_list(raw, limit=10)	Vereinheitlicht Message-Listen auf role, content, ts.
chunk_messages(messages, max_batch=30)	Teilt Nachrichten in Batches (API-Limit-Schutz).
split_long_text(text, max_len=10000)	Zerlegt lange Texte für Uploads.
Design-Notizen

Rollen-Whitelist (ALLOWED_ROLES) verhindert API-Fehler.

Chunking-Support schützt vor Zep-Limitüberschreitung.

Universell nutzbar in Thread- und Graph-Kontexten.


📁 memory.py
Kombiniert Thread-Memory (Konversation) und Graph-Memory (Zep Graph) in einer einheitlichen Speicher-Implementierung für Autogen-Agenten.

Eingebettete Komponenten
ZepThreadMemory

Verwaltet Zep-Threads:

ensure_thread() – erstellt/verifiziert Thread.

add_messages() – Batch-Upload mit Chunking.

list_recent_messages() – liefert vereinheitlichte Message-Liste.

get_user_context() / build_context_block() – erstellt nutzerbezogenen Kontext-Text.

ZepGraphAdmin

Low-Level-Wrapper über Zep Graph-Client:

Verwaltung von Graphen (create, list, update, clone)

Knoten / Kanten / Episoden-Operationen (add_node, add_fact_triple, get_*, delete_*)

Payload-Erstellung via build_edge_payload

Suche mit Parametern, Rerankern u. BFS-Optionen.

ZepMemory

Oberklasse (autogen_core.memory.Memory) mit kombinierten Fähigkeiten:

Verwaltet Thread + Graph-Kontext.

Implementiert add(), add_episode(), query(), get_context().

Nutzt injizierte GraphAPI-Instanz (set_api(get_api)).

Design-Notizen

Single-Source-Policy: Thread-Logik nur in ZepThreadMemory; Graph-Calls ausschließlich über GraphAPI.

Trennung von Typen: message → Thread, data → Graph.

Fehler-Resilienz: Defensive Behandlung von API-Fehlern.

Kontext-Aggregation: Kombiniert User- und Recent-Kontext + kompakten Graph-Ausschnitt.


📁 graph_api.py
Zentrale, dünne Fassade über ZepGraphAdmin.
Normalisiert Zep-Objekte (node, edge, episode) zu stabilen Dict-Formaten für Tools & Manager.

Kernbestandteile
Normalisierer

_EdgeInfo, _NodeInfo, _EpisodeInfo – Dataclasses mit .to_dict()

Hilfsfunktionen _edge_from_zep, _node_from_zep, _episode_from_zep

GraphAPI

Führt Zep-Operationen aus und gibt normalisierte Ergebnisse zurück.

Wichtige Methoden

set_ontology(schema)

add_node(name, summary=None, attributes=None)

add_edge(head_uuid, relation, tail_uuid, ..., rating, valid_at, ...)

add_data(data, data_type="text") / add_raw_data(...)

delete_edge, delete_episode, clone_graph, clone_user_graph

search(**params) → Liste von normalisierten Dicts

get_node, get_edge, get_node_edges

GraphAPIProvider

Factory/DI-Wrapper:

get_api() → gibt eine persistente GraphAPI zurück.

scoped(graph_id) → erzeugt neuen Scope mit gleichem Client.

Design-Notizen

Normierungs-Zentralisierung: Nur hier werden Zep-Antwortobjekte in Dicts umgewandelt.

Scoped APIs: Ermöglichen Multi-Graph-Betrieb pro User.

Integrationsebene: Wird von MemoryManager, Tools und ZepMemory genutzt.