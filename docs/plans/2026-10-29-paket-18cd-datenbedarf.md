# Paket 18C/18D — Welche Daten brauchen wir wirklich?

Stand 2026-10-29. Entscheidungsgrundlage zu [Paket 18](2026-10-28-paket-18-audit-und-fehlerbehandlung.md):
Wo kann der Chatbot auf Daten verzichten, und wo kostet der Verzicht eine Funktion? Geprüft am Code
(Backend, Widget, Studio, Evaluation, Golden-Läufe), nicht geschätzt.

**Ampel:** 🟢 weglassen ohne Folgen · 🟡 weglassen, wenn ein kleiner Ersatz kommt · 🔴 wird gebraucht

## Kurz gesagt

- **Logs (18C):** Kein Teil der App liest Logs. Das Studio zeigt Daten aus der Datenbank, nicht
  aus den Logs. Inhalte aus den Logs zu nehmen kostet also **keine Funktion**, nur Bequemlichkeit
  bei der Fehlersuche. Die lässt sich ersetzen: Speichert der Chatbot die **Trace-ID** mit jedem
  Zug, führt eine Logzeile direkt zum Gespräch im Studio (30 Tage).
- **Debug-Block (18D):** Er ist **zur Hälfte Funktion**. Das Widget braucht einige Felder, vor
  allem beim Neuladen eines Gesprächs. Der Rest ist Diagnose für Studio und Auswertung und kann
  hinter eine Freigabe. Ganz abschalten würde das Widget beschädigen.
- **Fehlertexte (18D):** Niemand wertet Fehlerklasse oder Anbietertext aus. Weglassen ist 🟢.

## 1 Logs (18C)

Rund 50 Logaufrufe auf INFO/WARNING tragen Inhalte. Wer heute nur die Logs hat, sieht dort, was
gefragt und geantwortet wurde. Nach 18C sieht er Länge, Kennungen und Trace-ID; den Inhalt findet,
wer Zugang zum Studio hat.

| Was steht im Log | Stellen | Wofür heute | Ersatz | Ampel |
|---|---|---|---|---|
| Ausschnitte der Nutzernachricht (60–100 Zeichen) | ~6 | sehen, welcher Satz ein Verhalten auslöste | Trace-ID → Gespräch im Studio | 🟡 |
| Thema/Suchbegriff aus der Nachricht (`thema`, `topic`, `query`, Suchlink) | ~20 | Themenerkennung, Schnellwege (Canvas, Lernpfad) prüfen | steht im gespeicherten Zug (Entitäten, Suchmetadaten) | 🟡 |
| Antwortausschnitte vor/nach dem Umschreiben (Typ-Fokus, Halluzinations-Wächter) | 2 | sehen, was umgeschrieben wurde | Originaltext im gespeicherten Debug-Block ablegen (nur DB) | 🟡 |
| Schnellantworten (weggelassene, ergänzte) | 2 | kaum | Anzahl genügt | 🟢 |
| MCP-Argumente: **Filter** (Fach, Stufe, Typ, Lizenz, URIs) | 2 | Filterfehler finden — der häufigste Fehlertyp | — keine Personendaten | 🟢 behalten |
| MCP-Argumente: **Freitext-Suche** (`query`) | 2 | dito | Länge. Gespeichert ist der Begriff nur bei **erfolgreichen** Suchen (Suchmetadaten) — nicht bei abgelehnten Aufrufen, Werkzeugen ohne Metadaten und in der Agent-Spur (dort nur Argumentnamen). Voller Ersatz erst mit der Zugakte (§7) | 🟡 |
| Titel öffentlicher Materialien und Sammlungen | ~10 | Treffer und Auflösung prüfen | — öffentliche Katalogdaten, keine Personendaten | 🟢 behalten |
| Titel der Seite, auf der die Person ist | 1 | Seitenkontext prüfen | Kennung der Seite statt Titel (Arbeitsbereiche können privat sein) | 🟢 |
| **Sitzungs-ID** | 7 + Zugriffszeile | Zeilen eines Gesprächs verbinden | kurzer Hash; die ID wirkt wie ein Schlüssel zum Verlauf | 🟢 |
| **IP-Adresse** (Uvicorn-Zugriffszeile) | 1 | Drosselung nachvollziehen | steht im Traefik-Log; eigene Zugriffszeile ohne IP | 🟢 |
| Fehlermeldungen (`str(e)`) | ~110 | Fehlersuche | behalten; nur Eingabewerte aus Pydantic-Fehlern und SQL-Parameter entfernen | 🟢 |
| Prompts von LiteLLM (nur bei `LOG_LEVEL=DEBUG`) | – | – | Bibliothek auf WARNING deckeln | 🟢 |

