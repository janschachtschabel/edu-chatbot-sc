# Paket 11 — Fremde MCP-Server, Einbettungswechsel, Anmeldungs-Dokument (2026-10-15)

Auftrag des Nutzers vom 2026-10-15 (Antwort auf die offenen Entscheidungen aus Paket 10). Nur Staging,
nichts committet.

## Entscheide des Nutzers

| Punkt | Entscheid |
|---|---|
| A-2 Zugangsblock im `sessionStorage` | langfristig lösen, kurzfristig unkritisch (MCP wird umgebaut) — für das MCP-Team dokumentieren, mit Widerruf und den übrigen MCP-/Anmeldungs-Punkten in einem eigenen Dokument |
| A-7, A-9 | besser erklären (Entscheid danach) |
| P9-3 Abschied mit Anlass in anderem Satz | so lassen |
| AcademicCloud und Einbettungen | so lassen; ein Einbettungsmodell der AcademicCloud muss aber machbar und angebbar sein (die Wissensbasis liegt heute im OpenAI-Raum) |
| Studio-Akzentfarbe | wie empfohlen (`#1b64d9`) |
| Werkzeuge neuer MCP-Server | sollen nutzbar sein, ohne die Nutzung des WLO-Servers zu verändern; prüfen, wie generisch die Anbindung ist |
| Drittressourcen | prüfen, ob noch etwas von Drittservern geladen wird (Google Fonts usw.) |

## Befunde der Erkundung (2026-10-15)

**MCP-Server (wlo-mcp-server-sc, nur gelesen):** Der Block `wlo2.…` enthält Benutzername und Passwort
(oder ein edu-sharing-Ticket), RSA/AES-verschlüsselt für den Server; er läuft nicht ab und gilt, solange
sein `jti` in der Erlaubnisliste des Servers steht. Wer ihn besitzt, handelt als die Person (Bearer).
`POST /auth/revoke {token}` nimmt ihn heraus, `POST /auth/revoke-all` alle Blöcke eines Kontos — beide ohne
CORS, aus einer fremden Seite also nicht aufrufbar; serverseitig (Backend → MCP) schon. Kein Ablauf, keine
Bindung an Herkunft oder Werkzeuge; `/auth/ticket` mit `Access-Control-Allow-Origin: *`.

**Anbindung im Chatbot:** Katalog fest (`services/mcp/tool_defs.py`, `tool_defs_curation.py`), `tools/list`
nur für „Server prüfen“ und Studio-Beschreibungen. Werkzeuge eines zweiten Servers erreichen das Modell nie.
WLO-gebunden: Schreib-Abnahme (`domain/write_confirm`), `tool_mode` (Präfix `wlo_`), Einrahmen fremder
Ausgaben (`domain/untrusted_text`, nur benannte WLO-Werkzeuge), Cache (Sperrliste nur `wlo_*`),
`preparedRequest` aus **jedem** Server (`mcp/client.py` → `read_prepared_write`). Der Zugangsblock geht nur
an den Hauptserver (`transport._client_fabrik`). SSRF-Prüfung beim Speichern und vor „Server prüfen“, nicht
beim Aufruf.

**Drittressourcen:** keine Schriften, CDNs, Analyse-Skripte; Swagger/Redoc aus; Studio-CSP `default-src
'self'`. Geladen werden nur die Vorschaubilder der Karten — live gemessen vom WLO-Repositorium
(`…/edu-sharing/preview`); fremde Hosts erscheinen nur als Link-Ziele (erst beim Klick).

**AcademicCloud:** `/academiccloud/models` (b-api, 2026-10-15) führt 10 Modelle, kein Einbettungsmodell.
`LLM_EMBED_MODEL` leitet Nicht-`text-embedding-`-Modelle auf der AcademicCloud schon heute über
`/academiccloud`. Es fehlt der Wechsel des Vektorraums: `rag_chunks.embedding vector(<dim>)` wird in der
ersten Migration fest angelegt, `import-rag --force` bettet nur Seed-Bereiche neu ein.

## Arbeitspakete

- **A Dokument „MCP und Anmeldung“** (`docs/mcp-und-anmeldung.md`): für das MCP-Team und uns — Block,
  Risiko A-2 (Gastseite), Widerruf (A-4, mit serverseitigem Weg), S-1 Ticket-Tausch, V-2 kurzlebige Blöcke,
  CORS `/auth/ticket`, `wlo_auth_status`, `preparedRequest`, Wünsche an den Umbau.
