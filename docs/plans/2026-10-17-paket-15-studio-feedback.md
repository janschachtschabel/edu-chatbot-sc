# Paket 15 — Studio nach Nutzer-Rundgang: Fehler beheben, Seiten neu schneiden

Stand: freigegeben 2026-10-17 („better coding workflow skill nutzen und umsetzen wie vorgeschlagen“), gebaut 2026-10-18; Abnahme (Review, Testcontainer) siehe Log.

## 1 Ziel

Die Anmerkungen aus dem Studio-Rundgang des Nutzers nach Paket 14 umsetzen:
- die Fehler mit Wirkung beheben (falsche Anzeige von Vorgaben, Streaming-Vorgabe, Eval-Start, Vermischung Agent/Muster in der Auswertung);
- Werkzeuge, Skills und Zielgruppen als gemeinsame Seiten neu ordnen;
- die verschachtelten Formulare (Anzeige, Tour & Lotse, Kontext-Aktionen, Sicherung) lesbar machen.

## 2 Ausgangslage (fünf Prüfungen, 2026-10-17, nur lesend)

| Befund | Ursache | Beleg |
|---|---|---|
| Token-Streaming „an“, wirkt aber nicht | Im Agent-Modus streamt nur `respond_to_user`; das Werkzeug gibt es nur mit `betrieb.agent_schnellantworten` — Vorgabe `false`. Das Studio zeigt die Abhängigkeit nicht. | `respond_agent.py:110`, `domain/stream_gate.py:31`, `seeds/01-base/engine.yaml:80`, `config_models/engine.py:182`; Log `boerdi-chat-test` 19:20:54 „gesperrt (ohne_antwort_werkzeug)“ |
| RAG im Agent „aus“, wirkt aber | Studio zeigt einen nicht gespeicherten Schlüssel als aus/leer; der Server nimmt die Modell-Vorgabe (`RagAreaDef.agent=True`). | `schema-form/field-control.component.ts:73`, `api/config.py:214-218` |
| „Rolle & Grenzen“ leer | dieselbe Ursache: `agent_rolle` fehlt im Dokument, der Agent nutzt `ROLLE_VORGABE` + R-05/R-08/R-13/R-15; wer eine Regel ergänzt, ersetzt die vier still. | `config_models/engine.py:132,150,164`, `agent_kopf.py:131` |
| RAG-Bereich ohne `mode` fehlt auch dem Agent | `load_rag_config` verwirft ihn | `config_loader/rag.py:13-16` |
| Eval-Lauf startet nicht (502) | Testcontainer ohne `EVAL_CHAT_URL`, Rückfall `localhost:8000`, Container lauscht auf 8100 | `services/eval/run_store.py:31,52-73`, Dockerfile:86 (Container 2026-10-17 mit `-e EVAL_CHAT_URL` neu gestartet) |
| „Alle auswählen“ wählt nicht alle | lässt `auf_abruf` (GV-RED-1, schreibt echt) bewusst aus; Beschriftung sagt es nicht | `eval-golden-start.component.ts:142-144` |
| Judge im Studio aus | `signal(false)` überstimmt Backend-Vorgabe `True`; Kostenzeile zählt Judge-Aufrufe zu knapp; Hinweis beschreibt Judge v1 | `eval-golden-start.component.ts:55,103`, `api/eval.py:145`, `i18n/catalogue/eval-start.ts:78` |
| Pattern-Nutzung mischt Agent-Züge | kein Engine-Filter im Backend, Studio-Filter lokal `'alle'` | `services/eval/queries.py:225`, `api/eval.py:258-268`, `eval-pattern-usage.component.ts:112` |
| Kosten: Judge/Simulator fehlen, kein Engine-Filter | nur Chat-Endpunkte buchen `usage_events` | `api/chat.py`, `api/agent.py`, `usage_analytics.py:285` |
| Trends leer (Agent) | keine Läufe in `boerdi_test` — kein Fehler; Qualitätslinien nur mit Judge | `queries.py:99`, `trends_v2.py` |
| Lasttest: zwei langsame Suchen | MCP-Ausreißer 22,1 s (Server) und Ausweich-Kette nach leerer Suche (6 Runden); Master-Skill nur 1,2 s; n=3 je Art → p95 = Maximum | Prüfung `lt-b97eb9de93a3`, `services/loadtest.py:335-418` |
| Lasttest-Radios verrutschen | `.lt-pick` (für Verlaufsknöpfe) an Radios, Grid-Fieldset | `loadtest.component.html:59`, `.scss:32-39,199-211` |
| Verschachtelte Formulare (Anzeige, Tour, Kontext-Aktionen) | jedes nicht-einfache Feld (auch jedes Textfeld) bekommt ein eigenes `<details>`; eine Gruppe allein wiederholt ihre Legende; Wert-Maps als „Schlüssel / Feld / Entfernen“ | `schema-form/form-sections.ts:35,60-91,115`, `schema-field.component.html:22-25,215-252` |
| Tour nicht generisch | sechs Schritte fest im Code (`STEP_ORDER`), `steps`/`angebote` als JSON-Kästen | `domain/tour.py:40`, `config_models/base_widget.py:209-233` |
| Sicherung ungeordnet | fünf Karten, Werksfassung oben und unten | `views/backup.component.html:12,85` |
| Alle Bereiche: kein Zurück, Verwerfen grau | Brotkrume ist `<p>`; ein JSON-Entwurf zählt nicht als ungespeichert | `area-editor.component.html:2,74`, `schema-form/json-value.component.ts:36,93-110` |
| Begrüßung: Tour-Chip doppelt, „Entfernen“ klebt | `tour_reply` als Feld und als Marker an den Startchips; kein Abstand in `.sf-entry` | `base_widget.py:25-29`, `list-items.ts:88-112`, `_sf-meldungen.scss:46-71` |
| „Kopfangaben“ unverständlich | M01/M02 zeigen die Muster-Frontmatter (Routing), die hier nicht wirkt (Sicherheits-Tor erzwingt M01/M02) | `curated-pages-agent.ts:60-67`, `graph/nodes/respond.py:82` |
| Werkzeuge doppelt, Skills doppelt | WLO-Liste im MCP-Panel (Schalter) und in `agent-tools` (lesend); `agent-skills` auf Agent- und Patterns-Seite | `agent_tool_overview.py:88-122`, `curated-pages-inhalt.ts:145`, `curated-pages-agent.ts:85` |
| Policy im Agent nur mit I01 | Agent überspringt die Klassifikation | `graph/nodes/assess.py:122` |