**Folge für die Fehlersuche:** „Was hat die Person gefragt?“ beantwortet dann das Studio statt
des Logs. Für eine akute Analyse lässt sich `LOG_CONTENT=true` setzen; dann stehen Inhalte auf
DEBUG, bis man es wieder ausschaltet.

## 2 Debug-Block (18D)

Der Block geht heute an **jeden** Client: in der Live-Antwort und über den öffentlichen
Verlaufsabruf (`GET /api/sessions/{id}/messages`, für jeden, der die Sitzungs-ID kennt). Gespeichert
wird er in der Datenbank; das Studio liest ihn über eine angemeldete Route.

| Feld(gruppe) | Wer liest es | Ohne: was passiert | Ampel |
|---|---|---|---|
| Wiederherstellung: `_query_metas`, `_web_links`, `_type_focus`, `_dokumente`, `_topic_page_view`, `_prepared_write` | Widget beim Neuladen | Nach dem Neuladen fehlen Suchlink, Links, Typ-Hinweis, Dokumente, Themenseite und die Schreib-Vorschau | 🔴 |
| `pattern` (z. B. „M06“, „TOUR:…“) | Widget: Tour und Begrüßung erkennen, Gruppierung | Tour-Antworten und Begrüßung werden falsch dargestellt | 🔴 (harmlos) |
| `intent`, `state`, `tools_called`, `phase3_modulations` | Routing-Ereignis an die Host-Seite — nur mit Attribut `emit-routing-debug`; Debug-Panel | leeres Ereignis bei Einbettungen, die es eingeschaltet haben | 🟡 |
| `persona`, `signals` (Schlüsse über die Person) | Routing-Ereignis, Debug-Panel | dito | 🟡 |
| `entities` (Thema, Fach, Stufe aus der Nachricht) | nur Debug-Panel | nichts | 🟢 |
| `safety` (Stufen, Scores, Gründe) | Studio, Auswertung | nichts für Personen | 🟢 |
| `outcomes[].error` (roher Fehlertext) | Studio, Auswertung | nichts; ein Code genügt | 🟢 |
| `trace`, `token_usage`, `pattern_reasoning`, `pattern_id_hint`, `llm_engine_match`, `engine`, `confidence`, `policy`, `context` | Studio, Auswertung, Golden-Läufe | nichts für Personen; Golden-Läufe brauchen den Studio-Schlüssel | 🟢 |

Debug-Panel im Widget (Attribut `show-debug-button`) und Routing-Ereignis zeigen heute alles, sobald
eine Seite das Attribut setzt — das kann jede Seite, die das Widget einbettet.

## 3 Fehlertexte (18D)

| Was | Wer liest es | Ampel |
|---|---|---|
| Fehlerklasse in der Blase („gaierror“, „AuthenticationError“) | niemand; die Auswertung erkennt Fehlerantworten am Textbaustein — der wird beim neuen Text mit angepasst | 🟢 |
| Roher Anbietertext im Canvas-Material | niemand | 🟢 |
| Neu: Fehlernummer (Trace-ID, geprüft: nur Hex, begrenzte Länge) | Support findet die Logzeile | Gewinn |

## 4 Was zu entscheiden ist

