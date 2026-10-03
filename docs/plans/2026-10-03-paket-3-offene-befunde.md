# Paket 3: offene Befunde, erste Runde

Stand 2026-10-03. Auftrag des Nutzers: „neue oder offene Befunde beheben und danach Stand
berichten“. Bei Entscheidungen folgt der Nutzer den Empfehlungen.

Quellen:
- `docs/offene-befunde-und-todo.md`, vor allem §1.4 (neu seit PR #9);
- Audit 2026-09-29, Abschnitte 6 und 7 (`docs/audits/2026-09-29-audit.md`).

## Auswahl

Aufgenommen sind Befunde, die vier Bedingungen erfüllen:
- Sie sind am heutigen Code nachgeprüft.
- Die Behebung ist klar.
- Sie braucht keinen Golden-Lauf, keine Master-Skill-Änderung und keine neue Abhängigkeit.
- Es gibt keine offene Infrastruktur-Frage.

Reihenfolge: zuerst Sicherheit und Datenschutz, dann Korrektheit, dann Wartbarkeit.

**Nicht in diesem Paket** (bleibt in der Befundliste):
- B-H3, C-H1, CSP und HSTS, SSE-Abbruch, `retention_days`, `markitdown`-Extras, Lizenz-Gate: Entscheidungen oder Infrastruktur.
- Responses-Plan, Antwortsprache im Muster-Modus, RAG nur für M04/M15: Diese brauchen einen Golden-Lauf.
- Akzentfarbe, `color-scheme`, Live-Regionen im Studio: Prüfung im Dunkelmodus und mit Screenreader.
- Angular 22.2 und Dateien über 300 Zeilen: eigene Schritte.

## Aufgaben

### T1 · MCP-Zugangsblock nur an den primären Server (Audit A-M2/B-M2)

- **Befund:** `transport._open_session(url)` baut die Fabrik aus `auth.build_http_client_factory()` für jede Adresse. Dienst-Token oder persönlicher Zugangsblock gehen damit auch an weitere Server der Registry und an `POST /api/config/mcp-servers/discover?url=…`.
- **Behebung:** Die Kopfzeile geht nur an die primäre Adresse (`resolve_mcp_url()`). An andere Adressen geht die SDK-Standardfabrik.
- **Datei:** `backend/src/boerdi/services/mcp/transport.py`, Test `backend/tests/…/test_mcp_transport*.py`.
- **Nachweis:** Ein Test mit gesetztem Token prüft beide Fälle. Primär: Kopfzeile vorhanden. Fremde Adresse und Discover: keine Kopfzeile.

### T2 · Nur angebotene Werkzeuge ausführen (Audit B-M1)

- **Befund:** Die Agent-Schleife (`services/agent_loop.py`) schickt jeden Werkzeugnamen an den MCP, auch einen, der nicht in `tools` stand. Damit ließe sich etwa ein Schreibwerkzeug am Anonym-Deckel vorbei aufrufen.
- **Befund im Muster-Weg:** `services/tool_loop.py` prüft ebenfalls nicht gegen das Angebot.
- **Behebung:** Vor dem MCP-Aufruf wird gegen die Namen des Angebots geprüft. Ein fremder Name bekommt eine Werkzeug-Antwort „nicht verfügbar“ und wird nicht ausgeführt. Virtuelle Werkzeuge bleiben unberührt.
- **Nachweis:** Je Schleife ein Test: Das Modell ruft ein nicht angebotenes Werkzeug, der MCP-Fake bleibt unberührt, und die Werkzeug-Antwort meldet „nicht verfügbar“.

### T3 · Verbrauch der Schreib-Abnahme vor dem Aufruf speichern (Audit B-M3)

- **Befund:** `redeem_write_approval` (`services/write_approval.py`) streicht den Merkposten vor dem MCP-Aufruf, aber nur im Speicher. In der Datenbank steht er erst nach dem Aufruf nicht mehr. Bricht der Zug dazwischen ab, ließe sich derselbe Schreibvorgang mit einem zweiten „ja“ erneut absetzen.
- **Behebung:** `update_session(…, entities=…)` direkt nach dem Streichen.
- **Nachweis:** Ein Test hält die Reihenfolge fest: Die Sitzung ist gespeichert, bevor der Aufruf beginnt.

### T4 · Bereichsschlüssel beim Wiederherstellen prüfen; Export bleibt im Zielordner (Audit A-M7)

- **Befund:** `export_tree` (`services/seed_io.py`) schreibt nach `dst / key`. Ein Schlüssel mit `..` landet außerhalb des Ordners. Das Wiederherstellen aus einer ZIP-Datei übernimmt jeden Schlüssel.
- **Behebung:**
  - `export_tree` lehnt Pfade außerhalb von `dst` ab.
  - Das Wiederherstellen weist Schlüssel ab, die kein gültiger Bereichspfad sind: kein `..`, kein absoluter Pfad, keine leeren Teile.
- **Nachweis:** Tests mit `../x` und `/abs` für Export und Wiederherstellen.

### T5 · Konfiguration nach Wiederverbindung neu laden (Audit C-M NOTIFY)

- **Befund:** `ConfigChangeListener._run` (`db/notify.py`) verbindet nach einem Abriss neu. Benachrichtigungen aus der Zwischenzeit sind dann verloren, und eine Replik nutzt veraltete Konfiguration, auch Datenschutz-Schalter, bis zum Neustart.
- **Behebung:** Nach jeder Wiederverbindung (nicht beim ersten Verbinden) meldet der Listener `on_reconnect`. `ConfigStore` lädt daraufhin alle bekannten Bereiche neu (Cache und Datenbank) und benachrichtigt die Abonnenten. Zuerst wird `LISTEN` eingerichtet, dann neu geladen.
- **Nachweis:** Der Listener-Test simuliert einen Abriss; `on_reconnect` wird genau einmal gerufen. Der Store-Test prüft, dass `_on_area_changed` für Cache- und Datenbank-Bereiche läuft.

### T6 · Neustart mitten im Zug (Befundliste §1.4)

- **Befund:** `resetSession()` und der Neustart-Knopf leeren den Verlauf. Die Antwort des laufenden Zugs landet danach trotzdem im frischen Verlauf, samt den Folgen aus `onResult`. Die Eingabe bleibt bis dahin gesperrt.
- **Behebung im Widget:**
  - `runSendMessage` merkt sich die Sitzungs-ID beim Start. Ist sie nach dem Warten eine andere, verwirft der Zug alles: Antwort, Fehlerblase, `onResult`, `setLoading`, Fokus.
  - `restart()` und `resetSession()` geben das Laden frei.
  - Der Netz-Stream wird NICHT abgebrochen: Ein Abbruch liefe in den POST-Rückfall und stellte die Frage erneut.
- **Prüfung vorab:** Der Rahmen `connected` setzt keine Sitzungs-ID. Er erzeugt nur das Lade-Label.
- **Nachweis:**
  - Unit-Test in `send-message.spec.ts` (Sitzung wechselt während `stream`).
  - E2E-Test in `embed.spec.ts`: `resetSession()` während ein verzögerter Zug läuft, danach genau eine Blase und eine freie Eingabe.

### T7 · Keine Ausnahmetexte an Endnutzer, kein Fehlertext in der Historie (Audit 6.3)

- **Befunde:**
  - `tool_loop.py`: Bei einem LLM-Fehler wird „Fehler bei der Verarbeitung: {e}“ zur Antwort, fest deutsch und mit dem Ausnahmetext.
  - `llm_learning_path.py`: `learningPath.error` zeigt `{error}`.
  - `api/chat.py`: Der Rückfall speichert `[unhandled error: Typ]` als Assistenz-Nachricht. Gezeigt wurde der Person etwas anderes, und der gespeicherte Text geht in die Modell-Historie.
- **Behebung:**
  - Den Grund ins Log schreiben, der Person einen festen, lokalisierten Text zeigen.
  - Gespeichert wird genau der Text, den die Person sah.
- **Nachweis:** Tests, die den Ausnahmetext in der Antwort und im gespeicherten Text ausschließen.

### T8 · Vokabular-Cache hält keinen MCP-Fehler fest (Audit 6.3)

- **Befund:** `_ensure_label_cache` (`services/mcp/arg_resolvers.py`) erwartet eine Ausnahme. `call_mcp_tool` liefert im Fehlerfall aber einen Text (`is_mcp_error`). Der Cache gilt dann bis zum Neustart als geladen. Der Fix B5 von 2026-06-10 greift deshalb nie.
- **Behebung:** Bei `is_mcp_error(raw)` warnen und nicht als geladen markieren.
- **Nachweis:** Test mit einem Fehlertext als Rückgabe: Danach gilt der Cache nicht als geladen, der nächste Bedarf ruft erneut.

### T9 · EscalationBlock-Vorgaben gleich der Laufzeit (Audit 6.9)

- **Befund:** Im Modell stehen `legal_classifier` und `downgrade_false_positives` auf `False` (`domain/config_models/base_governance.py`). `services/safety/service.py` fällt auf `True` zurück. Das Studio zeigt die Schalter deshalb aus, während sie wirken.
- Ein Speichern schaltet sie dagegen nicht ab: Das getippte PUT speichert das rohe Dokument, ein unberührtes Feld bleibt also fehlend (geprüft am Studio-Formular, Vorgaben gelten dort nur für neue Listeneinträge).
- **Behebung:** Im Modell `True` setzen und die Studio-Fixture `area-schemas.fixture.ts` neu erzeugen.
- **Nachweis:** Ein Test vergleicht die Modell-Vorgabe mit dem Rückfall im Code. Dazu laufen die Fixture-Wächter.

### T10 · Muster-Kennung `AGENT` reservieren (Befundliste §2, ST-5 Befund 4)

- **Befund:** `AGENT` kennzeichnet Agent-Züge (`domain/agent_pattern.py`, gelesen in `turn_assembly` und `turn_links`). Eine Muster-Datei mit dieser Kennung schaltete in der Muster-Maschine den Karten-Schutz ab.
- **Behebung:**
  - Der Muster-Lader überspringt die Kennung mit Warnung.
  - Ein Speichern über die Konfig-API wird abgewiesen, wenn die Kennung dort prüfbar ist.
- **Nachweis:** Lader-Test mit einer Muster-Datei `id: AGENT`.

## Ablauf

- Je Aufgabe: zuerst ein roter Test, dann der Fix, dann der Test grün.
- Nach dem Paket laufen die volle Backend-Suite, Lint und Frontend-Unit sowie die E2E-Tests.
- Danach ein frischer Prüfer auf den Diff. Das Log steht unten.
- Upload: Branch `paket-3-offene-befunde` vom Branch `token-streaming` (PR #9), PR gestapelt auf #9. Den Merge macht der Nutzer.

## Log

### T1 · erledigt (2026-10-03)
- `transport._client_fabrik(url)`: Die Fabrik mit Block gibt es nur, wenn `url` (ohne Schrägstrich am Ende) gleich `resolve_mcp_url()` ist. Sonst kommt die SDK-Standardfabrik.
- `test_mcp_auth.py`, neue Klasse `TestNurPrimaererServer` (5 Tests):
  - primäre Adresse, auch mit Schrägstrich am Ende;
  - fremde Adresse;
  - Werkzeug eines weiteren Servers;
  - Discover.
  - Zuvor rot: 3 von 5.
- Der bestehende Verdrahtungstest öffnete `https://beispiel.test/mcp` und erwartete dort den Block, hielt also genau das Leck fest. Er öffnet jetzt die primäre Adresse und prüft weiter, dass die Kopfzeile über `httpx_client_factory` geht.
- MCP-Tests: 108 passed; `ruff` sauber.

### T2 · erledigt (2026-10-03)
- Neues Modul `domain/werkzeug_angebot.py` mit `angebotene_namen(tools)` und `NICHT_ANGEBOTEN`.
- **Agent-Schleife:** Die Prüfung steht VOR `gate.prepare`, denn die Wall setzt bei einem Schreibwerkzeug womöglich einen Schlüssel ein. Virtuelle Werkzeuge bleiben unberührt.
- **Muster-Schleife:** Die Prüfung steht direkt hinter der Sicherheitssperre, mit dem Ergebnis `not offered`.
  - Ausnahme: das Werkzeug des offenen Vorgangs vom Zugbeginn (`_pending_at_turn_start`). Sonst liefe eine Zustimmung über den Fingerabdruck-Weg (E1) ins Leere, wenn das Muster des Ja-Zugs keine Kuration anbietet. Gefunden beim Gegenlesen; Test `test_bestaetigung_auch_ohne_das_werkzeug_im_angebot` (zuvor rot).
- Testgerüste:
  - `test_agent_loop._lauf` und `test_tool_loop._run_loop` bieten jetzt an, was das Skript ruft. Vorher bot `_lauf` nur `search_wlo_content` an, und `_run_loop` bot gar nichts an.
  - Wer die Sperre prüft, reicht das Angebot ausdrücklich herein.
- Neue Tests (alle zuvor rot):
  - `test_werkzeug_angebot.py` (4);
  - zwei in `test_agent_loop.py`;
  - einer in `test_tool_loop.py`;
  - einer in `test_write_confirm.py`.
- Lauf: 248 passed (Schleifen, Schreib-Abnahme, Generate, Streaming-E2E); `ruff` sauber.

### T3 · erledigt (2026-10-03)
- `redeem_write_approval` speichert die Sitzung ohne Merkposten direkt nach dem Streichen, also vor dem MCP-Aufruf. Ein Schreibfehler bricht ab, bevor etwas geändert wurde.
- Test `test_der_verbrauch_steht_in_der_db_bevor_gerufen_wird` (zuvor rot: `['aufruf', 'gespeichert']`).
- 118 passed; `ruff` sauber.
- **Nicht angefasst:** Der Fingerabdruck-Weg im Tool-Loop streicht ebenfalls zuerst im Speicher und speichert am Zugende. Das ist ein seltener Rückfall, und der Server nimmt den Schlüssel nur einmal an. Das begrenzt den Schaden auf eine Fehlermeldung.

### T4 · erledigt (2026-10-03)
- **Export:** `seed_io.export_tree` prüft alle Ziele vorab (`resolve()` liegt unter `dst`). Zeigt ein Schlüssel hinaus, wirft es `ValueError` und schreibt nichts.
- **Wiederherstellen:**
  - Alle drei Wege (Upload, Schnappschuss, Werkszustand) laufen über `config_snapshots._apply_config`.
  - Dort gilt jetzt dieselbe Regel wie beim getippten Schreiben: `api/config.is_writable_area_key`, also Pfadprüfung, `model_for` und `_is_file_key`.
  - Andere Schlüssel werden mit Warnung übersprungen; `areas` zählt nur die geschriebenen.
- **Vorab geprüft:** Alle 61 Seed-Schlüssel erfüllen die Regel. Gültige Bereiche älterer Sicherungen gehen also nicht verloren.
- Tests (beide zuvor rot):
  - `test_export_tree_bleibt_im_zielordner`;
  - `test_restore_schreibt_nur_bereiche_die_das_studio_schreiben_darf` (gegen Postgres; vorher 3 statt 1 geschrieben).
- 59 passed; `ruff` sauber.

### T5 · erledigt (2026-10-03)
- **Listener:** `ConfigChangeListener.start(on_change, on_reconnect=None)`. Nach jeder WIEDERverbindung, nicht beim ersten Verbinden, ruft er `on_reconnect`, und zwar nach dem neuen `LISTEN`. Fehler im Rückruf landen im Log.
- **Store:** `ConfigStore._on_reconnect` → `_resync`. Es lädt Cache- und Datenbank-Bereiche neu, über `_on_area_changed`: überschreiben ohne Lücke und die Abonnenten benachrichtigen. Fällt die Bereichsliste aus, lädt es wenigstens den Cache neu.
- **Tests:** `test_notify_reconnect.py` (3, ohne Datenbank, Verbindungs-Attrappe; zuvor rot).
- **Lauf:** 21 passed, 2 skipped (Valkey); die echten LISTEN-Tests laufen weiter grün. `ruff` sauber.

### T6 · erledigt (2026-10-03)
- **Widget, Zug:** `runSendMessage` merkt sich die Sitzungs-ID beim Start (`SendMessageContext.sessionId`). Ist sie bei einem Ausgang eine andere, kehrt der Zug zurück, ohne etwas anzufassen: kein Ergebnis, keine Stale- oder Fehlerblase, kein `onResult`, kein Laden oder Fokus. Ebenso kein POST-Rückfall, und Phasen- und Textrahmen werden ignoriert.
- **Widget, Neustart:** `restart()` und `resetSession()` geben das Laden frei, auch bei `showWelcome=false` (`LifecycleContext.setLoading`).
- **Nicht gebaut:** einen Abbruch des Netz-Streams. Er liefe in den POST-Rückfall; der Stream läuft im Hintergrund aus.
- **Tests:**
  - `send-message.spec.ts`: drei Tests, je einer für Stream-Antwort, Stream-Fehler und POST-Antwort nach dem Neustart.
  - `lifecycle.spec.ts`: ein Test.
  - Alle vier zuvor rot: die alte Antwort erschien, POST stellte die Frage neu, das Laden blieb gesperrt.
- **E2E:** `embed.spec.ts` „resetSession() mitten im Zug“. Die `fetch`-Hülle hält die Antwort 1,5 s zurück.
  - Gegen das alte Bundle rot: Die Eingabe war nach 500 ms noch gesperrt, die späte Antwort erschien als zweite Blase.
  - Nach `build:widget` grün. `embed.spec.ts` lief fünfmal durch, 90 passed.

### T7 · erledigt (2026-10-03)
- **Muster-Schleife:** Bei einem LLM-Fehler ist die Antwort jetzt `error.internal` mit dem Typ der Ausnahme, nicht mehr „Fehler bei der Verarbeitung: {e}“.
  - Nebenwirkung: Die Auswertung (`eval/run_profile.fallback_texts`) erkennt diesen Fall jetzt als Ersatzsatz.
  - `simplify:` Der Loop kennt die Oberflächensprache nicht und nimmt `DEFAULT`.
- **Weitere Vorlagen** (beim Gegenlesen gefunden, dieselbe Klasse): `learningPath.error`, `curation.error`, `action.browse.loadFailed`, `action.lp.failed` tragen kein `{error}` mehr. Der Grund steht im Log; `llm_curation` und `llm_learning_path` haben dafür einen Logger bekommen.
- `material.genFailed` reichte nur den Typ durch und war damit kein Leck. Der Platzhalter heißt jetzt `{kind}` wie bei `error.internal`.
- **Wächter** `test_kein_satz_reicht_einen_ausnahmetext_durch`: Keine Bot-Vorlage trägt mehr einen Platzhalter `{error}`.
- `api/chat.py`: Der Rückfall speichert den Text, den die Person sieht, statt `[unhandled error: Typ]`.
- **Angepasste Tests:** Vier Tests hielten den Ausnahmetext in der Antwort fest, darunter zwei englische.
- Lauf: 198 passed (Schleife, Generate, Chat, Direktaktionen, Kuratierung, Lernpfad, Canvas, Auswertung, i18n); `ruff` sauber.

### T8 · erledigt (2026-10-03)
- `_ensure_label_cache` prüft `is_mcp_error(raw)`. Ein Fehlertext gilt nicht mehr als geladen, der nächste Bedarf ruft erneut. Das `except` bleibt für Unerwartetes; sein Kommentar sagt jetzt, dass Netzfehler als Text kommen.
- **Test** `test_ensure_label_cache_mcp_fehlertext_latcht_nicht` (zuvor rot). Er nutzt die echte Fehlerform: `call_mcp_tool` liefert Text. Der ältere Test fälschte eine Ausnahme, die es im Betrieb nicht gibt.
- 62 passed; `ruff` sauber.

### T9 · erledigt (2026-10-03)
- `EscalationBlock.legal_classifier` und `.downgrade_false_positives` stehen jetzt auf `True`, gleich dem Rückfall in `services/safety/service.py`.
- Die Fixture `area-schemas.fixture.ts` ist neu erzeugt. Im Diff stehen genau die zwei Vorgaben, also 4 Zeilen. Der OpenAPI-Vertrag ist unverändert.
- **Test** `test_ein_block_mit_den_modell_vorgaben_wirkt_wie_ein_leerer` prüft das eigentliche Versprechen: Ein Block mit den Modell-Vorgaben wirkt wie ein leerer, im Altweg und beim Herabstufen. Zuvor rot: `never` gegen `smart`.
- 75 passed (Safety, Fixture-Gleichlauf, Konfig-Endpunkte).

### T10 · erledigt (2026-10-03)
- `domain/config_models/patterns.py`: `RESERVIERTE_KENNUNGEN = {"AGENT"}` und `ist_reservierte_kennung`. Gross- und Kleinschreibung sowie Leerraum zählen nicht.
- **Tor beim Speichern:** Das Feld `PatternFrontmatter.id` weist die Kennung ab, `PUT /api/config/data/03-patterns/…` liefert damit 422.
- **Lader:** `load_pattern_definitions` überspringt gespeicherte Muster mit dieser Kennung und schreibt eine Warnung.
- **Ort der Konstante:** Sie steht in `config_models` statt in `agent_pattern`, weil `agent_pattern` die Muster-Maschine importiert. Ein Test hält beide Konstanten gleich.
- `test_muster_kennung_reserviert.py` (6, zuvor rot). Die Fixture bleibt unverändert, denn der Validator ändert das JSON-Schema nicht.
- 136 passed; `ruff` sauber.

### Gesamtnachweis (2026-10-03)
- **Backend:**
  - Volle Suite: 4985 passed, 4 skipped. Das sind 28 Tests mehr als vor dem Paket (4957).
  - `ruff` sauber, OpenAPI-Vertrag unverändert.
- **Frontend:**
  - `lint` und alle `check:*` grün.
  - ui 856 (vorher 852), widget 70, studio 1327.
  - Im ersten Gesamtlauf liefen 9 Studio-Dateien in die 5-s-Frist, während parallel ein Prüfer Tests fuhr (bekannt, §5). Allein gelaufen: 110 von 110 Dateien grün.
  - Budget: gzip 161,01 / 175 kB.
- **E2E:** Die ganze Suite lief zweimal durch, 100 passed.

### Review mit frischem Blick (2026-10-03)

Ein Prüfer ohne Kontext hat den Diff gelesen. Er fand zwei mittlere und drei kleine Befunde; alle fünf sind am Code nachgeprüft und behoben, jeder mit einem zuvor roten Test.

- **R-1 (mittel, T4): Wiederherstellen verlor Bereiche ohne Modell.**
  - Beispiel: `01-base/rag-retrieval` wird gelesen, ist aber nicht registriert. Der Seed-Abgleich vorab hatte das nicht erfasst, denn der Bereich steht in keinem Seed.
  - Jetzt gilt beim Wiederherstellen die Pfadregel des rohen Datei-Schreibens (`is_restorable_area_key`) statt der Modell-Liste.
  - Dazu dieselbe Ausgangsprüfung wie beim Studio-Schreiben (`_assert_area_document_safe`). Geprüft wird alles, bevor etwas geschrieben wird; ein Verstoß antwortet 400.
  - Tests: Wiederherstellen mit `rag-retrieval` und `../…`; interne MCP-Adresse mit Antwort 400, nichts geschrieben.
- **R-2 (mittel, T6): Der Neustart gab das Laden frei, aber nur der Chat-Zug war an die Sitzung gebunden.**
  - Tour-Start, Tour-Tick, Kontext-Gruß und die vier Karten-Aktionen gaben das Laden danach frei, auch mitten in einem neuen Zug B, und rendern weiter in den frischen Verlauf.
  - Folge: Antworten in der Reihenfolge B, C, Antwort B, Antwort C; mit mehreren Repliken liefen zwei Züge zugleich.
  - Jetzt nutzen alle Lade-Besitzer dieselbe Wache `sitzungsWache` (`session/session-id.ts`). Die Kontexte tragen `sessionId`. Damit landet auch kein später Lernpfad mehr im frischen Verlauf; der Teil war schon vor dem Paket so.
  - Tests: 10 neue, je Ablauf Erfolg und Fehler.
- **R-3 (klein bis mittel, T2): Die Musterliste war als Sperre zu eng.**
  - M10 verlangt im Text `get_node_details`, M18 `get_compendium_text` und `lookup_wlo_publishers`, ohne sie in `tools` zu nennen. Gespeicherte Muster ändert kein Seed.
  - Der Muster-Weg sperrt jetzt, was nicht im Katalog des Muster-Wegs steht (`_nameable_tools()`). Ohne Zugangsblock fehlen dem Katalog die kuratierenden Werkzeuge.
  - Eine Abweisung bucht kein `outcome` mehr. Als `error` senkte sie die Zuversicht und kippte als einziges Ergebnis den Zustand auf Rückfrage.
  - Der Hinweis „hole sie mit get_skill“ ist damit kein toter Weg mehr, denn `get_skill` steht im Katalog.
- **R-4 (klein, T2): Die Agent-Schleife zählte abgewiesene Aufrufe nicht als Stillstand.** Das tut sie jetzt; Test mit zwei gleichen abgewiesenen Aufrufen.
- **R-5 (klein, T10): Das Tor stand nur im Modell.**
  - `_assert_area_document_safe` prüft die Kennung jetzt für alle allgemeinen Schreibwege: getippt, roh und Wiederherstellen.
  - `PUT /api/config/patterns` prüft sie selbst.
  - Neue Meldung `patterns.idReserved` (de/en). Tests für drei Schreibwege und den Gegenfall.

**Bewusst nicht geändert:**
- Die Agent-Schleife sperrt weiter streng gegen ihr Angebot, denn dort sitzt der Anonym-Deckel.
- `_resync` lädt alle Bereiche gleichzeitig und versucht einen Fehlschlag nicht erneut. Das ist eine Robustheitslücke, kein Fehler, und dasselbe Muster wie `_refresh`.

**Nachweis nach dem Review:**
- **Backend:** 4992 passed, 4 skipped; `ruff` sauber; OpenAPI-Vertrag unverändert.
- **Frontend:**
  - `lint` und `check:*` grün.
  - ui 866 und widget 70; studio unverändert bei 1327 (seit dem letzten Lauf nicht berührt).
  - Bundle neu gebaut, Budget gzip 161,09 / 175 kB.
- **E2E:** 2× 100 passed.
