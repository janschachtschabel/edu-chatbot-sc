# Repository-Audit: edu-chatbot-sc

**Prüfdatum:** 03.10.2026 · **Repository:** janschachtschabel/edu-chatbot-sc

**Geprüfter Stand:** main, Commit 610abec6e4a67baf6d08721149b81168a41a89a7 vom 01.10.2026.

**Ergebnis:** Das Projekt hat eine gute Architektur- und Testbasis. Die größten verbleibenden Risiken liegen an den Übergängen zwischen HTTP, Hintergrundaufgaben, Modellausgabe, Werkzeugausführung, Konfigurationscache und Persistenz. Vor weiterer Skalierung und dem Ausbau schreibender Funktionen sollten diese Übergänge abgesichert werden. Für mehr Geschwindigkeit ist die Verringerung zusätzlicher Modellaufrufe derzeit aussichtsreicher als ein pauschaler Wechsel auf teurere Modelle.

Der Bericht enthält **22 priorisierte Befunde**, **17 isolierte Reproduktionsbelege**, getrennte Empfehlungen für Muster- und Agent-Modus sowie konkrete Vorschläge für Studio und Widget. Bekannte offene Punkte sind ausdrücklich gekennzeichnet. Es wurden keine Änderungen an den Repository-Quellen vorgenommen.

**Zuerst angehen:** Werkzeugfreigaben tatsächlich vor der Ausführung prüfen; SSE-Abbruch und Wiederaufnahme konsistent lösen; Agent-Limits auf laufende Aufrufe anwenden; RAG-Importe verlustfrei gestalten; Konfiguration atomar und versionsgebunden speichern. Im Mehrreplikabetrieb kommt die clusterweite Sitzungssperre hinzu.

**Die stärksten Tempohebel:** Agent-Schnellantworten im Antwortaufruf nach Anpassung des Master-Skills aktivieren; stabile Promptteile und veränderlichen Kontext trennen; nur unabhängige Leseabrufe parallelisieren; echte Textausgabe ins Widget streamen.

---

## Orientierung

