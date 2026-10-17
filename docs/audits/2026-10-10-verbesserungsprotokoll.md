# Verbesserungsprotokoll — boerdi-chat (Antwortzeit, Qualität, Parallelisierung, Funktionen)

**Datum:** 2026-10-10 · Begleitdokument zu [`2026-10-10-fehlerprotokoll.md`](2026-10-10-fehlerprotokoll.md).
Nur Vorschläge, kein Code geändert. Gewinn-Angaben sind **Schätzungen** aus dem Code-Pfad und müssen
vor der Umsetzung gemessen werden (Jaeger-Spans, `quality_logs`, Lasttest). Aufwand: **S** < ½ Tag,
**M** 1–3 Tage, **L** > 3 Tage.

---

## 1. Antwortzeit (Latenz)

| # | Vorschlag | Stelle | Geschätzter Gewinn | Aufwand |
|---|---|---|---|---|
| A-1 | **Klassifikator-Frist** (8–10 s) mit Fallback statt 75 s × Retries | [`classify.py:116`](../../backend/src/boerdi/services/classify.py#L116) | Hänger-Fälle von Minuten auf Sekunden | S |
| A-2 | **Prompt-Caching beim Klassifikator:** statischer Systemteil zuerst, dynamischer Kontext zuletzt (teilweise umgesetzt, Seitenblock steht noch vor dem Verlauf). Cache-Trefferquote je Anbieter messen | [`classify.py:84-99`](../../backend/src/boerdi/services/classify.py#L84-L99) | 20–40 % weniger TTFT bei Anbietern mit Prefix-Cache | S |
| A-3 | **httpx-Client-Pool für MCP** je (Server-URL, Aufrufer-Fingerprint); die MCP-Session pro Aufruf bleibt, aber TCP/TLS wird wiederverwendet | [`mcp/transport.py`](../../backend/src/boerdi/services/mcp/transport.py) | 50–200 ms je Cache-Miss | M |
| A-4 | **Spekulative Suche bei M16 abbrechen** statt abwarten | [`respond.py:161-168`](../../backend/src/boerdi/graph/nodes/respond.py#L161-L168) | ein MCP-Roundtrip (≈ 0,3–1,5 s) im M16-Zug | S |
| A-5 | **Seitenkontext-Auflösung parallel zu `assess`** (nur bei Nicht-Ping; Ping bleibt vorgelagert) | `graph/nodes/page_context_enrich.py` | kalt bis 4–7 s, warm ≈ 0 | M |
| A-6 | `resolve_page_context` und `_bestand_anhaengen` per `gather`, wenn die `collection_id` bekannt ist | `page_context_enrich.py` | 0,3–2 s kalt | S |
| A-7 | `master_skill.prompt_block` und `resolve_prefetch` im Agent-Zug parallel | `graph/nodes/respond_agent.py:192,261` | 0,3–1,5 s | S |
| A-8 | **Query-Embedding-LRU** (z. B. 512 Einträge, TTL 1 h) — gleiche Fragen, Quick-Replies und Golden-Flows treffen oft | [`rag/embed.py:47`](../../backend/src/boerdi/services/rag/embed.py#L47) | 0,3–1 s bei Wiederholungen | S |
| A-9 | **Rerank-Kandidaten auf ≈ 1000 Zeichen kürzen** vor dem Cross-Encoder | [`rag/rerank.py:325`](../../backend/src/boerdi/services/rag/rerank.py#L325) | deutlich weniger CPU je Zug (Qualität vorher A/B-messen) | S |
| A-10 | **Persist bündeln:** `update_session`, `save_message`, `finalize_message` und Quality-Log in einer Transaktion (flush statt commit dazwischen) | `graph/nodes/persist.py`, `services/turn_persist.py` | 3–4 DB-Roundtrips je Zug (5–20 ms; mehr bei entfernter DB) | M |
| A-11 | **SSE-Abbruch früher erkennen** (`request.is_disconnected()` alle N `text_delta`), um `/api/agent` und Streams ohne Zuhörer zu stoppen | [`api/sse.py:180`](../../backend/src/boerdi/api/sse.py#L180) | spart LLM-Kosten und Slots bei Abbrüchen | S |
| A-12 | **Begrüßung sofort rendern**, Kontextgruß nachschieben; Eingabe während einer Antwort offen lassen und die nächste Nachricht vormerken | `ui/src/shell/lifecycle.ts:301-317`, `send-message.ts:125` | gefühlte Wartezeit deutlich kürzer | M |
| A-13 | **Skeleton/Teiltext ab `connected`**-Event statt erst ab dem ersten `text_delta` | `ui/src/shell/send-message.ts:189-205` | gefühlte TTFB | S |

## 2. Parallelisierung

| # | Vorschlag | Stelle | Gewinn | Aufwand |
|---|---|---|---|---|
| P-1 | **Unabhängige MCP-Tool-Calls einer LLM-Runde per `asyncio.gather`** — das Diagnose-Log zeigt die Kandidaten schon. Schreib-Tools und Aufrufe mit Reihenfolge-Abhängigkeit bleiben seriell; Cards in Originalreihenfolge zusammenführen | [`tool_loop.py:366-386`](../../backend/src/boerdi/services/tool_loop.py#L366-L386) | bei 2–3 Calls: Summe → Maximum (≈ 1–3 s) | M |
| P-2 | **Single-Flight für identische MCP-Cache-Misses** (gleicher Key → ein Aufruf, die anderen warten auf dessen Future) | [`mcp/client.py:316-340`](../../backend/src/boerdi/services/mcp/client.py#L316-L340) | weniger Last bei Spitzen (Kampagnen, Golden-Runs) | S |
| P-3 | **RAG über mehrere Bereiche in einer SQL** (`area = ANY(:areas)` + `ROW_NUMBER() OVER (PARTITION BY area)`) statt seriell pro Bereich | [`rag/retrieval.py:217-220`](../../backend/src/boerdi/services/rag/retrieval.py#L217-L220) | 10–50 ms je Bereich | S |
| P-4 | **Ingest-Embeddings im Stapel** (64 Texte je Request) statt eines Requests je Chunk | [`rag/embed.py:93-125`](../../backend/src/boerdi/services/rag/embed.py#L93-L125) | 5–20× schnellerer Import, weniger 429 | S–M |
| P-5 | **CE-Gate je Target parallel** über den Rerank-Pool (wenn > 1 Worker) | `graph/nodes/respond.py:331-344` | 0,2–0,5 s je weiterer Liste | S |
| P-6 | **Heuristischer Vorabruf parallel zur Klassifikation**, nur bei eindeutiger Suchabsicht (Materialtyp + Fach erkannt) | `graph/nodes/merge.py`, `services/prefetch.py` | bis ≈ 1 s | L (Risiko: falscher Intent verändert den MCP-Zustand, siehe `prefetch.py:73-81`) |
| P-7 | **DB-Pool konfigurierbar** (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) passend zu `LLM_MAX_CONCURRENCY` | [`db/session.py:19-30`](../../backend/src/boerdi/db/session.py#L19-L30) | Voraussetzung, damit P-1…P-6 unter Last wirken | S |

## 3. Qualität

| # | Vorschlag | Nutzen | Aufwand |
|---|---|---|---|
| Q-1 | **Golden-Flows als CI-Job** (`evals/run_golden.py` + `compare_golden.py`) gegen eine gespeicherte Baseline, nachts oder per Label; Gate auf Regressionen (letzter Lauf: 2026-09-27) | Regressionen fallen vor dem Deploy auf | M |
| Q-2 | **LLM-as-Judge-Trend:** Stichprobe echter Züge täglich bewerten (Relevanz, Faktentreue zu Tool-Ergebnissen, Sprache, Länge), Trend im Studio | messbare Antwortqualität statt Einzelfälle | M |
| Q-3 | **RAG-Recall-Messung:** kleiner Goldsatz Frage → erwarteter Chunk; prüft M-3 (HNSW-Filter) und A-9 (Kürzen) objektiv | belastbare Retrieval-Entscheidungen | S–M |
| Q-4 | **Hybrid-Retrieval** (pgvector + `tsvector` BM25-artig, Reciprocal Rank Fusion), gut für Eigennamen, Fächer und Abkürzungen | bessere Treffer bei Fachbegriffen | M |
| Q-5 | **Fallback-Zähler sichtbar machen:** Klassifikator-Salvage, MCP-Timeouts, leere Suche, Moderation fail-open als Kennzahlen im Studio-Dashboard | Qualitätseinbrüche früh erkennen | S |
| Q-6 | **Antwort-Feedback** (👍/👎 + optionaler Grund) je Bot-Blase → `quality_logs`; fließt in Q-2 und in die Pattern-Pflege | direkte Nutzerstimme | M |
| Q-7 | **Coverage-Untergrenzen** je Projekt (Widget zuerst) und **Ratchet** für die 300-Zeilen-Regel in der CI | Wartbarkeit hält sich selbst | S |
| Q-8 | **Flaky-Quarantäne** für Playwright (Retry-Statistik, separates Label) | stabile CI | S |
| Q-9 | **Breite `except` abbauen** (207× `BLE001`, 10× `S110`): wo Fehler nur geschluckt werden, mindestens `debug`-Log und ein Zähler | weniger „stille“ Fehler wie M-1 | M (schrittweise) |

## 4. Funktionen, die gut passen würden

| # | Funktion | Begründung / Andockpunkt | Aufwand |
|---|---|---|---|
| F-1 | **Stopp-Knopf** während des Streams (sauberer Abbruch inkl. Backend-Cancel über A-11) | Standard in Chat-UIs; spart Kosten | S–M |
| F-2 | **Sichere Sitzungsübergabe** per Einmal-Ticket statt roher `bsid` (löst H-1) | Cross-TLD-Handoff bleibt, Datenschutz besser | M |
| F-3 | **Quellen-/Belegansicht:** pro Antwort „Woher stammt das?“ (MCP-Treffer, RAG-Abschnitte mit Bereich) aufklappbar | Vertrauen; Lehrkräfte wollen prüfen | M |
| F-4 | **Merkliste / Export:** Karten sammeln und als Liste/PDF exportieren oder in eine WLO-Sammlung schreiben (Schreib-Tools gibt es schon) | passt zum Kurations-Weg | M |
| F-5 | **Verlauf löschen durch die Person** (Self-Service, DSGVO Art. 17) direkt im Widget; Backend-Funktion `delete_session` existiert | Datenschutz-Komfort | S |
| F-6 | **Folgefragen-Vorschläge aus Treffern** (Facetten: Bildungsstufe, Materialtyp) als Quick-Replies, aus `_queryMeta` gespeist | schnellere Verfeinerung der Suche | S–M |
| F-7 | **Barrierefreiheits-Modus**: einfache Sprache auf Wunsch (Schalter → Prompt-Block), Vorlesen pro Blase (Speech-API vorhanden) | Zielgruppe Schule | S–M |
| F-8 | **Admin-Replay:** einen Zug aus dem Verlauf mit anderer Konfiguration/Engine im Studio erneut ausführen (Diff der Antworten) | Pattern-Pflege und Fehlersuche | M |
| F-9 | **Semantic Answer Cache** für häufige, kontextfreie Fragen (Embedding-Ähnlichkeit > 0,95 + gleiche Seite/Sprache) mit kurzer TTL | Latenz und Kosten bei FAQ-Fragen | M (Risiko: veraltete Antworten) |

---

## Empfohlene Reihenfolge (größter Effekt pro Aufwand)
1. A-1, A-4, P-2, P-7, A-11: alle S, verringern Hänger und Leerlauf.
2. P-1 (gather im Tool-Loop) und A-3 (MCP-Keep-alive): größter messbarer Latenzgewinn.
3. Q-1 + Q-3 + Q-5: Messbarkeit herstellen, **bevor** Q-4/A-9/P-6 die Qualität verändern.
4. A-12/A-13 + F-1: spürbar schnellere UX im Widget.
5. F-2 zusammen mit dem Fix für H-1.
