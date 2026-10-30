# Follow-up to the disruption audit — what was fixed and what was not

**Date:** 2026-10-28 · **Applies to:** the audit "Bot disruptions and general observations" plus
"Specific code suggestions" (undated, received October 2026) · **Code state:** `main` after this
change (branch `audit-18ab`).

Thank you for the audit. Every point was checked against the current code. Some points had
already been fixed, because the audit describes a slightly older state (about late September). The
rest is either fixed in this change (packages **18A** and **18B**) or planned in packages
**18C–18F**, which are described at the end.

**Update 2026-10-30:** packages **18C and 18D** are done (four pull requests, see
`docs/aenderungen/2026-10-29-*` and `2026-10-30-*`). Their rows below now say ✅ 18C/18D.
Package **18E** is done as well (two pull requests, `docs/aenderungen/2026-10-30-paket-18e-*`);
its rows say ✅ 18E. Package **18F** closes the list (`docs/aenderungen/2026-10-30-paket-18f.md`).

Legend: ✅ fixed in this change · ◐ partly fixed · ✔ fixed earlier · ⏳ planned (package) ·
➖ accepted, not changed

## 1 Disruption tests

| Audit point | Status | What changed / why not |
|---|---|---|
| No readiness check; a replica without Postgres keeps getting traffic | ✔ | `/ready` (internal port 8101) checks Postgres; the container health check uses it. The compose default is now 1 replica. |
| Retries on authentication errors (`num_retries=2`) | ✔ | Removed. The SDK does not retry a 401. |
| Moderation fails silently; the safety service does not notice | ✅ 18A | See §3. |
| Log does not say that the LLM key is the cause of a 401 | ✅ 18F | One place sees every model call (chat, embedding, classifier, stream): a 401 gives one line per minute with provider, route and the key's source (own key → ERROR, a key passed on by the proxy → WARNING), never the key or the provider's text; counter `boerdi_llm_schluessel_abgelehnt_total` and an alert rule for the own key. A 401 wrapped by the classifier library is recognised too. |
| Error class shown to the user ("gaierror", "AuthenticationError", "InternalServerError") | ✅ 18D | One translated message ending in an error number ("Fehlernummer: …", the first 12 characters of the trace ID) — also in the stream's error frame and in the widget. The Studio finds the turn by that number (page "Gespräche"). Class and message only go to the log. The raw LiteLLM text from the audit ("Fehler bei der Verarbeitung: litellm…") was already removed earlier. |
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
| `graph/nodes/respond.py` (3×), `obs/tasks.py` `cancel_and_drain` — cancel + await swallows everything, no timeout | ✅ 18E | One helper for "cancel and wait" (`cancel_and_drain`, 5 s): our own cancellation reaches the caller, a task that ignores the cancel holds it up for at most the limit (warning), errors of the tasks go to debug with their type. It replaces all copies, including the stream, the session lock and shutdown. |
| `domain/guide_mode.py`, `domain/cards/links.py`, `services/rag/retrieval.py`, `services/page_context.py`, `services/response_prompt_tools_text.py`, `services/turn_links.py` (QueryMeta loop) | ✅ 18E | A new scan found 133 silent handlers. 7 hid real risks and are fixed (e.g. an invalid value silently turned a rate-limit window off, an invalid policy pattern dropped its rule, a broken header was saved as empty). 18 now log — a rate-limited warning where a fallback hides Studio settings or skews a result, debug otherwise — with a narrower catch where only parsing happens. The rest are fine on purpose (parsing with a fallback, browser storage, cleanup). From your list: the QueryMeta loop logs at debug, `retrieval` lost its catch-all (every access is type-checked), `cards/links` is a deliberate fallback chain (marked), the others parse with a fallback and stay. Ruff now enforces S110 and TRY400; the widget logs 13 failures with error type, status and error number only. |
| Bot text, quick replies and user text in logs (`turn_links.py`, `turn_persist.py`, `widget_postprocess.py`) | ✅ 18C | Larger than reported: about 55 places in 22 files. The log now holds no content — only lengths, short session IDs and filter values; content only at DEBUG with `LOG_CONTENT=true`. What a turn did is stored per turn for the Studio (the turn record), found by the trace ID. An AST guard checks every logger call, and a canary test runs real turns over all paths with a marker word. |

