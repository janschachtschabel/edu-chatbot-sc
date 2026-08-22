# evals — Golden-Flow-Suite v2 (Anwendungsfall-Abnahme über alle drei Maschinen)

12 deterministische Multi-Turn-Flows (`GV-…`), je Zielgruppe 2–3 typische
Anwendungsfälle als natürliche Gespräche. **Eine Quelle:**
`backend/seeds/eval/gold-flows.yaml` (Studio-editierbar über den Bereich
`eval/gold-flows`); die frühere Kopie in `evals/` ist seit GV2 gelöscht, der
Runner-Default zeigt auf die Seed-Datei. v1-Dateien (persona/intent-Checks)
weist der Runner mit Exit-Code 2 ab — deren Erwartungen beschreiben die Anlage
seit dem Engine-Umbau nicht mehr.

Plan + Begründung: `docs/plans/2026-08-22-golden-v2-anwendungsfaelle.md`.

## Was hart geprüft wird (deterministisch, engine-fair)

| Check | Regel |
|---|---|
| `register` | `sie` \| `du`. Ehrlich: misst die Heuristik nichts (neutral), zählt der Turn als „nicht messbar" (None), nicht als bestanden. |
| `structure` | `idoc` ⇒ ≥1 Dokument-Box, `cards` ⇒ ≥1 Karte — egal, ob Muster-Weiche oder `zeige_dokument` sie erzeugt hat. |
| `tools_any` | mind. eines der genannten Werkzeuge wurde gerufen (Namen vor dem ersten Leerzeichen). Bei je Maschine verschiedenen Namen steht die Vereinigung (`wissen_suchen` = Agent, `query_knowledge` = Muster). |
| `qr` | ≥1 Quick-Reply (immer geprüft). |
| Fehler-Turn | HTTP-/Transportfehler ⇒ Exit 1. |
| `host` | **weich**: Karten-Links auf `REPO_BASE_URL` — berichtet, blockiert nie. |

`must_offer` ist Pflicht je Turn und geht an den **LLM-Judge** (Achse
`auftrag_erfuellt`, 0–2, `services/eval/judge.py`) — nie in die harte Quote.
Judge-Ausfälle werden als `judge_failed` gezählt, nicht als 0 gemittelt;
`pattern_match` ist None, wenn kein Muster (M01–M20) lief.
persona/intent-Erwartungen gibt es in v2 nicht mehr — Klassifikator-Güte
misst die generative Strecke.

## Läufe (einer je Engine)

```powershell
cd backend
uv run python ../evals/run_golden.py --only GV-LEH-1                  # Smoke (1 Flow)
uv run python ../evals/run_golden.py --engine pattern --label v2-pattern
uv run python ../evals/run_golden.py --engine agent   --label v2-agent
uv run python ../evals/run_golden.py --engine hybrid  --label v2-hybrid
```

- `--engine` setzt `X-Boerdi-Engine` für jeden Zug und überschreibt einen
  Engine-Eintrag aus `EVAL_CHAT_HEADERS`; ohne Flag misst der Lauf die
  Server-Vorgabe (`engine: default` im Bericht). Der Bericht trägt die Engine
  als Top-Level-Feld — der A/B-Vergleich benennt damit beide Seiten.
- Ziel-URL: `--url` oder `EVAL_CHAT_URL` (Default `http://localhost:8000/api/chat`).
- Zug-Timeout: `EVAL_CHAT_TIMEOUT` in Sekunden (Default 120; gilt auch für den
  Backend-Lauf). Die alten 60 s verbuchten legitime Mehr-Runden-Züge der
  Schleifen-Maschinen als Chat-Fehler — asymmetrisch genau gegen die Engines,
  die der A/B-Lauf vergleicht. Unlesbare Werte brechen mit Exit 2 ab.
- Weitere Kopfzeilen: `EVAL_CHAT_HEADERS` als JSON-Objekt. Unlesbares JSON
  bricht mit Exit-Code 2 ab — ein stiller Rückfall wäre der teuerste Ausfall:
  man hielte einen Muster-Lauf für einen Agent-Lauf. Der Report nennt nur die
  **Namen** der Kopfzeilen, nie die Werte (eine davon kann die Zugangs-Kennung
  tragen).
