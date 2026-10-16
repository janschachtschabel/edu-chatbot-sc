/**
 * Where the sessions behind a number came from (ST-9) — the `scope` query value
 * of `/api/quality/*`, `/api/usage/period` and `/api/sessions/`.
 *
 * The backend reads it from the session-id prefix (`services/session_origin.py`):
 * `production` means neither eval (`eval-`), load test (`loadtest-`) nor a studio
 * trial run (the chat probe's `studio-` sessions and, since Paket 9, the task
 * tester's rows booked as `studio-probe`); the studio preview embeds the real
 * widget, so its chats count as production.
 */
export type OriginScope = 'all' | 'production' | 'eval';

/** Query parameters for a scope: none for `all`, so the default request stays
 *  exactly what it was before the filter existed. */
export function scopeParams(scope: OriginScope): { scope: OriginScope } | undefined {
  return scope === 'all' ? undefined : { scope };
}
