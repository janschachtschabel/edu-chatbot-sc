# Paket 6: Plan-Rest, Werkszustand und Aufräumen ohne Entscheid

Stand 2026-10-08. Auftrag des Nutzers: „offene punkte vom plan umsetzen, die du ohne
entscheidungen bauen kannst … falls du optimierungen vornimmst die in die seeddaten müssen —
mach das und sorge dafür, dass man eine art factory reset machen [kann] … mit den im repo
ausgelieferten seed daten und konfigs für pattern und andere gesprächs konfigs … nach eigenem
ermessen fortfahren“. Messen und Prüfen im Browser macht der Nutzer danach.

Die Entscheide, die dieses Paket NICHT trifft, stehen kurz erklärt in
[`../entscheidungen-offen.md`](../entscheidungen-offen.md).

## 0 Ausgangslage (geprüft, nicht vermutet)

- **Werkszustand gibt es schon** (Plan [`2026-08-17-werkszustand-im-studio.md`](2026-08-17-werkszustand-im-studio.md)):
  Studio → Sicherung → „Auslieferungsstand aus dem Abbild“ mit „Fehlende nachziehen“ und „Alles auf
  Auslieferungsstand“ (`GET /api/config/seed`, `POST /api/config/seed/apply`, Modus `missing`/`exact`;
  `exact` legt vorher einen Schnappschuss an und läuft seit Paket 4 D4 in einer Transaktion).
  Der Seed-Baum trägt 61 Bereiche, darunter alle 20 Muster, 6 Personas, Domänen-Regeln, Lotse,
  Begrüßung, Gold-Flows. Lücken:
  - Kein Test hält Registry und Seed-Baum in beiden Richtungen fest; heute decken sie sich (37 feste
    Schlüssel), aber nichts verhindert eine Drift.
  - Kein Test prüft jede Seed-Datei gegen ihr Modell. Ein ungültiger Seed käme erst beim Reset ans
    Licht — und `exact` prüft nicht wie das Wiederherstellen (`_apply_config`), es schreibt.
  - Schnappschuss und Vergleich stammen aus zwei Lesevorgängen; ein Speichern dazwischen wird
    überschrieben, steht aber nicht im Schnappschuss.
  - Ohne Studio gibt es nur `boerdi import-config` (überschreibt, löscht nichts, kein Schnappschuss,
    je Bereich eine Transaktion). Ein exakter Reset per Kommandozeile fehlt.
  - Nicht Teil des Resets (bleibt so, wird dokumentiert): Wissensbasis-Dokumente (`import-rag`),
    Master-Skill und Skills (edu-sharing), Umgebungsvariablen, Sitzungen, Logs, Eval-Läufe.
  - **Wichtig für den Nutzer:** `01-base/engine` steht im Seed auf `mode: pattern`. Ein exakter
    Reset stellt eine Anlage also auf die Muster-Maschine — im Betrieb soll laut D-15 der Agent
    Vorgabe sein. Das ist ein Entscheid (Seed-Vorgabe), kein Teil dieses Pakets.
- **Studio:** Muster und Personas sind Ordner-Bereiche (`group-section`), ohne Suche, Zähler,
  Duplizieren und Löschen. Die Dimensionen-Seite stapelt acht `<details>`. Die
  Architektur-Referenz ist ein Port der ALT-Seite und beschreibt nur die Muster-Maschine.
- **ST-3d, ID neuer Dokumente:** Die Regel „erstes Wort“ ist seit Paket 4 D5 ersetzt (Slug des
  ganzen Namens). Offen: Geprüft wird nur der Schlüssel, nie die Kennung; eine Persona wird zur
  Laufzeit über `_persona_slug(id)` gefunden, ein Schlüssel daneben läuft ins Leere.
- **`DELETE /api/config/file`** löscht jeden Bereich, auch `01-base/policy`; der Studio-Weg ruft es
  nie. Gelöschte Seed-Dokumente kommen beim nächsten Start zurück (`migrate` ruft
  `import-config --only-missing`).

## 1 Aufgaben

Je Phase Schritt 0: `/better-coding-workflow` neu laden, bei Studio-Arbeit dazu
`/better-coding-frontend`. Test zuerst, rot gesehen, dann grün.

### Phase B · Backend-Härtung (Befundliste §5)

- **B1 · ReDoS in Studio-Regeln.** Zwei Stellen wenden ein im Studio gepflegtes Muster auf jede
  Nachricht an: Lotsen-Regeln (`02-domain/guide-rules`, `guide_qr_injector.find_guide_match`) und
  Policy-Regeln (`01-base/policy`, `match.message_regex` in `domain/policy.py`).
  - Ein gemeinsames Modul `domain/regel_regex.py`: übersetzen mit `regex` (Apache-2.0 AND
    CNRI-Python, steht über `tiktoken` schon im Lock, wird direkte Abhängigkeit) und suchen mit
    Zeitgrenze. Läuft die Zeit ab, gilt die Regel für diese Nachricht als nicht getroffen, mit
    WARNING im Log (ohne Nachrichtentext).
  - Speichern prüft mit demselben Motor: die Lotsen-Regeln wie bisher, neu auch die Policy-Regeln
    (400 mit Regel und Fehler).
  - Tests zuerst: `^(\w+\s?)*$` gegen eine lange Nachricht endet binnen Frist ohne Treffer; normale
    Muster treffen wie mit `re`; ungültige Policy-Regex beim Speichern → 400.
