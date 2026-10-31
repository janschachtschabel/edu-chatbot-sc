/**
 * A failed studio request, with the status code kept MACHINE-READABLE.
 *
 * ALT's `fetchJson` threw `new Error("HTTP 403 /url — body")`
 * (studio/src/lib/api.ts:15-19), so a caller wanting to distinguish "logged
 * out" (401) from "backend down" (502) had to string-match the message. Every
 * view here needs that distinction to pick between "bitte neu anmelden" and
 * "erneut versuchen", so the status is a field.
 */
import type { FieldProblem } from './field-problems';

/**
 * What a 409 says about the stored state (Paket 4, D5): someone saved since
 * the editor loaded. `version` is `null` when the area was deleted meanwhile;
 * `updatedAt` is ISO in UTC, formatted where it is shown.
 */
export interface SaveConflict {
  readonly version: number | null;
  readonly updatedBy: string | null;
  readonly updatedAt: string | null;
}

export class StudioApiError extends Error {
  constructor(
    /** HTTP status, or 0 when the request never reached the server. */
    readonly status: number,
    /** Short, already-truncated German or backend-supplied explanation. */
    readonly detail: string,
    readonly url: string,
    /** A 422's entries, each with its document path (ST-2e) — so the form can
     *  put every message next to its field instead of in one line below it. */
    readonly problems: readonly FieldProblem[] = [],
    /** A 409's stored state — who saved, when, which version. */
    readonly conflict: SaveConflict | null = null,
    /** A 429's `Retry-After` in seconds (Paket 19, H-3), `null` without one. */
    readonly retryAfterS: number | null = null,
  ) {
    super(`HTTP ${status} ${url} — ${detail}`);
    this.name = 'StudioApiError';
  }

  /** The cookie is gone or invalid — the shell must send the user to /login. */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** Too many failed attempts from this address (Paket 19, H-3) — wait `retryAfterS`. */
  get isRateLimited(): boolean {
    return this.status === 429;
  }

  /** The studio is not configured at all (STUDIO_PASSWORD unset, fail-closed). */
  get isDisabled(): boolean {
    return this.status === 503;
  }
}