## 3 Entscheide des Nutzers (2026-10-17)

1. **Werkzeuge und Skills:** zwei gemeinsame Seiten unter „Gemeinsam“. „Werkzeuge“ zeigt alle Werkzeuge (eingebaut, WLO, weitere MCP-Server) mit Schaltern. „Skills“ zeigt den Master-Skill (Vorschau, Optionen), das Skill-Register und die Skill-Brücke. Die Agent-Seite „Werkzeuge & Skills“ und die doppelte Werkzeugliste im MCP-Panel entfallen.
2. **Zielgruppen:** neue gemeinsame Seite mit der Anrede je Persona und dem Rückfall `persona_formality` (bisher unter Anzeige). Die übrigen Persona-Einstellungen bleiben unter Muster › Dimensionen.
3. **Freie Persona-Gespräche:** später, eigenes Paket (§10).
4. **MCP-Zeitgrenze:** bleibt 60 s. Der Lasttest wird besser messen (Aufwärm-Anfrage, Zeile je Anfrage), der Ausreißer geht ans MCP-Team.
5. Aus der Rückmeldung selbst: Streaming und Agent-Schnellantworten in der Grundeinstellung an; Judge im Gold-Lauf standardmäßig an; Pattern-Nutzung ohne Agent-Einträge.

## 4 Ansätze

**Anzeige von Vorgaben (Kern-Fehler).**
- (A) Der Server füllt beim `GET /data` die Modell-Vorgaben ein. Das Studio zeigt die wirksamen Werte. Nachteil: Beim nächsten Speichern landen alle Vorgaben im Dokument und folgen künftigen Vorgabe-Änderungen nicht mehr (Werksabgleich, eigene Fassung). Verworfen.
- (B) Das Studio zeigt für einen fehlenden Schlüssel die Schema-Vorgabe an und markiert sie als „Vorgabe“. Geschrieben wird nur, was jemand ändert. **Gewählt**: Das Dokument bleibt schlank, die Anzeige stimmt mit dem Server überein. Für Vorgaben aus `default_factory` muss das Schema die Vorgabe tragen (`json_schema_extra`). Ein Wächter-Test prüft für alle Bereiche, dass Schema-Vorgabe gleich Modell-Vorgabe ist.

**Lesbare Formulare.**
- (A) Generische Korrekturen im Schema-Formular: Textfelder ohne eigenen Aufklapper, keine doppelte Legende, Wert-Maps als Tabelle.
- (B) Eigene Panels je Seite (Anzeige-Tabelle, Tour-Schritte, Kontext-Aktionen je Seitentyp).
- **Gewählt: A zuerst, dann B nur, wo A nicht reicht** (Tour, Kontext-Aktionen, Anzeige-Regeln). A wirkt auf jeder Seite und kostet kein Startpaket.

**Startpaket (Budget 1,2 MB, heute 1,15 MB).** Neue Panels würden die Fehlergrenze reißen. Gewählt: Panels und Dashboards in `curated-view` per `@defer (on viewport)` laden. Angular schneidet sie dann in eigene Chunks, ohne neue Routen. Das ist Aufgabe 0.

## 5 Design

### 5.1 Navigation nach Paket 15

| Bereich | Seiten |
|---|---|
| Agent | Übersicht · Rolle & Grenzen · Prompt & Test |
| Muster | Übersicht · Identität & Schutz · Domänenwissen · Patterns · Dimensionen · Materialformate |
| Gemeinsam | Begrüßung · Kontext-Aktionen · Tour & Lotse · **Zielgruppen** · Wissen · **Werkzeuge** · **Skills** · Anzeige · Datenschutz |
| Auswertung | unverändert |
| System | Betrieb · Alle Bereiche · Sicherung · Vorschau |

`agent-werkzeuge` leitet auf `werkzeuge` weiter. Wächter aus Paket 14 (eine Heimat je Bereich, Heimat in jedem Arbeitsbereich) gilt weiter.

### 5.2 Vorgaben im Formular (A3)

- `field-control`: Ein fehlender Wert zeigt `schema.default`. Neben dem Feld steht die Plakette „Vorgabe“ (Text, nicht nur Farbe). Ändern schreibt den Wert, „Auf Vorgabe zurück“ entfernt den Schlüssel.
- Objekte und Listen ohne Wert (`agent_rolle`, `schutzregeln`) zeigen die Vorgabe als Ausgangsstand. Die erste Änderung übernimmt die ganze Vorgabe plus Änderung, also keine stillen Verluste mehr.
- Backend: `default_factory`-Felder bekommen ihre Vorgabe ins Schema. Wächter `test_schema_vorgaben_gleich_modell` prüft über alle Bereichs-Modelle, dass die Schema-Vorgabe gleich `Model().model_dump()` ist.