- **B2 · URL-Import: Frist auch für Kopfzeilen.** `url_safety.hole_begrenzt` (requests im Thread)
  kann Kopfzeilen und Umleitungen nicht begrenzen. Neu: Abruf über `httpx.AsyncClient` mit einem
  Transport, der jede Anfrage (auch jeden Umleitungs-Schritt) per `assert_public_url` prüft, unter
  `asyncio.timeout(frist)` für Verbindung, Kopfzeilen, Umleitungen und Rumpf; Bytedeckel wie bisher.
  - Tests zuerst: ein lokaler Server, der Kopfzeilen tröpfelt, endet zur Frist; Umleitung auf eine
    interne Adresse wird abgewiesen; Bytedeckel per Kopfzeile und beim Lesen.
- **B3 · Tests, die unter Last still fehlen.** Die Proben `pg_available`/`dev_db_ready` laufen je
  Prozess einmal (Cache) mit längerer Frist; in der CI (`CI=true`) wird ein Überspringen durch
  diese Tore ein Fehler.
- **B4 · „Tool not found“ als Transport.** Meldet ein Server einen JSON-RPC-Fehler „Methode nicht
  gefunden“ oder „ungültige Parameter“, hat er geantwortet und nichts ausgeführt: Art `tool`, keine
  Wiederholung. Andere JSON-RPC-Fehler bleiben `transport` (ob geschrieben wurde, ist offen).
- **B5 · `PUT /api/config/patterns` und `sources: []`.** `PatternEntry.sources` wird
  `list[str] | None`; geschrieben wird, wenn nicht `None`. Vertrag neu erzeugen (bewusst).
- **B6 · Umwandlungsfehler beim RAG-Import.** `Umwandlungsfehler` trägt eine Art; der Router
  antwortet zweisprachig, ein fehlendes Paket im Image mit 500 (Fehler des Servers), eine
  unsichere oder nicht ladbare Adresse mit 400, ein Format ohne Wandler weiter mit 415.
- **B7 · Abnahme-Zug im Agent-Modus als `M18`** (Runde-2-Plan N-5, kosmetisch): nur wenn die
  Kennzeichnung an einer Stelle hängt; sonst als Befund stehen lassen.

### Phase W · Werkszustand

- **W1 · Wächter für den Seed.** Tests: (a) jeder feste Schlüssel der Registry hat eine Seed-Datei,
  jede Seed-Datei hat ein Modell (Gruppen über das Präfix); (b) jedes Seed-Dokument besteht die
  Prüfung, die auch das Wiederherstellen macht (Modell, Schlüssel, Lotsen- und Policy-Regex,
  reservierte Kennung). Rot belegt mit einer kaputten Kopie im Temp-Ordner.
- **W2 · Seed-Anwenden prüft wie das Wiederherstellen.** Erst prüfen (422 mit Liste, nichts
  geschrieben, kein Schnappschuss), dann Schnappschuss und Vergleich aus EINEM Lesevorgang, dann
  schreiben und löschen in einer Transaktion. Eine Dienst-Funktion für Studio und Kommandozeile.
- **W3 · Kommandozeile.** `boerdi import-config --exact` (Schnappschuss, schreiben, löschen, eine
  Transaktion) und `--dry-run` (zeigt neu/abweichend/nur in der Datenbank, schreibt nichts).
- **W4 · Doku.** `deploy/README.md` und `INSTALL.md`: Werkszustand im Studio und per
  Kommandozeile, was er umfasst und was nicht, der Hinweis zur Vorgabe-Maschine.

### Phase S · Studio (Betriebsmodi-Plan §9.3, mit Z2 fällig)

- **S1 · ST-3d Ordner-Bereiche als Liste│Editor** (Muster, Personas).
  - Backend: `POST /api/config/documents` (`{group, id, label, source?}`) legt ein Dokument an
    oder dupliziert eins. Der Server leitet den Schlüssel ab (Muster: Slug der Kennung; Personas:
    `_persona_slug`), prüft die Kennung (nicht leer, ohne Leerzeichen, nicht reserviert, in der
    Gruppe eindeutig ohne Rücksicht auf Groß/Klein) und das Modell; 409, wenn es sie schon gibt.
  - `DELETE /api/config/file` nur noch für Dokumente in `03-patterns/` und `04-personas/`,
    zweisprachige Fehler, optional `expected_version` (409).
  - Studio: Liste links mit Zähler, Suche, Titel je Eintrag, Neu, Duplizieren, Löschen (Rückfrage
    in zwei Schritten; bei Dokumenten aus dem Auslieferungsstand mit dem Hinweis, dass der nächste
    Start sie wieder anlegt). Die Seitenliste aus `object-list` wird dafür eine eigene,
    darstellende Komponente.
