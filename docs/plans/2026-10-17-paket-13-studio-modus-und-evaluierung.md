# Paket 13 — Studio nach Betriebsmodus, Evaluierung mit Ablauf-Judge, Messbedingungen

Stand 2026-10-17. Status: **freigegeben 2026-10-17, in Umsetzung.**

## 1 Ziel

Das Studio zeigt nur, was im gewählten Betriebsmodus wirkt, und die Evaluierung sagt je
Golden-Ablauf und insgesamt, wie gut der Chatbot ist — in beiden Modi gleich fair, mit
Kurzbericht, farbigen Matrizen und lückenlosen Messbedingungen (Modell, Weg, Prompts,
Konfiguration, Zeiten), damit spätere Änderungen messbar werden.

## 2 Ausgangslage (Erkundung 2026-10-17)

**Studio.** `domain/area_effects.py` hält je Konfigurationsbereich und Maschine die Wirkung
(`voll`, `teilweise`, `krise`, `keine`), `GET /api/config/effects` liefert sie samt Vorgabe-Maschine.
Das Studio zeigt sie nur als Plakette „Wirkt in: …“ (`views/effect-badge.component.ts`) und als
Banner, wenn eine ganze Seite nirgends wirkt. Nichts wird ausgeblendet: Navigation
(`studio-views.ts`), Abschnitte (`curated-pages-*.ts`), Panels und Analyse-Reiter sind in beiden
Modi gleich. Die Analyse (`quality.component.ts`: Matrix, Ablauf, Diagnose) hat keinen
Modus-Filter, obwohl Agent-Züge dort als `AGENT`/`I01` erscheinen und die Grafiken nichts
aussagen. Das Speichern von `mode` auf `/agent` aktualisiert die Wirkungsdaten erst nach dem
nächsten Seitenwechsel.

**Evaluierung.** Golden v2 (`seeds/eval/gold-flows.yaml`, 22 Abläufe, 46 Züge, Zielgruppe je
Ablauf, harte Prüfungen je Zug). Der Judge (`services/eval/judge.py`, Prompt byte-genau aus ALT)
bewertet **jeden Zug einzeln, ohne Gesprächsverlauf**, auf 0–2 mit Achsen, von denen
`pattern_match`/`pattern_hint_verdict` nur in der Muster-Maschine Sinn haben. Je Ablauf gibt es
nur die harten Prüfungen, keine Note und keinen Text; die Zug-Notizen zeigt das Studio im
Golden-Lauf nicht an. Gespeichert werden Modell, Anbieter, Master-Skill-Prüfsumme und
Agent-Deckel (`run_conditions.py`); **nicht** gespeichert: Übertragungsweg (Responses/Chat,
Basis-URL), Denkparameter, Prompts, Konfigurationsstände, Gold-Flow-Fassung, App-Version,
Judge-Kosten. Schrittzeiten (`zeiten_ms`, `per_phase.ms`) liegen im Zug-Debug, werden aber nie
ausgewertet; Agent-Runden, Werkzeug-Ergebnisse und `debug.engine` verwirft `flatten_debug`.

**Alter Chatbot (badboerdi).** Heatmap Persona × Intent nach Judge-Note (grün/limette/
gelb/rot), Problemliste der schwächsten Züge mit Mängel-Chips, Konfusionsmatrizen, A/B-Vergleich
der Golden-Läufe mit Δ, Routing-Matrix Persona × Intent → häufigstes Muster. Schwächen, die wir
nicht übernehmen: eine echte 0 sah aus wie „keine Daten“, Zellen nicht klickbar, keine Zeiten
in Eval-Zügen, keine Modell-/Prompt-Stände je Lauf.

## 3 Entscheide des Nutzers (2026-10-17)

| Frage | Entscheid |
|---|---|
| Studio-Trennung | **Umschalter im Kopf** „Ansicht: Agent · Muster · Beide“, vorbelegt mit dem aktiven Betriebsmodus; ohne Wirkung Ausgeblendetes verschwindet, „Beide“ zeigt alles mit Plaketten |
| Judge-Ebene | **Ablauf + Zug**: ein Aufruf je Ablauf mit ganzem Verlauf (Skalen + Kurzstatement), dazu knapp je Zug |
| Skala | **1–5** mit Verankerung je Stufe |
| Matrizen | **Zielgruppe × Anwendungsfall**, **Ablauf × Skala**, **Persona × Intent** (nur Muster-Ansicht) |
| Judge-Modell | das Chat-Modell (heute `gpt-6-luna`), überschreibbar mit `EVAL_JUDGE_MODEL` — so ist es schon gebaut (`scenario_gen.judge_model`) |

## 4 Ansätze an den offenen Stellen

**Prompts festhalten.**
- A: nur Prüfsummen je Zug — billig, aber man sieht nicht, *was* sich geändert hat.
- B: Prüfsummen je Zug plus eine Ablage `prompt_versions(hash → text)`, beschrieben beim Bauen der
  **festen** Systemteile (Agent-Kopf, Master-Skill, Seitenregeln, Muster-Antwort-Schichten,
  Klassifikator-Festteil) — jede Fassung genau einmal gespeichert, Vergleich zweier Läufe zeigt
  den Text-Unterschied. **Empfehlung.**
- C: ganze Prompts je Zug im Lauf — groß (Master-Skill ~18 kB je Zug), und der variable Teil
  trüge Nutzertext.

**Anwendungsfall.** Die Abläufe sind mehrstufig (GV-LEH-1: Suche → Lernpfad → Arbeitsblatt →
Lösungen). Ein Anwendungsfall je Ablauf wäre falsch; er gehört an den **Zug** (`anwendungsfall`
in `expect`). Die Matrix Zielgruppe × Anwendungsfall mittelt die Zug-Gesamtnoten.

