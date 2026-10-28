# Follow-up to the disruption audit — what was fixed and what was not

**Date:** 2026-10-28 · **Applies to:** the audit "Bot disruptions and general observations" plus
"Specific code suggestions" (undated, received October 2026) · **Code state:** `main` after this
change (branch `audit-18ab`).

Thank you for the audit. Every point was checked against the current code. Some points had
already been fixed, because the audit describes a slightly older state (about late September). The
rest is either fixed in this change (packages **18A** and **18B**) or planned in packages
**18C–18F**, which are described at the end.

Legend: ✅ fixed in this change · ◐ partly fixed · ✔ fixed earlier · ⏳ planned (package) ·
➖ accepted, not changed

## 1 Disruption tests

| Audit point | Status | What changed / why not |
|---|---|---|
| No readiness check; a replica without Postgres keeps getting traffic | ✔ | `/ready` (internal port 8101) checks Postgres; the container health check uses it. The compose default is now 1 replica. |
| Retries on authentication errors (`num_retries=2`) | ✔ | Removed. The SDK does not retry a 401. |
| Moderation fails silently; the safety service does not notice | ✅ 18A | See §3. |
| Log does not say that the LLM key is the cause of a 401 | ⏳ 18F | A clear log line ("provider rejects the key: provider, route"), rate-limited. |
| Error class shown to the user ("gaierror", "AuthenticationError", "InternalServerError") | ⏳ 18D | One translated message with a short error number (trace ID). Class and message only go to the log. The raw LiteLLM text from the audit ("Fehler bei der Verarbeitung: litellm…") was already removed earlier. |
| Several calls hit the same dead endpoint (circuit breaker) | ⏳ later | Costs latency only in the failure case. |
| "Worksheet **or** interactive material" returns only one type | ✅ 18B | See §4. |
| Type-focus rewrites the answer; search link filters only one type | ✅ 18B | The label and the search link now name and filter **all** requested types. The rewrite itself stays by design: it stops sentences like "here are matching videos" while the items sit behind the search link, which now shows both types. With the search down there are no content cards, and since mid-October the model's own answer ("search not reachable") is then kept. |
| Anti-hallucination watchdog crashes (`'list' object has no attribute 'strip'`) | ✅ 18B | Entities can arrive as lists. They are now normalised, and the watchdog tolerates lists. |
| "Do you see this test message?" → `medientyp='quiz'` | ◐ 18B | Short keywords (`test`, `spiel`, `kurs`) now count only at the end of a word: "Klassentest" and "Onlinekurs" still count; "testen", "Testnachricht", "Protest", "Beispiel" and "Exkurs" no longer do. Your English example still gives `quiz`: "Test" is also the German word for an exam, and we did not want to lose "Hast du einen Test zu Brüchen?". |
| Closing the browser mid-response | ➖ | Nothing to fix (your result). |

## 2 Code suggestions

| File / place | Status | Note |
|---|---|---|
| `api/chat.py` — fallback `save_message` swallowed | ✔ | Logs at debug with stack trace. |
| `services/mcp/tool_args.py` — second validation error swallowed | ✅ 18B | Now logged at warning, **without input values** (only location and error type). The raw arguments still pass through on purpose (fail-open): the MCP server validates again and returns an error the model can read. |
| `graph/nodes/respond.py` (3×), `obs/tasks.py` `cancel_and_drain` — cancel + await swallows everything, no timeout | ⏳ 18E | One helper for "cancel and wait": it passes on our own cancellation, logs unexpected errors and has a time limit. |
| `domain/guide_mode.py`, `domain/cards/links.py`, `services/rag/retrieval.py`, `services/page_context.py`, `services/response_prompt_tools_text.py`, `services/turn_links.py` (QueryMeta loop) | ⏳ 18E | Log at debug or warning; narrow the caught exception where possible. A full scan found 124 such handlers: 87 are fine, 30 should log, 7 hide real risks (e.g. an invalid value silently turns the rate limit off). |
| Bot text, quick replies and user text in logs (`turn_links.py`, `turn_persist.py`, `widget_postprocess.py`) | ⏳ 18C | Larger than reported: about 55 places in 22 files. Rule from now on: never content at INFO or above; at DEBUG only with `LOG_CONTENT=true`. A test will check all logger calls. Already done here: the "test message" log line in `merge.py` no longer contains the message. |

## 3 Moderation outage (18A)