- **B Entscheidungen** in `entscheidungen-offen.md` nachziehen; A-7/A-9 neu erklärt.
- **C Akzentfarbe** — erledigt: `--st-accent: #1b64d9` (nur Studio).
- **D Einbettungswechsel:** Kommando `boerdi rag-einbettung-wechseln [--probe]`: misst die Dimension des
  eingestellten Modells mit einem Probeaufruf, stellt die Spalte um (Index weg, Typ neu, Vektoren leer),
  bettet ALLE Abschnitte neu ein (Seed und Studio-Uploads), stapelweise und fortsetzbar, legt den Index
  wieder an. Über 2000 Dimensionen: Abbruch mit Hinweis (Grenze des HNSW-Index). Doku in `deploy/README.md`.
- **E Werkzeuge fremder MCP-Server** (Entwurf unten), TDD.
- **F Drittressourcen** — geprüft, Ergebnis oben; keine Änderung nötig.

## Entwurf E — Werkzeuge fremder MCP-Server

Ziel: Werkzeuge eines im Studio eingetragenen Servers sind nutzbar; am WLO-Weg ändert sich nichts.

1. **Übernahme statt Laufzeit-Abfrage:** „Server prüfen“ im Studio liest `tools/list`; „übernehmen“
   speichert Name, Beschreibung, Eingabeschema und `annotations` im Registry-Eintrag (`tool_schemas`).
   Der Katalog liest nur die Konfiguration — kein Netz im Zug, die Redaktion sieht, was angeboten wird.
2. **Eigener Namensraum:** das Modell sieht `<server-id>__<werkzeug>` (≤ 64 Zeichen, `[a-zA-Z0-9_-]`);
   Aufruf mit dem Originalnamen an die URL dieses Servers. Keine Kollision mit WLO-Namen möglich.
3. **Nur lesende Werkzeuge** (Phase 1): angeboten wird ein Werkzeug nur mit `annotations.readOnlyHint:
   true`. Schreibende Werkzeuge fremder Server bräuchten eine eigene Abnahme — bis dahin nicht angeboten,
   im Studio als „schreibend — nicht angeboten“ gezeigt.
4. **Schutz:** Ausgabe als nicht vertrauenswürdig eingerahmt; kein `preparedRequest` aus fremden Servern;
   kein Zugangsblock (schon so); URL-Prüfung auch beim Aufruf; Werkzeuge im Studio einzeln abschaltbar
   (bestehende Freigabe je Werkzeug).
5. **Angeboten:** im Agent-Modus mit dem übrigen Katalog; im Muster-Modus, wo ein Muster das Werkzeug unter
   `tools:` nennt.

## Log

- 2026-10-15: Erkundung (zwei Such-Agenten, Live-Probe Vorschaubilder, AcademicCloud-Modellliste). C erledigt.
- 2026-10-15, A: [`docs/mcp-und-anmeldung.md`](../mcp-und-anmeldung.md) — Ablauf, Inhalt des Blocks, Risiken R1–R5
  (R1 = A-2: auf einer Drittseite kann jedes Skript den Block lesen und bis zum Widerruf als die Person
  lesen und schreiben), Wünsche an den MCP-Umbau (kurzlebige Token, Bindung, Widerruf aus dem Widget,
  Herkunftsliste für `/auth/ticket`, Annotationen).
- 2026-10-15, B: `entscheidungen-offen.md` — A-2, P9-3, AcademicCloud und Akzentfarbe als entschieden; A-4
  mit dem serverseitigen Widerruf als Möglichkeit; A-7 und A-9 neu erklärt (Entscheid offen).
- 2026-10-15, C: `--st-accent: #1b64d9` (5,42:1 auf Weiß … 4,86:1 auf der Auswahlfläche); `check:contrast`
  grün, Studio-Build mit der Farbe im CSS. Drei veraltete Kontrast-Kommentare berichtigt.
- 2026-10-15, D: `services/rag/einbettung_wechsel.py` + `boerdi rag-einbettung-wechseln [--probe |
  --fortsetzen]`; Doku `deploy/README.md` „Einbettungsmodell wechseln“. Tests zuerst: 7 gegen echtes
  Postgres (neue Dimension, gleiche Dimension bettet trotzdem neu ein, Probe ändert nichts,
  `EMBED_DIM`-Abweichung und > 2000 brechen vor jeder Änderung ab, Fortsetzen holt nur Fehlendes,
  Fortsetzen mit falscher Spalte bricht ab) und 5 für die Kommandozeile. Bekannte Grenze: der
  Anbieter-Weg setzt für e5-Modelle keine `query:`/`passage:`-Präfixe.
- 2026-10-15, F: keine Änderung — keine Schriften, CDNs oder Analyse-Skripte; Vorschaubilder kommen vom
  WLO-Repositorium (live gemessen).