**Ausblenden.** Ein Bereich verschwindet in der Ansicht X, wenn `area_effects[bereich][X] ==
"keine"`; `krise` bleibt sichtbar, eingeklappt, mit dem Hinweis „wirkt hier nur bei Krise und
Drohung“ (M01/M02 müssen im Agent-Modus pflegbar bleiben); `teilweise` bleibt mit Plakette. Eine
Seite verschwindet aus der Navigation, wenn alle ihre Abschnitte und Panels ausgeblendet sind.
Ein direkter Aufruf einer ausgeblendeten Seite zeigt sie trotzdem — mit einem Banner und einem
Knopf „Ansicht wechseln“ (keine toten Links aus Lesezeichen).

## 5 Design

### 5.1 Messbedingungen v2 (Lauf) und Zug-Spur

`services/eval/run_conditions.py` liefert zusätzlich:

```text
engine_effective     "agent" | "pattern"
route                {"api": "responses" | "chat", "basis": "<host ohne Pfad>", "anbieter": "..."}
llm_parameter        {"reasoning_effort", "verbosity", "service_tier"}   # was wirklich gesendet wird
judge                {"modell", "prompt_fassung": "<sha256[:12] der Judge-Vorlagen>"}
gold_flows           {"hash": "<sha256[:12] der ausgewählten Abläufe als kanonisches JSON>", "ids": [...]}
konfiguration        {"hash": "<sha256[:12] über alle Bereiche>",
                      "bereiche": {"<area>": {"version": int, "hash": "<12>", "stand": "werk|eigen|..."}}}
prompt_bausteine     {"<name>": "<hash12>"}   # feste Systemteile zum Laufstart
app                  {"version": "<BOERDI_VERSION>", "commit": "<GIT_SHA>"}   # Build-Argumente
```

`route` kommt aus `services/llm.py` (`route()` entscheidet heute schon; neu: eine reine Funktion
`route_beschreibung(model) -> dict`, die dieselbe Entscheidung als Daten liefert, ohne Schlüssel).
`app` aus zwei neuen Umgebungsvariablen, im `Dockerfile` als `ARG` gesetzt und in
`.github/workflows/image.yml` mit Tag/Commit befüllt; lokal leer.

**Zug-Spur.** `evals/run_golden.flatten_debug` behält zusätzlich: `engine`, `spur` (die
`zeit`/`llm`-Zeilen aus `debug.trace`), `runden` (Agent: Anzahl, Stoppgrund, je Runde
`dauer_ms`, Token, Werkzeugnamen), `werkzeug_ergebnisse` (`tool`, `status`, `item_count`,
`latency_ms`), `prompt_hashes` (Phase → Hash). `token_usage` bleibt.

**Prompt-Ablage.** Neue Tabelle `prompt_versions(hash text PK, art text, text text, erstmals
timestamptz, zuletzt timestamptz)`, Migration `0012`. `services/prompt_ablage.py`:
`merke(art: str, text: str) -> str` (Hash zurück; schreibt im Hintergrund, `ON CONFLICT DO
UPDATE zuletzt`), Prozess-Cache der bekannten Hashes, damit ein Zug höchstens einmal je neuer
Fassung schreibt. Aufrufer: Agent-Systemteil (`respond_agent`), Muster-Antwort-Festteil
(`response_prompt_builder`), Klassifikator-Festteil (`classify_prompt`), Seitenregeln. Nur feste
Teile — ein Wächter-Test stellt sicher, dass weder Nutzernachricht noch Seitendaten darin stehen.
Keine Aufbewahrungsfrist nötig (keine personenbezogenen Daten).

**Judge-Kosten.** Judge- und Berichtsaufrufe laufen über einen eigenen `usage_acc`; der Lauf
speichert `judge_usage` (Token, Aufrufe, Kosten nach `pricing`).

### 5.2 Golden-Abläufe: Anwendungsfall und Erwartung

`gold-flows.yaml` bleibt `version: 2`, neue Felder sind Pflicht ab diesem Paket:

```yaml
- id: GV-LEH-1
  zielgruppe: P-LEH
  title: "..."
  erwartung: "Lehrkraft erwartet Material, dann einen Lernpfad daraus, ..."   # neu, für den Ablauf-Judge
  turns:
    - message: "..."
      expect:
        anwendungsfall: suchen          # neu, Pflicht
        must_offer: "..."
        tools_any: [...]
```

Anwendungsfälle (geschlossene Liste in `domain/config_models/knowledge.py`,
`Anwendungsfall = Literal[...]`): `suchen`, `zusammenstellen`, `erzeugen`, `ueberarbeiten`,
`zeigen`, `erklaeren`, `wlo_wissen`, `orientieren`, `kuratieren`, `rueckmeldung`, `schutz`,
`sonstiges`. Alle 46 Züge bekommen einen Wert; `erwartung` je Ablauf ein bis drei Sätze.

### 5.3 Judge v2

Neues Modul `services/eval/judge_v2.py` (der ALT-Judge bleibt unverändert für generative Läufe
bis Phase G). Vorlagen in `services/eval/prompts_v2.py`; `JUDGE_V2_FASSUNG` = Hash der Vorlagen.

**Ablauf-Judge** `judge_ablauf(ablauf: dict) -> AblaufUrteil` — ein Aufruf je Ablauf. Eingabe:
Zielgruppe (Label + Beschreibung aus `04-personas`), `erwartung`, je Zug Nutzertext,
sichtbare Antwort (mit Dokumenten/Karten wie heute `augment_bot_text`), `anwendungsfall`,
`must_offer`, aufgerufene Werkzeuge mit Ergebnisstatus. **Keine** Muster-, Intent- oder
Persona-Kennungen der Maschine — beide Modi werden am Gespräch gemessen.

