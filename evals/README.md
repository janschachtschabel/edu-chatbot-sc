# evals — Golden-Flow-Suite (Abnahme-Instrument, Spec §5.7)

12 deterministische Multi-Turn-Flows (GS-1…GS-12) mit harten Soll-Checks
(persona/intent/register/structure/qr; host soft). `gold-flows.yaml` ist die
unveränderte Kopie aus ALT (`badboerdi/backend/chatbots/wlo/v1/eval/gold-flows.yaml`)
— Flows nur dort UND hier synchron ändern, sonst ist der A/B-Vergleich (P11) wertlos.

## Läufe

```powershell
cd backend
uv run python ../evals/run_golden.py --only GS-1          # Smoke (1 Flow)
uv run python ../evals/run_golden.py --label ref-alt      # voller Lauf gegen ALT (:8000)
$env:EVAL_CHAT_URL="http://localhost:8100/api/chat"
uv run python ../evals/run_golden.py --label neu          # gegen NEU (Dev-Compose)
```

- Ziel-URL: `--url` oder `EVAL_CHAT_URL` (Default `http://localhost:8000/api/chat` = ALT lokal).
- Kopfzeilen: `EVAL_CHAT_HEADERS` als JSON-Objekt, geht an jeden Zug. Damit
  läuft **eine** Suite gegen **beide** Maschinen (der Umschalter ist eine
  Kopfzeile, A4a). Unlesbares JSON bricht mit Exit-Code 2 ab — ein stiller
  Rückfall wäre der teuerste Ausfall: man hielte einen Muster-Lauf für einen
  Agent-Lauf. Der Report nennt nur die **Namen** der Kopfzeilen, nie die Werte
  (eine davon kann die Zugangs-Kennung tragen).
- Latenz **je Zug** steht im Report (`golden_metrics.latency`: p50/p95/max) und
  in der Konsole. Die Gesamtdauer beantwortet „ist der Agent schneller" nicht:
  sie mischt 24-Sekunden-Suchen mit Sofortantworten.
- **`REPO_BASE_URL` muss dem Repo des Ziel-Backends entsprechen** (z. B.
  `https://repository.staging.openeduhub.net` bei Staging-Config), sonst
  schlägt der Soft-Check `host` systematisch fehl. In ALT lief der Runner
  im Backend-Prozess und teilte dessen Env — standalone ist das Operator-Pflicht.
  Welches Repositorium das Ziel-Backend tatsächlich führt, muss man dabei nicht
  raten: `curl <ziel>/api/health` nennt es im Feld `repo`. Es kann aus der
  Konfiguration kommen (Studio → Karten-Pipeline → `repo_base_url`) statt aus
  der Env des Backends — dann gilt der Konfig-Wert.
- Report: JSON unter `evals/reports/golden-<utc>-<label>.json` (Scorecard
  `golden_metrics` + volle Konversationen). Exit-Code 0 = alle harten Checks bestanden.
- Kostenhinweis: 12 Flows ≈ 40 LLM-Turns — **volle Läufe startet der Nutzer**
  (CLAUDE.md); Paket-Gates ab P4 nutzen die dort genannte Teilmenge.
- LLM-Judge + eval_runs-Persistenz sind absichtlich NICHT hier: das ist der
  Backend-Eval-API (P7). Dieser Runner ist die framework-freie CLI für
  Referenz-/A/B-Läufe (P11).
  Seit C3 gibt es die weiche Ebene wirklich, in `services/eval/golden.py` — sie
  liest genau die Turn-Felder, die `run_flows` hier aufzeichnet (`debug` als
  Teilmenge via `flatten_debug`, `expected_persona`/`expected_intent`,
  `cards_count`, `response_length`). Wer diese Form ändert, muss dort
  nachziehen; die Tests in `backend/tests/test_golden_runner.py` nageln sie fest.

## A/B-Vergleich (P11, §9-Schritt 4)

Zwei Reports vergleichen — was tut NEU anders als ALT, pro Flow und pro Turn:

```powershell
cd backend
uv run python ../evals/compare_golden.py `
    --ref ../evals/reports/golden-<utc>-ref-alt.json `
    --new ../evals/reports/golden-<utc>-neu.json --label cutover
```

- Report: `evals/reports/ab-<utc>-<label>.json`. Exit-Code 1 = harte Regression,
  Fehl-Turn in NEU oder Strukturbruch (Flow/Turn nur auf einer Seite).
- Verglichen werden Check-Ergebnisse, Klassifikation (persona/intent/pattern) und
  Struktur (cards/idocs/qr). **Nicht** verglichen werden Wortlaut, Textlänge und
  Sie/du-Zähler: die weichen bei jedem LLM-Lauf ab und würden die eine echte
  Abweichung im Rauschen begraben. Für die Stichproben-Redaktion trägt der
  JSON-Report beide Wortlaute an jedem abweichenden Turn mit.
- `host` bleibt weich wie im Runner — wird gemeldet, blockiert nicht.
- Beide Läufe müssen dieselbe `gold-flows.yaml` gefahren haben; sonst meldet der
  Vergleich den Strukturbruch, statt ihn stillschweigend wegzumitteln.

### Muster-Engine gegen Agent-Modus (A5)

```powershell
cd backend
uv run python ../evals/run_golden.py --label pattern
$env:EVAL_CHAT_HEADERS='{"X-Boerdi-Engine":"agent"}'
uv run python ../evals/run_golden.py --label agent
Remove-Item Env:\EVAL_CHAT_HEADERS
uv run python ../evals/compare_golden.py `
    --ref ../evals/reports/golden-<utc>-pattern.json `
    --new ../evals/reports/golden-<utc>-agent.json `
    --ignore-classification --label engine-ab
```

`--ignore-classification` nimmt Persona, Intent und Muster aus dem Vergleich:
der Agent klassifiziert nicht und wählt kein Muster, diese drei weichen dort an
fast jedem Zug ab — von Bauart wegen, nicht als Befund. Übrig bleibt, worum es
geht: Register, Struktur, Quick-Replies, Host — und die Latenz. Für den
ALT↔NEU-Vergleich bleibt die Flagge **aus**, denn dort ist eine andere
Klassifikation sehr wohl ein Befund. Der Report trägt `ignore_classification`
mit, damit ihm anzusehen ist, dass gefiltert wurde.