### 5.3 Werkzeuge (gemeinsam)

- Eine Tabelle über alle Werkzeuge aus `agent_tool_overview`: Name, Herkunft (eingebaut / WLO / Server-ID), angeboten in Agent/Muster, Sperrgrund, Schalter an/aus.
- Der Schalter schreibt `werkzeuge_aus` des jeweiligen Servers. Eingebaute Werkzeuge haben keinen Schalter, nur ihren Sperrgrund.
- Filter nach Herkunft, Suche.
- Die Liste baut sich aus dem Katalog des Zugs plus den übernommenen Fremdwerkzeugen. Neue Server erscheinen also ohne Code-Änderung.

### 5.4 Wissen (gemeinsam)

- Reiter „RAG“ | „MCP-Server“.
- MCP-Server je eine zugeklappte Zeile: Name, URL, Status, „n Werkzeuge, k aus → Werkzeuge“.
- Aufgeklappt: Felder, „Werkzeuge entdecken/übernehmen“, „Entfernen“ (nicht beim Hauptserver). „Server hinzufügen“ unter der Liste.
- Die Werkzeug-Schalter wandern auf die Seite Werkzeuge.

### 5.5 Skills (gemeinsam)

- Master-Skill-Panel mit Text-Vorschau.
- Skill-Register und Suche (`agent-skills`).
- Skill-Brücke im Muster-Modus (`engine.muster_skills`).
- Die Agent-Übersicht verlinkt hierher.

### 5.6 Zielgruppen (gemeinsam)

- Anrede-Tabelle (Panel `anrede`).
- Darunter der Rückfall `device-config.persona_formality`: Tabelle Persona × Anrede statt Wert-Map.
- Hinweis: gilt in beiden Modi; weitere Persona-Einstellungen unter Muster › Dimensionen (nur Link, wenn im Agent-Bereich).

### 5.7 Rolle & Grenzen (Agent)

- Rolle: Textfeld, Vorgabe sichtbar (5.2).
- Schutzregeln: Liste aller Regeln R-01…R-15 als Kontrollkästchen mit Regeltext aus `guardrails`. Angehakt ist, was der Agent bekommt.
- Schutzantworten: Liste „Krise (M01) | Drohung (M02)“ mit Antworttext, Kernregel, Ton, Länge, Schnellantwort-Art; keine Routing-Felder, kein „Kopfangaben“-Rahmen. Hinweis: „Erkennung und Routing → Muster › Patterns“.
- Sicherheitsstufe, Policy (mit Hinweis: im Agent-Modus greifen nur Regeln ohne Anliegen-Bedingung).

### 5.8 Lesbarkeit generisch (D)

- Textfelder (`multiline`) zählen als einfach: kein eigener Aufklapper.
- Ein Abschnitt mit genau einer Gruppe zeigt keine zweite Legende.
- Maps einfacher Werte als Tabelle „Schlüssel | Wert | ×“.
- Abstand vor „Entfernen“ in Listenzeilen.
- Marker-Zielfelder (`tour_reply`) werden nicht als eigenes Feld gezeigt. Passt der gespeicherte Wert zu keinem Chip, erscheint eine Warnung.

### 5.9 Seiten mit eigenem Schnitt (E)

- **Anzeige:** Reiter „Im Chat“ · „Karten“ · „Kopfzeile“ · „Geräte“.
  - „Im Chat“: eine Tabelle (Element · an/aus · Höchstzahl · Extra) über `display_rules`.
  - `per_pattern`/`exclude_patterns` als Pattern-Chips.
  - Geräte-Höchstzahlen als feste Tabelle Desktop/Tablet/Mobil.
- **Tour & Lotse:** Reiter „Tour“ · „Lotse“ · „Lotsen-Regeln“.
  - Tour: Grundwerte kurz.
  - Schritte als geordnete Liste (Reihenfolge `STEP_ORDER` vom Server) mit Detail DE/EN nebeneinander.
  - Gruppen als Objektliste.
  - `angebote` als Tabelle (Beschriftung | Pfad).
  - Links als Tabellen.
  - `flows` lesend hinter einem Aufklapper.
  - Das Speicherformat bleibt; die Typisierung geschieht im Panel.
- **Kontext-Aktionen:** Reiter je Seitentyp, jeweils Begrüßung DE/EN und Chip-Tabelle (DE | EN | Art | Aktion/URL | ×). „Allgemein“ trägt Schalter, Hosts, Texte und `curate_prompt` hinter einem Aufklapper. Vorbild: `badboerdi/studio/.../ContextActionsView.tsx`.
- **Sicherung:** Reiter „Sichern“ (Snapshots, Voll-Backup, Eigener Grundstand) und „Werksfassung“.
  - „Werksfassung“: eine Zustandszeile, Liste je Bereich, Vergleich je Zeile aufklappbar.
  - Hinweise unter „Was bedeutet das?“, Sammelaktionen unter „Alle Bereiche auf einmal“.
- **Alle Bereiche:** Brotkrume als Link zu `/bereiche`, dazu „Zurück zu {Seite}“, wenn `area-homes` eine Heimat kennt. Ein JSON-Entwurf oder -Fehler zählt als ungespeichert; „Verwerfen“ setzt auch Entwürfe und Feldfehler zurück.