- [1. Umfang, Evidenz und Grenzen](#1-umfang-evidenz-und-grenzen)
- [2. Architektur und vorhandene Stärken](#2-architektur-und-vorhandene-stärken)
- [3. Befunde mit hoher Priorität](#3-befunde-mit-hoher-priorität)
- [4. Weitere bestätigte Befunde](#4-weitere-bestätigte-befunde)
- [5. Prozess- und Antwortgeschwindigkeit](#5-prozess--und-antwortgeschwindigkeit)
- [6. Antwortqualität gezielt verbessern](#6-antwortqualität-gezielt-verbessern)
- [7. Kosteneinsparung und Kostenkontrolle](#7-kosteneinsparung-und-kostenkontrolle)
- [8. Studio: Funktionalität und Verwaltbarkeit](#8-studio-funktionalität-und-verwaltbarkeit)
- [9. Widget: sinnvolle Ergänzungen](#9-widget-sinnvolle-ergänzungen)
- [10. Empfohlene Umsetzungsfolge](#10-empfohlene-umsetzungsfolge)
- [11. Prüfplan für die nächste Implementierungsrunde](#11-prüfplan-für-die-nächste-implementierungsrunde)
- [12. Reproduktionsbelege und Quellen](#12-reproduktionsbelege-und-quellen)

| Interesse | Empfohlener Einstieg |
| --- | --- |
| Konkrete Fehler beheben | Abschnitt 3, danach 4 und die Abnahmetests in 11 |
| Beide Modi schneller machen | Abschnitt 5; Agent-Inline-Weg und stabile Prompts zuerst |
| Antwortqualität und Kosten | Abschnitte 6 und 7; Fehlpfade und Quellenbezug mitmessen |
| Studio und Widget ausbauen | Abschnitte 8 und 9; Lebenszyklus und Versionen als Grundlage |
| Planung und Nachvollziehbarkeit | Abschnitte 10–12 sowie die eingebetteten Anlagen der zugehörigen PDF-Fassung |

## 1. Umfang, Evidenz und Grenzen

Geprüft wurden Backend, beide Chat-Betriebsmodi, der direkte Agent-Endpunkt, MCP-Transport und Werkzeugpolitik, RAG, Datenbank- und Konfigurationszugriffe, Studio, Widget, Tests, CI und Deployment-Konfiguration. 1.403 ausgewählte Textdateien des festgelegten Commits wurden lokal verfügbar gemacht und gegen ihre Git-Blob-Hashes verifiziert. Binärdateien, große generierte Architekturansichten und ältere Audit-/Planbestände wurden nicht vollständig heruntergeladen; die relevanten Vorgängerdokumente wurden gezielt gelesen.

Die Prüfung verbindet Quellcodeanalyse, vorhandene CI-Evidenz, lokale Tests und gezielte Fehlerreproduktionen. Die Reproduktionen ersetzen externe LLM-, MCP- und Datenbankgrenzen durch kontrollierte Fakes. Sie belegen lokale Logikfehler, ohne einen Angriff auf ein laufendes System oder eine reale Datenbankwirkung vorzutäuschen.

Nicht ausgeführt wurden bezahlte Modellaufrufe, schreibende Golden-Flows gegen Staging, ein Produktionslasttest, ein Screenreader-Test oder ein Live-Audit des externen WLO-MCP-Servers. Aktuelle Produktionskonfiguration, tatsächliche Diensttoken-Rechte, Datenbestand, Latenzverteilung und Rechnungen lagen nicht vor. Deshalb sind vorgeschlagene Laufzeitgewinne Messhypothesen; aus Repository-Plänen übernommene Messwerte sind gesondert gekennzeichnet.

| Prüfung | Ergebnis und Aussagekraft |
| --- | --- |
| Backend lokal | 4.526 bestanden, 317 übersprungen, 4 umgebungsbedingt abgewählt, 2 bekannte xfails; 68,04 s |
| Backend-CI am geprüften Commit | 4.773 bestanden, 74 übersprungen, 2 xfails; Postgres und Jaeger vorhanden |
| Frontend lokal | UI 837, Widget 70, Studio 1.327 bestanden; insgesamt 2.234 Tests |
| Lint und Verträge | Ruff, ESLint, OpenAPI-Gate und Bereichsschema-Gate bestanden |
| Frontend-Wächter | Tokens, Überschriften/Tabellen, Fokus-/Kontrastregeln, Radien und Attributdokumentation bestanden |
| Builds | Widget und Studio erfolgreich; Widget 550,78 kB roh, 159,81 kB gzip |
| Widget-Budget | 91,8 % des 600-kB-Rohbudgets, 91,3 % des 175-kB-gzip-Budgets; zusätzliche Angular-Warnschwelle 550 kB um 780 Byte überschritten |
| Browser-E2E | 49 bestanden in der CI; mockbasierter Widget-Harness, Chromium; lokal kein passender Browser vorhanden |
| Python-Abhängigkeiten | Aktueller pip-audit des gesperrten Laufzeitexports: 136 Pakete, keine bekannten Meldungen |
| npm-Abhängigkeiten | Vorliegendes Gesamtaudit: 24 betroffene Pakete, davon 2 critical, 16 high, 5 moderate, 1 low; keine 24 unabhängigen Exploits |
| Eigene Reproduktionen | 17 Belege; Übersicht in Abschnitt 12.1, Ergebnisse und ausführbares Skript in den Anlagen der zugehörigen PDF-Fassung |

Die vier lokalen Ausschlüsse betreffen zwei Ressourcenmessungen wegen der Prozesssicht der Prüfumgebung, die OTEL-Prüfung ohne Jaeger und eine Health-Prüfung ohne lokale Datenbank. Die übrigen übersprungenen Tests benötigen insbesondere Postgres, Valkey oder das externe ALT-Referenzrepository.

Eine zusätzliche npm-Abfrage mit getrenntem Produktionsfilter wurde automatisch abgelehnt, weil sie Paketmetadaten des privaten Repositorys an die öffentliche Registry übertragen würde. Sie wurde nicht erneut versucht. Die Einordnung der vorhandenen Meldungen verwendet ausschließlich das bereits erhaltene Gesamtaudit und die dev-Markierungen des lokalen Lockfiles.

**Prioritäten:** P1 = vor Skalierung, Schreibfreigabe oder dem betroffenen Ausbau beheben; P2 = nächster Verbesserungszyklus; P3 = optionale Erweiterung. Priorität beschreibt die Wirkung in diesem Projekt, nicht den CVSS-Wert einer Abhängigkeit. „Neu“ bedeutet: in den gezielt gelesenen Vorgängerbefunden nicht enthalten. Eine vollständige historische Neuheitsprüfung ist damit nicht behauptet.

## 2. Architektur und vorhandene Stärken

| Aspekt | Muster-Modus | Agent-Modus |
| --- | --- | --- |
| Entscheidung | Klassifikation, Musterwahl, Modulation, Routing | Modell entscheidet innerhalb des angebotenen Werkzeugkatalogs |
| Klassifikator | Safety, Klassifikation und Memory-Prüfung werden teilweise parallel ausgeführt | Kein Intent-Klassifikator; Safety bleibt aktiv |
| Antwort | Musterbriefing und ausgewählte Werkzeuge, eigener Tool-Loop | Master-Skill, Persona-/Domänenrahmen und Agent-Schleife |
| Wissensabruf | Musterabhängige RAG-Whitelist und Vorabrufe | Wissenswerkzeug und kontextabhängige Vorabrufe |
| Schnellantworten | Inline-Weg standardmäßig an; Fallback bleibt | Inline-Weg vorhanden, standardmäßig aus |
| Begrenzung | Tool-Loop und vorhandene Retry-/Safetyregeln | Vorgabe 30 Iterationen, 900 s, 900.000 Token; Grenzen derzeit zwischen Runden |
| Chat-Rahmen | Session, Karten, Dokumente, Geschichte, Persistenz | Erbt denselben Chat-Rahmen; /api/agent ist dagegen ein separater Maschinenendpunkt |

Positiv sind die klare Schichtung, typisierte Konfigurationsmodelle, umfangreiche Unit-Tests und Vertragswächter, strukturierte Werkzeug-Outcomes, vorhandene Phasenzeiten und Kostenansichten, pgvector mit HNSW-Index, DOMPurify vor Markdown-Ausgabe und ein Studio-BFF mit HttpOnly-Cookie statt Admin-Schlüssel im Browser.

Wichtige frühere Reparaturen sind im aktuellen Code tatsächlich vorhanden: keine Wiederholung bestätigter MCP-Schreibaufrufe mit confirmToken; Schwärzung der Bestätigungsschlüssel; Bindung der Usage-/Query-Sammler vor LangGraph; Rollback nach bestimmten geschluckten DB-Fehlern; serieller RAG-Zugriff auf derselben AsyncSession; Moderationsfrist; Rumpfgrößenlimit; korrigierte Backup-Rotation. Diese Punkte werden nicht als neue Fehler ausgegeben.

Der dritte „Hybrid“-Modus wurde bewusst entfernt. Eine Wiederbelebung ist für die hier identifizierten Probleme nicht erforderlich. Auch die Wahl des Klassifikatormodells und die hohen Agent-Vorgaben sind dokumentierte Entscheidungen; die Empfehlungen beginnen mit besserer Ausführung und Messbarkeit dieser bestehenden Entscheidungen.

## 3. Befunde mit hoher Priorität

### F01 · P1 · Sitzungssperren gelten nur pro Prozess

**Status:** bekannt, im aktuellen Stand erneut bestätigt. **Betrifft:** beide Chat-Modi bei mehreren Repliken.

chat.py serialisiert über asyncio.Lock aus api/session_locks.py. db/locks.py enthält zwar acquire_session_lock, aber keinen produktiven Aufrufer. Die Produktions-Compose setzt weiterhin standardmäßig drei Repliken. Zwei Anfragen derselben Session können deshalb auf verschiedenen Repliken denselben alten Zustand lesen und konkurrierend überschreiben. Betroffen sind turn_count, Referenzen auf angezeigte Materialien und offene Schreibvorschläge.

**Verbesserung:** Bis zur Behebung BACKEND_REPLICAS=1 als Betriebsmaßnahme erwägen. Dauerhaft den gesamten Turn clusterweit serialisieren, etwa mit einem sitzungsgebundenen Advisory-Lock auf dedizierter Verbindung oder einem Queue-/Fencing-Verfahren. Ein xact-Lock an der bestehenden Request-Session reicht wegen mehrerer Commits im Turn nicht aus. Sticky-Routing ist keine vollständige Sperre.

**Abnahme:** Zwei echte Backend-Prozesse, dieselbe Session, kontrolliert überlappende Turns: keine verlorenen Zustände, eindeutige Reihenfolge und Freigabe bei Abbruch. Quellen: api/chat.py ab 82/143, api/session_locks.py, db/locks.py:13, deploy/compose.prod.yml:131.

### F02 · P1 · SSE-Aufgaben überleben den Abbruch; Fallback kann den Turn wiederholen

**Status:** Lebenszyklusproblem bekannt; zusammenhängender Retry-/Idempotenzpfad erneut geprüft. **Betrifft:** Chat und direkter Agent-Endpunkt; Widget.

sse_turn erzeugt einen separaten Task. Er wird im Timeout-Zweig bei is_disconnected abgebrochen, aber es fehlt eine äußere finally-Behandlung für GeneratorExit oder CancelledError. Sowohl aclose als auch das Abbrechen des Consumers ließen in den Reproduktionen den Task weiterlaufen; sein Cleanup war noch nicht ausgeführt. Gleichzeitig kann die Request-Datenbanksitzung enden. Das Widget fällt bei Netzwerk-, Parser- und vielen Streamfehlern auf einen neuen POST /chat zurück. Eine turn_id zur Deduplizierung ist nicht Bestandteil dieses Pfads.

**Folge:** zusätzliche Modellkosten, blockierte Slots, längere Wartezeiten und unter bestimmten Fehlerbedingungen doppelte Verarbeitung. Die Widget-Meldung, der alte Turn werde fertig gespeichert, ist zudem nicht für jeden Abbruchpfad garantiert. Der öffentliche error-Frame enthält außerdem Exceptiontyp und str(exception), bis 400 Zeichen. Ein Dummy-Geheimnis und interner Pfad wurden darin reproduziert; gekürzter Text ist keine Schwärzung. Hier einen generischen Fehlercode plus Korrelations-ID senden und Details nur privat protokollieren. Auch der Muster-Loop enthält einen Freitext-Fehlerpfad.

**Verbesserung:** Eine konsistente Policy wählen: Abbruch mit cancel-and-drain in finally oder ein bewusst weiterlaufender, verwalteter Job mit eigener DB-Session, Status und Wiederaufnahme. Beide Varianten benötigen eine stabile turn_id mit serverseitiger Deduplizierung; Wiederaufnahme darf keine neue Schreibausführung auslösen. Widget-Abbruchsignal bei Destroy/Reset weiterreichen.

**Abnahme:** Disconnect vor/nach Werkzeugwirkung, Reader-Abbruch und POST-Fallback produzieren höchstens einen logischen Turn und keinen unverwalteten Task. Quellen: api/sse.py:55, api/chat.py:143, UI shell/send-message.ts:100-135, stream/stream-client.ts.

### F03 · P1 · Angebotener Werkzeugkatalog ist keine Ausführungsfreigabe

**Status:** bekannt, Agent-Pfad isoliert reproduziert. **Betrifft:** beide Antwortschleifen; Safety und Host-Fähigkeiten.

Die Agent-Schleife prüft einen Modellaufruf nicht gegen die Namen in tools. In der Reproduktion war tools leer; search_wlo_content wurde trotzdem an die Ausführung weitergereicht. Im Muster-Loop existiert ein expliziter Safety-Blocklist-Check, aber keine vollständige Prüfung gegen active_tools. Das bloße Weglassen eines Werkzeugs aus dem Prompt erzwingt weder read-only noch die Pattern-Whitelist.

Das belegt einen fehlenden serverseitigen Schutz, nicht bereits einen erfolgreichen Fremdangriff. Eine weitere Argumentprüfung oder ein WriteGate ersetzt diese Freigabeprüfung nicht.

**Verbesserung:** Vor jeder Ausführung einen gemeinsamen Dispatcher verwenden: erlaubter Name aus dem konkreten Turn-Katalog, gültige Argumente, Safety-/Policyfreigabe, Host-tool_mode und Schreibrechte. Auch virtuelle Werkzeuge nur akzeptieren, wenn sie angeboten wurden. Abgewiesene Calls als strukturierte Tool-Antwort zurückgeben und protokollieren.

**Abnahme:** Ein gefälschtes Modell emittiert ausgeschlossene Such-, Schreib- und virtuelle Werkzeuge: kein externer Aufruf. Quellen: services/agent_loop.py:198/325-418, services/tool_loop.py:594-608, services/agent_tools.py, services/outcome_service.py:36.

### F04 · P1 · Agent-Frist und Tokenbudget begrenzen laufende Aufrufe nicht

**Status:** Fristproblem bekannt; Budgetüberschreitung und fehlende Ausgabereservierung reproduziert. **Betrifft:** Agent-Chat und /api/agent.

Die Schleife prüft Zeit und verbrauchte Token am Rundenanfang. Der LLM-Aufruf, mehrere Tool-Aufrufe derselben Runde und der Vorabruf vor der Schleife werden nicht durch eine gemeinsame Restfrist begrenzt. Ein letzter Text kann die Prüfung umgehen: Bei Frist 5 s kam ein bei 6 s geliefertes Ergebnis mit stop_reason=text zurück. Bei Budget 1.000 Token wurden 1.500 verbraucht und ebenfalls text gemeldet. Der Aufruf enthält kein verbleibendes Ausgabe-Limit.

Die vorhandenen 30/900/900.000-Vorgaben sind kein unbeabsichtigter Tippfehler. Das Problem ist die unklare Bedeutung der Grenzen und das Überschreiten innerhalb einer Runde.

**Verbesserung:** End-to-end-Frist inklusive Queue, Safety, Prefetch, LLM, Tool und Retry; Restzeit pro Aufruf weiterreichen. Vor einer Modellrunde Promptbedarf und Ausgabeobergrenze reservieren. Modellabhängig den unterstützten Output-Parameter verwenden: max_tokens allein wird für bestimmte Modellgruppen im Transport verworfen. Verbrauch nach jedem Aufruf prüfen und bei Überschreitung ehrlich markieren. Zusätzlich absolute Kostenbudgets pro Workload/Tag anbieten.

**Abnahme:** Ein langsames Tool und ein letzter großer LLM-Call überschreiten das deklarierte Verhalten nicht unbemerkt. Quellen: services/agent_loop.py:245-280, services/agent_run.py:78-117, services/llm.py:130-145/212, domain/config_models/engine.py:58-60.

### F05 · P1 · Agent-Schreibvorschläge werden im Folgezug nicht eingelöst

**Status:** bekannt, zwei strikte xfails weiterhin vorhanden. **Betrifft:** Agent-Chat mit write_mode=propose.

Der Chat-Vorlauf erwartet entities._pending_write und die Vorschau aus _write_preview. Die Muster-Schleife legt diese Daten an, das Agent-WriteGate in der Vorgabe propose dagegen nicht dauerhaft für den nächsten Turn. Ein „ja“ findet deshalb keinen einlösbaren Vorschlag; die Änderung bleibt in der Vorschau oder wird erneut vorgeschlagen. Die Sicherheitszusage, ohne Zustimmung nichts auszuführen, wird durch den dritten Test weiter geprüft.

**Verbesserung:** Einen gemeinsamen Vorschlags-/Freigabezustand für beide Modi verwenden: Werkzeug, kanonische Argumente, handelnde Identität, Fingerabdruck, Ablauf und serverseitiger Bestätigungsschlüssel. Vorschau ohne Schlüssel im Widget darstellen; Zustimmung an genau diesen Vorgang binden. F01-F03 und Idempotenz müssen dabei mitgelöst sein. Diensttoken-Kuration separat als bewusste Betreiberfreigabe darstellen; die tatsächlichen Token-Rechte wurden hier nicht live geprüft.

**Abnahme:** Beide xfails in normale grüne Tests überführen; Nein, Zwischenzug, Ablauf, Benutzerwechsel und doppelte Bestätigung ausführen. Quellen: tests/test_agent_schreib_abnahme.py:216 ff., services/agent_write.py, services/write_approval.py, graph/nodes/respond_agent.py.

### F06 · P1 · RAG-Import verliert Text bei fehlgeschlagenem Embedding

**Status:** neu gegenüber den gelesenen Vorgängerbefunden, reproduziert. **Betrifft:** Studio-Ingest und spätere Antwortqualität.

ingest_document überspringt jeden Chunk mit Embedding=None und gibt anschließend len(chunks) zurück. In der Reproduktion wurden zwei Abschnitte gemeldet, einer gespeichert. Der fehlende Text existiert danach nicht als RagChunk. embed_missing_chunks sucht jedoch nur vorhandene Zeilen mit NULL-Embedding und kann diesen Verlust nicht reparieren. Der Modulkommentar verspricht vollständige Dokumente durch eine Transaktion, obwohl die aktuelle Schleife Teilbestände ausdrücklich committet.

**Verbesserung:** Alle Texte mit Status pending speichern; Embeddings anschließend als wiederholbaren Job erzeugen. Alternativ den gesamten Import bei einem fehlenden Vektor sauber zurückrollen. Die erste Variante ist bei großen Dokumenten robuster. Im Studio attempted/stored/embedded/failed getrennt anzeigen, fehlgeschlagene Abschnitte wiederholen und Dokument-Hash gegen doppelte Importe verwenden. Keine offene DB-Transaktion während langer Netzaufrufe halten.

**Abnahme:** Ein, mehrere und alle Embeddings schlagen fehl: kein Textverlust, keine falsche Erfolgszahl, Wiederholung ergänzt genau die fehlenden Vektoren. Quellen: services/rag/ingest.py:98-134/156, services/rag/embed.py:83.

### F07 · P1 · Restore umgeht Validierung und ist nicht atomar

**Status:** bekannte Grundprobleme, durch mehrere Reproduktionen konkretisiert. **Betrifft:** Studio-Backup, Werksstand und CLI-Export.

_apply_config parst das ZIP und schreibt Bereiche einzeln. Ein ungültiger Engine-Wert bad-mode wird vom Parser akzeptiert. Scheitert der zweite Schreibvorgang, ist der erste bereits gespeichert. Schlüssel wie ../bad bleiben zulässig. Der ZIP-Parser schreibt selbst keine Dateien außerhalb eines Verzeichnisses; ein separater Export über seed_io.export_tree verwendet diesen Schlüssel jedoch direkt als Pfad. Das Erzeugen einer Datei außerhalb des vorgesehenen Exportordners wurde in einem eigenen temporären Testverzeichnis nachgewiesen.

Die vorhandenen Upload- und Entpackgrößenlimits sind sinnvoll, ersetzen diese Prüfungen aber nicht. Der Restore ist Studio-geschützt; eine anonyme ZIP-Upload-Schwachstelle wird nicht behauptet.

**Verbesserung:** Alle Mitglieder vorab prüfen: normalisierter Bereichsschlüssel, erlaubte Endung, keine absoluten Pfade/.., keine Kollisionen, gültige YAML-/Markdown-Struktur und dieselben Pydantic-/Sicherheitsregeln wie beim Formular. Gesamten Diff in einer DB-Transaktion anwenden; erst nach Commit Caches aktualisieren. Merge und exakte Wiederherstellung ausdrücklich unterscheiden. Auch export_tree muss resolve/relative_to erzwingen.

**Abnahme:** Fehler im letzten Bereich verändert keinen Bereich; falsche Pfade und Schemas werden vor dem ersten Write abgewiesen. Quellen: api/config_snapshots.py:44-54, services/snapshots.py:66-99, services/seed_io.py:107-119, api/config.py:267-303.

### F08 · P1/P2 · Konfigurationscache kann auf einen älteren Stand zurückfallen

**Status:** Reihenfolgerennen neu reproduziert; Reconnect- und Guide-Probleme bekannt. **Betrifft:** beide Modi und Studio-Wirksamkeit.

Jede NOTIFY-Nachricht startet einen unabhängigen _refresh. _fetch liefert nur data, keine Version. Ein langsamer älterer Abruf kann nach einem neueren landen und dessen Cacheeintrag ersetzen. Die Reproduktion endet mit v=1 im Cache, obwohl v=2 bereits gelesen wurde. Nach einer LISTEN-Unterbrechung gibt es keinen Abgleich verpasster Änderungen. Zusätzlich hält guide_qr_injector kompilierte Regeln dauerhaft; reset_compiled_cache wird produktiv nicht beim Speichern aufgerufen.

**Verbesserung:** Daten und Version gemeinsam laden; nur monotone Versionen übernehmen, Löschungen ebenfalls versionieren. Refresh pro Bereich bündeln/serialisieren, bei Reconnect einen vollständigen Versionsabgleich durchführen. Abgeleitete Caches erst nach erfolgreicher Übernahme invalidieren. Guide-Cache an Bereichsversion koppeln. Cachealter und Version pro Replik im Studio anzeigen.

**Abnahme:** Überlappende Saves, Notifier-Ausfall und Reconnect enden auf allen Repliken beim letzten DB-Stand; Guide-Regeln greifen ohne Neustart. Quellen: services/config_store.py:78-99/126-152, db/notify.py:81-105, services/guide_qr_injector.py:231-281.

## 4. Weitere bestätigte Befunde

### F09 · P2 · Direkte Agent-Aufrufe fehlen in der dauerhaften Kostenbuchung

**Status:** neu gegenüber den gelesenen Vorgängerbefunden. **Betrifft:** /api/agent, dessen Stream und Studio-Agent-Tester.

Die Agent-Endpunkte rufen run_agent ohne usage_acc auf und schreiben keinen UsageEvent. Die Schleife erzeugt intern einen Sammler, dessen Inhalt nicht zurückgegeben oder persistiert wird. Der Agent-Chat über /api/chat wird dagegen gebucht. Embeddings werden im Transport ebenfalls nicht in der Chat-Usage erfasst. Im Klassifikator kehrt der Salvage-Pfad vor der Usage-Buchung zurück. Fehler und Abbrüche können bereits angefallene, bekannte Kosten aus der Erfolgsbuchung ausschließen.

**Verbesserung:** Gemeinsames Usage-Ledger für Chat, Maschinenauftrag, Import, Eval/Judge und Fehlerpfade. Aufruf-ID, Endpoint, Engine, Phase, Provider/Modell, Cache-Token, Service-Tier, Ergebnisstatus und Preisversion speichern. Unbekannte Kosten als unbekannt kennzeichnen. Keine erfundenen Nullkosten für abgebrochene Provideraufrufe. Historische Schätzungen nicht unbeabsichtigt mit einer neuen Preistafel umrechnen.

**Abnahme:** Ein Studio-Agent-Test erscheint mit seinem tatsächlichen Aufrufverbrauch in der passenden Kostenkategorie. Quellen: api/agent.py:35-66, services/agent_run.py:78-117, services/agent_loop.py:221, services/llm.py:251-303, services/classify.py:98-106, services/usage_store.py:44.

### F10 · P2 · Klassifikator-Salvage akzeptiert ungültige Typen und Werte

**Status:** neu, reproduziert. **Betrifft:** Muster-Modus bei erschöpften Instructor-Validierungsversuchen.

_salvage filtert nur bekannte Feldnamen und verwendet model_construct. Dadurch werden keine Typen, Wertebereiche oder Querbedingungen geprüft. Die Reproduktion erzeugt signals als String, entities als Liste und intent_confidence=99. Das widerspricht dem Kommentar, ungültige Felder würden auf Vorgaben zurückfallen, und kann in nachfolgenden Knoten Fehler oder falsche Entscheidungen verursachen.

**Verbesserung:** Felder einzeln validieren, fehlerhafte Felder verwerfen und das Ergebnis nochmals als vollständiges Modell prüfen. IDs gegen die aktuell erlaubten Intent-/Persona-/Signalregister prüfen; bei unbrauchbarem Ergebnis einen klaren Default verwenden. Fehlversuche samt vorhandener Usage erfassen.

**Abnahme:** Ungültige Listen/Strings, unbekannte IDs, negative/zu große Confidence und gemischte Teilresultate führen zu einem gültigen ClassificationResult. Quelle: services/classify.py:109-138.

### F11 · P2 · Result-Schema wird dem Modell angeboten, serverseitig nicht durchgesetzt

**Status:** neu gegenüber den gelesenen Vorgängerbefunden, reproduziert. **Betrifft:** Maschinenauftrag und strukturierte Gastgeberergebnisse.

Das freie result_schema wandert in die Werkzeugparameter. submit_result übernimmt args.result jedoch ohne Prüfung gegen dieses Schema. Ein Schema für score als Integer von 0 bis 5 akzeptierte in der Reproduktion {score: bad}. Die Annahme, jeder Anbieter erzwinge den Vertrag, ist im Backend nicht abgesichert; ein verlässliches Maschinenresultat braucht eine Prüfung nach dem Modellaufruf.

**Verbesserung:** Schema selbst vorab prüfen, unterstützten Draft/Teilumfang dokumentieren und referenzierte externe URLs nicht automatisch laden. Ergebnis lokal validieren. Bei Fehler höchstens eine begrenzte Reparaturrunde oder ein strukturierter Vertragsfehler; zusätzlich providerseitig strict nur dort nutzen, wo der Provider es unterstützt. Größe und Tiefe von Schema/Ergebnis begrenzen.

**Abnahme:** Fehlender Pflichtschlüssel, falscher Typ, Grenzwert, zusätzliche Felder und ungültiges Schema werden deterministisch behandelt. Quellen: api/schemas_agent.py:29-49, services/agent_tools.py, services/agent_loop.py:350-382.

### F12 · P2 · MCP-Result-Cache ignoriert den ausgewählten Server

**Status:** neu, reproduziert. **Betrifft:** dynamische MCP-Registry im Studio.

Der Schlüssel besteht aus Werkzeugname, Aufrufer-Fingerprint und Argumenten. Die Aufrufertrennung ist vorhanden und richtig. Server-URL und Registry-Version fehlen jedoch. Nach einem Wechsel von Server A zu B gab get_node_details weiter das Ergebnis von A zurück, ohne B aufzurufen. Die TTL dieses Werkzeugs beträgt 30 Minuten.

**Verbesserung:** Serveridentität, Registry-/Schema-Version und relevante Wissensversion in den Cache-Namensraum aufnehmen. Änderungen eines Servers invalidieren dessen Einträge. Nach erfolgreichen Änderungen betroffene Leseeinträge ebenfalls invalidieren; parallele identische Cachemisses mit Singleflight bündeln. Schreibaufrufe weiter nicht cachen oder unkontrolliert wiederholen.

**Abnahme:** Serverwechsel, identische Werkzeugnamen auf zwei Servern und unterschiedliche Identitäten teilen keinen falschen Eintrag. Quellen: services/mcp/tool_cache.py:102-129, services/mcp/client.py, services/config_loader/mcp.py.

### F13 · P2 · always-RAG greift im Muster-Modus für viele Muster nicht

**Status:** bekannt, aktuell bestätigt. **Betrifft:** Antwortqualität und Studio-Erwartung im Muster-Modus.

phase3_modulate setzt rag_areas immer auf eine Liste, auch wenn sie leer ist. _resolve_rag_areas wertet jede vorhandene Liste als explizite Whitelist. Damit wird der dokumentierte Default-Zweig für always-Bereiche auf diesem Pfad nicht erreicht. In den Seeds haben nur M04 und M15 explizite Bereichslisten. Die tatsächliche Produktionskonfiguration könnte davon abweichen.

**Verbesserung:** Semantik ausdrücklich modellieren: „Vorgabe erben“, „kein RAG“ oder „explizite Bereiche“. Fehlenden Wert und absichtlich leere Liste unterscheiden. Im Studio je Muster die effektiv verwendeten Quellen anzeigen und before/after-Eval fahren; nicht pauschal alle Wissensbereiche in jeden Turn einfügen.

**Abnahme:** Geerbter always-Bereich wird verwendet; bewusst deaktiviertes RAG bleibt aus; ungültiger Bereich wird sichtbar abgewiesen. Quellen: domain/pattern_engine.py:61/263, domain/route_head.py:21-45, Seeds 03-patterns.

### F14 · P2 · Studio-Saves können fremde Änderungen überschreiben

**Status:** bekannt. **Betrifft:** parallele Redaktion und vollständige Dokument-PUTs.

Konfigurationsbereiche haben DB-Versionen, die Schreib-API verlangt aber keine erwartete Version. Zwei Redakteure können dieselbe alte Datei bearbeiten; der zweite Save überschreibt den ersten. Die vorhandene Sicherung gegen eigene Eingaben während eines laufenden Saves ist eine andere, bereits reparierte Fehlerklasse. Das vollständige Dokument zu speichern ist dagegen sinnvoll, weil unbekannte Schlüssel erhalten und Löschungen ausdrückbar bleiben.

**Verbesserung:** expected_version oder ETag/If-Match hinzufügen; Konflikt als 409/412 mit Diff anbieten. Neu anlegen darf nur mit Create-if-absent erfolgen. History, Autor und Wiederherstellung pro Bereich im Editor zugänglich machen. Merge nicht still automatisch durchführen.

**Abnahme:** Zwei Browser speichern dieselbe Basisversion; der zweite erhält einen Konflikt und behält seinen Entwurf. Quellen: api/config.py:267-303, services/config_store.py:22-35/135, Studio schema-form/area-doc-editor.ts und core/config-api.service.ts.

### F15 · P2 · Mehrere Studio-Einstellungen haben keine produktive Wirkung

**Status:** bekannt, Leser-Suche erneut durchgeführt. **Betrifft:** Verwaltung, Governance und erwartete Funktionalität.

retention_days ist in zwei Modellen vorhanden, aber kein automatischer Löschpfad liest es. Die Einstellung verspricht damit Verhalten, das nicht umgesetzt wird. Weitere bekannte Beispiele sind agent.safety, extra_crisis_terms, extra_pii_terms, confidence_adjustments und guide-mode.default_enabled. 01-base/rag-retrieval wird gelesen, ist aber nicht regulär registriert. Die intern verwendete Musterkennung AGENT ist nicht geschützt. Einige fachliche Vorgaben von Modell und Laufzeitfallback unterscheiden sich.

**Verbesserung:** Effektive Konfiguration aus Registry plus tatsächlichen Lesern ableiten. Nicht wirksame Felder als „nicht implementiert“ kennzeichnen oder entfernen. Für Aufbewahrung einen idempotenten, messbaren Löschjob mit Vorschau, klaren Tabellengrenzen und bewusstem Umgang mit Backups bauen. AGENT reservieren. Safety bleibt aktiv, bis eine ausdrücklich sichere Semantik beschlossen ist.

**Abnahme:** Für jedes sichtbare Feld existiert eine Effektprüfung oder eine sichtbare Erklärung; ein Aufbewahrungsjob löscht die fachlich festgelegten Datensätze. Quellen: domain/config_models/base_governance.py:66/134, domain/config_models/engine.py:119, domain/area_effects.py, docs/offene-befunde-und-todo.md.

### F16 · P2 · Ingest belegt trotz eigenem Deckel die Live-LLM-Kapazität

**Status:** neu gegenüber den gelesenen Vorgängerbefunden, reproduziert. **Betrifft:** beide Chat-Modi während RAG-Importen.

embed_many erzeugt pro Import einen eigenen Semaphore. embed_text ruft im API-Modus aber llm.embedding auf, und dieser nimmt den Semaphore live. Die Reproduktion bestätigt zwei Live-Slot-Eintritte für zwei Importabschnitte. Mehrere gleichzeitige Importe können so das Chatkontingent belegen. Ein lokaler Importdeckel ist außerdem kein globaler Importdeckel.

**Verbesserung:** Providerkapazität bewusst auf Live-Chat, Live-Query-Embedding und Hintergrund-Ingest aufteilen; zusätzlich globale Queue-/Concurrencygrenzen je Prozess und Workload. Batch-Embeddings verwenden, wo der Anbieter sie unterstützt, und Ergebnisindizes zuverlässig zuordnen. Lokale Inferenz nur nach CPU-/Qualitätsbenchmark; sie ist bereits als Alternative vorhanden und teilt sich den Rerank-Pool.

**Abnahme:** Große und mehrere parallele Importe verschlechtern die vereinbarte Chat-p95 nicht unkontrolliert; Queuezeiten getrennt messbar. Quellen: services/rag/embed.py:46-63/83-115, services/llm.py:251-303.

### F17 · P2 · Dateikonvertierung und URL-Ingest sind nur teilweise abgesichert

**Status:** fehlende Extras bekannt und DOCX-Fehler frisch reproduziert; URL-Fristen ergänzt geprüft. **Betrifft:** Studio-Wissensimport.

Das Projekt deklariert markitdown ohne Format-Extras. Ein minimaler gültiger DOCX-Test wird erkannt, scheitert aber mit FileConversionException und MissingDependencyException für docx. Das Widget-/Studioangebot darf nicht mehr Formate versprechen, als das ausgelieferte Image wirklich konvertiert. PDF/PPTX/XLSX sollten ebenfalls mit realen kleinen Fixtures geprüft werden; für diese Formate wird hier kein eigener erfolgreicher oder fehlgeschlagener Lauf behauptet.

Der URL-Pfad hat sinnvolle SSRF- und Redirect-Prüfungen. Der eigene requests-Adapter setzt jedoch keine Downloadfrist oder Byteobergrenze. Eine synchrone DNS-Prüfung läuft vor to_thread im Async-Pfad; langsames DNS kann diesen Pfad blockieren. Das Abbrechen von to_thread beendet einen bereits laufenden Netzaufruf nicht zuverlässig.

**Verbesserung:** Nur benötigte Format-Extras nach Lizenzprüfung installieren und ihre Verfügbarkeit über eine Capability-API anzeigen. URL-Download mit Connect-/Read-/Gesamtfrist, maximalen Bytes und Redirectzahl sowie geschlossener Session durchführen; DNS im geeigneten Worker oder asynchron. Embeddingmodell und Vektorversion im Bestand speichern; Reindex beim Modellwechsel erzwingen. expected_dim hat derzeit keinen produktiven Leser.

**Abnahme:** Echte unterstützte Dateien im gebauten Image konvertieren; langsame und zu große URLs brechen kontrolliert ab; Modellwechsel mischt keine unterschiedlichen Vektorräume. Quellen: backend/pyproject.toml:21, services/rag/ingest.py:38-95, services/url_safety.py:31-101, services/rag/embed.py:68.

### F18 · P2 · Nachgenerierte Schnellantworten erhalten die Chatsprache nicht

**Status:** bekannt, Aufrufstellen bestätigt. **Betrifft:** englische Sitzungen, besonders Agent-Modus mit separater QR-Generierung.

Die zwei Aufrufe in turn_assembly für normale Nachgenerierung und Host-Chip-Mischung reichen lang nicht weiter. generate_quick_replies fällt auf Deutsch zurück. Der spekulative Weg reicht die Sprache bereits durch. Dadurch kann die Antwort Englisch, die Vorschlagsgenerierung aber deutsch angeleitet sein.

**Verbesserung:** Auf allen QR-Pfaden die aufgelöste Turn-Sprache übergeben; Inline- und Fallback-Vorschläge gegen dieselben Regeln prüfen. Guide-Chips und Host-Vorgaben dabei erhalten. Sprache nicht nur über den Browser bestimmen: die bestehende UI-Locale-Weitergabe ist bereits richtig umgesetzt.

**Abnahme:** Englische Turn-/Host-Mix-/Fallbackfälle bekommen englische Anweisungen und passende Chips. Quellen: services/turn_assembly.py:229-236/303-310, services/quick_replies_llm.py:141, graph/nodes/respond.py:395.

### F19 · P1/P2 · Seiteninhalte stehen auf Anweisungsebene und destabilisieren den Promptcache

**Status:** bekannt aus dem Responses-Plan; aktuelle Promptzusammensetzung bestätigt. **Betrifft:** beide Modi, besonders Responses-Brücke.

respond_agent hängt den Seitenblock als system-Nachricht an; der Muster-Promptbuilder fügt den Seitenblock dem Systemprompt hinzu. Fremde Beschreibungen oder Volltexte stehen so neben Betreiberregeln. Das ist eine schwache Vertrauensgrenze, selbst wenn textuelle Marker existieren. Der vorhandene Fremdtext-Rahmen kann durch gleiche Endmarker im Inhalt irritiert werden; eine erfolgreiche Modellmanipulation wurde hier nicht live nachgewiesen.

Die Repository-Messung berichtet zudem, dass LiteLLM mehrere system-Blöcke als instructions verbindet und Seitenwechsel den Cache treffen können. Das ist ein vorhandener Bericht, keine neue Provider-Livemessung dieses Audits.

**Verbesserung:** Stabile Betreiberregeln und redaktionell freigegebene Anleitungen von veränderlichen Seiten-/Werkzeugdaten trennen. Daten in einem klaren User-/Tool-Kontext mit Herkunft unterbringen; nur explizit vertrauenswürdige Skills dürfen Anweisungen liefern. Native Provider-Nachrichtenstruktur prüfen, bevor die Responses-Brücke ersetzt wird. Promptcache und b-api-Antwortcache getrennt behandeln; B_API_CLEAR_CACHE nicht blind ausschalten, da der Cache-Bust einen dokumentierten Anbieterfehler umgeht.

**Abnahme:** Seitenwechsel verändert den stabilen Regelblock nicht; adversarialer Seitentext und Endmarker aktivieren keine gesperrten Werkzeuge; Antwortqualität bleibt im Vergleich erhalten. Quellen: graph/nodes/respond_agent.py:293-306, services/response_prompt_builder.py:195-215, domain/untrusted_text.py:111-126, services/llm.py:185-210, Responses-Plan vom 29.09.

### F20 · P2 · npm-Sicherheitsmeldungen sind kein CI-Gate

**Status:** bekannte Lücke, aktuelle Zahl und Abhängigkeitsstände neu geprüft. **Betrifft:** Build-/Testlieferkette und zwei Produktionspakete.

Das aktuelle Gesamtaudit meldet 24 betroffene Paketknoten. @angular/build und piscina werden als critical gezählt, hängen aber zusammen; piscina 5.2.0 ist ein Dev-Paket. Das Hersteller-Advisory GHSA-67c8-pqhq-4rmx beschreibt einen Prototype-Pollution-Gadget mit zusätzlicher Voraussetzung, dass Object.prototype bereits kontrollierbar ist; 5.3.2 ist ein korrigierter 5.x-Stand. Ein öffentlich erreichbarer RCE-Pfad im gelieferten Widget wurde nicht nachgewiesen.

Die zwei als Produktion markierten betroffenen Pakete sind @angular/router 22.1.1 und DOMPurify 3.4.13. Die Router-Meldung betrifft laut Audit SSR; dieses Projekt liefert eine SPA, keinen Angular-SSR-Server. Die DOMPurify-Meldung erfordert IN_PLACE plus entfernenden afterSanitize-Hook; der gelesene Renderer verwendet String-Sanitization ohne diesen Modus. Diese Voraussetzungen sind im betrachteten Pfad nicht vorhanden. Trotzdem sollten kompatible Korrekturversionen übernommen werden.

**Verbesserung:** Abhängigkeiten gezielt und kohärent aktualisieren; keine blinde --force-Reparatur oder automatische Downgrade-Empfehlung für den Lizenzprüfer. Ein zeitlich begrenztes, begründetes Ausnahmeverfahren und ein npm-Gate neben dem vorhandenen Python-Gate hinzufügen. Versions-/Advisoryabgleich so gestalten, dass private Paketmetadaten nur an einen freigegebenen Dienst übertragen werden.

**Abnahme:** Beide Builds, Lizenz-/Bundle-Gates und Tests bleiben grün; jede verbleibende Meldung hat Reichweitenbegründung und Ablaufdatum. Quellen: package-lock.json, .github/workflows/ci.yml:96 ff.; Hersteller-Advisory piscina und DOMPurify-Advisory im Quellenanhang.

### F21 · P2 · Studio-Identität und Betriebsabsicherung bleiben grob

**Status:** bekannte Punkte im aktuellen Stand bestätigt. **Betrifft:** Verwaltung und Deployment.

Das Studio hat einen brauchbaren BFF und SameSite=Strict/HttpOnly. Der Cookie-Token ist jedoch deterministisch aus dem gemeinsamen Passwort abgeleitet. Logout löscht den Browsercookie; einzelne gestohlene Tokens können serverseitig nicht widerrufen werden. Es fehlen persönliche Admin-Identitäten und Rollen für Lesen, Redaktion, Betrieb und destruktive Aktionen. CSP/HSTS sind in der gelesenen App-/Compose-Konfiguration nicht eingerichtet; ein vorgelagerter Proxy könnte sie dennoch setzen.

Traefik erhält den Docker-Socket mit :ro; das macht Docker-API-Operationen nicht schreibgeschützt. Backups liegen auf demselben Host, und ein erfolgreicher automatischer Restore-Test ist nicht im betrachteten Pfad vorhanden. Der Image-Workflow publiziert unabhängig vom Ergebnis des Quellen-CI; dies ist ausdrücklich dokumentiert, aber ein Release-Risiko. CORS ist standardmäßig offen; die tatsächliche Produktionsumgebung ist unbekannt.

**Verbesserung:** Individuelle Identität/RBAC, zeitlich begrenzte widerrufbare Sitzungen, actor im Auditlog; Studio-Herkunft und kompatible CSP/HSTS bewusst konfigurieren. Docker-Socketproxy mit minimalen Endpunkten, externe Backupkopie plus Restore-/Fehleralarm. Image parallel bauen, aber erst nach erfolgreichem CI für denselben Commit promoten. CORS- und wirksame Containerressourcengrenzen sichtbar prüfen.

**Abnahme:** Viewer kann nicht schreiben, Operator keine Redaktionsrechte übernehmen, Logout/Revocation sperren Tokens; fehlgeschlagenes CI verhindert Promotion. Quellen: api/studio_bff.py:54-102, api/studio_auth.py, deploy/compose.prod.yml:51/149, .github/workflows/image.yml:20/259 ff.

### F22 · P2 · Eval-Verwaltung lädt schwere Daten und startet nicht atomar

**Status:** schwere Listenabfrage bekannt; Start-Rennen aus aktuellem Code abgeleitet, nicht mit realem Postgres reproduziert. **Betrifft:** Studio-Tempo und Hintergrundkosten.

list_runs verwendet select(EvalRun), obwohl die Listenansicht nur Metadaten braucht. Dadurch werden auch große JSONB-Konversationen geladen und über den Treiber dekodiert. Der Startwächter prüft „kein running vorhanden“ vor dem späteren Insert; ohne gemeinsame DB-Sperre oder passende Constraint können zwei konkurrierende Starts beide passieren. Hintergrundtasks sind prozesslokal; nach Absturz räumt der Startpfad alte running-Zeilen erst nach zwei Stunden auf. Der bestehende Cancelpfad hat dagegen bereits eine Taskregistry und DB-Prüfpunkte, also keineswegs gar keinen Abbruch.

**Verbesserung:** Nur benötigte Spalten projizieren, Detaildaten separat laden, Cursor-Pagination und adaptives Polling verwenden. Startreservierung atomar in der DB oder über Lease/Fencing durchführen. Heartbeat, Eigentümer, Statusübergänge und Wiederanlaufentscheidung für Jobs speichern. Agent-Tester und lange Studio-Anfragen benötigen ebenfalls Abbruch-/Statusunterstützung; firstValueFrom alleine bietet den Aufrufern kein Cancel-Signal.

**Abnahme:** Zwei gleichzeitige Starts ergeben genau einen Lauf; Liste liest keine Transkripte; Restart und Abbruch über eine andere Replik hinterlassen eindeutige Endstände. Quellen: services/eval/queries.py:26-59, services/eval/run_store.py:75-101, generative_run.py:86-105, golden_run.py:128-145, obs/tasks.py, Studio core/studio-api.service.ts.

## 5. Prozess- und Antwortgeschwindigkeit

### 5.1 Muster-Modus

Der vorhandene Inline-Schnellantwortweg ist bereits Standard. Ihn nochmals „einzuführen“ wäre keine Verbesserung. Im Repository-Plan vom 30.09. wird für vier Fragen mit je zwei Wiederholungen eine Verkürzung von 15,9 auf 9,1 s Median berichtet. Diese kleine Stichprobe ist ein guter Hinweis auf die Wirkung vermiedener Zusatzaufrufe, aber kein Produktions-p95.

| Maßnahme | Konkreter Ansatz | Nutzen / Einschränkung |
| --- | --- | --- |
| Klassifikationsprompt verkleinern | Bei gleichem, ausdrücklich gewähltem Modell redundant wiederholte Erläuterungen entfernen; stabile Taxonomie vorne, Turn-Kontext hinten | Weniger Prefill-/Eingabetoken; Golden-Vergleich schützt Klassifikationsqualität |
| RAG früher vorbereiten | Query-Embedding parallel zum Assess vorbereiten; echte Abfrage erst nach gültiger Quellenwahl oder nur sicher vorhersehbare Always-Bereiche | Überlappt Wartezeit; keine unzulässige Wissensquelle vorweg aktivieren |
| SQL statt Session-Parallelität | Mehrere RAG-Bereiche in eine geeignete SQL-Abfrage mit Bereichsquoten bündeln | Spart Roundtrips; asyncio.gather auf einer AsyncSession würde einen reparierten Fehler zurückbringen |
| Gezielte Fast Paths | Vorhandene Direktaktionen, Pagination, Tour und bestätigte Filteränderungen ausbauen | Kein Modell für rein deterministische Bedienaktionen; Policy-/Authchecks trotzdem zentral |
| MCP-Aufwärmung erhalten | Bestehendes Vokabular-Prewarm und TTL-Caches behalten, Singleflight ergänzen | Reduziert kalte identische Abrufe ohne zusätzliche Modellaufrufe |
| Generationsbudget passend | Modellabhängige Ausgabebegrenzung und passende Verbosity nach Antwortart | Weniger lange Ausgaben; volle Unterrichtsdokumente separat und vollständig liefern |

Ein anderes Klassifikatormodell ist im gelesenen Plan ausdrücklich abgewählt. Die erste Optimierungsrunde sollte diese Entscheidung respektieren. Ein späterer Modellvergleich wäre eine gesonderte Option, keine Voraussetzung für schnellere Muster-Turns.

### 5.2 Agent-Modus

| Maßnahme | Konkreter Ansatz | Nutzen / Einschränkung |
| --- | --- | --- |
| Agent-Inline-QR aktivieren | Master-Skill und Vorlage gemeinsam anpassen, dann AGENT_INLINE_QUICK_REPLIES=1 | Vorhandener Weg spart den nachgelagerten Modellaufruf; im Repository 12,2 auf 6,8 s Median bei 8 Turns berichtet |
| Werkzeugkatalog gezielt anbieten | Deterministische Capabilities und Aufgabentypen, ggf. gestufte Tool-Discovery; Freigabe immer F03 | Weniger Schema-/Prompttoken und Fehlwahlen; nötige Fähigkeiten müssen erreichbar bleiben |
| Unabhängige Lese-Tools parallel | Begrenzte Parallelität mit Ergebnissen pro tool_call_id und stabiler Reihenfolge | Spart serielle Netzwartezeit; Writes und abhängige Calls bleiben geordnet |
| Verbindung wiederverwenden | HTTP-Pooling oder per-Run-MCP-Session nach Server und Authidentität getrennt | Weniger TLS/Initialize-Roundtrips; keine global geteilte Sitzung zwischen Identitäten |
| Wiederholungsschleifen erkennen | Kurzes Fenster aus Aufrufschlüssel plus Ergebnis/Fortschritt statt nur letztem Call | Erfasst A-B-A-B-Loops; legitime Wiederholung nach geändertem Bestand zulassen |
| Laufhistorie begrenzen | Budgetierter Kontext, kurze belegte Ergebnisreferenzen, unveränderliche IDs und Quellen erhalten | Weniger erneute Eingabetoken je Runde; keine blinde Volltextkürzung |

### 5.3 Gemeinsame Laufzeitsteuerung

Queuezeit, Providerzeit, Werkzeugzeit, DB-Poolwartezeit und End-to-end-Latenz müssen getrennt messbar sein. Die vorhandenen LLM-ms enthalten Queue und Transport zusammen. Ergänzen: Zeit bis zum ersten sichtbaren Text, p50/p95/p99 je Engine und Turnart, Modellaufrufe/Turn, Retryquote, Cachequote, Deadline-/Cancelquote und Kosten pro erfolgreich erledigter Aufgabe.

Eine Replik mehr erhöht zugleich mögliche Providerparallelität, DB-Verbindungen und Kosten. Deshalb Concurrency aus einem Kapazitätsbudget ableiten, anstatt Repliken nur anhand der CPU-Zahl zu erhöhen. Warteschlangen begrenzen und Überlast als 429/503 mit Retry-After ausdrücken. Jobs mit eigener Session dürfen nicht die Request-Session nebenläufig benutzen. Transaktionen kurz halten und teure Netzphasen außerhalb offener DB-Transaktionen planen.

Fast-/Priority-Tiers sollten gegen Kosten pro erfolgreich erledigter Aufgabe bewertet werden. Der Repository-Plan berichtet für fast nur 9,1 auf 7,7 s, nennt aber deutlich höhere Tokenpreise und Provider-/Regionsgrenzen. Diese Angaben wurden hier nicht aktuell gegen den Anbieter nachgemessen. Eine allgemeine Aktivierung ist daher keine begründete Sparmaßnahme.

## 6. Antwortqualität gezielt verbessern

**Quellenbezug prüfen.** Jede zitierte nodeId oder RAG-Passage muss aus einem tatsächlich erfolgreichen Abruf stammen. Quellenbezeichnung, URL, Passage-ID, Versionsstand und relevante Metadaten gemeinsam führen. Bei Teilabruf oder Fehlern die geprüfte Teilmenge klar benennen. Das gilt besonders für Prüfaufträge im Studio und Maschinenresultate.

**Suche fachlich bewerten.** HNSW, Query-Embedding-Wiederverwendung und Rerank sind bereits vorhanden. Als nächster Ausbau bietet sich eine lexikalische Suche neben Vektoren mit nachvollziehbarer Fusion an, besonders für exakte Titel, Fachbegriffe und IDs. Bereichsquoten und Metadaten wie Sprache, Fach, Stufe, Materialtyp und Lizenz vor bzw. beim Ranking berücksichtigen. Den bestehenden Hybrid-Kartenpfad nicht mit einer noch fehlenden lexikalischen RAG-Suche verwechseln.

**Struktur verbindlich machen.** F10/F11 beheben, Tool-Outcomes statt Freitextheuristiken stärker verwenden und Trefferzahlen aus strukturierten Metadaten ableiten. Eine additive Confidence-Heuristik ist kein kalibrierter Wahrheitswert; sie sollte nicht als objektive Antwortsicherheit dargestellt werden.

**Kontext stabil und vollständig halten.** Zusammenfassungen versionieren; Referenzen auf tatsächlich gezeigte Karten und Dokumente erhalten. Lange Volltexte, die die Person angefordert hat, vollständig im Dokumentkanal ausgeben, während das Modell nur die benötigten Ausschnitte plus Referenz erhält. Der Agent trennt Ergebnis und Begleitprosa bereits: diese Trennung erhalten.

**Grenzfälle zuerst evaluieren.** Deutsche und englische Rückfragen, mehrdeutige Persona, fehlende Treffer, veraltete Quellen, falsche Materialstufe, widersprüchliche Fakten, Prompt-Injection im Material, nicht angebotene Tools, schemawidrige Ergebnisse und Zustimmung/Abbruch gehören in dasselbe Vergleichsset für beide Modi.

Die bestehenden Golden-Flows und Engine-Vergleiche im Studio sind eine gute Grundlage. Qualität nicht nur von einem LLM-Judge bewerten lassen: harte Regeln für Quellengültigkeit, Toolfreigabe, Materialmetadaten, Schreibwirkungen und Schemaerfüllung ergänzen. Eine zusätzliche Qualitätsmodellrunde pro Live-Antwort wäre zunächst teuer und langsam; gezielte Offline-Auswertung ist hier die bessere erste Investition.

## 7. Kosteneinsparung und Kostenkontrolle

| Hebel | Umsetzung | Was gemessen werden muss |
| --- | --- | --- |
| Zusätzliche QR-Calls vermeiden | Agent-Inline-Weg nach Skill-Abgleich; vorhandenen Muster-Weg erhalten | Anteil Inline/Fallback und eingesparte Modellaufrufe |
| Stabile Prompts | Regeln/Schema vorne stabil; dynamische Daten separat | uncached/cached Eingabetoken je Folgeturn und Seite |
| Weniger Werkzeug-/Ergebnistoken | Katalog stufenweise, bestehende Result-Redaktion ausbauen, Karten nicht als Volltext doppeln | Prompttoken pro Runde, Fehlwerkzeugquote, Ergebnisvollständigkeit |
| Fehlerkosten sichtbar machen | F09-Ledger inklusive API-Aufträgen, Import, Fehler, Retry und Abbruch | Verbrauch gegen Providerabrechnung abgleichen; unbekannte Beträge sichtbar |
| Harte Ressourcengrenzen | F04, idempotente Turns und Tages-/Auftragsbudget | Kosten pro erfolgreicher Aufgabe, Abbruchquote, nicht nur Kosten pro Anfrage |
| Embeddings bündeln | Batch, Dokumenthash, Query-Cache mit Modell-/Bestandsversion | Callzahl und Import-/Live-p95; lokale CPU-Kosten einbeziehen |
| Offline-Arbeit anders behandeln | Generierung/Judge in Hintergrundqueue; günstigeres Modell oder Batch nur nach Qualitätsvergleich | Qualitätsdifferenz und Vollkosten einschließlich Wartezeit |

Für die Schätzung gilt grundsätzlich: ungecachte Eingabetoken mal Eingabepreis plus gecachte Eingabetoken mal Cachepreis plus Ausgabetoken mal Ausgabepreis, jeweils pro Million. Reasoning-Token nicht nochmals berechnen, wenn sie im Providerfeld completion_tokens bereits enthalten sind. Währung, Preisversion und Service-Tier explizit speichern. Die bereits vorhandene Decimal-Rechnung und Kennzeichnung unbekannter Modellpreise erhalten.

Kein pauschaler Antwortcache für personalisierte, aktuelle oder schreibende Aufgaben. Ein zulässiger Cache braucht mindestens Identität/Rechte, Modell-/Promptversion, Wissensversion, Sprache und relevante Parameter. Der bestehende b-api-Cache-Bust bleibt bestehen, bis der Anbieterpfad mit korrektem Schlüssel und Leerantwortfällen verifiziert ist. Native Promptwiederverwendung ist ein anderer Mechanismus als das Wiederverwenden kompletter Antworten.

## 8. Studio: Funktionalität und Verwaltbarkeit

| Ergänzung | Konkrete Oberfläche / Funktion | Priorität |
| --- | --- | --- |
| Wirksame Konfiguration | Seed, DB, Env-Override und effektiven Wert nebeneinander; Modus, Modell, Limits, Master-Skill-Hash und Replikversion sichtbar | P1/P2 |
| Sicherer Editor | Version/ETag, Konflikt-Diff, Autor, History und Entwurf behalten; abhängige Referenzen validieren | P2 |
| Atomarer Restore | Vollständigen Diff und Fehler vor dem Apply anzeigen; Merge/Exact erläutern; automatischen Rückwegsnapshot erhalten | P1 |
| RAG-Arbeitsliste | Importstatus je Dokument/Chunk, Fehler wiederholen, Duplikate erkennen, Embeddingmodell und Aktualität zeigen | P1/P2 |
| Retrieval-Prüftisch | Anfrage, Bereich, gefundene Passage, Score/Rerank, Metadaten und tatsächlich verwendete Quellen vergleichen | P2 |
| Agent-Prüftisch | Gespeicherte Tests mit Engine, Sprache, Toolmodus und Budget; Fortschritt, Stopp und Usage-Ergebnis statt langem stummen POST | P2 |
| Kosten-/Tempoansicht | p95/TTFT und Kosten nach Engine, Endpoint, Phase, Nutzer-/Jobkategorie; unbekannte Kosten kennzeichnen | P2 |
| Rollen und Auditspur | Viewer, Redaktion, Operator, Admin; actor und konkrete Änderung statt bloß studio als Urheber | P2 |
| Job-Verwaltung | Heartbeat, Eigentümer, Budget, Teilresultate und eindeutiger Cancelstatus; aktive Jobs beim Navigieren wiederfinden | P2 |
| Leichtere Listen | Nur Metadaten laden, Cursor/Filter; Detailtranskript erst beim Öffnen; Polling bei unsichtbarem Tab drosseln | P2 |
| Veröffentlichung von Konfiguration | Entwurf, geprüfter Snapshot, Vergleichslauf und gezielte Promotion/Zurücksetzung auf Version | P3 |

Nicht als neue Lücken behandeln: Studio hat bereits Kostenansichten, Engine-Vergleich, Golden-/generative Läufe, Master-Skill-/Toolübersichten, Schemaformulare, Widget-Vorschau, Werks-/Auslieferungsstand und Backups. Die Aufgabe ist, diese Funktionen konsistent, überprüfbar und bei Parallelität sicher zu machen.

Konfiguration sollte pro Turn einen konsistenten Versionssatz besitzen. Sonst kann ein Turn einen alten Safety-Wert und einen neuen Werkzeugkatalog kombinieren. Ein unveränderlicher Config-Snapshot am Turnanfang macht Debug, Regression und Rollback nachvollziehbar. Größere Dateien nach Verantwortlichkeiten aufteilen, besonders agent_loop/respond_agent/tool_loop, ohne bereits vorhandene Paritäts- und Vertragszusage beiläufig umzuschreiben.

## 9. Widget: sinnvolle Ergänzungen

| Ergänzung | Warum sie hier hilft | Umsetzungshinweis |
| --- | --- | --- |
| Stopp und Wiederaufnahme | Lange Agent-Aufgaben brauchen Kontrolle; heutiger Stream kann weiterlaufen | F02/F04 zuerst, stabile turn_id; schon ausgeführte Writes nicht als rückgängig darstellen |
| Sichtbarer Textstrom | Phasenmeldungen überbrücken Wartezeit, liefern aber noch keinen Antwortinhalt | Textdeltas puffern, etwa 80-150 ms als Startwert; Plaintext inkrementell, Markdown blockweise/final; keine internen Reasoning-Inhalte anzeigen |
| Präzise Fehleraktion | 429, Offline, Deadline und Validierungsfehler erfordern verschiedene Reaktionen | Retry-After/Status respektieren; Wiederaufnahme statt blindem neuen POST; Eingabe für Korrektur behalten |
| Belegte Quellenbox | Materialauswahl und Antwortqualität werden überprüfbar | Bereits vorhandene Karten/Links um Passage, Aktualität und Auswahlgrund ergänzen, nur aus echten Abrufen |
| Feedback pro Antwort | Fehler nach Engine und Aufgabe gezielt beheben | Hilfreich/nicht hilfreich plus Grund; Turn-/Configversion referenzieren, nicht ungefragt komplette sensible Inhalte erfassen |
| Eindeutige Schreibvorschau | Vertrauen und Schutz vor versehentlichem Kuratieren | Ziel, Änderung, Identität, Ablauf sowie Bestätigen/Verwerfen anzeigen; mit F05 verbunden |
| Verlauf und Export | Unterrichtsdokumente und Quellen sollen nach Refresh wieder nutzbar sein | Vorhandene Druck-/Dokumentfunktion erhalten; optional Gesprächsexport und vollständige Wiederherstellung strukturierter Ergebnisse |
| Zugänglicher Laufstatus | Phasenwechsel und Ergebnisse sollen auch ohne Sichtkontakt verständlich sein | Persistente Live-Region, begrenzte Ansagen, Tastatur-/Fokusführung in Shadow DOM; mit realem Screenreader prüfen |

Text-Streaming war bereits vorhanden bzw. versucht und wurde wegen Flackerns zurückgenommen; send-message.ts ignoriert text_delta ausdrücklich. Der Ausbau muss deshalb die Darstellung verbessern und Endergebnis/Teiltext sauber abgleichen. Er wird die Zeit bis zur fertigen Antwort nicht automatisch verkürzen. Für Agent-Werkzeugrunden sollen weiterhin verständliche Phasenmeldungen erscheinen, bevor überhaupt nutzergeeigneter Text entsteht.

Schon vorhanden sind unter anderem Deutsch/Englisch, Spracheingabe/-ausgabe, Karten und Facetten, Dokumentausgabe und Druck, Host-Bridge, persönliche Anmeldung mit PKCE/Ticket und vorbereitete Schreibvorgänge. Diese Funktionen müssen nicht neu erfunden werden. Die erste Widget-Runde sollte sich auf Kontrolle, Wiederaufnahme, Textstrom und präzise Fehler konzentrieren.

Für das Widget bleibt das Single-File-Artefakt wichtig. Vor weiteren Bibliotheken Bundleanteile messen; doppelte Inhalte und unbenutzte Imports entfernen. Eine Umstellung auf Split-Bundles nur als ausdrücklich andere Einbettungsform planen, weil sie den bestehenden Ein-Datei-Vertrag verändern würde.

## 10. Empfohlene Umsetzungsfolge

| Paket | Inhalt | Ergebnis / Abhängigkeit | Aufwandklasse |
| --- | --- | --- | --- |
| A · Korrektheit zuerst | F03 Dispatcher, F04 Frist/Budget, F06 Ingest, F10/F11 Validierung, öffentliche Fehlertexte vereinheitlichen | Verlässliche Ausführung; neue Negativtests | mittel, mehrere getrennte PRs |
| B · Turn-Lebenszyklus | F01, F02, F05; turn_id, Cancel/Resume und einmalige Schreibwirkung | Grundlage für Mehrrepliken, Stop-Widget und Agent-Kuration | groß |
| C · Redaktion verlässlich | F07, F08, F12, F14/F15; atomare Änderungen und Versionsbezug | Studio zeigt den tatsächlich wirksamen Stand | mittel bis groß |
| D · Tempo ohne Modellwechsel | Agent-Inline-QR plus Skill, F18 Sprache, F16 Kapazität, SQL-/MCP-Pooling und Singleflight | Weniger Calls und Queuezeit; gleicher Funktionsumfang | klein bis mittel je Teil |
| E · Messung und Qualität | F09 Ledger, Quellenprüfungen, gemeinsame Evalfälle, Studio-p95/TTFT | Belastbare Qualitäts-/Kostenentscheidung pro Engine | mittel |
| F · Bedienung und Betrieb | Textstream, Stop/Resume, Feedback; F20-F22, RBAC, Backup-/Releaseabsicherung | Schnellere Wahrnehmung, bessere Verwaltung und Releases | mittel bis groß |

Die Aufwandklassen sind relative Planungsgrößen, keine verbindlichen Schätzungen. Für kleine Einzelkorrekturen ist typischerweise ein enger Patch möglich; Job-/Lock-/Freigabearchitektur und RBAC benötigen Entwurf und Integrationsprüfung. A-C sollten vor einem Ausbau schreibender Multi-Replika-Funktionen abgeschlossen sein. Der Agent-Inline-QR-Weg kann als eigener kleiner Tempo-Patch parallel vorbereitet werden, solange Master-Skill und Golden-Nachweis berücksichtigt werden.

Änderungen an turn_id, Kostenmetadaten, Versions-CAS und Jobstatus können den eingefrorenen API-Vertrag betreffen. Dafür eine bewusst kompatible Erweiterung oder versionierte API planen; das Vertrags-Gate nicht einfach regenerieren, um unbeabsichtigte Änderungen grün zu machen. Golden-/Live-Läufe mit realen Schreibwirkungen bleiben explizit kontrollierte Staging-Arbeit.

## 11. Prüfplan für die nächste Implementierungsrunde

| Bereich | Wesentliche Prüfung | Erfolgskriterium |
| --- | --- | --- |
| Zwei Repliken | Gleiche Session, gleichzeitige Turns und Schreibfreigaben | Kein Zustandsverlust, keine doppelte Wirkung |
| Streamlebenszyklus | Disconnect/Cancel vor und nach Toolwirkung, Fallback und Wiederaufnahme | Keine unverwalteten Tasks, ein logischer Turn |
| Toolpolitik | Modell ruft nicht angebotene Tools und virtuelle Tools auf | Kein unerlaubter Dispatcher-/MCP-Aufruf |
| Laufbudget | Langsamer Provider/Tool, Retry, volle Queue, letzte Runde zu teuer | Vertrag eingehalten oder eindeutig als überschritten markiert |
| Konfiguration | Zwei Editoren, Reconnect, verspäteter Refresh, ungültiger Restore | Konflikt statt Überschreiben; alle Repliken letzte Version |
| RAG | Fehlende Embeddings, All-fail, Dokumentduplikat und Modellwechsel | Texte erhalten, richtige Zähler, reparierbarer Zustand |
| Struktur | Ungültige Klassifikation, Ergebnis und Schema | Gültiger Fallback oder klarer Vertragsfehler |
| Studio | Echter Login, Rollen, Edit-Konflikt, Restore, Job-Abbruch | Wichtigste Wege browserübergreifend bedienbar |
| Widget | Streaming ohne Flackern, Tastatur/Screenreader, Offline/429/Resume | Lesbarer Verlauf, präzise Aktion, keine Doppelverarbeitung |
| Qualität und Kosten | Dieselben Aufgaben in beiden Modi, DE/EN, kalt/warm, gleiche Konfigversion | Harte Funktionschecks plus Qualität, p95, TTFT und Kosten pro Erfolg |

Für einen Latenzvergleich mindestens mehrere Dutzend repräsentative Fälle je Kategorie und Wiederholungen verwenden, getrennt nach kalten/warmen Caches und kurzer Antwort/Dokument/Werkzeugkette. Loadtest auf isoliertem Staging mit realistischen Parallelitäten, während zusätzlich ein großer RAG-Import läuft. Keine Prozentersparnis aus der 8-Turn-Stichprobe als allgemeines Ziel versprechen.

CI gezielt erweitern: Valkey-Dienst für Cluster-/Limiterprüfungen, echte Studio-E2E und Reproduktionsfälle an den Nahtstellen. Die ALT-Paritätsprüfungen benötigen weiterhin das externe Referenzrepository; entweder zuverlässig bereitstellen oder die verbleibende Nichtabdeckung ausdrücklich führen. Unit-Testzahl allein ersetzt diese Integrationsprüfungen nicht.

## 12. Reproduktionsbelege und Quellen

### 12.1 Isolierte Belege

| Nr. | Probe | Beobachtung |
| --- | --- | --- |
| 1 | SSE generator close | Task läuft nach aclose weiter; Cleanup noch nicht ausgeführt |
| 2 | SSE consumer cancel | Consumer-Abbruch beendet den Arbeitstask nicht |
| 3 | SSE error disclosure | Dummy-Geheimnis und interner Pfad erscheinen im öffentlichen Fehlerframe |
| 4 | Agent deadline | 5-s-Frist, Ergebnis bei 6 s, stop_reason=text |
| 5 | Agent token budget | Budget 1.000, Verbrauch 1.500, stop_reason=text |
| 6 | Agent tool allowlist | Leerer angebotener Katalog, trotzdem Suchwerkzeug ausgeführt |
| 7 | Agent result schema | Integer-Schema akzeptiert String bad |
| 8 | RAG partial ingest | Zwei Chunks gemeldet, einer gespeichert; zweiter Text verloren |
| 9 | Config refresh order | Neuere Version 2 wird durch verspätete Version 1 überschrieben |
| 10 | Snapshot validation | Ungültiger Engine-Modus vom ZIP-Parser akzeptiert |
| 11 | Snapshot partial restore | Erster Bereich nach Fehler im zweiten schon geschrieben |
| 12 | Snapshot unsafe key | Schlüssel ../bad vom Parser akzeptiert |
| 13 | MCP cache server scope | Serverwechsel A zu B liefert A ohne Abruf von B |
| 14 | Classifier salvage | signals=str, entities=list, intent_confidence=99 akzeptiert |
| 15 | Ingest uses live LLM capacity | Zwei Importchunks nehmen zwei Live-Slots |
| 16 | Config export path boundary | Kontrollierte Datei außerhalb des gewählten Exportordners erzeugt |
| 17 | DOCX ingestion converter | DOCX erkannt; erforderliche optionale Abhängigkeiten fehlen |

Die Fehlertextprobe enthält nur einen frei erfundenen Dummywert. Es wurden keine realen Geheimnisse abgerufen oder offengelegt. Die Exportprobe arbeitet ausschließlich innerhalb eines eigenen temporären Verzeichnisses.

**Zusätzliche Anlagen der zugehörigen PDF-Fassung (`Audit_edu_chatbot_sc_2026-10-03.pdf`):** `probes.py`, `probe-results.json`, `source-manifest.json` und `audit-evidence.json`. Das Skript mit den gesperrten Backend-Abhängigkeiten ausführen; externe Grenzen werden gepatcht. Beispiel vom Repositoryverzeichnis: backend/.venv/bin/python /pfad/zu/probes.py. In einer Prüfumgebung mit SOCKS-Proxy kann zusätzlich socksio nötig sein; dies war eine reine Prüfwerkzeug-Ergänzung und kein Patch des Repository-Lockfiles.

### 12.2 Quelle zum geprüften Stand

Alle Codeverweise im Bericht gelten für den oben genannten Commit. Die Dateiliste unten enthält anklickbare, auf diesen Commit fixierte Links. Lange Dateien sind nicht pauschal als vollständig zeilenweise geprüft zu verstehen; der Audit konzentriert sich auf relevante Funktionen und Datenflüsse.

**Turn, SSE und Zustand**

- [backend/src/boerdi/api/chat.py:82](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/chat.py#L82)
- [backend/src/boerdi/api/sse.py:55](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/sse.py#L55)
- [backend/src/boerdi/api/session_locks.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/session_locks.py#L1)
- [backend/src/boerdi/db/locks.py:13](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/db/locks.py#L13)
- [backend/src/boerdi/graph/build.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/graph/build.py#L1)
- [backend/src/boerdi/api/deps.py:31](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/deps.py#L31)

**Agent, Freigabe und Ausgabe**

- [backend/src/boerdi/services/agent_loop.py:198](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/agent_loop.py#L198)
- [backend/src/boerdi/services/agent_run.py:78](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/agent_run.py#L78)
- [backend/src/boerdi/services/agent_tools.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/agent_tools.py#L1)
- [backend/src/boerdi/services/agent_write.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/agent_write.py#L1)
- [backend/src/boerdi/services/tool_loop.py:594](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/tool_loop.py#L594)
- [backend/src/boerdi/services/write_approval.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/write_approval.py#L1)
- [backend/src/boerdi/api/agent.py:35](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/agent.py#L35)
- [backend/src/boerdi/api/schemas_agent.py:29](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/schemas_agent.py#L29)
- [backend/tests/test_agent_schreib_abnahme.py:209](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/tests/test_agent_schreib_abnahme.py#L209)
- [backend/src/boerdi/services/outcome_service.py:36](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/outcome_service.py#L36)

**Wissen, LLM und Qualität**

- [backend/src/boerdi/services/rag/ingest.py:98](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/rag/ingest.py#L98)
- [backend/src/boerdi/services/rag/embed.py:83](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/rag/embed.py#L83)
- [backend/src/boerdi/services/rag/retrieval.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/rag/retrieval.py#L1)
- [backend/src/boerdi/services/url_safety.py:31](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/url_safety.py#L31)
- [backend/src/boerdi/services/llm.py:130](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/llm.py#L130)
- [backend/src/boerdi/services/classify.py:109](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/classify.py#L109)
- [backend/src/boerdi/domain/pattern_engine.py:263](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/domain/pattern_engine.py#L263)
- [backend/src/boerdi/domain/route_head.py:21](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/domain/route_head.py#L21)
- [backend/src/boerdi/services/turn_assembly.py:229](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/turn_assembly.py#L229)
- [backend/src/boerdi/services/quick_replies_llm.py:141](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/quick_replies_llm.py#L141)
- [backend/src/boerdi/graph/nodes/respond_agent.py:293](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/graph/nodes/respond_agent.py#L293)
- [backend/src/boerdi/services/response_prompt_builder.py:195](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/response_prompt_builder.py#L195)
- [backend/src/boerdi/domain/untrusted_text.py:111](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/domain/untrusted_text.py#L111)

**Konfiguration, Cache und Usage**

- [backend/src/boerdi/api/config.py:267](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/config.py#L267)
- [backend/src/boerdi/services/config_store.py:78](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/config_store.py#L78)
- [backend/src/boerdi/api/config_snapshots.py:44](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/config_snapshots.py#L44)
- [backend/src/boerdi/services/snapshots.py:66](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/snapshots.py#L66)
- [backend/src/boerdi/services/seed_io.py:107](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/seed_io.py#L107)
- [backend/src/boerdi/db/notify.py:81](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/db/notify.py#L81)
- [backend/src/boerdi/services/guide_qr_injector.py:231](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/guide_qr_injector.py#L231)
- [backend/src/boerdi/services/mcp/tool_cache.py:102](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/mcp/tool_cache.py#L102)
- [backend/src/boerdi/services/mcp/client.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/mcp/client.py#L1)
- [backend/src/boerdi/services/mcp/transport.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/mcp/transport.py#L1)
- [backend/src/boerdi/services/usage_store.py:44](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/usage_store.py#L44)
- [backend/src/boerdi/services/usage_analytics.py:85](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/usage_analytics.py#L85)
- [backend/src/boerdi/domain/config_models/engine.py:58](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/domain/config_models/engine.py#L58)
- [backend/src/boerdi/domain/config_models/base_governance.py:66](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/domain/config_models/base_governance.py#L66)
- [backend/src/boerdi/settings.py:312](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/settings.py#L312)

**Studio, Widget und Betrieb**

- [frontend/projects/ui/src/shell/send-message.ts:72](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/ui/src/shell/send-message.ts#L72)
- [frontend/projects/ui/src/stream/stream-client.ts:115](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/ui/src/stream/stream-client.ts#L115)
- [frontend/projects/ui/src/shell/chat-shell.component.ts:830](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/ui/src/shell/chat-shell.component.ts#L830)
- [frontend/projects/ui/src/markdown/markdown-renderer.ts:152](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/ui/src/markdown/markdown-renderer.ts#L152)
- [frontend/projects/studio/src/app/core/studio-api.service.ts:31](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/studio/src/app/core/studio-api.service.ts#L31)
- [frontend/projects/studio/src/app/core/agent-api.service.ts:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/studio/src/app/core/agent-api.service.ts#L1)
- [frontend/projects/studio/src/app/schema-form/area-doc-editor.ts:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/studio/src/app/schema-form/area-doc-editor.ts#L1)
- [frontend/projects/studio/src/app/views/agent-tester.component.ts:108](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/projects/studio/src/app/views/agent-tester.component.ts#L108)
- [backend/src/boerdi/api/studio_auth.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/studio_auth.py#L1)
- [backend/src/boerdi/api/studio_bff.py:54](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/api/studio_bff.py#L54)
- [backend/src/boerdi/services/eval/queries.py:26](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/eval/queries.py#L26)
- [backend/src/boerdi/services/eval/run_store.py:75](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/services/eval/run_store.py#L75)
- [backend/src/boerdi/obs/tasks.py:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/src/boerdi/obs/tasks.py#L1)
- [deploy/compose.prod.yml:131](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/deploy/compose.prod.yml#L131)
- [.github/workflows/ci.yml:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/.github/workflows/ci.yml#L1)
- [.github/workflows/image.yml:20](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/.github/workflows/image.yml#L20)
- [backend/pyproject.toml:21](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/backend/pyproject.toml#L21)
- [frontend/package-lock.json:1](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/frontend/package-lock.json#L1)


### 12.3 Quellen für bekannte Befunde und interne Messungen

- [Offene Befunde und Todo](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/docs/offene-befunde-und-todo.md)
- [Audit 29.09.2026](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/docs/audits/2026-09-29-audit.md)
- [Responses, Systemteil und Cache](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/docs/plans/2026-09-29-responses-systemteil-und-cache.md)
- [Muster-Kette und Agent-Inline-Messung](https://github.com/janschachtschabel/edu-chatbot-sc/blob/610abec6e4a67baf6d08721149b81168a41a89a7/docs/plans/2026-09-30-muster-kette-zeit.md)
- [CI-Lauf des geprüften Commits](https://github.com/janschachtschabel/edu-chatbot-sc/actions/runs/36843818440)

Die internen Pläne und Audits wurden mit dem aktuellen Code abgeglichen. Als bereits behoben dokumentierte Punkte werden nur dann erneut genannt, wenn der aktuelle Pfad weiterhin ein konkretes Problem zeigt. Die 9,1-/6,8-s-Werte stammen aus dem Kette-Plan, nicht aus einer eigenen Anbieter-Livemessung.

### 12.4 Externe Abhängigkeitsreferenzen

- [Piscina: Hersteller-Advisory GHSA-67c8-pqhq-4rmx](https://github.com/piscinajs/piscina/security/advisories/GHSA-67c8-pqhq-4rmx)
- [DOMPurify: Advisory GHSA-p98j-92pf-mc4p](https://github.com/advisories/GHSA-p98j-92pf-mc4p)
- [Angular-Router: Meldung GHSA-ff3f-86qr-9cv3 aus npm-Metadaten](https://github.com/advisories/GHSA-ff3f-86qr-9cv3)

Das Angular-Advisory war über die Webabfrage nicht zusätzlich abrufbar; seine Einordnung hier stützt sich auf den Titel und Versionsbereich im bereits vorliegenden npm-Audit. Die Herstellerquelle von Piscina bewertet die Meldung als High, das npm-/GitHub-Datenbankergebnis als Critical. Deshalb wird die Scannerzahl wiedergegeben und die tatsächliche Voraussetzung separat bewertet.

---

**Empfohlener erster Arbeitsauftrag:** gemeinsamer Werkzeug-Dispatcher, belastbare Laufgrenzen und verlustfreier RAG-Import mit Tests; anschließend Turn-Lebenszyklus und Konfigurationsversionen. Den vorhandenen Agent-Inline-QR-Weg danach mit angepasstem Master-Skill freigeben und beide Modi am selben Aufgabenbestand nachmessen.
