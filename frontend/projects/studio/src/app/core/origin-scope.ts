/**
 * Where the sessions behind a number came from (ST-9) — the `scope` query value
 * of `/api/quality/*`, `/api/usage/period` and `/api/sessions/`.
 *
 * The backend reads it from the session-id prefix (`services/session_origin.py`):
 * `production` means neither eval (`eval-`), load test (`loadtest-`) nor a studio
 * trial run (the chat probe's `studio-` sessions and, since Paket 9, the task
 * tester's rows booked as `studio-probe`); the studio preview embeds the real
 * widget; since Plan 2026-11-10 (TB-E2) its chats carry the mark `_vorschau` (trial runs `_probe`)
 * (column `sessions.vorschau`, migration 0022) and count as `probe`, not as production. `probe`
 * holds only the widget preview — the agent page's chat trial (`studio-`) and the task tester
 * (`studio-probe`) are neither production nor `probe`, they show under `all`.
 */
export type OriginScope = 'all' | 'production' | 'eval' | 'probe';

/** Query parameters for a scope: none for `all`, so the default request stays
 *  exactly what it was before the filter existed. */
export function scopeParams(scope: OriginScope): { scope: OriginScope } | undefined {
  return scope === 'all' ? undefined : { scope };
}
