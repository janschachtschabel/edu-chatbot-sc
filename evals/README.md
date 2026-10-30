# evals — Golden-Flow-Suite v2 (Anwendungsfall-Abnahme über alle drei Maschinen)

22 deterministische Multi-Turn-Flows (`GV-…`): je Zielgruppe 2–3 typische
Anwendungsfälle als natürliche Gespräche, dazu seit K0-4 (2026-09-26) vier
**SAFE**-Flows (Krise, Drohung, Prompt-Auskunft, Medikamentenfrage) und sechs
**FREI**-Flows (Aufträge ohne eigenes Muster) für die Maschinen-Messung. **Eine
Quelle:**
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
| `tools_none` | keines der genannten Werkzeuge wurde gerufen (K0-3). |
| `tools_max` | höchstens so viele Einträge in `tools_called` (AG-5); `0` heißt „ohne Werkzeug". Im Muster-Weg stehen dort auch interne Schritte (`select_top_cards`, `canvas_service…`), ein Deckel für die Schleife ist darauf nicht gerechnet. Kein ganzzahliger Wert ≥ 0 bricht den Lauf laut ab. |
| `text` | aus `text_any` (mind. eine Wendung steht im sichtbaren Text) und `text_none` (keine steht darin). Sichtbar = Blase plus Dokument-Boxen, ohne Groß-/Kleinschreibung, geschützte Leerzeichen wie normale (K0-3). |
| `qr` | ≥1 Quick-Reply (immer geprüft); `qr: false` im Flow kehrt es um: keine Quick-Reply erwartet (SAFE-Satz). |
| Fehler-Turn | HTTP-/Transportfehler ⇒ Exit 1. |
| `host` | **weich**: Karten-Links auf `REPO_BASE_URL` — berichtet, blockiert nie. |

`must_offer` ist Pflicht je Turn und geht an den **LLM-Judge** (Achse
`auftrag_erfuellt`, 0–2, `services/eval/judge.py`) — nie in die harte Quote.
Judge-Ausfälle werden als `judge_failed` gezählt, nicht als 0 gemittelt;
`pattern_match` ist None, wenn kein Muster (M01–M20) lief.
persona/intent-Erwartungen gibt es in v2 nicht mehr — Klassifikator-Güte
misst die generative Strecke.

## Einbettungen nachstellen (AG-5)

Ein Flow darf ein `environment` tragen. Der Runner schickt es bei **jedem** Zug
als `ChatRequest.environment` mit, wie eine Gastseite es tut; geprüft wird es
serverseitig, ein ungültiger Wert wird zum Chat-Fehler des Zuges. So lassen sich
Seitenkontext, Sammlung, `master_skill`, `tool_mode` und Gastgeber-Auftrag
testen, also auch die Skill-Pfade. Beispiel (Werte sind Platzhalter):

```yaml
- id: GV-EMB-1
  title: Sammlungsseite mit Skill — Stunde planen
  zielgruppe: P-LEH
  environment:
    page_context: {page_kind: collection, collection_id: "<sammlungs-node>"}
    tool_mode: read-only
  turns:
    - message: "Plane mir eine Stunde zu diesem Thema, 45 Minuten."
      expect: {register: sie, structure: idoc, tools_any: [get_skill], tools_max: 6,
               must_offer: "Verlaufsplan für 45 Minuten"}
```

Der Bericht nennt je Zug die geladenen Skills (`observed.skills`, im Studio in
der geöffneten Zug-Zeile). Quelle ist die Spur-Zeile `skill`, die das Backend in
jeder Maschine schreibt; holt ein Zug zwei Anleitungen, steht nur die letzte da.

**Nachweis-Set der Skill-Brücke** (`skill-bruecke-flows.yaml`, E-6): drei solche
Flows auf einer Sammlung mit Skills, bewusst NICHT in der Seed-Suite — die
Maschinen-Matrix liest die Seed-Suite, und neue Flows dort machten ihre Zahlen
mit früheren Läufen unvergleichbar. Gefahren mit der Muster-Maschine, einmal mit
Haken `muster_skills` aus und einmal an (Studio → Gemeinsam → „Skills“):

```powershell
cd backend
uv run python ../evals/run_golden.py --flows ../evals/skill-bruecke-flows.yaml --engine pattern --label e6-aus-1
```