Skalen 1–5 (je Stufe im Prompt verankert: 5 = vorbildlich, 4 = gut mit Kleinigkeit,
3 = brauchbar mit klarer Schwäche, 2 = deutlich mangelhaft, 1 = verfehlt):

| Schlüssel | Frage an den Judge |
|---|---|
| `zielgruppe` | Wurde die Zielgruppe erkannt und passend angesprochen (Anrede, Ton, Niveau)? |
| `anliegen` | Wurde das Anliegen in jedem Zug richtig verstanden, auch über Rückbezüge? |
| `angebot` | Kamen die erwarteten Angebote bzw. wurde der Auftrag erfüllt (`must_offer`)? |
| `werkzeuge` | Passten Werkzeuge und Filter (nötig, nicht überflüssig, sinnvolle Filter)? |
| `verlauf` | War die Gesprächsführung frei von Ablauffehlern (Wiederholung, vergessener Kontext, unnötige Rückfrage, Abbruch, Widerspruch)? |
| `qualitaet` | Waren die Antworten sachlich richtig, konkret und sinnvoll? |
| `sicherheit` | Wurden Leitplanken eingehalten (bei Schutz-Abläufen besonders streng)? |

Ausgabe (JSON, `response_format=json_object`, Temperatur 0):

```json
{"skalen": {"zielgruppe": {"note": 4, "grund": "..."}, "...": {}},
 "gesamt": 4,
 "statement": "2–4 Sätze: was auffiel, auch Dinge, die keine Skala misst",
 "auffaelligkeiten": [{"zug": 2, "art": "verlauf|ton|werkzeug|inhalt|technik|sonstiges", "text": "..."}]}
```

`gesamt` ist ein eigenes Urteil, kein Mittel. Noten werden auf 1–5 geklemmt; ein Fehlschlag
wirft `JudgeError` → `ablauf.judge_failed` (wie heute je Zug, keine stille 1).

**Zug-Judge** `judge_zug(zug, verlauf_davor) -> ZugUrteil` — je Zug, mit den vorigen Zügen
verdichtet (je Zug Nutzertext + erste 400 Zeichen der Antwort). Skalen 1–5: `anliegen`,
`angebot`, `qualitaet`, `ton`; dazu `gesamt` und `notiz` (ein Satz).

Aufrufe je Lauf: 22 Abläufe + 46 Züge + 1 Bericht ≈ 69 statt heute 46.

### 5.4 Auswertung, Kurzbericht, Export

`services/eval/auswertung_v2.py` (rein, ohne E/A, gut testbar):

```text
je_ablauf[id]   = {zielgruppe, skalen{k: note}, gesamt, harte_quote, latenz_p50, token, kosten,
                   werkzeugaufrufe, statement, auffaelligkeiten, judge_failed}
gesamt          = {gesamt_mittel, skalen_mittel{k}, harte_quote, latenz{p50,p95}, kosten_je_zug,
                   judge_kosten, ablaeufe, zuege, fehler}
matrix_zielgruppe_anwendungsfall[zielgruppe][anwendungsfall] = {mittel, n}   # Zug-Gesamtnoten
matrix_ablauf_skala[ablauf_id][skala] = note
matrix_persona_intent[persona][intent] = {mittel, n}   # nur Muster-Züge, erkannte Werte
zeiten          = {phase: {p50, p95, anteil}}          # aus spur/zeiten_ms
```

Kurzbericht: ein Judge-Aufruf über die Statements + Kennzahlen → 5–8 Sätze Einschätzung und
höchstens drei „Baustellen“ mit Ablauf-Bezug (`summary.kurzbericht`). Export:
`GET /api/eval/runs/{id}/bericht.md` (Markdown: Messbedingungen, Gesamt, Matrizen als Tabellen,
je Ablauf Noten + Statement).

Vergleich (`engine_compare.py`, `GET /api/eval/compare`): zusätzlich Skalen-Mittel, Gesamt,
**Unterschiede der Messbedingungen** (Modell, Weg, Parameter, geänderte Bereiche, geänderte
Prompt-Bausteine mit Link auf den Text-Unterschied `GET /api/eval/prompt-diff?a=&b=`).
Trends (`queries.py`): Reihen je Skala, Gesamt, Latenz p50, Kosten je Zug; Punkte, an denen sich
Modell, Konfiguration oder Prompt änderten, werden markiert.

### 5.5 Studio: Ansicht-Umschalter

- `core/studio-ansicht.service.ts`: `ansicht = signal<'agent' | 'pattern' | 'beide'>`;
  Startwert aus `localStorage['boerdi_studio_ansicht']` (in try/catch), sonst aus
  `EffectsApi.effects().engine`; `zeigt(engines?: readonly Engine[]): boolean`;
  `bereichSichtbar(area): 'ja' | 'krise' | 'nein'`.
- `shell/ansicht-umschalter.component.ts`: Segment-Schalter im Kopf (`role="radiogroup"`,
  Pfeiltasten, sichtbarer Fokus, Text statt nur Farbe), i18n-Teil `catalogue/ansicht.ts`.
- Kennzeichnung: `StudioView.engines?`, `CuratedPanelSection.engines?` (Agent-Panels →
  `['agent']`, `agent-skills` → `['agent','pattern']` wegen `muster_skills`),
  `TabDef.engines?` (Analyse: `matrix`, `flow`, `diagnosis` → `['pattern']`), Übersichtskarten
  `engines?`. Bereiche nehmen die Wirkung aus `area_effects`.
- Analyse: `core/quality-api.service.ts` schickt `engine` mit; Backend-Endpunkte unter
  `/api/quality/*` filtern `pattern_id = 'AGENT'` bzw. `<> 'AGENT'` (Ansicht „beide“ = kein Filter).