- **S2 · ST-4c Reiter mit Zählern** (Dimensionen). Kopfkarte mit den Zahlen (Personas, Intents,
  States, Entities, Signale; ein Abruf `/config/elements`) und Reiter statt gestapelter Abschnitte;
  die drei NEU-Bereiche ohne ALT-Reiter bekommen Reiter ohne Zahl. Nach dem Speichern zählt die
  Seite neu. Offene Änderungen bleiben beim Reiterwechsel erhalten.
- **S3 · Architektur-Referenz für beide Maschinen.** Ablauf nach dem echten Graphen (13 Knoten,
  drei frühe Ausgänge), ein Abschnitt „Zwei Maschinen“ (Unterschiede, Agent-Kette, Werkzeuge,
  Deckel und Ende-Gründe, Schreib-Abnahme, SF-1), die aktive Vorgabe-Maschine live
  (`/config/effects`); veraltete Aussagen raus (feste Werkzeugzahl, „sieben Phasen für jede
  Nachricht“, Port-Notizen „ALT nannte …“).
- **S4 · Wirksame Wissensbereiche je Muster** (externes Audit F13): Das Formular zeigt, welche
  Bereiche bei „nicht gesetzt“ tatsächlich wirken, und dass ohne `rag` unter den Quellen keine
  wirken.

### Phase G · Gatekeeper-Skill per Knoten-ID

Untersuchung (nur lesend, Code beider Seiten und eine kleine Lese-Probe am MCP-Server). Liegt die
Ursache in unserem Code, wird sie hier behoben; sonst wird der Befund mit Beleg dokumentiert.

### Phase R · Dateien über 300 Zeilen (verhaltensgleich)

Nur Schnitte, die im Plan stehen oder die dieses Paket ohnehin berührt; je Datei ein eigener
Schritt, die vorhandenen Tests sind der Beleg. Mindestens: `services/rag/ingest.py` →
`services/rag/umwandeln.py`; Studio `schema-form.scss` (Teildateien je Baustein),
`curated-views.ts` und `i18n/catalogue/curated.ts` (nach Seitengruppen), `schema-field` (nach
Feldarten), `eval-run-detail` (Gold-Zug-Tabelle als Komponente), `i18n/catalogue/area-editor.ts`.
Was bleibt, steht danach in der Befundliste §5.

### Abschluss

- Volle Suiten (Backend, Frontend), ruff, eslint, `check:*`, Vertrags-Wächter.
- Ein frischer Prüfer liest den Diff.
- Befundliste, Pläne und Memory nachziehen; Erledigtes streichen.
- Commit, Upload und Deploy macht der Nutzer (oder auf ausdrücklichen Auftrag).

## 2 Nicht in diesem Paket

- Alles in [`../entscheidungen-offen.md`](../entscheidungen-offen.md), darunter die Seed-Vorgabe der
  Maschine und das Studio-Startpaket (aufteilen der Kataloge widerspräche der bewussten Regel „beide
  Sprachen beieinander“).
- B1–B3 (Anrede): nach der Nachmessung.
- Läufe gegen Staging, Golden-, Eval- und Lasttests: Nutzer.

## Log

### B1 · erledigt — ReDoS in Studio-Regeln
- `domain/regel_regex.py`: `uebersetze`/`trifft` mit `regex` und Zeitgrenze 0,05 s; eine abgelaufene Suche gilt als kein Treffer (WARNING mit Muster, ohne Nachrichtentext). Lotsen-Regeln (`guide_qr_injector`) und Policy-Regeln (`domain/policy.py`) nutzen es; das Speichern prüft beide mit demselben Motor (`config_guards`, neu `policy.regexInvalid`). `regex>=2026.7.10` ist direkte Abhängigkeit (Lock-Diff: nur die Markierung „direkt“).
- Befund beim Bau: `regex` löst den klassischen Fall `^(\w+\s?)*$` selbst sofort; die Zeitgrenze greift bei Mustern, die seine Schutzmechanik aushebeln (`^(?:a|(?=a)a)+$`, gemessen Abbruch nach 0,05 s). Ohne Fix (mit `re`) brauchten Lotse und Policy je 6,7–7,7 s für 26 Zeichen.
- Tests: `tests/test_regel_regex.py` (7, vorher 7 rot); die Lotsen-Tests pinnen ihre Regeln jetzt mit `regel_regex.uebersetze` statt `re.compile`.

### B2 · erledigt — URL-Import: Frist auch für Kopfzeilen
- `url_safety.hole_begrenzt` ist jetzt asynchron: `httpx.AsyncClient` mit `_SsrfTransport` (prüft jede Anfrage, auch jeden Umleitungs-Schritt, DNS im Thread) unter `asyncio.timeout(frist)` für Verbindung, Kopfzeilen, Umleitungen und Rumpf; Bytedeckel wie bisher. Der Wächter-Thread (`_abschalten`) entfällt. `DownloadAbgebrochen` trägt `grund` (`zu_gross`/`zu_langsam`) und `wert`.
- Gegenprobe vorher: tröpfelnde Kopfzeilen, Frist 0,3 s → Abbruch erst nach 3,31 s (Ende des Servers). Tests gegen echte Sockets: `tests/test_url_safety.py` (7 neue Abruf-Tests, darunter Kopfzeilen und Umleitung nach innen).