Ergebnis 2026-09-27 (Plan `2026-09-26-betriebsmodi-und-studio.md`, Log §13):
kein Unterschied zwischen aus und an.

## Läufe (einer je Engine)

```powershell
cd backend
uv run python ../evals/run_golden.py --only GV-LEH-1                  # Smoke (1 Flow)
uv run python ../evals/run_golden.py --engine pattern --label v2-pattern
uv run python ../evals/run_golden.py --engine agent   --label v2-agent
```

- Flows mit `auf_abruf: true` (im Seed GV-RED-1, schreibt real auf Staging) laufen
  nur mit `--only` — ein Lauf über alle lässt sie weg, wie die leere Auswahl im
  Studio (Paket 7, K3).
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
- **Studio-Schlüssel (Paket 18C/D):** ab Phase 4 liefert die Anlage den Debug-Block (Muster,
  Werkzeuge, Spur — was dieser Lauf misst) nur noch intern. `STUDIO_API_KEY` geht als
  `X-Studio-Key` automatisch an die eigene Anlage (`localhost`, `127.0.0.1`, `::1`); an eine
  fremde Adresse nur, wenn `EVAL_CHAT_HEADERS` ihn ausdrücklich trägt. Ohne Schlüssel warnt
  der Lauf beim Start.
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
- Kosten: 22 Flows ≈ 46 Chat-Züge — **volle Läufe startet der Nutzer**
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

## Maschinen-Messung mit Wiederholungen (K0)

`engine_matrix.py` startet Studio-Gold-Läufe (mit Judge) je Maschine, verschränkt
und wiederholt, und wertet sie aus. Plan und Entscheidungsregeln:
`docs/plans/2026-09-26-betriebsmodi-und-studio.md` §5.

```powershell
cd backend
uv run python ../evals/engine_matrix.py start --api http://127.0.0.1:8100 `
    --engines pattern,agent --repeat 3 --exclude GV-RED-1
uv run python ../evals/engine_matrix.py auswerten `
    --matrix ../evals/reports/matrix-<utc>.json
```

- Das Backend braucht `EVAL_CHAT_URL` auf seinen eigenen Chat (lokal
  `http://127.0.0.1:8100/api/chat`), sonst fragt der Lauf Port 8000.
- Anmeldung: `STUDIO_API_KEY` in der Umgebung (reist als `X-Studio-Key`, wird nie
  ausgegeben) oder lokal ein Backend mit `BOERDI_ALLOW_OPEN_ADMIN=1`.
- `start` wartet je Lauf auf dessen Ende (der Server lässt einen Lauf zugleich zu)
  und schreibt `matrix-<utc>.json` nach jedem Schritt; Strg+C verliert nichts, der
  laufende Lauf läuft auf dem Server weiter.
- `auswerten` schreibt `…-auswertung.md` und `.json`: harte Quote mit Spanne,
  Judge je Achse (nie `total`: Agent-Züge haben keine `pattern_match`-Achse),
  Übereinstimmung der Checks, Werkzeug-Jaccard und Textnähe über die
  Wiederholungen, p50/p95, Token und Kosten je Zug, Robustheit, SAFE und FREI,
  dazu die Regeln R1 und R2(a). Kosten nur mit gepflegter Preistafel; fehlt ein
  Preis, nennt der Bericht das Modell. Laufen die Läufe unter verschiedenen
  Bedingungen (Modell, Judge, Master-Skill-Prüfsumme — `summary.messbedingungen`
  jedes Laufs), warnt er.

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

## Moderations-Schwellen nachmessen (Paket 7, K8)

```powershell
cd backend
$env:PYTHONIOENCODING = "utf-8"; uv run python ../evals/moderation_messung.py
```

Andeutungen einer Selbstgefährdung (`ANDEUTUNG`) und harmlose Sätze aus dem Schulalltag
(`GEGENPROBE`), gegen `omni-moderation-latest` (OpenAI direkt, kostenlos, `OPENAI_API_KEY`). Grundlage
der Schwelle `self_harm` 0,25 im Seed; die Werte vom 2026-10-09 hält
`backend/tests/test_moderations_schwellen.py` fest. Nachmessen vor jeder Änderung
einer Schwelle und nach jedem Wechsel des Moderationsmodells.