### 5.10 Auswertung (F)

- **Gold-Lauf:**
  - Judge standardmäßig an; Kostenzeile zählt Züge + Abläufe + 1.
  - Hinweis auf Judge v2.
  - Knopf „Alle außer ‚nur auf Abruf‘“ plus „inkl. auf Abruf“ mit Warnsatz.
- **Hilfstexte:**
  - **Gold-Lauf:** feste, von Hand geschriebene Abläufe, harte Prüfungen, vergleichbar A/B.
  - **Generativer Lauf:** erfundene Szenarien je Zielgruppe × Anliegen, Judge-Urteil, breiter, nicht wiederholbar, misst die Vorgabe-Maschine.
- **Pattern-Nutzung:** Backend-Parameter `engine` (wie `_scope_clause`), Studio bindet an `ansicht.maschine()`; im Agent-Bereich entfällt der Reiter „Pattern-Nutzung“.
- **Kosten:**
  - Engine-Filter (an `maschine()`).
  - Judge-, Simulator- und Szenario-Aufrufe als `usage_events` mit Sitzung `eval-<lauf>` und `quelle='eval-judge'`, `'eval-simulator'` bzw. `'eval-szenario'`.
- **Lasttest:**
  - Option „Aufwärm-Anfrage“ (vorgabe an, zählt nicht).
  - `result.requests[]` je Anfrage (Art, Stufe, Dauer, Werkzeuge, Runden, MCP-ms).
  - Tabelle zeigt bei n < 20 „max“ statt „p95“.
  - Radios mit eigener Klasse `.lt-radio`.

### 5.11 Betrieb und Grundeinstellung (A1, A2)

- Seed `01-base/engine.yaml`: `agent_schnellantworten: true`; Modell-Vorgabe `True`; Texte angepasst.
- Betrieb-Seite: Hinweis, wenn Vorgabe-Maschine Agent und Streaming an, aber Schnellantworten aus.
- **Voraussetzung (Nutzer):** Master-Skill-Abschnitt „Schnellantworten“ nach `docs/plans/2026-09-30-muster-kette-zeit.md` §„Vorschlag für den Master-Skill“ übertragen. Der Live-Text beschreibt noch den zweiten Aufruf (geprüft 2026-10-17).
- Dockerfile `ENV EVAL_CHAT_URL=http://127.0.0.1:8100/api/chat`; Rückfall in `run_store.py` auf Port 8100.
- `load_rag_config` behält Bereiche ohne `mode` für die Agent-Schleife.

## 6 Globale Regeln

- Nur `boerdi-chat` ändern; badboerdi nur lesen. Commits/Deploys macht der Nutzer.
- Studio: Angular 22 zoneless, Signale, OnPush, kein RxJS-Abo; alle Texte über den Katalog (de/en), Wächter `en.spec.ts`.
- Gates: `npx eslint projects/studio/src`, `check:tokens|a11y|contrast|radii`, `build:studio` (Fehler ab 1,2 MB), Backend `uv run pytest`, `ruff` (100).
- Konfiguration bleibt Seed-Import-Quelle (`backend/seeds/`); Seed-Änderung ⇒ Werksabgleich-Folgen im Log nennen.
- Browser-Abnahme nur gegen Wegwerf-DB; Eval-/Gold-/Lastläufe startet der Nutzer.
- Dateien ≤ ~300 Zeilen; neue Panels als eigene Komponenten.

## 7 Aufgaben

### Phase 0 — Startpaket
Schritt 0: `/better-coding-workflow`, `/better-coding-frontend`.
- **0.1** `curated-view`: Panels per `@defer (on viewport) { … } @placeholder { Ladezeile }`; dasselbe für die Evaluation-Reiter. Nachweis: Build-Ausgabe, Startpaket kleiner als heute (1,15 MB); Specs grün (Defer in Tests: `DeferBlockBehavior.Playthrough`).

### Phase A — Fehler mit Wirkung
Schritt 0: `/better-coding-workflow`.
- **A1** Grundeinstellung Schnellantworten: Test `test_seed_engine_schaltet_streaming_und_schnellantworten_ein`, `test_betriebsschalter` auf `True`; Seed, Modell, Schema-Fixture, Feldtexte; Betrieb-Hinweis (Spec).
- **A2** `EVAL_CHAT_URL`: Test für den Rückfall-Port; Dockerfile-ENV.
- **A3** Vorgaben im Formular (5.2): Backend-Wächter Schema-Vorgabe = Modell-Vorgabe, `json_schema_extra` für Factory-Felder; Studio `field-control`/Liste/Objekt mit Vorgabe-Plakette und „Auf Vorgabe zurück“ (Specs: fehlender Bool mit Vorgabe `true` zeigt an; Ändern schreibt; Zurück entfernt; Liste übernimmt Vorgabe beim ersten Ändern).
- **A4** `load_rag_config`: Bereich ohne `mode` bleibt für den Agent (Test).
- **A5** Pattern-Nutzung mit `engine` (Backend-Test + Studio-Spec, Reiter im Agent-Bereich weg).
- **A6** Kosten: Engine-Filter (Test) und Buchung von Judge/Simulator/Szenario (Test: ein Gold-Lauf mit Judge-Attrappe erzeugt `usage_events` mit `quelle='eval-judge'`, Kosten-Seite zählt sie unter Eval).
- **A7** Gold-Lauf: Judge an, Zählung, Hinweistext, Knöpfe „Alle außer …“/„inkl. auf Abruf“ (Specs).