- Latenz **je Zug** steht im Report (`golden_metrics.latency`: p50/p95/max) und
  in der Konsole — die Antwort auf „ist der Agent schneller".
- **`REPO_BASE_URL` muss dem Repo des Ziel-Backends entsprechen** (z. B.
  `https://repository.staging.openeduhub.net`), sonst schlägt der Soft-Check
  `host` systematisch fehl. `curl <ziel>/api/health` nennt das Repo im Feld
  `repo`; es kann auch aus der Studio-Konfiguration kommen (Karten-Pipeline →
  `repo_base_url`) statt aus der Env.
- Report: `evals/reports/golden-<utc>-<label>.json` (Scorecard `golden_metrics`
  + volle Konversationen). Exit-Code 0 = alle geprüften harten Checks bestanden;
  der Exit-Code sagt etwas über den Bot, nicht über das Messwerkzeug.
- Kosten: 12 Flows ≈ 33 Chat-Züge — **volle Läufe startet der Nutzer**
  (CLAUDE.md). Achtung `GV-RED-1`: der Bestätigungs-Turn legt beim Echtlauf
  REAL einen Datensatz auf dem Staging-Bestand an — wer das nicht will, lässt
  den Flow per Auswahl weg.
- LLM-Judge + eval_runs-Persistenz sind absichtlich NICHT hier, sondern in der
  Backend-Eval-API (`services/eval/golden*.py`); der Studio-Gold-Start nutzt
  denselben Runner per Pfad-Import und hat seit GV5 einen Engine-Wähler.
  Wer die Turn-Record-Form ändert (`debug`-Teilmenge via `flatten_debug`,
  `golden.expected.must_offer`, `cards_count`, `response_length`), muss dort
  nachziehen; `backend/tests/test_golden_runner.py` nagelt sie fest.
- Der **Studio-Lauf** liest die Flows aus dem Config-Store (`eval/gold-flows`),
  die CLI aus der Seed-Datei. Hält der Store noch das v1-Set, einmalig je
  Umgebung chirurgisch importieren: `uv run boerdi import-config --from <baum>`
  mit einem Baum, der NUR `eval/gold-flows.yaml` enthält (ein voller Import
  würde redaktionelle Studio-Stände zurückrollen). Das Seed-Panel deckt den
  Fall nicht ab: `missing` überspringt bestehende Bereiche, `exact` schreibt
  alle abweichenden. Erfolgskontrolle: der Bereich wandert im Panel-Diff von
  „abweichend" nach „gleich".

## A/B-Vergleich (auch über Engines)

```powershell
cd backend
uv run python ../evals/compare_golden.py `
    --ref ../evals/reports/golden-<utc>-v2-pattern.json `
    --new ../evals/reports/golden-<utc>-v2-agent.json --label engines
```

- Report: `evals/reports/ab-<utc>-<label>.json`, Kopf trägt
  `engine_ref`/`engine_new`. Exit-Code 1 = harte Regression, Fehl-Turn in NEU
  oder Strukturbruch (Flow/Turn nur auf einer Seite). **Ungleiche Engines sind
  der gewollte A/B-Fall, kein Fehler.**
- Verglichen werden Check-Ergebnisse und Antwort-Struktur (cards/idocs/qr).
  **Nicht** verglichen werden Wortlaut, Textlänge, Sie/du-Zähler — und seit v2
  auch die Mechanik (beobachtetes Muster, Werkzeugliste): die ist je Maschine
  von Bauart wegen anders; was davon zählt, behauptet der `tools_any`-Check.
  Das frühere `--ignore-classification` ist damit gegenstandslos und entfernt.
- Für die Stichproben-Redaktion trägt der JSON-Report beide Wortlaute an jedem
  abweichenden Turn mit; `host` bleibt weich.
- Beide Läufe müssen denselben Flow-Stand gefahren haben; sonst meldet der
  Vergleich den Strukturbruch, statt ihn stillschweigend wegzumitteln.