| # | Frage | Empfehlung | Was es kostet |
|---|---|---|---|
| D1 | Trace-ID mit jedem Zug speichern (Gespräch und Qualitätsprotokoll)? | **Ja** — Voraussetzung, um Inhalte aus den Logs zu nehmen | kleine Migration |
| D2 | Bei Umschreibungen den Originaltext im gespeicherten Debug-Block ablegen (nur DB, sichtbar im Studio)? | **Ja** | nichts |
| D3 | In MCP-Logzeilen Filterwerte behalten, Freitext-Suche nur als Länge? | **Ja** — die meisten Suchfehler sind Filterfehler (auch der Audit-Fall), und die Filter bleiben sichtbar | Bis zur Zugakte (§7) fehlt bei gescheiterten Aufrufen der Suchtext |
| D4 | Titel öffentlicher Materialien und Sammlungen im Log behalten? | **Ja** — keine Personendaten | nichts |
| D5 | Debug-Block teilen: Funktionsteil (🔴-Zeilen) immer, Rest nur mit Freigabe — live **und** im öffentlichen Verlaufsabruf? | **Ja** | Widget liest die Funktionsfelder künftig aus einem eigenen Block |
| D6 | Routing-Ereignis: `pattern`, `intent`, `state`, `tools_called` weiter für jede Einbettung mit Attribut; `persona` und `signals` nur mit Freigabe? (Die Nachricht im Ereignis stammt aus dem Eingabefeld der Seite selbst und verlässt sie nicht.) | **Ja** | Einbettungen, die `persona`/`signals` auswerten, brauchen die Freigabe |
| D7 | Was ist eine Freigabe? | **Studio-Anmeldung** (Cookie oder Schlüssel). Optional später: eine Liste erlaubter Herkünfte für Debug in Einbettungen | Debug-Panel in fremden Einbettungen zeigt nur noch den Funktionsteil |
| D8 | Golden-Läufe schicken den Studio-Schlüssel mit (`EVAL_CHAT_HEADERS`)? | **Ja** | eine Zeile in der Startanleitung |
| D9 | Gespeicherter Debug-Block in der DB bleibt vollständig (Studio braucht ihn, 30 Tage)? | **Ja** | nichts |

Mit diesen Empfehlungen verliert **keine Person im Chat** eine Funktion. Einschränkungen treffen nur
Einbettungen, die heute Debug-Panel oder Routing-Ereignis nutzen — und Golden-Läufe ohne
Studio-Schlüssel.

## 5 Vollständige Bestandsaufnahme je Kanal und Log-Stufe

Geprüft am 2026-10-29: eigene Logaufrufe per AST, Fremd-Logger per Laufzeitprobe mit der echten
Logging-Einrichtung (`main._configure_logging`), Antworten am Code. Normalbetrieb heißt
`LOG_LEVEL=INFO`, `LOG_FORMAT=json`.

### 5.1 Logs

| Quelle | Normalbetrieb (INFO/WARNING) | DEBUG | Was tun |
|---|---|---|---|
| Eigene Logzeilen | ~50 Stellen mit Inhalt (Tabelle §1), 7 mit Sitzungs-ID | 1 Stelle: Werte kuratierender Werkzeugargumente (`mcp/client.py`) | Platzhalter bzw. Kurzhash; die DEBUG-Stelle nur mit `LOG_CONTENT` |
| Uvicorn-Zugriffszeile | **jede Anfrage:** IP und roher Pfad, beim Verlaufsabruf mit Sitzungs-ID | dito | abschalten; eigene Zeile: Pfad-Vorlage, Status, Dauer, Trace-ID |
| `slowapi` | **jede Drosselung:** WARNING mit dem Limit-Schlüssel = IP | dito | Logger deckeln, eigene Zeile ohne IP |
| LiteLLM | Modell, Wiederholungen — ohne Inhalt. **Eigener Handler:** jede Zeile ein zweites Mal auf stderr, am JSON-Format und an jedem Filter vorbei | **ganze Anfragen samt Prompt** | eigenen Handler entfernen; Logger auf WARNING, außer mit `LOG_CONTENT` |
| OpenAI-SDK | Wiederholungen | **Request-Optionen samt Prompt** | WARNING, außer mit `LOG_CONTENT` |
| MCP-Client (SDK) | – | **JSON-RPC-Nachrichten samt Argumenten und Ergebnissen** | WARNING, außer mit `LOG_CONTENT` |
| `httpx` | schon WARNING | – | bleibt |
| `httpcore`, `h11` | – | Verbindungsdetails, keine Kopfzeilenwerte | WARNING (nur Rauschen) |
| SQLAlchemy | still | still | `hide_parameters=True` — sonst stehen in DB-Fehlermeldungen die Parameter, also auch Nachrichtentexte |
| Fehlermeldungen (`str(e)`) | Pydantic-Fehler zeigen den Eingabewert | | nur Ort und Art (Helfer `_fehlerorte` gibt es schon) |
| asyncpg, markitdown, onnxruntime, huggingface_hub, opentelemetry, langgraph | ohne Inhalt | ohne Inhalt (beim Import evtl. Dateinamen) | bleiben |
| OpenTelemetry-Export (nur mit `OTEL_EXPORTER_OTLP_ENDPOINT`) | Span-Attribute mit rohem Pfad, also Sitzungs-ID | | Pfad auf die Vorlage setzen (Hook) |