- Evaluation: Lauf-Liste und Trends übernehmen die Ansicht als Vorbelegung des Filters.
- `/agent`: nach dem Speichern von `mode` `EffectsApi.neu_laden()` aufrufen.
- `/bereich/**`: Plakette auch im allgemeinen Bereichs-Editor.

### 5.6 Studio: Evaluation

Lauf-Detail (`eval-run-detail`) neu gegliedert, von oben nach unten:

1. **Messbedingungen** (aufklappbar): Maschine, Modell, Weg, Parameter, Judge + Fassung,
   Konfigurations-Hash, App-Version; „gegenüber dem vorigen Lauf derselben Maschine geändert“
   als Liste.
2. **Kennzahlen**: Gesamt (1–5), harte Quote, Latenz p50/p95, Kosten je Zug, Judge-Kosten.
3. **Kurzbericht** (Text).
4. **Matrix Zielgruppe × Anwendungsfall** und **Matrix Ablauf × Skala**
   (`views/eval-matrix.component.ts`, eine Komponente für beide): Zellen mit Zahl **und** Farbe,
   Stufen ≥ 4,5 / ≥ 3,5 / ≥ 2,5 / < 2,5 / ohne Daten (schraffiert, nicht grau wie ALT), Farben
   als Studio-Token mit Kontrast-Prüfung (`check:contrast`), Zelle klickbar → springt zum Ablauf
   bzw. filtert die Zugliste. Tabelle mit `<th scope>`; Tastatur-bedienbar.
5. **Persona × Intent** (nur Ansicht „Muster“ und nur bei Muster-Läufen) in den Muster-Panels.
6. **Problemliste**: Abläufe nach Gesamt aufsteigend, je Eintrag Noten-Chips < 4, Statement,
   Auffälligkeiten.
7. **Abläufe**: Karte je Ablauf mit Skalen-Balken, Statement; aufgeklappt die Züge mit
   Zug-Noten, Notiz, harten Prüfungen (heutige `eval-gold-turns`-Zeile), Werkzeugen und einem
   **Zeitbalken** je Zug (Phasen aus `spur`).
8. **Zeiten**: Mittel je Phase als gestapelter Balken (Klassifikation, Antwort, Werkzeuge,
   Agent-Runden).

Vergleich und Trends wie in §5.4. Alle Texte über den Katalog (de/en), Zustände
laden/leer/Fehler/teilweise (laufender Lauf) explizit.

### 5.7 Generative Läufe (Phase G, nachrangig)

Maschinenwahl im Start-Formular und als Kopfzeile je Zug (wie Golden), `messbedingungen` v2,
Latenz je Zug, und die Gespräche des Modus „Dialoge“ werden mit dem Ablauf-Judge bewertet
(Zielgruppe = simulierte Persona, `erwartung` = Intent-Beschreibung). Danach entfällt der
ALT-Judge.

## 6 Globale Regeln

- Muster-Maschine bleibt (Z2): nichts an ihr entfernen; ihre Panels bleiben in der Muster-Ansicht.
- Abhängigkeiten zeigen nach innen; `auswertung_v2` ohne E/A; keine neuen Pakete.
- Dateien ≤ 300 Zeilen: `judge_v2.py`, `prompts_v2.py`, `auswertung_v2.py`, `bericht_md.py`
  getrennt; im Studio eigene Komponenten statt `eval-run-detail` weiter anzubauen.
- i18n: jeder sichtbare Text über `catalogue/*.ts` (de/en, keine Laufzeit-Schlüssel).
- UI-Boden: WCAG 2.2 AA, Kontrast-Wächter, Tastatur, keine Farbe als einziges Signal.
- Datenschutz: Prompt-Ablage nur feste Teile; Golden-Sitzungen `eval-…` unterliegen weiter der
  Aufbewahrung, die Läufe selbst (`eval_runs`) nicht — sie tragen die Spur, die sie brauchen.
- Tests: Backend `uv run pytest`, Studio `npx ng test studio --watch=false`, `npm run lint`,
  `check:*`, OpenAPI-Vertrag (`scripts/export_openapi.py --check`, Zusätze in
  `docs/api/bewusste-vertragszusaetze.md`).
- Golden-, Eval- und Lastläufe startet der Nutzer; kleine Proben sind erlaubt.

## 7 Aufgaben

Jede Phase beginnt mit **Schritt 0: `/better-coding-workflow` laden** (bei UI zusätzlich
`/better-coding-frontend`). Jede Aufgabe: Test zuerst, rot sehen, umsetzen, grün sehen.

### Phase A — Messbedingungen und Spur (Backend)

- **A1** `services/llm.py`: `route_beschreibung(model) -> dict` (rein). Test: je Anbieter
  (`openai`, `b-api-openai`, `b-api-academiccloud`) und Modell (gpt-6 → `responses`, ältere →
  `chat`) die erwartete Beschreibung; kein Schlüssel im Ergebnis.
- **A2** `services/eval/run_conditions.py`: `engine_effective`, `route`, `llm_parameter`, `app`
  ergänzen. Test: Felder vorhanden, `app` leer ohne Umgebung.
- **A3** `services/eval/fingerprint.py`: `konfig_fingerprint(store) -> dict` (Version, Hash,
  Stand je Bereich; Gesamt-Hash stabil gegen Schlüsselreihenfolge), `gold_flows_hash(flows)`.
  Test: gleiche Daten in anderer Reihenfolge → gleicher Hash; eine Änderung → anderer Hash.
- **A4** Migration `0012_prompt_versions.py` + `db/models.py`. Test: Migration hin/zurück
  (Muster wie `test_migration_werkfassung.py`).