- 2026-10-15, Nachtrag zu Paket 10 (S-7): Die Studio-Feldtexte für `curation_reroute` fehlten (Wächter
  „jedes Feld trägt Beschriftung und Hilfetext in beiden Sprachen“) — beim S-7-Bau lief nur die
  Schema-Formular-Teilsuite. Ergänzt in `i18n/catalogue/fields-klassifikation.ts`.
- 2026-10-15, E: gebaut wie entworfen. Neu: `domain/fremdwerkzeug.py` (Auswahl, Namensraum),
  `services/mcp/fremdwerkzeuge.py` (Angebot, eigener Aufrufweg); eingehängt in `mcp/client`
  (Weiche vor dem WLO-Weg), `agent_tools._mcp_werkzeuge`, `response_tool_selection._nameable_tools`,
  `config_choices._tools`, `agent_tool_overview` (Art `external`), `untrusted_text`
  (`FREMDSERVER_FRAME_START`), `host_capabilities.erlaubt` (in „curate“ außen vor),
  `werkzeug_freigabe` (Schalter fremder Werkzeuge verbergen keine WLO-Namen); Modell
  `McpWerkzeugSchema`/`McpServer.tool_schemas`; „Server prüfen“ liefert Schema und `readOnlyHint`;
  Studio: Knopf „Werkzeuge übernehmen“, Hinweis „schreibend“, Gruppe „Extern“ in der Werkzeugliste.
- 2026-10-15, E-Review (frischer Prüfer, 3 MAJOR, 5 MINOR — alle am Quelltext bestätigt und behoben,
  je ein Test zuerst rot):
  1. Weiterleitung: ein übernommener Name eines weiteren Servers fing bei abgeschaltetem WLO-Server
     gleichnamige WLO-Aufrufe ab (samt vorbereiteter Schreibanfragen) → `_get_server_url_for_tool`
     überspringt übernommene Namen.
  2. SSRF über Umleitungen: das MCP-SDK folgt 307/308 immer → fremde Server bekommen
     `transport._ohne_umleitung`. Vier Tests in `test_mcp_auth.py` prüfen seither diese Fabrik (und
     weiter: kein `authorization`). Rest: ein DNS-Rebinding-Fenster zwischen Prüfung und Verbindung
     (bekannt, nicht geschlossen — bräuchte eine an die IP gebundene Verbindung).
  3. Ein Eintrag mit der Adresse des WLO-Servers bekäme den Zugangsblock → `angebotene` lässt ihn weg.
  4. Lange Server-Kennungen verloren den Trenner → Kennung höchstens 30, Werkzeug 32 Zeichen.
  5. Studio zeigte für ein übernommenes `search_skill` „aus“, die Laufzeit bot es an → gleiche Vorgabe.
  6. Eingabeschema über 8000 Zeichen wird nicht angeboten.
  7. Persönliche Daten in der Nachricht sperren auch fremde Dienste (Regex-Gate), die Werkzeugliste
     zeigt die Sperre.
  8. Antworten fremder Dienste auf 30 000 Zeichen gekürzt.
  Dazu der Ende-zu-Ende-Test durch die Agent-Schleife (`test_agent_schreib_abnahme.py`).
- Bekannte Grenzen E: schreibende Werkzeuge fremder Server werden nicht angeboten (bräuchten eine eigene
  Abnahme); keine Karten, nur Text; Beschreibungen im Eingabeschema stehen ungerahmt in der
  Werkzeugdefinition (die Redaktion übernimmt bewusst); im Muster-Modus nur, wo ein Muster den Namen
  unter `tools:` nennt.
- 2026-10-15, G (Nutzer-Entscheid zu A-2): Anmeldung nur auf erlaubten Seiten, **nur bei
  `CORS_ALLOW_ALL=false`** — `domain/anmelde_herkunft.anmeldung_erlaubt` (Liste aus `CORS_ORIGINS` oder
  Erweiterungs-Regel, ohne `Origin` = gleiche Herkunft); `/api/config/guide-mode` liefert sonst kein
  `mcp_auth_base`, das Widget zeigt dann weder Knopf noch Ticket-Tausch (unverändert). Offen (Vorgabe):
  alles wie bisher. Befund dabei: bei geschlossenem CORS kann der Browser die Antwort auf fremden Seiten
  ohnehin nicht lesen — die Regel macht die Nebenwirkung zur Zusicherung. Tests: 15
  (`test_anmelde_herkunft.py`). Doku: `.env.example`, `INSTALL.md`, `deploy/INSTALL-schnellstart.md`,
  `deploy/README.md` (Abnahme), `mcp-und-anmeldung.md`. Randfall: Ticket-Attribut auf nicht gelisteter
  Seite → erster Zug wartet einmal bis 5 s (S-4-Sperre).
