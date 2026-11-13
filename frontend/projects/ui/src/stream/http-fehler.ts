/**
 * Ein nicht-ok-Abruf als Fehler (Paket 18F): `status` und — wenn der Server sagt, wann es
 * wieder geht — `retryAfterMs`. Eine Stelle für Verlauf, Strom und POST; bis dahin las nur der
 * Verlauf `Retry-After`, und ein 429 auf dem Chat-Weg wurde zur allgemeinen Fehlerblase.
 */
import type { TranslateFn } from '../i18n/i18n';

export interface HttpFehler extends Error {
  status: number;
  retryAfterMs?: number;
  /** Paket R1-e: der Grund aus `detail` (ein kurzes Wort des Servers, etwa `abgewiesen`). */
  code?: string;
}

const CODE = /^[a-z][a-z0-9_]{0,39}$/;
/** Review R1, Befund 7: so lange darf der Rumpf eines Fehlers höchstens dauern — danach trägt der
 *  Status allein (ein hängender Proxy-Rumpf machte sonst aus einem 409 einen Zeitablauf). */
const CODE_FRIST_MS = 2_000;

/** Wie {@link httpFehler}, dazu `code` aus einem JSON-Rumpf `{detail: "<wort>"}` — nur ein kurzes
 *  Wort, nie freier Text des Servers. Ein unlesbarer oder zu langsamer Rumpf lässt `code` weg. */
export async function httpFehlerMitCode(resp: Response, wo: string): Promise<HttpFehler> {
  const fehler = httpFehler(resp, wo);
  let uhr: ReturnType<typeof setTimeout> | undefined;
  try {
    const frist = new Promise<undefined>((fertig) => { uhr = setTimeout(() => fertig(undefined), CODE_FRIST_MS); });
    const rumpf = (await Promise.race([resp.json(), frist])) as { detail?: unknown } | null | undefined;
    const detail = rumpf?.detail;
    if (typeof detail === 'string' && CODE.test(detail)) fehler.code = detail;
  } catch {
    // kein JSON — der Status allein trägt
  } finally {
    clearTimeout(uhr);
  }
  return fehler;
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

/** Paket AS-8b: in der Probe der Studio-Vorschau heißt ein 403 auf dem Chat-Weg „keine gültige
 *  Studio-Anmeldung“ (Backend: `probe_ohne_recht`) — sonst `null`. Nur mit `probe`, denn ein
 *  anderer 403 hätte einen anderen Grund. */
export function probeHinweis(t: TranslateFn, err: unknown, probe: boolean): string | null {
  return probe && (err as { status?: unknown } | null)?.status === 403
    ? t('error.probeOhneRecht') : null;
}

/** Der Satz für „Frist abgelaufen“ (Paket 19, M-15): der POST lief in seine Frist
 *  (`StreamStaleError` aus `postChat`) — sonst `null`. Über den Namen, nicht über
 *  `instanceof`: so bleibt dieses Modul frei vom Strom-Transport. */
export function fristHinweis(t: TranslateFn, err: unknown): string | null {
  return (err as { name?: unknown } | null)?.name === 'StreamStaleError' ? t('error.stale') : null;
}