### 5.2 Antworten an Clients (unabhängig von der Log-Stufe)

| Kanal | Was heute hinausgeht | Was tun |
|---|---|---|
| Live-Antwort und Strom-Frame `result`: `debug` | der volle Diagnoseblock | teilen (§2): Funktionsteil immer, Diagnose nur mit Studio-Anmeldung |
| Öffentlicher Verlaufsabruf | der gespeicherte Block vollständig | derselbe Filter |
| Fehlerblase Chat (`error.internal`) | Fehlerklasse | Fehlernummer statt Klasse |
| Fehler in der Werkzeugschleife | Fehlerklasse (über `error.internal`) | dito |
| Rückfall in `respond.py` | Fehlerklasse, hart deutsch | über `bot_text`, Fehlernummer |
| Canvas, Erzeugung gescheitert (`material.genFailed`) | Fehlerklasse | Fehlernummer |
| Canvas-Material (`material.createFailed: {e}`) | **roher Anbietertext im Material** | entfernen |
| Strom-Fehlerframe | „internal error“ | schon sauber |
| `/api/agent` | kein Debug-Block; Fortschritt nur mit Werkzeugnamen | schon sauber |
| Sprache | feste Begründungen | schon sauber |
| Studio, Evaluation, Lasttest | Fehler mit Klasse und Text — nur angemeldet | bleibt |

## 6 Minimale Fixes

Ziel: Im Normalbetrieb und auf DEBUG ohne Schalter stehen **keine Inhalte und keine IPs** im Log,
und kein Client bekommt ohne Freigabe Diagnose oder Fehlerinterna. Ohne Umbau des Widgets und ohne
Migration.

**18C (etwa 1 Tag mit Tests)**
1. `LOG_CONTENT` (Vorgabe aus). Eine Funktion stellt die Fremd-Logger ein: LiteLLM, OpenAI, MCP,
   httpcore, h11 auf WARNING, `slowapi` auf ERROR — außer mit `LOG_CONTENT`. Der eigene Handler
   von LiteLLM wird entfernt; alles läuft über unseren JSON-Handler. Startwarnung, wenn
   `LOG_CONTENT` an ist.
2. Uvicorns Zugriffszeile aus, eigene Zeile ohne IP und Query; statische Dateien nur auf DEBUG.
   Eigene Drosselungszeile ohne IP.
3. Helfer `inhalt(text)` → `‹N Zeichen›` und `kennung(session_id)` → Kurzhash; die ~50 Stellen
   umstellen. MCP-Argumente: Filterwerte und IDs bleiben, Freitext (`query`, `url`, Titel,
   Beschreibungen) nur als Länge.
4. `hide_parameters=True`; Pydantic-Fehler nur mit Ort und Art.
5. Prüfung: AST-Wächter für verbotene Namen in Logaufrufen ab INFO, dazu ein
   **Kanarienvogel-Test**: Ein Zug mit einem Markierwort in der Nachricht (LLM und MCP als
   Attrappe) — das Wort darf in keinem Logeintrag ab INFO und, ohne `LOG_CONTENT`, auch auf DEBUG
   nicht auftauchen.

