# Golden v2 — Anwendungsfall-Evaluation über alle drei Maschinen

Stand: 2026-08-22 · Status: **umgesetzt (GV1–GV7), Abschlussmessung offen (Nutzer)** · Vorgänger: `evals/README.md` (v1)

## 1. Befund (warum v1 nicht mehr durchläuft)

Der deterministische Golden-Runner (`evals/run_golden.py`, 36 Tests) ist solide —
aber sein Datensatz misst die **Klassifikator-Maschine**, die seit dem 17.08.
nur noch einer von drei Modi ist:

- **66 von 116 harten Checks hängen am Klassifikator** (36× `persona`, 39×
  `intent`, minus 9 zufällig passende). Agent/Hybrid überspringen den
  Klassifikator (`graph/nodes/assess.py:88-99`): Persona = Sitzungswert,
  Intent = hart „I01". Ein Agent-Lauf meldet ~43 % Quote und Exit 1 — als
  Befund wertlos.
- **Alle 12 `structure: idoc`-Checks** hängen an der Muster-Weiche M09/M10/M11
  (`services/turn_persist.py:513`), die im Agent-Modus tot ist; Dokument-Boxen
  entstehen dort über das Werkzeug `zeige_dokument`.
- **Der Judge bekommt im Agent-Modus keine Rubrik**: der Pattern-Lookup liefert
  wörtlich „(Pattern AGENT nicht in 03-patterns/ gefunden)"
  (`services/eval/judge.py:52-58`) und bewertet `pattern_match` ins Leere.
- **Der Studio-Gold-Lauf kann die Engine nicht wählen**
  (`services/eval/golden_run.py:144` ruft ohne Kopfzeilen) — er misst still die
  Vorgabe aus `01-base/engine.yaml`.
- `llm_engine_match_rate` fällt im Agent-Modus strukturell auf **0.0** und
  sieht in den Trends wie ein Absturz aus; die Muster-Serie bleibt leer
  (`services/eval/metrics.py:171-177`, `queries.py:122-132`).
- **`must_offer` ist toter Text** — in ALT wie NEU an jedem Turn gepflegt, im
  Studio angezeigt, aber nie geprüft und nie dem Judge übergeben. Die je Fall
  dokumentierte „ideale Antwort" wird von nichts ausgewertet.
- In `evals/reports/` liegt **ein** Bericht (10.07., Muster-Engine, gegen ALT).
  Es gibt keine Baseline der neuen Anlage.
- Abdeckungslücken v1: Intents I09–I11 (Kuratieren, QS, Erschließen) und die
  Anwendungsfälle hinter M17–M20 (Volltext, Bestand ändern, fremde Seite,
  Prüfen) kommen im Set nicht vor.

Reife Bausteine, die bleiben: Judge mit dynamischer Rubrik aus der Config
(`judge.py:32-236`), Anti-Fehlalarm-Klauseln (`prompts.py`, byte-genau aus
ALT), Hart/Weich-Trennung mit `None` = „nicht geprüft", Bot-Text-Anreicherung
(Judge sieht Idocs/Karten), Kostenschätzung, Trends, A/B-CLI.

## 2. Entscheidungen (Nutzer, 2026-08-22)

| Frage | Entscheidung |
|---|---|
| Set-Schnitt | **Neu nach Anwendungsfällen je Zielgruppe, ersetzt v1.** Klassifikator-Messung bleibt Aufgabe der generativen Strecke, nicht des Golden-Sets. |
| Harte Quote | **Nur deterministische Ergebnis-Checks**; Judge-Scores (inkl. Soll-Erfüllung) daneben, nie hineingemischt. Kein Gate auf LLM-Scores (ALT-Lehre). |
| Engines | **Ein Lauf je Engine + Vergleich.** Studio bekommt einen Engine-Wähler, die Kopfzeile wird durchgereicht, der Bericht trägt die Engine. |
| Umfang | **Erst Golden v2**; die generative Strecke bekommt nur das Nötigste (ehrliche `None`-Metriken, Judge-Rubrik-Fallback). Eigenes Paket später. |

