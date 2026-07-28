# boerdi-chat backend

FastAPI + LangGraph, PostgreSQL 17 + pgvector. Managed with [uv](https://docs.astral.sh/uv/).

```powershell
uv sync            # create .venv + install (locked)
uv run pytest      # test suite
uv run ruff check  # lint
uv run uvicorn boerdi.main:app --reload --port 8100   # dev server
```

Spec: [../docs/plans/2026-07-10-boerdi-chat-neubau.md](../docs/plans/2026-07-10-boerdi-chat-neubau.md)

## Das Widget ausliefern (C4)

Eine Host-Seite bindet den Chatbot mit zwei Zeilen und ohne Schlüssel ein:

```html
<script src="https://api.example.org/widget/boerdi-widget.js" defer></script>
<boerdi-chat api-url="https://api.example.org"></boerdi-chat>
```

Das Backend braucht dafür **nur** den Pfad zum gebauten Bündel:

```powershell
cd ..\frontend; npm run build:widget          # → frontend/dist/widget/browser/main.js
$env:WIDGET_DIST_DIR = "..\frontend\dist\widget\browser"
uv run uvicorn boerdi.main:app --port 8100
```

Fehlt das Bündel, antwortet `/widget/boerdi-widget.js` mit **503** und nennt den
Build-Befehl — nicht mit 404, das schickt Suchende auf die Tippfehler-Fährte.

**Warum der stabile Pfad umleitet (Verbesserung V1):** `/widget/boerdi-widget.js`
bleibt die URL, die in jeder Host-Seite steht, liefert aber einen 302 auf
`/widget/boerdi-widget.<hash>.js`. Erst diese URL trägt den Inhalt — mit
`Cache-Control: immutable` und einem Jahr Gültigkeit, weil der Hash aus dem
Dateiinhalt kommt. Ein neuer Build erzeugt damit von selbst eine neue URL. Das
ersetzt ALTs `no-store` (jeder Seitenaufruf lud ~412 kB neu) und beendet die
Fehlerklasse „Studio neu, Widget alt", bei der ein gecachtes Bündel seine Config
überlebte. Der Redirect selbst wird nie gecacht, sonst zeigte er nach einem
Deploy weiter auf das alte Bündel.

Drei Demo-Seiten liegen unter `/widget/` (Standard), `/widget/inline`
(eingebettet) und `/widget/classic` (dasselbe mit
`inline-result-grouping="false"` — ein echtes A/B). Sie laden das Widget über den
stabilen Pfad, also genau wie eine fremde Seite. Die **vollständige
Attribut-Liste steht nicht dort**, sondern im Studio unter *Übersicht →
Architektur & Referenz*: die wird aus einer Quelle gepflegt, die ein Test gegen
das Element festnagelt, und eine zweite abgetippte Liste wäre die, die zuerst
veraltet (ALTs Demo-Seite listete 17 der 18 Attribute).

## Evaluation

Zwei Lauf-Arten, beide live, beide in derselben `eval_runs`-Tabelle:

- **Gold-Flow** (`POST /api/eval/runs/golden`) spielt geprüfte Abläufe aus
  `eval/gold-flows.yaml` gegen `EVAL_CHAT_URL` und prüft jeden Turn
  **programmatisch** — deterministisch und A/B-vergleichbar. Der Runner ist
  `evals/run_golden.py`: bewusst framework-frei, ohne Import aus `boerdi.*`,
  auch als CLI nutzbar. Mit `judge: true` legt `services/eval/golden.py` die
  weiche Ebene darüber (ein Judge-Aufruf je beantwortetem Turn, ~40 bei 12
  Flows). Die **Headline bleibt deterministisch**: `avg_score` ist die harte
  Bestehensquote, der Judge-Schnitt steht als `judge_avg` daneben — sonst
  zeigten Lauf-Liste und Scorecard verschiedene Zahlen für denselben Lauf.
- **Generativ** (`POST /api/eval/runs`) lässt ein LLM Szenarien erfinden, die
  Persona spielen und die Antworten bewerten. Der Motor liegt in
  `services/eval/` (`scenario_gen` → `runner` → `judge` → `metrics`);
  `eval_service` besitzt die Persistenz drumherum.

**Der generative Lauf kostet Geld**: pro Turn ein Chat-Aufruf plus ein
Judge-Aufruf, plus ein Simulator-Aufruf je Kombination. `POST /api/eval/estimate`
liefert vorher ein Band. Alles läuft über die **Hintergrund**-Concurrency
(`llm.chat_completion(background=True)`, Limit `BG_LLM_MAX_CONCURRENCY`) und kann
dem Live-Verkehr keine Slots wegnehmen.

`summary.classification_metrics` ist die einzige Quelle der fünf Serien von
`GET /api/eval/trends`. **Beide** Lauf-Arten schreiben es (C3 hat es für
Gold-Läufe nachgezogen); die Serien zu Pattern-Hint und Judge-Zustimmung
bleiben allerdings leer, solange der Lauf ohne Judge gestartet wurde.

Modelle: `EVAL_SIMULATOR_MODEL` / `EVAL_JUDGE_MODEL`, je Aufruf aus den Settings
aufgelöst. Ein **leerer** Wert fällt auf `gpt-4o-mini` zurück — docker-compose
reicht `${VAR:-}` durch, die Variable ist im Container also gesetzt aber leer,
und `model=""` würde der Provider mit HTTP 400 ablehnen.