- 2026-10-15, Messung `tools/list` des WLO-Servers (für die Berichte): 41 Werkzeuge; Annotationen
  stimmig (28 `readOnlyHint: true`, die 13 schreibenden `wlo_*` nicht). Unser Katalog: 39 von 39
  Beschreibungen umgeschrieben, 36 mit anderen Parametern (meist `outputFormat` verborgen).
  Nebenbefunde: `search_skill` führte der Server bei der Messung nicht (dort abgeschaltet, siehe K;
  bei uns von Haus aus aus);
  `search_wlo_within_collection` bietet bei uns `excludeNodeIds`, der Server dort nur `skipCount` — prüfen.
- 2026-10-15, H (Nutzer: „machen wir so“): [`docs/mcp-feedback-werkzeuge.md`](../mcp-feedback-werkzeuge.md) —
  Ausgabeformat (`structuredContent` enthält in beiden Formaten dieselben Felder → `outputFormat` ist eine
  Doppelstruktur), übertragbare Beschreibungs-Zusätze, wo der Server weiter ist, Parameter, Nutzungsketten
  aus der Dev-DB (`lookup_wlo_vocabulary` 339 Aufrufe — verursacht durch unsere Beschreibung), Vorschläge
  für zusammengefasste Werkzeuge; Abschnitt 8 = Vorschläge C-1…C-6 für den Chatbot (nicht umgesetzt).

## Vorschläge für den Chatbot aus dem MCP-Abgleich (2026-10-15, nicht umgesetzt — nach dem MCP-Neubau)

Das Dokument für die MCP-Entwickler ist [`mcp-feedback-werkzeuge.md`](../mcp-feedback-werkzeuge.md); hier steht,
was der Chatbot selbst ändern könnte.

| Nr. | Vorschlag | Wirkung | Risiko |
|---|---|---|---|
| C-1 | `lookup_wlo_vocabulary` nur noch für Lizenz, Hochschulfächer und Schreibvorgänge empfehlen; die Such-Parameter („Labels aus lookup_wlo_vocabulary …“) entsprechend. Fach, Stufe, Typ und Zielgruppe gleicht der Client selbst ab (`arg_resolvers._resolve_filter_uris`: vorgewärmter Cache, unscharfe Suche, gecachter LLM-Rückfall). Für die Lizenz gibt es keinen Abgleich — dort bleibt das Nachschlagen sinnvoll. | weniger Aufrufe je Suchzug (heute 339 Nachschlagen auf 353 Suchen) | gering; Golden-Lauf, Trefferqualität mit Filtern prüfen |
| C-2 | Karten und die gekürzte Fassung für das Modell aus `structuredContent` lesen statt `outputFormat: json` anzufordern und den Textblock zu parsen. Was das Modell sieht, bleibt gleich (die eigene Kürzung). | unabhängig von der Textform des Servers, standardkonform | mittel; je Werkzeug prüfen, ob `structuredContent` dieselbe Form hat (für die Suche gemessen: ja) |
| C-3 | Texte und Schemas nachziehen, wo der Server weiter ist (`mcp-feedback-werkzeuge.md` §3.3), `search_skill` bleibt (abschaltbarer Rückfall, siehe K), `excludeNodeIds` bei `search_wlo_within_collection` klären | heute fehlende Funktionen | gering bis mittel; Golden-Lauf |
| C-4 | Den Zweistufen-Absatz (in 13 Beschreibungen, ~5 000 Zeichen je Zug mit Schreibrecht) **einmal** als Schreibregel in den Systemteil stellen, sobald ein schreibendes Werkzeug angeboten wird — in BEIDEN Modi (der Agent kennt M18 nicht; beide Wege kennen aber die angebotenen Werkzeuge). Beschreibungen behalten einen Satz: „zweistufig — siehe Schreibregel“. Mechanik, also im Code, nicht im Master-Skill. | weniger Token, eine Stelle für die Regel | mittel; Golden-Lauf der Schreibflüsse in beiden Modi |
| C-5 | `wlo_list_suggestions` ist lesend (Server-Annotation), zählt bei uns wegen `wlo_` als schreibend | im Lesemodus verfügbar | gering |
| C-6 | Vorabruf: drei Einzelsuchen statt `search_wlo_all` — klären, warum getrennt | ein Aufruf statt drei | zu prüfen |