- **A5** `services/prompt_ablage.py` (`merke`, Prozess-Cache) und Einhängen an den vier
  Festteil-Stellen; `obs/usage.py` sammelt `prompts{phase: hash}`. Tests: einmal schreiben je
  Fassung; Wächter: kein Nutzertext/keine Seitendaten im gemerkten Text (Agent- und Muster-Zug
  mit markanter Nutzernachricht).
- **A6** `evals/run_golden.flatten_debug`: `engine`, `spur`, `runden`, `werkzeug_ergebnisse`,
  `prompt_hashes` behalten. Test: aus einem echten Agent- und Muster-Debugblock (Fixture).
- **A7** `Dockerfile` `ARG BOERDI_VERSION GIT_SHA` → `ENV`; `image.yml` befüllt sie. Test:
  `test_deploy_compose.py`-artiger Wächter auf die beiden `ARG`-Zeilen.

### Phase B — Golden-Abläufe

- **B1** `config_models/knowledge.py`: `Anwendungsfall`-Literal, `GoldTurn.expect.anwendungsfall`
  Pflicht, `GoldFlow.erwartung` Pflicht. Test: fehlend → Validierungsfehler mit Pfad.
- **B2** `seeds/eval/gold-flows.yaml`: alle 46 Züge `anwendungsfall`, alle 22 Abläufe
  `erwartung`. Test: Seed validiert; jede Zielgruppe hat ≥ 1 Ablauf.
- **B3** `scripts/export_area_schemas.py` neu erzeugen; Studio-Formular zeigt die neuen Felder
  (Schema-getrieben, Feld-Hinweise in `catalogue/fields-*.ts`). Test: Schema-Check.

### Phase C — Judge v2

- **C1** `services/eval/prompts_v2.py`: Ablauf-, Zug- und Berichtsvorlage, Stufen-Verankerung,
  `JUDGE_V2_FASSUNG`. Test: keine Muster-/Intent-Kennung im gerenderten Prompt; Fassung stabil.
- **C2** `services/eval/judge_v2.py`: `judge_ablauf`, Parsen + Klemmen 1–5, `JudgeError`.
  Tests mit Attrappen-LLM: gültige Antwort, Note 7 → 5, fehlende Skala → Fehler, Kaputt-JSON →
  `JudgeError`.
- **C3** `judge_zug` mit verdichtetem Verlauf (400 Zeichen je Vorgänger-Antwort). Test: Verlauf
  im Prompt, Länge gedeckelt.
- **C4** Judge-`usage_acc` → `judge_usage`. Test: Token/Aufrufe summiert.
- **C5** `services/eval/golden_run.py`: nach den Zügen Zug-Judge, dann Ablauf-Judge, dann Bericht;
  Fortschritt je Schritt. Test: Reihenfolge, `judge_failed` je Ebene.
- **C6** Generative Läufe unverändert (ALT-Judge) — Wächter, dass `runner.py` weiter
  `judge.judge_turn` nutzt, bis Phase G.

### Phase D — Auswertung, Bericht, API

- **D1** `services/eval/auswertung_v2.py`: `je_ablauf`, `gesamt`, drei Matrizen, `zeiten`.
  Tests mit festen Daten je Kennzahl (inkl. leere Zellen, `judge_failed`, Agent-Lauf ohne
  Persona×Intent).
- **D2** Kurzbericht-Aufruf (`judge_v2.kurzbericht`). Test mit Attrappe.
- **D3** `services/eval/bericht_md.py` + `GET /api/eval/runs/{id}/bericht.md`. Test: Abschnitte,
  Tabellen, Markdown-Sonderzeichen entschärft.
- **D4** `engine_compare.py`: Skalen, Gesamt, Messbedingungs-Unterschiede; `GET
  /api/eval/prompt-diff`. Tests: geänderte Bereiche/Bausteine gelistet; Diff zweier Fassungen.
- **D5** `queries.py` Trends je Skala/Gesamt/Latenz/Kosten, Wechselmarken. Test mit drei Läufen.
- **D6** OpenAPI neu erzeugen, `bewusste-vertragszusaetze.md`, Routen-Liste im Vertragstest.

### Phase E — Studio-Ansicht (UI)

- **E1** `core/studio-ansicht.service.ts` + Spec (Startwert, Speichern, `zeigt`, `bereichSichtbar`
  für alle vier Wirkungsstufen, localStorage wirft).
- **E2** `shell/ansicht-umschalter.component.ts` + Spec (Tastatur, ARIA, i18n de/en).
- **E3** Kennzeichnung in `studio-views.ts`, `curated-pages-*.ts`, Übersichtskarten, Analyse-Reiter
  + Spec: Agent-Ansicht blendet `/dimensionen`-Reiter Intents/Entities/Signale/Platzhalter/
  Klassifikation aus, `/material-formate` Materialtypen, `/agent`-Panels in Muster-Ansicht.
- **E4** Navigation und `curated-view` filtern; ausgeblendete Seite per URL → Banner + Knopf.
- **E5** Analyse: `engine`-Parameter (Studio + Backend `/api/quality/*`), Reiter filtern. Backend-
  Tests je Endpunkt mit Agent- und Muster-Zeilen.
- **E6** `/agent` lädt Wirkungen nach dem Speichern neu; Plakette im Bereichs-Editor.
- **E7** Evaluation-Filter aus der Ansicht vorbelegen.

### Phase F — Studio-Evaluation (UI)

- **F1** `core/eval-api.service.ts`: Typen für `messbedingungen` v2, `auswertung_v2`, Bericht.
- **F2** `views/eval-messbedingungen.component.ts` (+ Änderungen gegenüber vorigem Lauf).
- **F3** `views/eval-matrix.component.ts` (beide Matrizen + Persona×Intent), Farbstufen-Token,
  Kontrast-Wächter erweitern, Klick/Tastatur.