### Phase B — Navigation und gemeinsame Seiten
Schritt 0: `/better-coding-workflow`, `/better-coding-frontend`.
- **B1** `studio-views.ts`: Seiten `zielgruppen`, `werkzeuge`, `skills` (gemeinsam); `agent-werkzeuge` → Weiterleitung `werkzeuge`; Wächter und Navigation-Spec anpassen.
- **B2** Seite Werkzeuge: Panel `werkzeug-tabelle` (5.3) + Spec (Herkunft, Schalter schreibt `werkzeuge_aus` mit Version, Konflikt, Fremdserver erscheint).
- **B3** Wissen: Reiter RAG | MCP-Server; `mcp-registry` als zugeklappte Server-Zeilen ohne Werkzeug-Schalter (Spec: Hinzufügen, Entfernen außer Hauptserver, Entdecken).
- **B4** Seite Skills: Master-Skill, `agent-skills`, `muster_skills`; aus Patterns- und Agent-Seite entfernt.
- **B5** Seite Zielgruppen: `anrede` + Rückfall-Tabelle `persona_formality`; aus Rolle & Grenzen und Anzeige entfernt.
- **B6** Rolle & Grenzen: Schutzregeln-Panel (Kontrollkästchen + Regeltext) + Spec; Schutzantworten-Liste ohne Routing-Felder (group-section mit `felder` je Dokument) + Spec.

### Phase C — Lesbarkeit generisch
Schritt 0: `/better-coding-workflow`, `/better-coding-frontend`.
- **C1** `form-sections`: `multiline` einfach; eine Gruppe ohne zweite Legende (Specs der Formular-Bausteine anpassen, Ursache je kaputter Spec benennen).
- **C2** Wert-Maps als Tabelle (Spec: Schlüssel umbenennen, Wert ändern, Zeile löschen, Tastatur).
- **C3** Listenzeilen-Abstand; Marker-Zielfeld ausblenden + Warnung (Spec Begrüßung).
- **C4** Bereichs-Editor: Zurück-Links, JSON-Entwurf zählt als ungespeichert, Verwerfen setzt zurück (Specs).
- **C5** Lasttest-Radios `.lt-radio` (Browser 375 px + Desktop).

### Phase D — Seiten mit eigenem Schnitt
Schritt 0: `/better-coding-workflow`, `/better-coding-frontend`.
- **D1** Anzeige: Reiter + Tabelle `display-rules` + Geräte-Tabelle (Panel-Specs).
- **D2** Tour & Lotse: Reiter + Panel `tour-schritte` (Reihenfolge vom Server, DE/EN) + `angebote`-Tabelle (Specs: Speichern behält Format bitgleich für unberührte Schritte).
- **D3** Kontext-Aktionen: Panel je Seitentyp (Spec: Begrüßung, Chip anlegen/löschen, Art „action“ zeigt Aktionsfeld).
- **D4** Sicherung: zwei Reiter, Vergleich je Zeile aufklappbar, Sammelaktionen hinten.

### Phase E — Lasttest und Auswertung
Schritt 0: `/better-coding-workflow`.
- **E1** Lasttest: Aufwärm-Anfrage, `result.requests[]`, „max“ bei kleinem n (Backend-Test + Spec).
- **E2** Hilfstexte Gold vs. generativ; Hinweis Policy im Agent-Modus.
- **E3** MCP-Ausreißer dokumentieren (`docs/mcp-und-anmeldung.md`, Abschnitt Beobachtungen: Werkzeug, Zeit, Datum).

### Phase F — Abnahme
- Volle Suiten Backend und Studio, Gates, Build (unter 1,2 MB, Ziel unter 1,1 MB nach 0.1).
- Browser gegen Wegwerf-DB: alle geänderten Seiten, beide Arbeitsbereiche, 375 px, hell/dunkel.
- Testcontainer mit neuem Image (mit `EVAL_CHAT_URL` aus dem Dockerfile), Werksabgleich auf `boerdi_test`.
- Review `/better-coding-review` mit frischem Prüfer; Befunde beheben.

## 8 Abnahmekriterien

| Kriterium | Nachweis |
|---|---|
| Vorgaben im Studio = Werte des Servers (RAG `agent`, `agent_rolle`, alle Bool-Felder) | Wächter A3 + Specs |
| Neue Grundeinstellung streamt im Agent-Modus | Seed-Test A1; Log „Token-Strom: muster=AGENT“ im Testcontainer nach Werksabgleich einer frischen DB |
| Gold-Lauf startbar im Container ohne Zusatz-Env | A2 + Image-Smoke |
| Pattern-Nutzung und Kosten getrennt nach Arbeitsbereich; Judge-Kosten sichtbar | A5/A6 |
| Werkzeuge einmal, mit Herkunft und Schalter; Skills einmal | B2–B4 |
| Keine Seite mit mehr als einer Aufklapp-Ebene unter dem Abschnitt (Anzeige, Tour, Kontext-Aktionen, Sicherung) | Specs D + Browser |
| Zurück aus „Alle Bereiche“, Verwerfen wirkt | C4 |
| Startpaket < 1,2 MB | Build |