## I — Reranker: Vorgabe aus, Modell bezieht sich selbst (Nutzer 2026-10-15)

Entscheide: Modell nicht im Repo/Image; Schalter `RAG_RERANKER_ENABLED` (Umgebung), Vorgabe aus; beim
Einschalten lädt sich das Modell ohne Handgriff; fehlt es, laufen keine Aufrufe darüber. Quelle:
Hugging Face, fest gepinnt (Nutzer-Wahl), Schwelle danach neu kalibrieren.

- Befund vorab: live `"reranker": "model-missing"` (eingeschaltet, Modell fehlt — also nie aktiv);
  die Reranker-Schalter standen nicht unter `environment:` des Backend-Dienstes und erreichten den
  Container nie; `/models` war schreibgeschützt eingehängt.
- Vergleich HF-Datei (`onnx/model_quint8_avx2.onnx`, Commit `1427fd6`) gegen unseren kalibrierten
  Export (20 Paare, eigene Ladeklasse): Korrelation 0,975, max. Abweichung 1,74, mittlere 0,73; an der
  Sammlungs-Schwelle 0,0 kippen 4/20 Grenzfälle (3× lässt HF relevante Treffer durch, die unser Export
  verwirft; 1× umgekehrt), Einzelinhalt-Schwelle −1,5 unverändert; gleiche Reihenfolge je Frage 5/7.
  Ursache: andere Quantisierungs-Ausgangsdatei (Tokenizer gekreuzt: gleiche Abweichung). Unser Export
  ist auf dem Server nicht nachbaubar (bräuchte Torch/optimum).
- Gebaut (Test zuerst): `services/rag/reranker_bezug.py` (gepinnte Quelle, Größe+SHA-256, atomar über
  Zwischenverzeichnis, Sperrdatei für mehrere Kopien, wartende Kopie übernimmt das Ergebnis,
  `_get_reranker`-Cache danach geleert = ohne Neustart); `rerank.py` (`HF_SLUG` vor altem Export,
  `modell_basis()`, Status `off|downloading|ready|download-failed|model-missing`); Settings
  (`rag_reranker_enabled` Vorgabe False, `RERANK_AUTO_DOWNLOAD`); Start-Vorwärmung stößt den Bezug an;
  Compose (Schalter unter `environment:`, Volume `reranker_models` beschreibbar), Dockerfile
  (`/models` gehört `boerdi`). Tests: `test_reranker_bezug.py` (13), Deploy-Wächter (2), Start (1),
  drei Vorgabe-Tests bewusst auf „aus“ umgestellt.
- **Berichtigung (Review):** wirksam ist `CARD_CE_GATE_COLLECTION` **−1,0** (seit 2026-08-16,
  `card_reranker.threshold_for_tool`); 0,0 stand nur noch im Modulkopf und im unbenutzten
  Settings-Feld (beides berichtigt). An −1,0 und −1,5 trifft die HF-Datei bei allen 20 Paaren
  dieselben Entscheidungen wie der alte Export (knappster Fall 0,12 von der Schwelle) — die
  „4 von 20“ galten für die nicht wirksame 0,0.
- **Offen — Nachmessung** (`CARD_CE_GATE_COLLECTION`, wirksam −1,0, per Umgebung überschreibbar):
  vor dem Einschalten im Betrieb mit dem HF-Modell messen — Paare aus Golden-Läufen (Frage, gezeigte
  Sammlung/Themenseite, Urteil passend ja/nein), Schwelle so wählen, dass die passenden durchkommen.
  Einzelinhalte (−1,5) zeigten keine Abweichung. Lokal liegt unter `backend/models` nur der alte
  Export; der HF-Ordner hat Vorrang, sobald er daliegt (lokal mit `RAG_RERANKER_ENABLED=true` einmal
  starten, dann bezieht er sich selbst).
- 2026-10-15, I-Review (frischer Prüfer, 2 MAJOR, 4 MINOR, NITs — alle bestätigt und behoben, Test zuerst):
  Status blieb bei nicht beschreibbarem Verzeichnis auf `downloading` (Ordner/Sperre jetzt im `try`,
  `bereitstellen` fängt alles → `download-failed`); Sperr-Kennung und Zwischenordner waren nur je PID
  eindeutig — im Container ist das überall 1 (jetzt Rechnername-PID-UUID, `mkdtemp`); Lebenszeichen
  der Sperre alle 30 s, Verfall 5 min statt 30; Gesamtfrist 15 min je Datei; unvollständiger
  Zielordner wird ersetzt; wartende Kopie entscheidet nach Alter der Sperre. Kommentare, INSTALL §8
  (Herkunft, Prüfwerte, Schwellen-Hinweis), Settings-Spiegel der Schwelle berichtigt.