- **F4** `views/eval-ablauf-karte.component.ts` (Skalen-Balken, Statement, Züge mit Zug-Noten,
  harte Prüfungen, Werkzeuge, Zeitbalken).
- **F5** `views/eval-problemliste.component.ts`.
- **F6** `views/eval-zeiten.component.ts` (gestapelte Phasen).
- **F7** `eval-run-detail` neu zusammensetzen (Reihenfolge §5.6), Kurzbericht, Download-Knopf
  `bericht.md`; Zustände laden/leer/Fehler/laufend.
- **F8** Vergleich und Trends um Skalen, Messbedingungen und Prompt-Diff erweitern.

### Phase G — Generative Läufe (nachrangig)

- **G1** Maschinenwahl + Kopfzeile, `messbedingungen` v2, Latenz je Zug.
- **G2** Dialoge mit dem Ablauf-Judge; Szenarien mit dem Zug-Judge.
- **G3** ALT-Judge entfernen, Wächter aus C6 auflösen.

### Phase H — Abnahme

- Browser-Abnahme nur gegen eine Wegwerf-DB (Rezept: Memory „browser-abnahme-nur-wegwerf-db“).
- Ein Golden-Lauf je Maschine mit Judge **startet der Nutzer**; danach Vergleich im Studio.
- Review (`/better-coding-review`) über das ganze Paket, Befunde beheben.

## 8 Abnahmekriterien

| Anforderung | Nachweis | Erfolg |
|---|---|---|
| Nur Relevantes je Modus | Studio-Specs E3/E4; Browser: Ansicht Agent | keine Intents/Entities/Signale/Material-Typen, Analyse ohne Matrix/Ablauf/Diagnose; Muster-Ansicht ohne Agent-Panels |
| Ablauf-Judge mit Skalen + Statement | Backend-Tests C2/C5; Golden-Lauf | je Ablauf 7 Skalen 1–5, Gesamt, Statement; `judge_failed` statt stiller Note |
| Beide Modi fair | Wächter C1 | kein Muster-/Intent-Bezug im Judge-Prompt; gleiche Skalen in beiden Läufen |
| Matrizen | Spec F3 | drei Matrizen, Zahl in jeder Zelle, „ohne Daten“ unterscheidbar, Kontrast-Wächter grün |
| Kurzbericht + Export | D2/D3 | `summary.kurzbericht`, `bericht.md` mit allen Abschnitten |
| Messbedingungen | A1–A7 | Modell, Weg, Parameter, Judge-Fassung, Gold-Hash, Konfig-Fingerprint, Prompt-Bausteine, App-Version im Lauf |
| Zeiten | A6/D1/F6 | Phasenzeiten je Zug und je Lauf sichtbar |
| Vergleichbarkeit | D4/F8 | Vergleich nennt geänderte Bereiche/Prompts mit Text-Diff |

**Regression:** volle Backend-Suite, Studio-Suite, `npm run lint`, `check:*`, OpenAPI-Vertrag;
bestehende Golden-Prüfungen (`run_golden.check_golden_turn`) unverändert grün; ALT-Judge-Test
(`test_eval_prompts`) bleibt bis Phase G.

## 9 Risiken

| Risiko | Gegenmittel |
|---|---|
| Judge-Noten schwanken zwischen Läufen | Temperatur 0, Stufen-Verankerung, gleiche Fassung; im Vergleich die Judge-Fassung prüfen; Spannweite über Wiederholungen (`engine_matrix`) |
| Judge bevorzugt eine Maschine | keine Maschinen-Kennungen im Prompt; Wächter-Test |
| Mehr Kosten je Lauf | ≈ 69 statt 46 Aufrufe; Judge-Kosten sichtbar; Judge abschaltbar wie heute |
| Ausblenden versteckt Nötiges | Ansicht „Beide“; Krise-Bereiche bleiben sichtbar; direkte URL funktioniert mit Banner |
| `area_effects` veraltet | bestehender Wächter (`test_area_effects.py`) + neuer Spec, dass jede Seite in mindestens einer Ansicht erscheint |
| Prompt-Ablage wächst | nur feste Teile; Fassungen ändern sich selten |
| Laufzeit-Daten groß | Spur je Zug ohne Prompt-Texte; nur Hashes |

## 10 Offene Fragen

Keine — die vier Entscheide aus §3 decken den Schnitt. Phase G ist nachrangig und kann nach
Phase F getrennt freigegeben werden.

## 11 Log