## 9 Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Vorgabe-Anzeige schreibt beim Speichern doch Vorgaben ins Dokument | Spec: unverändertes Speichern sendet keinen neuen Schlüssel |
| Agent-Schnellantworten an, Master-Skill noch alt | Hinweis im Log/Bericht; Werkzeug lief laut Messung trotzdem 8/8 über `respond_to_user`; Nutzer überträgt den Text |
| Seed-Änderung kippt eigene Fassungen | Werksabgleich überspringt geänderte Bereiche; Log nennt `boerdi_test`/Staging-Folgen |
| Tour-/Kontext-Panels verändern das Speicherformat | Specs: Rundlauf bitgleich |
| Generische Formular-Änderung (C1/C2) bricht viele Specs | Ursache je Spec, keine Tests abschwächen |
| Startpaket über 1,2 MB | Phase 0 zuerst |

## 10 Offene Fragen und Später

- Keine offenen Fragen für Paket 15.
- **Später (eigenes Paket):** freie Persona-Gespräche (eine Persona, N freie Gespräche, Einzelurteil); Policy-Regeln mit Anliegen im Agent-Modus (bräuchte Klassifikation im Agent-Zug); MCP-Sitzungen wiederverwenden; Master-Skill vorwärmen.

## 11 Log

| Datum | Schritt |
|---|---|
| 2026-10-17 | Rundgang des Nutzers, fünf Prüfungen (nur lesend), Testcontainer mit `EVAL_CHAT_URL` neu gestartet, Entscheide, Entwurf |
| 2026-10-17 | **0** gebaut — **Abweichung:** die Annahme „Panels per `@defer`“ war falsch (die Seiten laden längst einzeln). Gemessen: 502 kB Katalog im Hauptbündel und das ganze Widget (Chat-Fenster, marked, DOMPurify, Material, Icons) im geteilten Startbündel, weil `studio-language.service.ts` aus der Sammeldatei `@boerdi/ui` importierte. Direkte Importe aus `@boerdi/ui/i18n/*` → Startpaket **1,15 MB → 807,5 kB** (unter der Warnschwelle 1,1 MB). |
| 2026-10-17 | **A** gebaut: A1 `agent_schnellantworten` Vorgabe an (Seed, Modell, Fixture, Texte) + Hinweis an Abschnitten (`CuratedAreaSection.hinweise`) auf „Betrieb“; A2 `EVAL_CHAT_URL` im Dockerfile und Rückfall auf 8100 (Wächter `test_deploy_compose`); A3 Schema mit Factory-Vorgaben (`config_models/schema.area_schema`, Wächter über alle Bereichsmodelle) + Studio zeigt fehlende Werte mit Plakette „Vorgabe“, „Auf Vorgabe zurück“, erste Änderung unter einer Vorgabe schreibt sie mit (Batch); A4 `load_rag_config` behält Bereiche ohne `mode`; A5 Pattern-Nutzung `engine` serverseitig (`quality_analytics.engine_sql`, jetzt `IS DISTINCT FROM`), Reiter nur im Muster-Bereich, lokaler Betriebsart-Filter entfernt; A6 Herkunft `eval-…` ohne Sitzung zählt zur Auswertung, Gold-Lauf bucht Judge (`eval-judge`), generativer Lauf bucht Simulator/Judge/Szenarien (`services/eval/verbrauch.py`, auch nach Fehler), Kosten-Seite mit `engine`; Wächter `test_usage_coverage` ohne Eval-Ausnahmen; A7 Judge Vorgabe an, Zählung Züge + Abläufe + 1, Knöpfe „Alle außer/auch ‚nur auf Abruf‘“ mit Warnsatz, Judge-Hinweis v2. OpenAPI neu (2 Parameter, `bewusste-vertragszusaetze.md`). |
| 2026-10-17 | **B** gebaut: Seiten `zielgruppen`, `werkzeuge`, `skills` (gemeinsam), `agent-werkzeuge` → Weiterleitung; Personas unter Dimensionen ohne Anrede (`ohneFelder`), Anzeige ohne Rückfall; **Abweichung B6:** statt eines Schutzregel-Panels mit Kontrollkästchen ein Abschnitt „Rolle, Schutzregeln und Grenzen“ (`felder: agent_rolle, agent`) — zwei Abschnitte desselben Dokuments auf einer Seite schickten sich beim Speichern ins 409; die Schutzregeln bekommen dafür den Katalog `guardrails` (Vorschlagsliste „R-13: Wortlaut“, `agent_kopf.regeln`) und zeigen dank A3 die vier Vorgaben. Schutzantworten ohne Reiter, nur Antworttext/Kernregel/Ton/Länge/Schnellantwort-Art/verbotene Wendungen; ein echter Feld-Ausschnitt zeichnet keine „Kopfangaben“-Legende mehr (`pickFields`). Werkzeuge: Spalten Herkunft und Anbieten (`schalterFuer`, `McpRegistryStore` aus dem MCP-Panel gelöst), Speichern/Verwerfen/Konflikt, Verlassen-Schutz. Wissen mit Reitern „Wissensbereiche | MCP-Server“ (`CuratedView.reiter`, Abschnitte bleiben eingehängt), Server als zugeklappte Zeilen, Schalter dort entfernt (Verweis auf „Werkzeuge“). Nebenbefund behoben: ein Backend-Test hielt die alte Vorgabe „Schnellantworten aus“ fest. Backend 6312 grün (volle Suite vor B), Studio 1661 grün. |
| 2026-10-17 | **C** gebaut: Formular-Gliederung — mehrzeilige Felder kompakt, Hauptfeld zuerst; Gruppen-Abschnitte ohne doppelte Legende (`ohneLegende`), Marker-Ziel nicht als eigener Abschnitt (`markerZiel`, Warnsatz bei verwaistem Marker); Maps einfacher Werte (auch mehrzeilig) als Tabelle `.sf-map`; Entfernen-Knopf rechts mit Abstand. „Verwerfen“ wirkt (`verwerfbar`, Feldfehler werden mit verworfen); Bereichs-Editor mit Brotkrume „Alle Bereiche“ und „← Zurück zu ‚Seite‘“ (`heimatSeite`). Lasttest: Maschinen-Wahl als feste Knöpfe (`.lt-wahl`). **Abweichung:** Begrüßung — die englischen Texte gelten als Hauptfelder (`Primary()`), sonst landeten sie unter „Weitere Einstellungen“. |
| 2026-10-17 | **D** gebaut: Anzeige mit Reitern Chat/Karten/Kopfzeile/Geräte; Tour & Lotse mit Reitern Tour/Lotse/Regeln. **Abweichung D2:** statt eines eigenen Tour-Panels ein getipptes Backend-Modell (`TourStep…`, `TourSteps` mit den Rückfällen aus `tour.py`, `TourGroup.angebote`) — das generische Formular zeigt die Schritte dann als benannte Felder; 136 neue Feldtexte. **Abweichung D3:** Kontext-Aktionen ohne Seitentyp-Pivot; das tote Feld `ContextPill.params` entfernt, Maps als Tabellen. **Abweichung D1:** Anzeige ohne eigene Darstellungsregel-Tabelle (generische Tabellen + Reiter). Sicherung mit Reitern Werksfassung/Sichern, Erklärung hinter „Was bedeutet das?“. **Zwischenfall:** `i18n/catalogue/fields-tour.ts` versehentlich mit erzeugtem Inhalt überschrieben; aus dem Klon wiederhergestellt, alle 132 Werte gegen das vorher gebaute Bündel geprüft (0 Abweichungen), neue Einträge danach eingefügt. |
| 2026-10-17 | **E** gebaut: E1 Lasttest — Aufwärm-Anfrage (Vorgabe an, zählt nicht, `result.warmup`), je Stufe eine Zeile je Anfrage mit Werkzeugzahl und Werkzeugzeit aus dem Debug-Block, Studio zeigt „max“ statt „p95“ bei n < 20 und die Anfragen-Tabelle; `LoadTestProfile.warmup` im Vertrag. **Abweichung E1:** ohne Runden-/MCP-ms je Anfrage, nur Werkzeugzahl und -zeit. E2 Hilfetexte „Was ist ein Gold-/generativer Lauf?“ in beiden Startkästen; Hinweis am Werkzeug-Regelwerk: im Agent-Modus greifen nur Regeln ohne Anliegen-Bedingung. E3 Ausreißer `search_wlo_all` 22 s in `docs/mcp-und-anmeldung.md` §6 gemeldet (Zeitgrenze bleibt 60 s). |
| 2026-10-18 | **F** Abnahme: Backend **6320 grün** (4 übersprungen), Studio **1679 grün**, eslint/ruff sauber, Gates tokens/a11y/contrast/radii grün, Startpaket **826 kB**. Browser gegen `boerdi_p15_browser`: alle geänderten Seiten in beiden Arbeitsbereichen; zwei Befunde behoben — bei 375 px schob die Werkzeug-Tabelle die Seite auf (Grid-Element ohne `min-inline-size: 0`) und die Anrede-Tabelle lief über (jetzt eigener Scroll-Rahmen). |
| 2026-10-18 | **F** Testcontainer: Image `edu-chatbot-sc:paket15-lokal`, Migration + Werksabgleich auf `boerdi_test` (Engine „zugeordnet“ — entsprach schon dem neuen Werk), `boerdi-chat-test` neu; `EVAL_CHAT_URL` kommt aus dem Image. Abnahme Streaming im Agent-Modus: Suchfrage → 12 Text-Rahmen, 484 Zeichen, Drift nein; ein kurzer Gruß endete ohne `respond_to_user` (kein Strom) — der live geladene Master-Skill beschreibt noch die alte Schnellantwort-Mechanik (Text zum Übertragen: `2026-09-30-muster-kette-zeit.md`). Docstrings „Vorgabe aus“ berichtigt. |
| 2026-10-18 | **Review** (frischer Prüfer, `better-coding-review`): 0 kritisch, 2 schwer, 4 leicht, 1 Kleinigkeit — alle behoben, je mit vorher rotem Test. #1 abgeschaltete Fremdwerkzeuge verschwanden aus „Werkzeuge“ (nicht mehr einschaltbar) → Übersicht listet sie mit Sperre `hidden` (`angebotene(auch_aus=True)`); #2 Kosten ohne Maschine (Vorprüfung, Direkt-Aktionen) fielen in beiden Arbeitsbereichen heraus → zählen in beiden, die Seite sagt es; #3 erste Änderung in einer fehlenden Gruppe fror alle Geschwister-Vorgaben ein → nur noch, wenn die Gruppen-Vorgabe von den Kindern abweicht; #4 „Verwerfen“ räumte JSON-Entwürfe mit gleichem Wert nicht → Zähler `FORM_EPOCHE` vom Editor ans Feld; #5 Judge-Kosten des Gold-Laufs nach Fehler ungebucht → Buchung hinter `try/except`, eigene Sitzung; #6 Lasttest „max“ zeigte p95 → `max_s` je Art, n = erfolgreiche; #7 Compose-Kommentare (ALT-Port 8000) berichtigt. Nebenbefund (älter): `settings.eval_chat_url` liest niemand → `offene-befunde-und-todo.md`. |
| 2026-10-18 | **Review-Runde 2** (vier frische Prüfer: Backend · Formular · Seiten · Auswertung; Nutzer: alle beheben): 7 schwer, 21 leicht, 7 Kleinigkeiten — alle behoben (Liste §12), je mit vorher rotem Test, wo testbar (Ausnahme: Marker-Zeichen der MCP-Zeilen, im Browser geprüft). Darunter ein Rückschritt durch Fix #3 der ersten Runde (Liste/Map unter fehlender Gruppe: Entfernen ohne Wirkung) → `geerbt` + `kinderVorgaben`; Abbruch bucht jetzt (`finally` + `shield`); Werkzeugzeit wird gemessen (`outcome_service.call_with_outcome`, Schritt `respond.werkzeuge`); Fremdwerkzeug-Zeilen tragen `server_id`/`tool`. Ältere Punkte in `offene-befunde-und-todo.md`. Backend + Studio voll grün, Gates grün, Startpaket 830 kB, Vertrag unverändert; Browser gegen neu angelegte Wegwerf-DB. |