## J — Befunde behoben (Nutzer 2026-10-15)

Auswahl des Nutzers: Nebenbefunde des Katalogs, C-5, die drei älteren Befunde der Liste (§1.4); C-1 nur
auf Nebenwirkungen prüfen, wenn der MCP unverändert bleibt. Alles Test zuerst.

- **`search_skill` fehlt am Server:** nicht aus dem Katalog genommen (von Haus aus verborgen; laut
  Nutzer ein abschaltbarer Rückfall, siehe K). Stattdessen meldet der Abgleich je
  Server `werkzeuge_fehlen_am_server` (Katalog-Werkzeuge, die `tools/list` nicht führt), das Studio
  zeigt am Haken „fehlt am Server“ (`mcp.tool.serverMissing`, de/en). Nur Anzeige, nie gespeichert.
- **`search_wlo_within_collection`:** live gemessen — `excludeNodeIds` wird still übergangen (gleiche
  Treffer), `skipCount` blättert. Schema und Beschreibung auf `skipCount`; eine übergebene
  `excludeNodeIds`-Liste wird zu `skipCount = Anzahl` (alte Gewohnheit des Modells).
- **C-5:** `wlo_list_suggestions` ist lesend (`LESENDE_WLO_WERKZEUGE`), im Lesemodus verfügbar; die
  Wächter nennen die Ausnahme beim Namen.
- **Prompt nennt gesperrte Wissensbereiche:** `_tools_layer` gibt die Bereiche nur weiter, wenn
  `rag` unter den Quellen steht (`response_tool_selection.rag_erlaubt`, dieselbe Regel wie
  `_rag_allowed_for_pattern`). Ändert Antworten → Golden-Lauf (Befundliste §3).
- **markitdown-Folgeabrufe ohne Frist:** `_SsrfGuardAdapter.send` setzt `FOLGEABRUF_FRIST`
  (10 s Verbindung, 30 s Lesen), wenn der Aufrufer keine Frist gibt. Die Gesamtfrist des
  Kindprozesses (Paket 9) bleibt die äußere Grenze.
- **ALT-Sammelrouten:** `PUT /api/config/patterns` und `/personas` prüfen mit `kennungs_einwand`
  (wie das Studio) und schreiben nur, wenn alle Einträge bestehen; „P-“ wird abgewiesen. Dabei
  gefunden: die Muster-Route suchte vorhandene Schlüssel im Prozess-Cache — sah der ihn nicht, legte
  sie ein zweites Dokument mit derselben Kennung an. Jetzt aus der Datenbank (`current_config`).
- **C-1 geprüft (nicht umgesetzt).** Nebenwirkungen bei unverändertem MCP:
  1. Der eigene Abgleich wird zur einzigen Instanz. Gemessen mit den echten Vokabularen (75 typische
     Werte): exakt fast alles; falsch „Wirtschaft“ → Ernährung und Hauswirtschaft, „Technik“ →
     Farbtechnik und Raumgestaltung, „Text“ → Textbausteine (längster Teilwort-Treffer gewinnt);
     ohne Treffer und damit LLM-Rückfall: Oberstufe, Mittelstufe, Gymnasium, Klasse 7, Karte,
     Lehrkraft, Studierende. → Vorbedingung: `_fuzzy_lookup` berichtigen (Befundliste §1.4).
  2. Der LLM-Rückfall kostet je neuem Wert einen Aufruf, gecacht nur im Prozess (je Kopie, bis zum
     Neustart). Weniger als ein Modell-Umlauf für das Nachschlagen, aber nicht null.
  3. Das Modell sieht die Auswahl nicht mehr: Mehrdeutiges („Wirtschaft“: acht Fächer) entscheidet
     still der Abgleich, statt dass das Modell nachfragt oder den passenden Wert wählt.
  4. Lizenz und Schreiben brauchen das Nachschlagen weiter: `license` ist exakt und hat keinen
     Abgleich; die Schreibwerkzeuge laufen nicht durch `TOOL_PREPROCESSORS`.
  5. Die Anweisung steht an fünf Stellen: zwei im Code (`tool_defs`: Werkzeug- und
     Parameter-Beschreibungen; `response_prompt_tools_text`), drei in der Konfiguration (Guardrail
     R-07, `domain-rules`, Muster M05/M09/M12/M18/M20). Code allein zu ändern, ließe die
     Konfiguration widersprechen; die Konfiguration kommt erst per Import auf Staging/Prod — Studio-
     Änderungen dort bleiben stehen. Beides zusammen ändern.
  6. `HELPER_TOOLS` fügt das Werkzeug bei jeder Suche hinzu — bleibt (Lizenz), nur der Text ändert
     sich. Tests prüfen die Werkzeugliste, nicht den Text.
  7. Ändert Antworten und die Folge der Werkzeugaufrufe → Golden-Lauf beider Maschinen. Die 339
     Aufrufe stammen aus dem Server-Protokoll; was es uns an Zeit bringt, zeigen erst unsere Traces
     (Umläufe `lookup → lookup` und `lookup → search` je Zug).
  8. Einmaliger Bruch des Prompt-Caches durch geänderte Werkzeugtexte — vernachlässigbar.