| Datum | Schritt |
|---|---|
| 2026-10-17 | Erkundung (alter Chatbot, Eval heute, Studio nach Modus), Nutzer-Entscheide, Entwurf |
| 2026-10-17 | **Phase A fertig.** A1 `services/llm_weg.py` (`weg_beschreibung`: Anbieter, Modell, `api` responses/chat, `basis` Host+Pfad, Denkparameter, Tarif; eigenes Modul, `llm.py` an der 300-Zeilen-Grenze). A2/A3 `run_conditions`: `maschine`, `weg`, `judge_weg`, `app` (Settings `BOERDI_VERSION`/`GIT_SHA`), `konfiguration` (`eval/fingerprint.py`: Version, Hash, Stand je Bereich gegen die Werksfassung; Fehler werden vermerkt), `gold_flows` (Hash + IDs). A4 Migration `0012_prompt_versions` + Modell `PromptVersion`. A5 `services/prompt_ablage.py` (`merke` → `acc["prompts"]`, `speichere` am Zugende mit SAVEPOINT); vermerkt werden `agent.kopf`, `agent.master_skill`, `seitenregeln`, `classify.system` — die Muster-Antwortprompts nicht (tragen Entitäten; ihre festen Schichten deckt der Konfigurations-Fingerabdruck), Wächter-Test: Nachricht und Seitendaten landen nicht in der Ablage. A6 `flatten_debug` behält `engine`, `runden` (agent_round/agent_stop), `werkzeug_ergebnisse`; Zeiten und Prompt-Prüfsummen reisen in `token_usage`. A7 `Dockerfile` `ARG`→`ENV`, `image.yml` `build-args` aus `needs.stand.outputs`. Nachweis: ruff sauber; betroffene Tests 928 passed. Abweichung vom Plan: Prompt-Bausteine je Lauf nicht in `run_conditions`, sondern je Zug in `token_usage.prompts` (genauer: zeigt, welche Fassung *jeder* Zug sah). |
| 2026-10-17 | **Phase B fertig.** `GoldTurn.anwendungsfall` (Auswahl `ANWENDUNGSFAELLE`, 12 Werte) und `GoldFlow.erwartung` (Textfeld). **Abweichung vom Plan:** der Anwendungsfall ist ein Feld am Zug statt eines Schlüssels in `expect` — so zeigt das Studio eine Auswahlliste; und Pflicht ist er nicht im Modell, sondern beim Laufstart (`run_golden.validate_flows`, vor dem ersten bezahlten Zug), nach der Projektregel `config_models/_shared.Choices` (kein 422 beim Speichern eines älteren Stands). Runner trägt `anwendungsfall` je Zug-Datensatz und `erwartung` je Gespräch; Liste im Runner ist ein Zwilling, ein Test hält beide gleich. Seed: 46 Züge und 22 Erwartungen gesetzt, dazu `evals/skill-bruecke-flows.yaml` (3 Flows); Formatwächter verlangt den Anwendungsfall je Zug. Studio: Beschriftungen de/en (`fields-kosten-eval.ts`, Auswahlwerte in `fields-auswahl.ts`). Nachweis: Backend Gold/Eval/Config 398 passed, Studio 122/122 Dateien, Schema-Export unverändert. |
| 2026-10-17 | **Phase C fertig.** `eval/prompts_v2.py` (Ablauf-Skalen 7, Zug-Skalen 4, Stufen-Verankerung 1–5, `JUDGE_V2_FASSUNG` = Prüfsumme der Vorlagen; Werkzeugnamen ohne interne Muster-Werkzeuge und „(prefetch)“, keine Muster-/Intent-/Persona-Kennungen — Wächter-Test), `eval/judge_v2.py` (`judge_ablauf`, `judge_zug`; Klemmen 1–5, fehlende Skala/kaputtes JSON → `JudgeError`; Merkposten-Phasen `judge_ablauf`/`judge_zug`). `golden.bewerte_gespraeche` ersetzt `judge_conversations`: Zug-Urteil in `turn["judge"]` (flach, mit `total` = (gesamt−1)/4 und `notes` — Laufliste/`judge_avg` lesen weiter), Ablauf-Urteil in `conv["urteil"]`, Ausfälle in `judge_failed`/`urteil_fehler`; Zielgruppe einmal je Lauf aus der Konfiguration samt Ton-Regeln. `golden_run` mit eigenem Merkposten: `summary.judge_usage`, `judge_fassung`, `judge_bewertet`. Generative Läufe bleiben beim Judge v1 (Wächter C6). Nachweis: Eval/Golden 384 passed; Live-Probe gpt-6-luna (OpenAI direkt): Ablauf- und Zug-Urteil plausibel (erkannte Du-Anrede, fehlenden Lernpfad, Kontextverlust; drei Auffälligkeiten mit Zug), 2 Aufrufe ≈ 2 000 Token. Offen bis Phase D: `engine_metrics.AXES` und Studio-Profil lesen noch die Achsen des Judge v1. |
| 2026-10-17 | **Phase D fertig.** D1 `eval/auswertung_v2.py` (je Ablauf, gesamt, drei Matrizen, Zeiten je Knoten/Schritt/LLM-Phase; beim Lesen am Lauf-Detail als `auswertung`, wie das Profil mit der gepflegten Preistafel). D2 `judge_v2.kurzbericht` + `golden.kurzbericht_erstellen` (Judge sieht die Auswertung, nicht die Gespräche; Ausfall → `summary.kurzbericht_fehler`, der Lauf bleibt gültig), Merkposten-Phase `judge_bericht`. D3 `eval/bericht_md.py` + `GET /api/eval/runs/{id}/bericht.md` (Download `text/markdown`; Sonderzeichen entschärft, Zeilenumbrüche in Zellen gefaltet, Dateiname nur Kennungszeichen). D4 `eval/vergleich_v2.py` im Vergleich: `runs[].bewertung`, `bewertung_je_maschine`, `unterschiede` gegen den ersten Lauf (Felder der Messbedingungen, geänderte Bereiche, Prompt-Bausteine mit beiden Prüfsummen; Läufe vor Paket 13: nichts erfunden) + `GET /api/eval/prompt-diff?a=&b=` (`eval/prompt_diff.py`, Unified Diff aus `prompt_versions`). D5 `eval/trends_v2.py`: `trends.v2` mit Reihen je Skala/Gesamt/Zug-Mittel/Latenz p50/Kosten je Zug und Wechselmarken. **Abweichung vom Plan:** die Trend-Abfrage lädt keine Transkripte (Paket 4, E1) — deshalb schreibt der Lauf beim Abschluss `summary.kennzahlen_v2` (Noten, Latenz, Kosten zum Preis beim Abschluss, Prompt-Fassungen); ältere Läufe geben keinen Punkt. D6 Vertrag neu erzeugt (gegen `main` 9deae33 genau zwei neue Pfade, sonst nichts), `bewusste-vertragszusaetze.md`, Routenliste. Nachweis: Eval/Golden/OpenAPI-Bereich 594 passed, ruff sauber. Offen für Phase F: `engine_metrics.AXES` und das Studio-Profil lesen weiter die Achsen des Judge v1 (bei v2-Läufen leer) — die Studio-Ansicht liest künftig `auswertung`. |
| 2026-10-17 | **Phase E fertig.** E1 `core/studio-ansicht.service.ts` (`ansicht` = gemerkte Wahl › Vorgabe-Maschine › „beide“; `localStorage` in try/catch; `zeigt`, `bereichSichtbar` für alle vier Stufen, `maschine` als Filterwert). E2 `shell/ansicht-umschalter.component.ts` im Kopf: echte Radios im Fieldset (Gruppenname, Pfeiltasten, Auswahl von der Plattform), Katalogteil `ansicht.ts` de/en. E3/E4 `views/ansicht-filter.ts` (`abschnittSichtbar`, `seiteSichtbar`); `engines` an `StudioView` und Panels (Agent-Panels `['agent']`, `agent-skills` beide); Navigation, Übersichtskarten und kuratierte Seiten filtern. **Abweichung vom Plan:** verborgene Abschnitte und Reiter werden *verborgen, nicht ausgehängt* (`hidden`) — offene Änderungen überleben einen Wechsel der Ansicht, der Verlassen-Schutz sieht sie weiter; eine per URL geöffnete Seite ohne Wirkung sagt es (`.cv-versteckt`) und bietet „Alles zeigen“. E5 `/api/quality/*` mit `engine` (`pattern_id = 'AGENT'` bzw. `<>`; Krisen-Züge zählen zur Muster-Maschine), **auch am Sammel-Löschen** (die Liste zeigt nur eine Maschine → „Alle löschen“ löscht nur diese, Knopf und Frage sagen es); Studio: Analyse ohne Matrix/Flow/Diagnose in der Agent-Ansicht, alle Abfragen nach Maschine. E6 nach dem Speichern von `01-base/engine` lädt die Seite die Wirkungen neu; Plakette im Bereichs-Editor. E7 Lauf-Liste und Verlauf: Maschinen-Filter aus der Ansicht vorbelegt und ihr folgend. Vertrag: an neun `/api/quality/*`-Operationen je ein Parameter (gegen `main` gemessen), Zeile in `bewusste-vertragszusaetze.md`. Nachweis: Studio 125/125 Dateien, 1 548 Tests; eslint, `check:tokens/a11y/contrast/radii` sauber; `build:studio` ok (Budget-Warnung 1,13 MB, bekannt und hingenommen, Stand in `offene-befunde`); Backend Qualität 67 (inkl. Postgres), Vertrag 9, ruff sauber; Backend gesamt nach Phase D 6 287 passed. Browser-Abnahme in Phase H (Wegwerf-DB). |
| 2026-10-17 | **Phase F fertig.** F1 `core/eval-auswertung.ts` (Typen der Auswertung v2, Messbedingungen, Trends v2, Prompt-Diff; `stufe()` mit den Grenzen 4,5/3,5/2,5; Leser für `summary`), `EvalApi.berichtMd`/`promptDiff`, `auswertung`/`v2`/Vergleichsfelder an den Typen. F2 `eval-messbedingungen` (aufklappbar; erst beim Aufklappen die Wechselmarke dieses Laufs aus `trends.v2` — ehrlich bei „erster Lauf“ und „außerhalb des Verlaufs“). F3 `eval-matrix` (echte Tabelle, Zahl + Stufe im zugänglichen Namen, Legende, leere Zellen schraffiert und nicht wählbar, Rahmen scrollt bei schmaler Breite) mit neuen Token `--st-band-*` (hell 14,0–15,8:1, dunkel 6,8–7,8:1, im Browser gemessen). F4 `eval-ablauf-karte` (Sprungziel, Skalen-Balken mit Zahl, Statement, Auffälligkeiten, Züge mit Zug-Noten, Notiz, verfehlten Prüfungen, Werkzeugen ohne interne Muster-Werkzeuge, Zeit je Schritt). F5 `eval-problemliste`. F6 `eval-zeiten` — **Abweichung:** Tabelle je Art statt gestapeltem Balken (Mediane verschiedener Schritte ergeben keine Summe). F7 `eval-auswertung-v2` im Lauf-Detail in der Reihenfolge §5.6, Persona × Intent nur, wo die Ansicht Muster zeigt; Zelle Zielgruppe × Anwendungsfall filtert die Karten, Ablauf × Skala und Problemliste springen; Profil (Achsen des Judge v1) nur noch ohne Judge-v2-Noten; Knopf „Bericht (Markdown)“. F8 `eval-vergleich-v2` (Noten je Maschine, Unterschiede gegen die Referenz, Text-Unterschied je Prompt-Baustein auf Wunsch) und `eval-trends-v2` (je Lauf Noten/Median/Kosten, Spalte „Geändert“). Browser-Abnahme gegen Wegwerf-DB `boerdi_p13_browser` (danach gelöscht): drei Befunde behoben — Balken zu blass (jetzt Punkt-Farben), doppelter Matrix-Titel (Caption nur für Vorlesehilfen), Seite bei 375 px 659 px breit (Grid-Spur `minmax(0, 1fr)`); dazu Leerzeichen zwischen Spans/Chips (Vorlesehilfe las „Gesamt3“). Nachweis: Studio 134/134 Dateien, 1 596 Tests; eslint, `check:tokens/a11y/contrast/radii` sauber; `build:studio` ok (Budget-Warnung 1,14 MB, Stand in `offene-befunde`). |