## 3 Moderation outage (18A)

- **Visible:** the decision now records failed stages (`stages_failed`, reason
  `moderation_unavailable`). Missing credentials give one warning per process; the warm-up at start
  reports the outage instead of success. New counter `boerdi_safety_stage_total{stage,outcome}`.
- **No more "checked" without a check:** a risk is only downgraded when every stage that ran
  actually checked. This now also covers the LLM legal check, which failed just as silently. Both
  stages are counted (`stage="openai_moderation"` and `stage="llm_legal"`).
- **Switch `MODERATION_FAILURE_MODE`:** `open` (default) answers and makes the outage visible as
  above. `closed` replies with a friendly refusal for as long as moderation is down — in the
  chat, for direct actions and at `/api/agent`. Recommended for school use. The start warns about an
  unknown value (e.g. the German `geschlossen`) and about `closed` without any moderation access. Documented in
  `deploy/README.md`.
- **Long messages:** they were moderated only up to character 4000. Now in overlapping sections,
  in one call. Above about 30 000 characters the start and the end are checked, and the turn is
  marked as only partly checked (`moderation_partial`; `closed` refuses it).
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
| The debug block of every chat response reaches every client (error texts, model and tool names) | ✅ 18D — every response carries a public `ui` part; `debug` only with Studio login or the studio key (otherwise `null`), also in the history |
| The canvas shows the provider's raw error text in the generated material | ✅ 18D — an error number instead |
| A privacy switch saved as text (`messages: "false"`) was read as "on" — messages were stored although switched off | ✅ 18E — switches are read with the same rule as the check on save; if the privacy settings are unreadable, nothing is stored |
| Error lines wrote the provider's error text to the log (over a hundred places pass the exception to the message); it can repeat the user's input | ✅ 18E — provider and MCP errors appear only with their type, in the message and in tracebacks; the classifier library's own error line is muted unless `LOG_CONTENT` is on; the canary test now runs turns where every model call fails |
| Waiting for an LLM slot has no time limit; a hanging provider fills a replica | ✅ 18F — `LLM_SLOT_WAIT_S` (30 s): after that the turn answers "busy right now, try again in a minute" (no error number) and its further calls fail at once; background and import wait without a limit; counter and alert rule |
| Outer rate limit is 20/min per IP (too tight behind a school NAT); 429 looks like a generic error in the widget | ✅ 18F — 120/min per IP; an invalid value stops the start; the widget says "too many requests" with the wait time from `Retry-After` and puts the typed question back into the input field |
| Anonymous users have the same agent limits as logged-in users (no cost cap) | ➖ for now — the cost of an anonymous turn will be measured first |
| The session ID comes from the client; whoever knows it can read and continue the chat | ➖ known and accepted; write actions are bound to the logged-in person |
| The legal check sees only the first 2000 characters of a message | ⏳ noted, not yet planned |

## 6 How to check

- Backend tests: `test_safety_ausfall.py` (28), `test_mehrere_medientypen.py` (49), plus additions in
  the preflight, graph, assess, agent gate, merge, prefetch and tool loop tests. Full backend suite
  green. An independent review of this change found 4 major and 9 minor points; all are fixed
  except the answer rewrite, which we kept on purpose (§1).
- Moderation outage by hand: set a wrong key or a dead endpoint for moderation, then send a message.
  With `MODERATION_FAILURE_MODE=open` the log shows "moderation skipped …" and the counter
  `boerdi_safety_stage_total{stage="openai_moderation",outcome="fehler"}` rises
  (`keine_zugangsdaten` when no key is configured at all). With `closed` the bot refuses
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