### B3 · erledigt — DB-Tore in der CI
- `tests/pg_utils.py`: Proben je Prozess einmal (`functools.cache`), Frist 10 s. `tests/db_tor.py` + Hook in `conftest.py`: mit `CI=true` wird ein Überspringen durch ein DB-Tor ein Fehler.
- Beleg: `CI=true` mit unerreichbarer Datenbank → `test_guide_mode_endpoint.py` 9 Fehler statt 9 still übersprungen; ohne `CI` wie bisher übersprungen; der ALT-Paritätstest mit eigenem Grund bleibt übersprungen.

### B4 · erledigt — JSON-RPC „nicht gefunden“ ist kein Transportfehler
- `services/mcp/transport.py`: `McpError` mit `METHOD_NOT_FOUND`/`INVALID_PARAMS` (auch in einer `ExceptionGroup`) → Art `tool`, keine Wiederholung. `INTERNAL_ERROR` bleibt `transport`. Tests in `test_mcp_transport.py` (vorher 3 rot).

### B5 · erledigt — `sources: []` bleibt „keine Quelle“
- `PatternEntry.sources: list[str] | None`, geschrieben wenn nicht `None` (wie `rag_areas`). Der OpenAPI-Vertrag bleibt unverändert: die Route prüft die Einträge selbst. Test in `test_config_area_endpoints.py` (vorher rot, `KeyError: 'sources'`).

### B6 · erledigt — Umwandlungsfehler je Art, zweisprachig
- `Umwandlungsfehler` trägt `art` (`datei`, `format`, `server`, `adresse`, `abruf`, `zu_gross`, `zu_langsam`), `detail` und `wert`; der Text bleibt ALT-treu. `api/rag_umwandlung.py` (neu, aus `api/rag.py` herausgelöst, das sonst auf 315 Zeilen gewachsen wäre) bildet die Art auf Status und Satz ab: fehlendes Paket 500, Format 415, sonst 400 — Sätze de/en in `i18n/messages.py`. Eine Umleitung nach innen ist ein Adressfehler.
- Tests: `test_rag_router_ingest.py` (6 Arten × 2 Sprachen) und `.art`-Zusicherungen in `test_rag_umwandeln.py`; der 400-Test erwartet jetzt den zweisprachigen Satz statt des rohen Texts (gewollte Änderung).

### B7 · bleibt Befund
- Die Kennzeichnung `M18` hängt an einer Stelle (`write_approval._PATTERN_ID`), die Maschine aber steht im Vorlauf nicht fest: `preflight` bekommt `engine` nicht, und der Debug-Block des Abnahme-Zugs hat kein `engine`. Eine Korrektur bräuchte drei Stellen für einen kosmetischen Punkt — stehen gelassen, Befundliste §5 präzisiert.

### R1 · erledigt — `services/rag/ingest.py` geteilt
- Die Umwandler stehen in `services/rag/umwandeln.py` (verbatim verschoben), `ingest.py` hat 170 Zeilen. Tests entsprechend: `tests/test_rag_umwandeln.py` (Umwandler), `tests/test_rag_ingest.py` (Speichern).

