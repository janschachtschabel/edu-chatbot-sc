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
- **`REPO_BASE_URL` muss dem Repo des Ziel-Backends entsprechen** (z. B.
  `https://repository.staging.openeduhub.net` bei Staging-Config), sonst
  schlägt der Soft-Check `host` systematisch fehl. In ALT lief der Runner
  im Backend-Prozess und teilte dessen Env — standalone ist das Operator-Pflicht.
- Report: JSON unter `evals/reports/golden-<utc>-<label>.json` (Scorecard
  `golden_metrics` + volle Konversationen). Exit-Code 0 = alle harten Checks bestanden.
- Kostenhinweis: 12 Flows ≈ 40 LLM-Turns — **volle Läufe startet der Nutzer**
  (CLAUDE.md); Paket-Gates ab P4 nutzen die dort genannte Teilmenge.
- LLM-Judge + eval_runs-Persistenz sind absichtlich NICHT hier: das ist der
  Backend-Eval-API (P7). Dieser Runner ist die framework-freie CLI für
  Referenz-/A/B-Läufe (P11: `--label alt` vs `--label neu` Reports diffen).
  Seit C3 gibt es die weiche Ebene wirklich, in `services/eval/golden.py` — sie
  liest genau die Turn-Felder, die `run_flows` hier aufzeichnet (`debug` als
  Teilmenge via `flatten_debug`, `expected_persona`/`expected_intent`,
  `cards_count`, `response_length`). Wer diese Form ändert, muss dort
  nachziehen; die Tests in `backend/tests/test_golden_runner.py` nageln sie fest.
