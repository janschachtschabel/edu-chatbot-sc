/**
 * A failed studio request, with the status code kept MACHINE-READABLE.
 *
 * ALT's `fetchJson` threw `new Error("HTTP 403 /url — body")`
 * (studio/src/lib/api.ts:15-19), so a caller wanting to distinguish "logged
 * out" (401) from "backend down" (502) had to string-match the message. Every
 * view here needs that distinction to pick between "bitte neu anmelden" and
 * "erneut versuchen", so the status is a field.
 */
export class StudioApiError extends Error {
  constructor(
    /** HTTP status, or 0 when the request never reached the server. */
    readonly status: number,
    /** Short, already-truncated German or backend-supplied explanation. */
    readonly detail: string,
    readonly url: string,
  ) {
    super(`HTTP ${status} ${url} — ${detail}`);
    this.name = 'StudioApiError';
  }

  /** The cookie is gone or invalid — the shell must send the user to /login. */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** The studio is not configured at all (STUDIO_PASSWORD unset, fail-closed). */
  get isDisabled(): boolean {
    return this.status === 503;
  }
}
