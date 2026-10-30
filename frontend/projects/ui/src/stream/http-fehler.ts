/**
 * Ein nicht-ok-Abruf als Fehler (Paket 18F): `status` und — wenn der Server sagt, wann es
 * wieder geht — `retryAfterMs`. Eine Stelle für Verlauf, Strom und POST; bis dahin las nur der
 * Verlauf `Retry-After`, und ein 429 auf dem Chat-Weg wurde zur allgemeinen Fehlerblase.
 */
import type { TranslateFn } from '../i18n/i18n';

export interface HttpFehler extends Error {
  status: number;
  retryAfterMs?: number;
}

/** Die Wartezeit aus `Retry-After` in Millisekunden; nur Sekunden, kein HTTP-Datum. */
export function wartezeitMs(resp: Response): number | undefined {
  // ``0`` heißt „sofort“ und nicht „fehlt“ (Paket 9); ein fehlender Kopf ergäbe über
  // ``Number(null)`` ebenfalls 0 und wird deshalb vorher ausgeschieden.
  const roh = resp.headers?.get?.('Retry-After');
  const sekunden = roh == null || !roh.trim() ? NaN : Number(roh);
  return Number.isFinite(sekunden) && sekunden >= 0 ? sekunden * 1000 : undefined;
}

export function httpFehler(resp: Response, wo: string): HttpFehler {
  const ms = wartezeitMs(resp);
  return Object.assign(new Error(`${wo}: ${resp.status}`), {
    status: resp.status,
    ...(ms === undefined ? {} : { retryAfterMs: ms }),
  });
}

/** Der Satz für „zu viele Anfragen“ (429), mit Wartezeit, wenn sie mitkam — sonst `null`, und
 *  der Aufrufer zeigt seinen eigenen Fehler. */
export function drosselHinweis(t: TranslateFn, err: unknown): string | null {
  const e = err as { status?: unknown; retryAfterMs?: unknown } | null;
  if (e?.status !== 429) return null;
  const ms = typeof e.retryAfterMs === 'number' ? e.retryAfterMs : 0;
  return ms > 0
    ? t('error.rateLimitedWait', { sekunden: Math.ceil(ms / 1000) })
    : t('error.rateLimited');
}