### G · Gatekeeper-Skill per Knoten-ID — untersucht, drei Folgebefunde behoben
- Lese-Probe gegen den eingestellten MCP-Server (anonym): Die Sammlung „Optik“ (`9e7ae956…`) nennt drei Skills, `unresolved: []`; der Gatekeeper `5400fc80-2962-4083-80fc-802962908315` ist öffentlich, ein Original vom Typ `ai_skill`, und `get_skill` lädt ihn (2 621 Zeichen, vier Wiederholungen). **Nicht nachgestellt.** Den gemeldeten Satz „ist nicht abrufbar“ erzeugt der Server nur, wenn die übergebene Kennung abweicht (Präfix, eine Ziffer, Großschreibung, Titel statt ID) — oder bei jeder Störung beim Laden, denn er fasst 404, 401/403 und 5xx in denselben Satz. Wahrscheinlich hat das Modell eine abweichende Kennung übergeben (so schon 2026-08-16 gemessen: erfundene IDs).
- **G1:** Dieser Fehltreffer stand 180 s als Treffer im Cache (`tool_cache`); ein vorübergehender Ausfall spielte sich bei jedem neuen Versuch ab. Jetzt: `darf_cachen` lässt `get_skill`-Antworten mit „ist nicht abrufbar (“ aus. Test in `test_mcp_client.py` (vorher rot).
- **G2:** Der Nachfass-Hinweis nach `get_skill_registry` („jetzt get_skill mit DESSEN nodeId“) las nur die JSON-Hülle, das Werkzeug antwortet aber in Markdown (Vorgabe) — er stand im Betrieb nie da. Jetzt beide Formen (`_katalog_hat_eintraege`). Tests in `test_skill_registry_note.py`.
- **G3:** `katalog_aus_markdown` (vorher privat) hängte die Schlussnotiz des Servers an die Beschreibung des letzten Eintrags, wenn der keine Keywords hatte. Jetzt endet ein Eintrag an der Leerzeile. Test in `test_tool_result_redaction.py`.
- Nicht in unserem Code: Der MCP-Server sollte die Störung beim Laden unterscheiden (`readNodeMetadata` statt `getNodeMetadata` in `src/services/skills.ts:258`) — Vorschlag für die Pflegenden des Servers, hier nicht geändert. Zum Bestätigen auf Staging: Backend-Log `MCP tool get_skill args:` (die übergebene Kennung) und am Server `upstream returned non-OK`.

### W1 · erledigt — Wächter für den Seed
- `tests/test_seed_waechter.py` (5, ohne Datenbank): jeder feste Registry-Bereich hat eine Seed-Datei, jede Seed-Datei ein Modell, beide Gruppen bringen Dokumente mit, und der ganze Baum besteht `pruefe_bereiche` — dieselbe Prüfung wie ein Wiederherstellen. Gegenprobe: eine Kopie mit `mode: kaputt` wird mit 422 und Bereich abgewiesen.
- `api/config_guards.pruefe_bereiche` ist die aus `_apply_config` herausgezogene Prüfschleife (Wiederherstellen und Seed teilen sie jetzt). Damit `config_guards.py` unter 300 Zeilen bleibt (es wäre auf 324 gewachsen), stehen die Fehler-Antworten (400 nicht speicherbar, 409 Konflikt) jetzt in `api/config_antworten.py`.

### W2 · erledigt — Seed-Anwenden prüft und liest einmal
- `seed_sync.herstellen` (ein Ablauf für Studio und Kommandozeile): erst prüfen, dann den gelebten Stand EINMAL lesen — Schnappschuss und Vergleich aus demselben Lesevorgang —, dann schreiben und löschen in einer Transaktion. `POST /api/config/seed/apply` nutzt ihn; ein ungültiger Seed ergibt 422, ohne Schnappschuss und ohne Schreiben (vorher 200 und geschrieben).
- Tests: `test_seed_sync.py` (4 neue, ohne Datenbank: Reihenfolge, ein Lesevorgang, Abweisung vor allem), `test_snapshots_endpoints.py` (ungültiger Seed, vorher rot mit 200).

### W3 · erledigt — Werkszustand per Kommandozeile
- `boerdi import-config --exact` (Schnappschuss „vor Auslieferungsstand (Kommandozeile)", schreiben, löschen; Grenze von 50 Schnappschüssen wie im Studio) und `--dry-run` (nur die Listen). `--exact` mit `--only-missing` und `--dry-run` ohne `--exact` → Rückgabe 2. Tests in `test_cli_seed.py` (5 neue, vorher rot).
- Probelauf gegen die lokale Dev-DB mit dem echten Seed: 55 gleich, 6 abweichend, 0 neu, 0 nur in der DB. Abweichend sind `02-domain/domain-rules`, `04-personas/elt`, `04-personas/ler` (Import vom 2026-08-16, der Seed ist neuer), `01-base/engine` (lokal `agent`, Seed `pattern`), `01-base/pricing` (lokal USD mit gpt-6-Preisen) und `01-base/context-actions` (nur ein Zeilenende). Keine davon ist eine Optimierung, die in den Seed gehört.

### W4 · erledigt — Doku
- `deploy/README.md`: „Werkszustand per Kommandozeile" und „Was der Werkszustand umfasst — und was nicht", mit dem Hinweis zur Maschine (Seed `pattern`). `INSTALL.md`: `--exact`/`--dry-run` neben dem Voll-Import.

### S1 · erledigt — ST-3d: Ordner-Bereiche als Liste│Editor
- Backend: `api/config_documents.py` (neu). `POST /api/config/documents` legt ein Muster oder eine Persona an oder dupliziert eine (`source`); der Server leitet den Schlüssel ab (Muster: Kennung klein, Personas: `_persona_slug` — dort sucht die Laufzeit) und hält die Kennung je Ordner eindeutig, ohne Rücksicht auf Groß/Klein (409). `pruefe_kennung` gilt auch beim Speichern über Formular und Rohtext; eine Persona-Kennung, die nicht zu ihrem Schlüssel passt, wird abgewiesen (400). `DELETE /api/config/file` zog aus `config.py` (299 → 291 Zeilen) hierher und lässt die feste Konfiguration stehen: löschbar sind Muster, Personas und Bereiche ohne Modell (Tippfehler bleiben entfernbar), Antworten zweisprachig. Vertrag neu erzeugt: ein Pfad, ein Schema (`DocumentCreate`), zwei Beschreibungen; Zeile unter „Die Zusätze“, Routen-Inventar ergänzt.
  - Tests: `tests/test_config_documents.py` (16, vorher alle rot). Der alte Test `test_file_write_and_delete` löschte `01-base/welcome-config` — jetzt 400; der Rundlauf geht über einen Bereich ohne Modell (gewollte Änderung).
- Studio: Die Seitenliste von `object-list` ist eine eigene darstellende Komponente (`schema-form/entry-list.component`, Zähler, Suche, Titel mit Kennung, `aria-current`); `object-list` nutzt sie verhaltensgleich (13/13 Tests unverändert grün). `group-section` nutzt sie für Muster und Personas, dazu Duplizieren (freie Kennung `<id>_kopie`, `_kopie_2` …, nicht bei offenen Änderungen) und Löschen mit Rückfrage im Text (`role="alert"`), die sagt, ob das Dokument zum Auslieferungsstand gehört (dann legt es der nächste Start wieder an) oder nur in dieser Anlage steht. Der Verkehr mit dem Server steht in `views/group-documents.ts`, der Zustand der Feld-Reiter in `views/feld-reiter.ts` (die Komponente bliebe sonst über 300 Zeilen). Anlegen geht über die neue Route; der Name geht als JSON-Feld, kein YAML-Text mehr im Studio.
  - Tests: `group-section-ordner.spec.ts` (9 neu) und der angepasste `group-section.component.spec.ts` (Selektoren der neuen Liste, Anlegen über `POST /config/documents`).
- Texte: `groupSection.*` zog aus `i18n/catalogue/area-editor.ts` (306 → 269) in den eigenen Teil `group-section.ts`.
- `schema-form.scss` (458) ist entlang der Bausteine geteilt (`_sf-aufbau`, `_sf-eingaben`, `_sf-bausteine`, `_sf-meldungen`, Nabe 16 Zeilen); das kompilierte CSS ist byte-gleich (mit `sass` vorher/nachher verglichen).
- Im Browser gefunden (lokales Studio, Muster-Ordner): Das Raster teilte die Breite mit `auto-fit` gleich auf, und die Statuszeile belegte als drittes Element eine eigene Spalte — der Editor bekam ein Drittel. Jetzt eine Container-Abfrage wie bei `object-list` (Liste 15–20 rem, Editor der Rest; Zustand und Statuszeile über die ganze Breite). Geprüft im Browser: Anlegen, Duplizieren, Rückfrage beim Löschen samt Abbrechen, Liste und Suche, schmale Breite.

### R2 · erledigt — `eval-run-detail` (Gold-Zug-Tabelle als Komponente)
- Die Zug-Tabelle eines Gold-Laufs steht in `views/eval-gold-turns.component` (Eingaben `runId`, `metrics`, `conversations`), die Gesprächs-Typen in `views/eval-transcript.ts`, die geteilten Textzeilen in `views/_eval-text.scss`. `eval-run-detail.component.ts` 315 → 181 Zeilen; Klassen und DOM unverändert.
- Vorher festgehalten (gegen den alten Stand grün): ein offener Zug schließt beim Wechsel zu einem anderen Lauf und bleibt beim Neuladen desselben Laufs offen — deshalb bekommt die Tabelle die Kennung des Laufs, nicht nur die Metriken. 31/31 vorher und nachher.

### R3 · erledigt — `schema-field` (nach Feldarten)
- Die Regeln einer Liste (Einträge, Chips ST-2g, hervorgehobener Eintrag ST-2i) stehen in `schema-form/list-items.ts`, die einer Map (anlegen, entfernen, umbenennen) in `schema-form/map-entries.ts`; die Komponente rendert und rekursiert (`list.…`, `map.…` im Template). 320 → 191 Zeilen; DOM und Stile unverändert, die Vorlage bleibt bei 300.
- Gegenprobe mit eingebauten Fehlern: der Listen-Fehler fiel auf, der Map-Fehler (abgewiesene Umbenennung setzt das Feld nicht zurück) nicht — die vorhandene Prüfung lief über die RAG-Karte, seit ST-3 eine Objekt-Liste. Zwei Tests für die einfache Karte ergänzt; der Fehler fällt jetzt auf. Formular-Tests 289/289.

### S2 · erledigt — ST-4c: Dimensionen als Reiter mit Zählern
- `CuratedView.layout: 'tabs'` und `CuratedAreaSection.count`; die Dimensionen-Seite nutzt beides. Neue Komponente `views/curated-tabs.component`: Kopfkarte (je gezählter Achse „2 Personas — wer fragt“, Mehrzahl nach Sprache), Reiterleiste mit Zahl (`TabDef.count`, Name des Reiters „Personas (6)“), ein Reiter je Abschnitt; die drei NEU-Bereiche ohne ALT-Reiter ohne Zahl. Die Zahlen kommen aus einem Abruf (`/config/elements`) und werden nach jedem Speichern, Anlegen, Duplizieren oder Löschen neu geholt (`changed` an `area-section` und `group-section`). Besuchte Reiter bleiben eingehängt (verborgen per `hidden`); der Verlassen-Schutz der Seite zählt sie mit.
- Beim Bau gefunden und mit Test belegt: Der erste Reiter war nur über die Vorgabe offen und wäre beim Wechsel ausgehängt worden — offene Änderungen dort gingen verloren.
- Vorher geteilt (verhaltensgleich): `views/curated-views.ts` (399 → 91; Seiten in `curated-pages-inhalt.ts` und `curated-pages-betrieb.ts`) und `i18n/catalogue/curated.ts` (386 → 240 + `curated-betrieb.ts`).
- Tests: `curated-tabs.component.spec.ts` (5), Zähler in `tab-bar.component.spec.ts`.

### S3 · erledigt — Architektur-Referenz für beide Maschinen
- Neuer erster Abschnitt „Zwei Maschinen: Muster und Agent“ (`views/reference-machines.component`, Texte `i18n/catalogue/reference-machines.ts`): wer wählt (Studio, Attribut `engine`, Kopfzeile), die Vorgabe dieser Anlage live aus `/config/effects`, was beide teilen (Vorlauf, Sicherheit, Nachbereitung), eine Gegenüberstellung in fünf Zeilen (Einordnung, Steuerung, Werkzeuge, Ablauf, Schreiben) und SF-1 (Krise und Bedrohung antwortet auch im Agent-Modus die Muster-Maschine).
- Berichtigt: Pipeline, Input-Elemente und Prompt-Schichten sagen jetzt „im Muster-Modus“; die Port-Notiz „ALT nannte …“ ist weg; die feste Werkzeugzahl 12 (stimmte längst nicht mehr) ist ersetzt durch den Verweis auf „Werkzeuge und Sperren“; RAG- und MCP-Zugang nennen beide Maschinen; das Beispiel heißt „… im Muster-Modus“; der Kommentar an `PIPELINE` sagt, dass es ALTs Phasen sind, nicht die 13 Knoten des Graphen.
- Tests: `architecture-reference.component.spec.ts` (5 neu, zwei Zusagen an die neue Gliederung angepasst).

### S4 · erledigt — Wirksame Wissensbereiche je Muster (F13)
- `views/wirksame-bereiche.ts`: die Regel von `domain/route_head._resolve_rag_areas` als Zwilling (gesetzte Liste wörtlich, ohne `rag` keine, sonst der Katalog; ohne `sources` gilt die Engine-Vorgabe `["mcp"]`), der Satz dazu und der Zustand (`RagHinweis`, lädt `05-knowledge/rag-config` beim ersten offenen Muster). Das Muster-Formular zeigt den Satz im Reiter „Tools & Wissen“.
- Tests: `wirksame-bereiche.spec.ts` (5; Mutationsprobe: ohne die Quellen-Regel fallen 2) und ein Komponententest in `group-section-ordner.spec.ts`.

### Review · zwei frische Prüfer (2026-10-09)
Backend 16 Befunde, Studio 11, jeder am Quelltext nachgeprüft; je Befund erst ein Test, der rot war (Ausnahmen: reine Abdeckungs-Lücken, dort sagt es der Test).
- **Studio, behoben:**
  - Wirksame Wissensbereiche (S4): Der Zwilling kannte nur `route_head._resolve_rag_areas`, nicht die Quellen-Sperre `_rag_allowed_for_pattern` — ein Muster mit `sources: [mcp]` und gesetzter Liste zeigte Bereiche als wirksam, die die Laufzeit sperrt. Jetzt erst die Sperre, dann die Liste, als Vorgabe nur „immer“ und danach „auf Abruf“.
  - Lösch-Rückfrage an EIN Dokument gebunden (`views/loesch-rueckfrage.ts`): Duplizieren bei offener Rückfrage ließ „Ja, löschen“ die Kopie treffen, mit dem Auslieferungs-Hinweis des Originals. Ein Fehler steht nur bei seinem Dokument. Fokus: Rückfrage → „Abbrechen“, Abbrechen oder Fehler → „Löschen“, nach dem Löschen → Kopf der Liste. Während Anlegen, Duplizieren oder Löschen laufen, sind Wahl und Knöpfe gesperrt; ein angelegtes Dokument öffnet nicht über inzwischen begonnene Änderungen (`groupSection.createdNotOpened`).
  - Bedingtes Löschen: das Studio schickt den geladenen Stand, 409 hat einen eigenen Satz (`groupSection.removeConflict`).
  - Generationszähler für die Ordner-Liste und die Zähl-Abrufe der Reiter-Seite; jeder Reiter hat seinen Bereich (`aria-controls` zeigte bei ungeöffneten Reitern ins Leere); die Live-Region des Wissensbereiche-Satzes steht vorher im DOM.
  - `visually-hidden` gab es nirgends (schon im alten `object-list`): „enthält einen Fehler“ stand sichtbar da — jetzt `.sr`.
  - Architektur-Referenz: „Der Weg eines Zugs“ mit den 13 Knoten und den drei frühen Ausgängen — S3 versprach das, gebaut war nur die Gegenüberstellung. Der Seitenkontext beendet keinen Zug (der Vorlauf-Satz behauptete es); die sieben Phasen heißen jetzt eine Sicht auf die Muster-Maschine; der Satz zur Werkzeugzahl ist berichtigt.
  - Neue Tests auch für Verhalten, das schon stimmte: offene Änderungen im verborgenen Reiter, der Hinweis nur unter „Tools & Wissen“, Löschen mit offenen Änderungen. Tote Regel `.erd-hint code` entfernt (der Code steht im Template von `studio-rich`).
- **Backend, behoben:**
  - Vertrag: der Docstring von `DELETE /api/config/file` war nach der letzten Änderung nicht neu erzeugt — einziger Fehlschlag des ersten Gesamtlaufs (5288 bestanden).
  - „Kennung vergeben“ melden die Speicher-Routen mit 400 statt 409: dort heißt 409 „inzwischen gespeichert“, das Studio zeigte den Konflikt-Kasten ohne Grund, und „Trotzdem speichern“ lief wieder hinein. `POST /documents` bleibt 409.
  - Persona „P-“ ergab den Schlüssel `04-personas/` (weder bearbeit- noch löschbar) — jetzt 400; die Gruppenregel kommt aus `config_guards._single_group_leaf`. Die Form der Kennung (`_KENNUNG`) gilt auch beim Speichern.
  - Sicherheits-Muster (M01, M02, `crisis_pattern`/`threat_pattern`) lassen sich weder löschen noch umbenennen — die Umbenennung als Variante selbst gefunden: Der nächste Start legte das Muster nicht nach, weil der Schlüssel belegt bleibt.
  - `DELETE /api/config/file?expected_version=` (Plan S1, fehlte): 409 wie beim Speichern, `services/config_conflict.delete_checked`.
  - Policy: Ein Ausdruck, der kein Text ist (`2024`), passierte die Prüfung (`str(…)`) und warf zur Laufzeit einen TypeError in jedem passenden Zug. Jetzt beim Speichern abgewiesen, zur Laufzeit übersprungen.
  - URL-Import: `httpx` las bei `follow_redirects` jeden 3xx-Rumpf ganz, am Bytedeckel vorbei. Jetzt folgt `hole_begrenzt` selbst und schließt jeden Schritt ungelesen.
  - `httpx`-Logger auf WARNING in `_configure_logging`. Im Betrieb war das schon so — LiteLLM setzt es beim Import —, jetzt hängt es nicht mehr an dieser Nebenwirkung.
  - Einen Schnappschuss anlegen steht an einer Stelle (`snapshots.schnappschuss_anlegen`; drei Kopien in Studio-Route, Seed-Anwenden und Kommandozeile). Das Log „angewandt“ kommt erst nach dem Schreiben.
  - `i18n/messages.py` (328 Zeilen) geteilt: Ordner- und Import-Meldungen in `messages_dokumente.py`, ein Test gegen doppelte Schlüssel.
  - Tests: Der Wiederherstellen-Test „löschte“ einen festen Bereich (seit S1 abgewiesen, ungeprüft) und belegte nichts mehr — jetzt ändern und löschen mit Statusprüfung. Die Policy-Zeitgrenze an einem Ausdruck, an dem auch `regex` zurückspringt. Der Seed-Wächter prüft Kennungsform, Eindeutigkeit je Ordner und den Persona-Schlüssel (der Seed hält alles ein).
  - README: Was der Werkszustand mit nachträglich angelegten Wissensbereichen macht.
- **Entscheid statt Fix:** Policy bei Zeitüberschreitung „trifft nicht“ (wie geplant) — ob sperrende Regeln dann greifen sollen, steht in `entscheidungen-offen.md`.
- **Ältere Befunde** (nicht aus Paket 6) stehen in der Befundliste §1.5 und §5: Prompt nennt gesperrte Wissensbereiche, markitdown-Folgeabrufe ohne Frist, ALT-Sammelrouten ohne die S1-Regeln, fest deutsche Reiter-Namen, blockierendes `getaddrinfo` in der Restore-Prüfung.

### Abschluss · Prüfstand nach dem Review (2026-10-09)
- Backend: voller Lauf 5302 bestanden, 4 übersprungen (Umgebung: Valkey, ALT-Baum, Live-Dienste), 0 Fehlschläge. ruff sauber, `export_openapi --check` unverändert, Lizenz-Tor und `pip-audit` (Lock-Export, wie in der CI) ohne Befund — neu ist `regex` 2026.7.10 (Apache-2.0 AND CNRI-Python).
- Frontend: ui 867, widget 71, studio 1434, alle grün; eslint ohne Befund; `check:tokens`, `check:a11y`, `check:contrast`, `check:radii`, `check:docs`, `check:audit` grün. Produktions-Build ohne Budget-Meldung, Startpaket 1,09 MB (Warnung ab 1,1 MB).
- Browser (lokales Studio, nur lesend): „Der Weg eines Zugs“ mit 13 Knoten und drei markierten Ausgängen; Lösch-Rückfrage mit Fokus auf „Abbrechen“, nach dem Abbrechen zurück auf „Löschen“ — abgebrochen, nichts gelöscht; die leere Live-Region versteckt, unter „Tools & Wissen“ der Satz zu den wirksamen Bereichen.
- Nicht hochladen: `.claude/launch.json` (lokale Vorschau mit Maschinenpfaden).