- Prüfung J: Backend 5984 bestanden / 4 übersprungen, ruff sauber, OpenAPI und Bereichs-Schemas
  unverändert; Studio 1491/1491, eslint sauber. Ein Test (`test_respond_agent`, Lesemodus) zählte den
  ganzen Kuratier-Katalog als schreibend — mit derselben benannten Ausnahme wie die Wächter angepasst
  und um „`wlo_list_suggestions` ist im Lesemodus da“ ergänzt.

## K — Offenes aus J abgearbeitet (Nutzer 2026-10-15)

- **`search_skill` (Nutzer):** bleibt im MCP-Server und im Chatbot als Rückfall, falls die Skills über
  die Sammlungen nicht reichen; an- und abschaltbar, von Haus aus nicht genutzt. Der Stand passt
  dazu (Katalog ja, Vorgabe verborgen); bei der Messung war es am Server abgeschaltet, nicht entfernt.
  Studio-Hinweis berichtigt: „… scheitert jeder Aufruf, bis der Server es wieder anbietet“.
- **Abgleich der Filterwerte (Befundliste §1.4):** `arg_resolvers._fuzzy_lookup` nimmt einen Teilwort-
  Treffer nur noch, wenn er eindeutig ist — steckt der Wert in Schlüsseln mit verschiedenen URIs, gibt
  er `None` zurück, und der LLM-Rückfall wählt aus der ganzen Liste. Steckt ein Schlüssel im Wert,
  gewinnt wie bisher der längste. Test zuerst (drei rot, dann grün). Live mit den echten Vokabularen:
  die drei Fehltreffer (Wirtschaft, Technik, Text) sind weg, alle exakten Treffer unverändert; der
  LLM-Rückfall (gpt-6-luna, OpenAI direkt) wählte Wirtschaft → Wirtschaftskunde, Oberstufe →
  Sekundarstufe II, Klasse 7 → Sekundarstufe I, Lehrkraft → Lehrer/in; Text und Karte → keine
  Zuordnung (Bezeichnung geht an den Server). Damit ist die Vorbedingung für C-1 erfüllt; C-1 selbst
  bleibt eine Prompt-Änderung in Code und Konfiguration mit Golden-Lauf (J, Punkt 5–7).

## L — C-1 umgesetzt (Nutzer 2026-10-16)

Auftrag: C-1 umsetzen; Vokabular-Quellen der Nutzerin/des Nutzers (OEH-Vokabulare, Schulfächer im Vordergrund,
Hochschulfächer bewusst nicht) — nicht gebraucht, der Abgleich holt die Vokabulare über
`lookup_wlo_vocabulary` des MCP (24 h Cache). Lizenz (Nutzer-Hinweis: kein fertiges Vokabular, häufige
Werte aus dem Bestand): der MCP führt bereits ein Lizenz-Vokabular (14 Schlüssel samt Aliassen) —
das reicht, ein eigenes aus Suchfacetten ist nicht nötig.

- **Texte (Test zuerst, `tests/test_nachschlagen_nur_fuer_schreiben.py`):** `lookup_wlo_vocabulary`
  nur noch für Schreibvorgänge, Metadaten-Prüfung (z. B. `taxonid` im Browser-Plugin) und das
  Auflisten; für die Suche ausdrücklich nicht — weder Fach, Stufe, Typ, Zielgruppe noch Lizenz.
  Geändert: `tool_defs` (Werkzeug, `learningResourceType`, dreimal `license`), `response_prompt_tools_text`
  (vier Stellen), Seeds R-07, `domain-rules`, M05, M09, M12 (Synonym aus eigenem Wissen — das Vokabular
  ist kein Thesaurus). M18/M20 (Schreiben), Werkzeuglisten und `HELPER_TOOLS` bleiben. Die
  Master-Skill-Vorlagen sagten es NICHT schon so (Review 2026-10-16, #3: M05 „erst, wenn ein
  Begriff nicht greift“, M12 „Filterbegriffe über lookup normalisieren“) — angeglichen, der
  Wächter prüft sie mit; der übertragene Master-Skill in WLO muss nachgezogen werden.