## 12 Review-Runde 2 (2026-10-18) — Abarbeitungsliste

Vier frische Prüfer (Backend · Formular · Seiten · Auswertung), Nutzer: „alle Befunde beheben“. Je Befund ein vorher roter Test, wo testbar. Status `[x]` = behoben und grün.

Schwer
- [x] R2-1 (B1) Liste/Map unter fehlender Gruppe: Entfernen/Ändern per Index/Schlüssel ohne Wirkung bzw. Verlust (Regression aus Fix #3)
- [x] R2-2 (A1) Eval-Abbruch (`CancelledError`) überspringt die Buchung (Gold + generativ)
- [x] R2-3 (A2/D1) `respond.werkzeuge` schreibt niemand → Werkzeugzeit immer leer
- [x] R2-4 (A3) Schalter für Fremdwerkzeuge aus dem gekürzten Modellnamen → `server_id`/`tool` mitliefern
- [x] R2-5 (C1) neue MCP-Zeile klappt beim Tippen zu
- [x] R2-6 (C2) Kopfzeilen-Sprung auf `/sicherung` wechselt den Reiter nicht
- [x] R2-7 (C3) Texte „Nur lesend“/„ändert nichts“/Kreisverweis auf „Werkzeuge“

Leicht
- [x] R2-8 (B2) Vorgabe-Plakette für geerbte Werte und für Listen/Maps/Gruppen
- [x] R2-9 (B3) gekürzte Felder: „Vorgabe folgt Kindern“ über die vollen Kinder
- [x] R2-10 (B4) Map-Tabelle: Server-Meldung am Feld (`aria-invalid`, Fehlerzeile); Meldung zu `markerZiel`
- [x] R2-11 (B5/C8) JSON-Entwurf/-Fehler zählt als ungespeichert (Verlassen-Schutz, Kennzeichen)
- [x] R2-12 (B6) Umbenennen-Spec prüft das Ergebnis
- [x] R2-13 (A4) Tour: `null` wie die Laufzeit annehmen
- [x] R2-14 (A5) Seed-Kommentar `rag-config.yaml`
- [x] R2-15 (C4) Werkzeuge: Herkunft/„fest“ während Laden/Fehler; „Neu laden“ lädt Tabelle
- [x] R2-16 (C5) „Zurück“ zur Herkunftsseite
- [x] R2-17 (C6) `agent-tools` als Schreiber von `mcp-servers` erklären
- [x] R2-18 (C7) je Reiter ein Panel (`aria-controls` löst auf)
- [x] R2-19 (C9) Werksabgleich ans Ende („Alle Bereiche auf einmal“)
- [x] R2-20 (C10) sichtbarer Aufklapp-Marker an MCP-Zeilen
- [x] R2-21 (C11) Specs: 409 Werkzeuge, Fremdzeile mit Herkunft, Fragment-Wechsel, Kennung tippen
- [x] R2-22 (D2) Lasttest je Kategorie: Format über `sekunden()`, Texte aus dem Katalog, Spaltenkopf
- [x] R2-23 (D3) gescheiterte Aufwärm-Anfrage kenntlich, Zeile auch ohne Stufen
- [x] R2-24 (D4) EN „on demand only“ einheitlich
- [x] R2-25 (D5) Pattern-Nutzung: nur Muster-Züge (Text)
- [x] R2-26 (D6) Hilfesatz nicht im `summary`-Namen
- [x] R2-27 (D7) Specs: Arbeitsbereich-Wechsel Evaluation, Kosten-Wettlauf, localStorage aufräumen
- [x] R2-28 (A7) Ressourcen-Abtastung erst nach dem Aufwärmen

Kleinigkeiten
- [x] R2-29 (A6) Dockerfile-Zeilenumbrüche, Docstring 8000
- [x] R2-30 (B7) `restoreDefault`/`zurueckZurVorgabe` zusammenlegen
- [x] R2-31 (C12) veraltete Kommentare
- [x] R2-32 (C13) WLO-Werkzeug-Schalter nur am Server `wlo-mcp`
- [x] R2-33 (D8) `visited` ohne `pattern` nach Rücksprung
- [x] R2-34 (D9) `anfragen` als `computed`, Stufe als `th scope=row`, `RunProfile` mit `warmup`/`engine`
- [x] R2-35 Ältere Punkte nur eintragen (Tour-Pfade, JSON-Fehlertext, Lasttest-Rohzahlen, Anrede-Kopfzelle)