## 3. Zielbild: das v2-Format

**Eine Quelle**: `backend/seeds/eval/gold-flows.yaml` (Studio-editierbar über
den Bereich `eval/gold-flows`). Die Kopie `evals/gold-flows.yaml` entfällt;
die CLI zeigt per Default auf die Seed-Datei. (Regel „Seed ist die
Import-Quelle" gilt auch hier.)

```yaml
version: 2
flows:
  - id: GV-LEH-1
    zielgruppe: P-LEH            # nur Gruppierung/Anzeige — KEIN Check
    title: "Lehrkraft: Material -> Lernpfad -> Arbeitsblatt -> Loesungen"
    turns:
      - message: "Ich bereite eine Mathestunde für meine 3. Klasse zum Thema Brüche vor und suche passendes Material."
        expect:
          register: sie          # hart, wenn messbar (neutral => None, s.u.)
          structure: cards       # hart: >=1 Karte — egal, welche Maschine sie erzeugt
          tools_any: [search_wlo_all, search_wlo_content]   # hart: mind. eines gerufen
          must_offer: "Konkrete Material-/Sammlungstreffer zu Brüchen Primarstufe, mit Anschlussangebot."
      - message: "Gibt es dazu auch einen fertigen Lernpfad, den ich direkt einsetzen kann?"
        expect:
          register: sie
          structure: idoc
          must_offer: "Lernpfad-Vorschlag als strukturiertes Dokument, Schritte mit Material belegt."
```

**Erwartungen sind Ergebnisse, keine Klassifikator-Interna.**

| Feld | Art | Regel |
|---|---|---|
| `structure` | hart | `idoc` ⇒ ≥1 `inline_documents`; `cards` ⇒ ≥1 Karte; fehlt ⇒ nicht geprüft. Engine-fair: der Mechanismus (Muster-Weiche oder `zeige_dokument`) ist egal. |
| `tools_any` | hart | mindestens eines der genannten Werkzeuge in `tools_called` (Namen vor dem ersten Leerzeichen verglichen, wie `metrics.py:353-359`). Kodiert „Zuerst handeln" ohne Muster-Kopplung. Fehlt ⇒ nicht geprüft. |
| `register` | hart, wenn messbar | wie v1 — **aber ehrlich**: liefert die Heuristik `neutral` (z. B. Ansage-Zeile + 1-Satz-Lead vor einer Dokument-Box), zählt der Check als `None`, nicht als bestanden. |
| `qr` | hart | ≥1 Quick-Reply (wie v1, immer geprüft). |
| `host` | weich | wie v1 (Karten-Links auf `REPO_BASE_URL`). |
| Fehler-Turn | hart | HTTP-/Transportfehler wie v1. |
| `must_offer` | **Judge** | Pflichtfeld je Turn. Wird dem Judge als „SOLL-ANGEBOT" übergeben; neue Achse `auftrag_erfuellt` (0–2). Fließt in `judge_avg`, **nie** in die harte Quote. |
| `persona`/`intent` | **entfällt** | Klassifikator-Güte misst die generative Strecke (Persona×Intent-Matrix) — das bleibt deren Auftrag. |

**Harte Quote v2** = `structure` + `tools_any` + `register` + `qr` + fehlerfrei.
`host` bleibt weich. Exit-Codes und `None`-Semantik wie v1.

## 4. Der Set-Entwurf (Inhalt von GV2)

Je Zielgruppe 2–3 typische Anwendungsfälle als natürliche Gespräche (Regel aus
v1 bleibt: keine künstlichen Persona-Marker, zusammenhängende Sessions).
Arbeitsliste — Feinschliff im Paket, Redaktion kann später im Studio ändern:

| Flow | Zielgruppe | Anwendungsfall (deckt) |
|---|---|---|
| GV-LEH-1 | Lehrkraft | Material → Lernpfad → Arbeitsblatt → Lösungen ergänzen (Suche, Plan, Erzeugen, Überarbeiten) |
| GV-LEH-2 | Lehrkraft | Kachel → **Volltext anzeigen** → Text vereinfachen (M17-Weg, Überarbeiten) |
| GV-LER-1 | Schüler:in | Verständnisfrage („kapier Brüche nicht") → Erklärung → Übungsmaterial (Du-Register) |
| GV-LER-2 | Schüler:in | Quiz zu einem Thema erzeugen → Lösungen zeigen |
| GV-ELT-1 | Eltern | Kind unterstützen → passendes Grundschul-Material, einfacher Ton |
| GV-ENT-1 | Entscheider | Was ist WLO / Qualitätssicherung → Überblick (Wissensweg, keine Kacheln) |
| GV-RED-1 | Redaktion | **Fremde Seite erschließen**: URL → Eignung prüfen → Metadaten-Vorschlag → zweistufig anlegen (Vorschau, dann Ja) |
| GV-RED-2 | Redaktion | **Sammlung prüfen**: Kompendium vs. Bestand, Lücken mit Beleg, Suchvorschlag je Lücke |
| GV-RED-3 | Redaktion | Einreichen/Melden erklären (Abgrenzung zu Bot-Feedback) |
| GV-AND-1 | Unbekannt | Orientierung → erstes Anliegen → Suche |
| GV-AND-2 | Unbekannt | Feedback-Recovery: „hat nicht geholfen" → gezielt nachsteuern statt blind neu suchen |
| GV-WIS-1 | quer | WLO-Wissensfrage (interner Wissensbestand, `tools_any: [wissen_suchen]`) |

~12 Flows, ~35–40 Turns. Neu abgedeckt gegenüber v1: Volltext (M17),
zweistufiges Schreiben (M18/M20), Prüfen mit Beleg (M19), Wissensweg
(`wissen_suchen`). Der zweistufige Schreib-Fall bleibt auf Staging-Bestand
und nutzt die Vorschau-Stufe; der Ja-Turn prüft `tools_any` auf das
Schreib-Werkzeug — ausgeführt wird gegen Staging (Nutzer-Entscheid beim
ersten Echtlauf, ob der Flow aktiv ist).

## 5. Pakete

Jedes Paket beginnt mit `/better-coding-workflow` (Skill-Refresh), Test zuerst.

### GV1 — Runner v2 (`evals/run_golden.py` + Tests)
- `version: 2` parsen; v1-Dateien mit klarer Fehlermeldung abweisen (kein
  stiller Doppelbetrieb).
- Checks: `tools_any` neu; `register`-Ehrlichkeit (`neutral` ⇒ None);
  `persona`/`intent` aus `GOLDEN_CATS` entfernen; Scorecard-Felder nachziehen.
- `--engine pattern|agent|hybrid` ⇒ setzt `X-Boerdi-Engine` (zusätzlich zu
  `EVAL_CHAT_HEADERS`); Bericht trägt Top-Level-Feld `engine`.
- Begleitfix: `per_flow.persona`-Überschreiber (`run_golden.py:299-301`,
  im Studio als Bug dokumentiert `gold-scorecard.ts:35-43`).
- Tests: `test_golden_runner.py` auf v2 (Format-Pin, Check-Matrix, Engine-Flag,
  Register-None, v1-Abweisung).

### GV2 — Datensatz v2 (`backend/seeds/eval/gold-flows.yaml`)
- Die 12 Flows aus §4 austexten; `evals/gold-flows.yaml` löschen; CLI-Default
  auf die Seed-Datei; `evals/README.md` §Datensatz anpassen.
- Wächter: Format-Pin (Flow-IDs, jedes `expect` trägt `must_offer`,
  nur erlaubte Felder).

### GV3 — Vergleich v2 (`evals/compare_golden.py`)
- Kategorien nachziehen (`persona`/`intent` raus, `tools_any` rein);
  `--ignore-classification` entfällt (Zweck erledigt); beide Engines in den
  Berichtskopf (`engine_ref`/`engine_new`) — ungleiche Engines sind der
  gewollte A/B-Fall, kein Fehler.
- Tests: `test_golden_compare.py`/`test_golden_ab.py` nachziehen.

### GV4 — Judge: Soll-Erfüllung + Ehrlichkeit (`services/eval/`)
- `judge_turn(..., soll_angebot=None)`: bei Golden-Läufen wird `must_offer`
  injiziert, neue Achse `auftrag_erfuellt` (0–2) im Ausgabe-Schema; generative
  Läufe unverändert (Parameter bleibt None).
- `pattern_match` wird **None**, wenn kein echtes Muster (M01–M20) beobachtet
  wurde (Agent immer, Hybrid vor der Musterwahl) — statt Rubrik-Lücke
  „(Pattern AGENT nicht gefunden)". `total` normalisiert über die bewerteten
  Achsen.
- **`judge_failed`**: Judge-Fehler ⇒ Turn als `judge_failed` markiert, aus
  `judge_avg` ausgeschlossen, separat gezählt — statt stiller 0-Punkte
  (Schwäche aus ALT UND NEU).
- Tests: Achsen-Normalisierung, Soll-Injektion, failed-Ausschluss.

### GV5 — Engine-Wähler durchgängig (Backend + Studio)
- `GoldenRunRequest.engine` (`pattern|agent|hybrid|default`);
  `golden_run.py:144` reicht die Kopfzeile durch; Engine in `summary_json`.
- Studio Gold-Start: Engine-Auswahl (Default „Server-Vorgabe");
  Lauf-Liste/Detail zeigen die Engine; Scorecard rendert v2-Spalten
  (Feature-Erkennung über Berichtsversion, alte gespeicherte Läufe bleiben
  lesbar).
- Begleitfixe: `deleted`-Destrukturierung (`eval-api.service.ts:211-213` vs.
  `mutations.py:71`), veralteter Modulkopf `api/eval.py:5-14`.
- Tests: Backend (Header-Durchreichung, Request-Validierung), Studio-Specs.

### GV6 — Minimum generative Strecke (ehrliche Metriken)
- `llm_engine_match_rate` und `tool_compliance_rate` ⇒ **None statt 0.0**,
  wenn strukturell unmessbar (kein Hint / leere Muster-Karte); Trends zeigen
  Lücke statt Absturz.
- Mehr nicht — der Umbau der Matrix auf Zielgruppen-Anwendungsfälle ist ein
  eigenes späteres Paket.

### GV7 — Doku + Abschluss
- `evals/README.md` v2 komplett (Kommandos je Engine, Hart/Weich-Philosophie,
  A/B über Engines); Verweis in `docs/agent-modus.md` (bisher 0 Treffer für
  „golden"); `docs/architektur.md:620-623` prüfen.

## 6. Was ausdrücklich unberührt bleibt

- **Die generative Strecke** (Szenario-Generator, Simulator, Persona×Intent-
  Matrix) — nur die zwei ehrlichen `None`-Metriken aus GV6. Klassifikator-Güte
  bleibt ihr Auftrag.
- **Personas/Intents-Konfiguration** (`04-personas/`, `04-intents/`) — v2
  nutzt sie nur zur Gruppierung und für die Judge-Rubrik.
- `../badboerdi/` (Referenz) und der MCP-Server.
- Chat-Pipeline, Muster-Engine, Agent-/Hybrid-Schleifen: **keine Zeile** —
  gemessen wird, nicht umgebaut.

## 7. Verifikation

Je Paket: `uv run --directory backend pytest -q` (Suite wächst ab 4153) ·
`uv run ruff check .` · OpenAPI: ändert sich in GV5 (neues Request-Feld) ⇒
`export_openapi.py` **neu erzeugen**, sonst `--check`.

Kleine lokale Smokes (2–3 Turns, eine Engine) sind ok. **Die Abschlussmessung
startet der Nutzer** (Kosten): drei Läufe gegen denselben lokalen Backend —

```bash
uv run --directory backend python ../evals/run_golden.py --engine pattern --label v2-pattern
uv run --directory backend python ../evals/run_golden.py --engine agent   --label v2-agent
uv run --directory backend python ../evals/run_golden.py --engine hybrid  --label v2-hybrid
uv run --directory backend python ../evals/compare_golden.py --ref <pattern>.json --new <agent>.json --label engines
```

Erfolgskriterium: alle drei Läufe **laufen durch** (Exit-Code sagt etwas über
den Bot, nicht über das Messwerkzeug), die Berichte tragen die Engine, die
Scorecard im Studio zeigt harte Quote und Judge getrennt, `auftrag_erfuellt`
ist je Turn gefüllt.

## 8. Bekannte Grenzen / bewusst offen

- **Kein Multi-Sample**: jeder Turn läuft einmal; Flakiness-Erkennung (n-of-m)
  ist notiert, aber nicht Teil von v2 — erst Baseline, dann Varianz.
- **Golden auf Englisch** bleibt offen (C1-Notiz).
- Der zweistufige Schreib-Flow (GV-RED-1) schreibt real auf Staging — ob er im
  Standard-Set aktiv ist, entscheidet der Nutzer beim ersten Lauf.
- Studio-Gold-Lauf und CLI teilen den Runner per Pfad-Import — bleibt so
  (eine Prüf-Logik, zwei Einstiege).

## 9. Log

| Paket | Status |
|---|---|
| GV1 Runner v2 | ✅ 2026-08-22 — v2-Parse + v1-Abweisung (`load_flows`), Checks register-ehrlich/`tools_any`, `--engine`-Flag + `engine` im Bericht, `per_flow.zielgruppe` (Überschreiber-Fix), `DEFAULT_FLOWS` → Seed. `test_golden_runner.py` komplett auf v2. |
| GV2 Datensatz | ✅ 2026-08-22 — 12 Flows (33 Turns) in `backend/seeds/eval/gold-flows.yaml`, `evals/gold-flows.yaml` gelöscht (v1 liegt im Backup `backups/seeds-2026-08-10-…`), Format-Wächter. Klexikon-URL für GV-RED-1; `tools_any` je Fall als Vereinigung der Engine-Namen (`wissen_suchen`/`query_knowledge`). |
| GV3 Vergleich v2 | ✅ 2026-08-22 — vorgezogen (Kategorien-Wechsel riss die Compare-Tests an): `--ignore-classification` entfernt, Mechanik (pattern/tools_called) ist kein Abweichungs-Trigger mehr, `engine_ref`/`engine_new` im Kopf + Konsole. |
| GV4 Judge | ✅ 2026-08-22 — `soll_angebot`-Injektion + Achse `auftrag_erfuellt` (eigener Prompt-Block, ALT-Templates unangetastet), `pattern_match`=None ohne echtes Muster, `total` über bewertete Achsen normalisiert, `JudgeError` statt stiller Null; beide generativen Aufrufstellen abgesichert, `judge_failed_turns` im Summary. |
| GV5 Engine-Wähler | ✅ 2026-08-22 — `GoldenRunRequest.engine` (OpenAPI neu erzeugt), `golden_run` reicht die Kopfzeile durch + Engine in Config/Summary, Zielgruppen statt Persona im Run-Config. Studio: Radio-Gruppe im Gold-Start, Engine + Judge-Ausfälle im Lauf-Detail, `hardCats` aus dem Bericht abgeleitet (v1-Läufe bleiben lesbar), `tools_any`-Label. Begleitfixe: `deleted_eval_log_rows`-Mapping, veralteter `api/eval.py`-Kopf. |
| GV6 Ehrliche Metriken | ✅ 2026-08-22 — `llm_engine_match_rate`/`llm_hint_final_match_rate`/`tool_compliance_rate` = None bei leerem Nenner; die Trend-Serie überspringt None-Läufe (Lücke statt 0.0-Absturz). Alt gespeicherte 0.0 bleiben — rückwirkend nicht unterscheidbar. |
| GV7 Doku | ✅ 2026-08-22 — `evals/README.md` v2 komplett, Messen-Verweis in `docs/agent-modus.md` §2c, `docs/architektur.md` Golden-Absatz nachgezogen. |
| Review-Fixes | ✅ 2026-08-22 — 10 Befunde aus dem Eval-Subsystem-Review behoben: (1) Persona-/Intent-Raten None bei leerem Nenner + Trend-Skip (Golden-Läufe malten die Klassifikations-Trends auf 0 %); (2) H5-Hybrid-Prefetch-Gate zurückgenommen (Verbrauchsseite existierte nie, `respond_agent` verwarf immer — H-Plan §6); (3) `EVAL_CHAT_TIMEOUT`, Default 120 s statt 60 (CLI + Backend-Runner); (4) `chat_error_turns` in Summary/Scorecard + Lauf-Detail-Anzeige; (5) `compare_golden` blockt 0-Turn-Vergleiche (Exit 1); (6) generative Chat-Fehler-Züge unbewertet statt Judge 0.0 (wie Golden); (7) Lasttest-Engine-Feld (Backend Literal + `X-Boerdi-Engine` je Zug + Studio-Radio); (8+10) tote Doku-Zeile + toter Filter; (9) Register-„Ihr" belassen (Beobachtung). |
| Review-Runde 2 | ✅ 2026-08-22 — 3 Befunde aus dem zweiten Eval/Golden/Judge-Review: (1) MAJOR `judge.py`: leere/objektlose Judge-Antworten (content `""`, JSON-Array, achsenfreies Objekt) werfen jetzt `JudgeError` statt still 0 Punkte über alle Achsen zu verbuchen — der Array-Fall lief vorher als `AttributeError` AUSSERHALB des try (Szenario-Pfad: als Chat-Fehler fehlklassifiziert; Dialog-Pfad: Lauf-Abbruch); 4 Bestandstests mit achsenfreien Antworten dokumentiert angepasst. (2) `judge_failed_turns` auch im generativen Summary (`count_judge_failed_turns` in `metrics.py`, eine Definition für beide Familien). (3) Lauf-Detail zeigt Chat-Fehler-/Judge-Ausfall-Zähler auch ohne Gold-Metriken (Transkript-Zweig — ausgerechnet die generative Familie zeigte ihre toten Züge nie). Testlauf `eval-073ce8a4dc3c` (11 Flows ohne GV-RED-1, engine=pattern, Judge an): 60/63 hart = 95,2 %, judge_avg 0.799 über 29 Züge, 0 Chat-Fehler, 0 Judge-Ausfälle, Latenz p50 12,0 s/p95 21,8 s; Achsen-Schnitte safety 2.00 · intent_fit 1.90 · pattern_match 1.90 · persona_tone 1.48 · info_quality 1.24 · auftrag_erfuellt 1.07 (schwächste Achse: Muster-Engine bietet oft an statt zu liefern). CI-Stand: Backend 4197 / Studio 993. |
| UI-Feedback-Runde | ✅ 2026-08-22 — 6 Nutzer-Punkte zu den Eval-Ansichten: (1) Trend-Kurven tragen Achsen-Marken (Score: 0..Serienmaximum; Raten: fixe 0..100 %, `rateAxisTop`); (2) Pattern-Nutzung hat einen client-seitigen Betriebsart-Umschalter (alle/Muster/agent/hybrid) — AGENT/HYBRID sind Maschinen-Marker, keine Muster; Balken/Tabelle/Summenzeile folgen dem Filter (Verteilungen jetzt aus den Kombinationen statt den Server-Aggregaten); (3) Gold-Start: „Alle auswählen"/„Auswahl leeren" (GV-RED-1 abwählen = 2 Klicks statt N−1); (4) Gold-Lauf schreibt Zwischenstand JE FLOW (`_write_golden_progress`: total_turns, Aktivität „Flow i/n: <id> fertig (x/y Züge)", Teil-Transkripte; + Ansage vor der Judge-Phase) — vorher stand die Liste bis zum Finale auf „0 von N"; Lauf-Detail sagt bei laufendem Lauf „Noch keine Transkripte gespeichert" statt „gestorben"; (5) Pattern×Persona-Matrix (ALT-Auswertung) in Pattern-Nutzung, Zeilen/Spalten nach Turn-Summe; (6) Läufe-Tab: Lauf-Liste zuerst, beide Start-Formulare zugeklappt darunter (`<details>`). Fakes des Gold-Jobs folgen der neuen Je-Flow-Signatur (A4b). CI-Stand: Backend 4198 / Studio 999. |
| Review-Runde 3 | ✅ 2026-08-22 — dritter Pass über den GESAMTEN Eval-Bereich im Ist-Zustand (Backend `services/eval/*` + `api/eval.py` + `evals/run_golden.py`/`compare_golden.py`, Schwerpunkt Je-Flow-Fortschritt; Studio: alle 6 UI-Änderungen inkl. i18n beider Sprachen, `trend-chart.ts`, Lauf-Liste/-Detail; Stichprobe Lasttest-Engine-Feld): **0 Befunde** — Spec PASS, Security PASS, Correctness PASS, Performance PASS, Wartbarkeit PASS, Tests PASS. 4 NIT-Beobachtungen ohne Fix (bewusst): `by_pattern`/`by_intent` serverseitig weiter berechnet, aber vom Studio ungelesen (OpenAPI-Stabilität); `PatternUsage.pattern_id` als `string` typisiert obwohl SQL NULL liefern kann (Komponente wehrt überall mit `?? ''` ab); Skalen-Marken sitzen am Chart-Außenrand statt exakt auf der PAD-Linie (~6 px, Min/Max-Marken-Rahmung); `betriebsartOf` matcht per Präfix (Wertemenge maschinell fix). Beweise frisch: Backend 4198 passed/4 skipped (Exit 0, 2:35), Studio 999 passed (80 Dateien), ruff „All checks passed!". |
| NIT-Fix-Runde | ✅ 2026-08-22 — die 4 Beobachtungen aus Runde 3 auf Nutzer-Entscheid behoben: (1) `pattern_usage_stats` liefert nur noch `triples`/`total`/`scope` — die ungelesenen ALT-Aggregate `by_pattern`/`by_intent` samt zweier GROUP-BY-Queries entfernt (OpenAPI unverändert — die Route ist ein untypisiertes dict; PG-Test wacht jetzt über die ABWESENHEIT der Schlüssel); (2) `PatternUsage.triples`-Kennungen ehrlich `string \| null` (SQL-GROUP-BY über nullable Spalten), `betriebsartOf`/`id()` nehmen null; (3) `betriebsartOf` vergleicht den Kopf-Token EXAKT statt per Präfix („AGENTUR" ≠ agent; neuer Spec-Wächter mit EDGE-Fixture inkl. NULL-Triple — rot vor dem Fix); (4) Trends-Skalen-Marken absolut positioniert auf `calc(100% * 8/96)` bzw. `88/96` + `translateY(-50%)` — exakt auf den Plot-Linien bei JEDER Chart-Größe (der feste 2-px-Abstand saß bei der breiten, mitskalierenden Score-Kurve ~10 px daneben). Suiten: Backend 4198 passed/4 skipped (Exit 0), Studio 1000 passed (+1), ruff sauber, `export_openapi --check` unverändert; Backend neu gestartet, Endpunkt-Form (`scope/total/triples`) live verifiziert, Skalen im Browser sichtgeprüft. |
| Prod-Befund EVAL_CHAT_URL | ✅ 2026-08-22 — erster Eval-Start auf Prod brach im Preflight ab: „Chat-Backend nicht erreichbar unter http://localhost:8000/api/chat". Wurzel: `compose.prod.yml` reichte `EVAL_CHAT_URL` nur LEER durch (`${EVAL_CHAT_URL:-}`), der Code-Default zeigt auf ALT-Port 8000, das Prod-Image lauscht auf 8100 — die Eval-Funktion war im Container ohne Handarbeit in der Server-`.env` tot (der Preflight hat wie gebaut den Lauf verweigert statt 39 Züge zu verbrennen). Fix: BEIDE Compose-Dateien setzen jetzt den Container-Selbstaufruf `http://127.0.0.1:8100/api/chat` als Default (Prod: `${EVAL_CHAT_URL:-…}`, .env darf übersteuern; Dev: fest), neuer Wächter `test_eval_chat_url_hat_einen_container_tauglichen_default` in `test_deploy_compose.py` (rot vor dem Fix), Kommentar in `run_store.py` richtiggestellt. Sofort-Weg auf dem Server bis zum nächsten Deploy: `EVAL_CHAT_URL=http://127.0.0.1:8100/api/chat` in `deploy/.env` + `docker compose up -d backend`. Nebenbefund vom Screenshot: der Prod-Store hält noch die v1-Flows (GS-01…GS-12, 39 Züge) — der v2-Import (PUT `/api/config/data/eval/gold-flows`) steht dort weiter aus (Nutzer-Domäne). |
| Studio-Verdrahtungs-Review | ✅ 2026-08-22 — Nachprüfung aller Wege Studio→Backend (Anlass: Prod-Befund EVAL_CHAT_URL). Ergebnis: EINE HTTP-Schicht (`StudioApi`, `BASE = '/studio/api'`, relativ zur eigenen Origin), keine fetch/EventSource/WebSocket-Nebenwege, keine absoluten Hosts im Studio-Code (nur Doku-Beispiele `api.example.de`); Widget-Vorschau vorbildlich (`api-url = window.location.origin`, Element aus dem Workspace importiert, Widget-Fallback `'/api'` relativ, chat-api.ts:120); Downloads/Auth über dieselbe Basis. **1 Befund [MAJOR, Dev-only]:** `frontend/proxy.conf.json` zeigte 3× auf `localhost:8000`, das NEU-Dev-Backend läuft dokumentiert auf 8100 (backend/README, compose.dev — ALT belegt 8000) → jeder dokumentierte Dev-Weg (`npm start`/`start:studio`) lief gegen eine tote Tür (deshalb brauchte die Dev-Maschine einen Behelfs-Proxy). Gefixt auf 8100 + 2 stale README-Zeilen; neuer Wächter `dev-proxy.spec.ts` (JSON-Import, `resolveJsonModule` im Spec-tsconfig; rot vor dem Fix) — Gegenstück zum Compose-Wächter im Backend. Studio-Suite: 1001 passed (81 Dateien). |
| Abschlussmessung | offen (Nutzer): drei Läufe `--engine pattern|agent|hybrid` + `compare_golden` (§7); Entscheid GV-RED-1 beim ersten Echtlauf. Config-Stand: LOKAL hält der Store seit 2026-08-22 das v2-Set (Import über `PUT /api/config/data/eval/gold-flows` mit Hülle `{"data": …}` — normaler Studio-Schreibweg, mit History); auf STAGING nach dem Deploy noch nötig (gleicher PUT oder schmaler CLI-Baum `uv run boerdi import-config --from <baum>`, der NUR `eval/gold-flows.yaml` enthält). Das Seed-Panel deckt den Fall nicht: `missing` überspringt bestehende Bereiche, `exact` schreibt ALLE abweichenden. `GoldFlowsArea` nimmt v2 an (`extra="allow"`, `expect` frei, `version` ist `int`; fehlendes `persona` fällt auf `""`, und `golden_run` liest `zielgruppe or persona`) — geprüft 2026-08-22. |