- **Lizenz-Abgleich (Test zuerst, `tests/test_lizenz_abgleich.py`, neues Modul
  `services/mcp/lizenz_abgleich.py`):** exakt nach Vereinheitlichung (Groß/Klein, `-`/`_`,
  Versionsnummer), nie über Teilwörter, kein LLM-Rückfall; „OER“ bleibt (Sammelwert des Servers).
  Gemessen am Server: Schlüssel, Bezeichnung und Alias wirken gleich; „CC BY NC“ filterte still auf
  CC BY, unbekannte Werte wurden still übergangen (→ Feedback an das MCP-Team). Live nach dem Abgleich:
  „CC BY NC“ → `CC_BY_NC` (310 Treffer CC BY-NC statt 3885 CC BY), „cc-by-sa 3.0“ → `CC_BY_SA`
  (9597 statt ungefiltert 47292), „Gemeinfrei“ → `PDM`, „OER“ unverändert.
- **Dabei gefunden und behoben:** der Vokabular-Parser nahm nur `URI: http…` — die Lizenz liefert
  Schlüssel; die ersten Tests sahen es nicht, weil sie den Cache direkt füllten (Test gegen das echte
  Antwortformat nachgezogen). `search_wlo_within_collection` lief nicht durch den Abgleich, obwohl es
  dieselben Filter hat (der Agent nutzt es) — jetzt in `TOOL_PREPROCESSORS`.
- **Deploy:** fünf Konfigurationsbereiche auf Staging/Prod nachziehen (Befundliste §4).

## M — Review der Vokabular-Änderungen (2026-10-16)

Frischer Prüfer (better-coding-review, gegen die echten Server-Vokabulare `wlo-mcp-server-sc/src/vocabs.ts`
nachgerechnet): 3 MAJOR, 3 MINOR, 2 NIT — alle bestätigt und behoben, Test zuerst.

- **#1 Teilwort-Treffer mitten im Wort:** kurze Aliasse trafen in fremde Wörter.
  - Gemessene Fehltreffer: „Literatur“/„Sicherheit“ → Informatik („it“), „Realschule“ → Schule,
    „Hörspiel“ → Lernspiel, „Bildungsplan“ → Bild.
  - Jetzt: Ein Schlüssel zählt nur als ganzes Wort (Beugungsendung erlaubt), mindestens 4 Zeichen,
    und nur, wenn die längsten Treffer eindeutig sind. Steckt der Wert im Schlüssel, muss er am
    Wortanfang stehen („Sicherheit“ ≠ „Arbeitssicherheit“).
  - Live geprüft: Die Fehltreffer sind weg, „Interaktives Material“ und „Info“ wirken weiter.
- **#2 Lizenz:** Was der Abgleich nicht fand, ging roh an den Server, und der filterte über Teilwörter
  falsch („CC BY-NC-SA 3.0 DE“ → CC BY).
  - Jetzt werden Länderzusätze und Versionen abgeschnitten und CC-Werte aus BY/NC/SA/ND gebildet.
  - Nicht Zuordenbares wird weggelassen; dann gilt die Beschreibung „filtert nicht“.
  - Ist das Vokabular nicht ladbar, geht der Wert unverändert durch.
  - Live: „CC BY-NC-SA 3.0 DE“ → `CC_BY_NC_SA` (6511 Treffer), „Public Domain“ (mehrdeutig) wird
    weggelassen, Sammelwerte bleiben.
- **#3 Master-Skill-Vorlagen** (`docs/skills/vorgehen*.md`): Sie empfahlen bei M05/M12 noch das
  Nachschlagen. Angeglichen; der Wächter prüft sie jetzt mit. Der übertragene Master-Skill in WLO
  muss nachgezogen werden (Nutzer).
- **#4 Klassenangaben:** „Klasse 7“ geht unverändert an den Server, der sie exakt kennt, statt an
  den LLM-Rückfall. Wunsch an das MCP-Team, alle Aliasse auszugeben (`mcp-feedback-werkzeuge.md`).
- **#5 Sammelwerte:** „OER“, „freie/offene Lizenz(en)“ und „OER-Lizenz(en)“ bleiben ausdrücklich
  unberührt, auch wenn das Vokabular einmal den Alias „oer“ führte.
- **#6–#8:** `architektur.md` (`skipCount` bei `_within_collection`), M12-Text („Synonym aus eigenem
  Wissen“), Lizenz wird vorgewärmt.