- **Visible:** the decision now records failed stages (`stages_failed`, reason
  `moderation_unavailable`). Missing credentials give one warning per process; the warm-up at start
  reports the outage instead of success. New counter `boerdi_safety_stage_total{stage,outcome}`.
- **No more "checked" without a check:** a risk is only downgraded when every stage that ran
  actually checked. This now also covers the LLM legal check, which failed just as silently. Both
  stages are counted (`stage="openai_moderation"` and `stage="llm_legal"`).
- **Switch `MODERATION_BEI_AUSFALL`:** `offen` (default) answers and makes the outage visible as
  above. `geschlossen` replies with a friendly refusal for as long as moderation is down — in the
  chat, for direct actions and at `/api/agent`. Recommended for school use. The start warns about an
  unknown value (e.g. `closed`) and about `geschlossen` without any moderation access. Documented in
  `deploy/README.md`.
- **Long messages:** they were moderated only up to character 4000. Now in overlapping sections,
  in one call. Above about 30 000 characters the start and the end are checked, and the turn is
  marked as only partly checked (`moderation_partial`; `geschlossen` refuses it).
- **Also fixed:** a cancelled check or an incomplete answer no longer passes as a result. If the
  whole safety check fails, the regex-only fallback is marked as unmoderated. `search_wlo_all` is
  now blocked in crisis turns like the other search tools. Refused turns appear in the evaluation.
- **Unchanged:** the regex gate always runs, also when moderation is down.

## 4 Several media types (18B)

- Entities are normalised: `medientyp` keeps the first value, `medientypen` holds all of them.
  If a message names types, only those count; the list does not grow over a conversation.
- A filter list for the search tools is split into single calls (at most 3) inside the MCP client.
  Results are merged and de-duplicated by `nodeId`; the server's notices after the result stay.
  If one of the calls fails, the model is told which type is missing. A list with one value is
  unwrapped. The tool descriptions and the prompt rule say "one type per call".
- Label: "Arbeitsblätter oder interaktive Medien". The search link filters all types.

## 5 Also found while checking (not in the audit)

| Finding | Status |
|---|---|
| The debug block of every chat response reaches every client (error texts, model and tool names) | ⏳ 18D — only with Studio login or an approved debug switch |
| The canvas shows the provider's raw error text in the generated material | ⏳ 18D |
| Waiting for an LLM slot has no time limit; a hanging provider fills a replica | ⏳ 18F — limit (about 30 s), then a friendly "busy" message |
| Outer rate limit is 20/min per IP (too tight behind a school NAT); 429 looks like a generic error in the widget | ⏳ 18F — 120/min per IP, own 429 message |
| Anonymous users have the same agent limits as logged-in users (no cost cap) | ➖ for now — the cost of an anonymous turn will be measured first |
| The session ID comes from the client; whoever knows it can read and continue the chat | ➖ known and accepted; write actions are bound to the logged-in person |
| The legal check sees only the first 2000 characters of a message | ⏳ noted, not yet planned |

## 6 How to check

- Backend tests: `test_safety_ausfall.py` (28), `test_mehrere_medientypen.py` (49), plus additions in
  the preflight, graph, assess, agent gate, merge, prefetch and tool loop tests. Full backend suite
  green. An independent review of this change found 4 major and 9 minor points; all are fixed
  except the answer rewrite, which we kept on purpose (§1).
- Moderation outage by hand: set a wrong key or a dead endpoint for moderation, then send a message.
  With `MODERATION_BEI_AUSFALL=offen` the log shows "moderation skipped …" and the counter
  `boerdi_safety_stage_total{stage="openai_moderation",outcome="fehler"}` rises
  (`keine_zugangsdaten` when no key is configured at all). With `geschlossen` the bot refuses
  politely.
- Several types: ask for "Arbeitsblatt oder interaktives Material zum Klimawandel". The log shows two
  `search_wlo_content` calls without a `-32602` error, and the search link carries both filters.

## 7 Useful next tests (live only)

These need a running system and fit the method of your audit (break something, observe, note):

1. Moderation down, then the test sentences from `evals/moderation_messung.py`: how much does the
   regex gate catch alone?
2. Prompt injection hidden in the full text of a material or in page text.
3. Slow instead of dead services (10/30/60 s delay, e.g. toxiproxy), with more than 20 parallel turns.
4. A small load test over HTTP/SSE through Traefik.