Preis: Bei gescheiterten MCP-Aufrufen fehlt im Log der Suchtext (Filter, Fehlerart und Länge
bleiben). Wer genau hinsehen muss, schaltet kurz `LOG_CONTENT` ein.

**18D (etwa ½–1 Tag mit Tests)**
1. Eine Erlaubnisliste für den Debug-Block an einer Stelle: beim Ausliefern (Live, Strom-`result`)
   und im öffentlichen Verlaufsabruf. Erlaubt: `pattern`, `intent`, `state`, `tools_called`,
   `phase3_modulations` und die Wiederherstellungsfelder (`_query_metas`, `_web_links`,
   `_type_focus`, `_dokumente`, `_topic_page_view`, `_prepared_write`). Alles andere nur mit
   Studio-Anmeldung (dieselbe Prüfung wie die Studio-Routen). Das Widget liest weiter aus `debug`
   — **keine Frontend-Änderung**.
2. Fehlertexte ohne Klasse und ohne Anbietertext, mit Fehlernummer (Trace-ID, geprüft: nur Hex,
   begrenzte Länge); die Auswertung erkennt die neuen Texte.
3. Golden-Läufe: Studio-Schlüssel in `EVAL_CHAT_HEADERS` (Startanleitung).

Gespeichert wird weiter alles (Studio braucht es); `outcomes[].error` darf deshalb Text bleiben.

## 7 Saubere Umsetzung — ohne dass Inhalte im Log bleiben müssen

Grundsatz: **Das Log sagt, dass etwas geschah und wie lange; die Datenbank sagt, was.** Beides
verbindet die Trace-ID. Dann muss kein Inhalt mehr ins Log, ohne dass die Fehlersuche leidet.

1. **Trace-ID je Zug speichern** (Nachricht und Qualitätsprotokoll; kleine Migration). Aus jeder
   Logzeile führt sie zum Gespräch im Studio.
2. **Zugakte:** Ein Sammler je Zug (ContextVar, wie heute `_query_metas` und der Verbrauch) nimmt
   auf, was heute als Inhalt ins Log geht: jeder Werkzeugaufruf mit den Argumenten, wie das Modell
   sie schickte und wie sie aufgelöst wurden, Status, Fehlerart, Dauer; Umschreibungen mit
   Original, Ersatz und Grund; Schnellwege mit Thema. Gespeichert im Diagnoseteil des Zugs — auch
   bei früh endenden Zügen und in der Fehlerblase. Die Agent-Spur darf dann Werte führen; „nur
   Namen“ war nur nötig, weil der Block öffentlich war.
3. **Zwei Blöcke statt einem:** `ui` (Funktionsteil, fest typisiert, öffentlicher Vertrag; das
   Widget liest künftig dort, mit Rückfall auf alte gespeicherte Nachrichten) und `debug`
   (Diagnose, nur Studio). Ein Antwortmodell je Publikum statt Herausfiltern — neue
   Diagnosefelder sind dann automatisch nicht öffentlich.
4. **Logging nur noch über Ereignisse mit erlaubten Feldtypen** (Kennungen, Zahlen, Aufzählungen,
   Filter-URIs). Inhalte gehen in die Zugakte; mit `LOG_CONTENT` zusätzlich auf DEBUG.
5. **Fremd-Logger und OpenTelemetry** wie in §6; ein Test hält die Liste der gedeckelten Logger
   fest.
6. **Fehler als Code:** Antworten tragen nur Code und Fehlernummer, nie Text aus einer Ausnahme.
7. **Prüfung:** AST-Wächter, Kanarienvogel-Test (Log, öffentliche Antwort, öffentlicher Verlauf)
   und ein Vertragstest für die Schlüssel des `ui`-Blocks.

Aufwand: etwa 3–4 Tage, davon der größte Teil Zugakte und `ui`-Block samt Widget.

**Empfehlung zur Reihenfolge:** Erst die minimalen Fixes (§6, schließen das Risiko in 1½–2 Tagen),
dann Trace-ID und Zugakte (§7.1–2, holen die Diagnose zurück, die das Log abgibt), zuletzt der
`ui`-Block (§7.3), wenn ohnehin am Widget gearbeitet wird.
