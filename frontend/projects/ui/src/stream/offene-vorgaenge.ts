/** Die Antwort von `POST /api/ui/vorgaenge/offen` (Paket K2a) — Form und Prüfung. Die Kennung
 *  eines Gesprächs ist dessen Geheimnis; nur wohlgeformte Einträge werden je zu einem Wechsel. */

import { isValidSessionId } from '../session/session-id';

export type OffenerStatus = 'wartet_auftrag' | 'wartet_person';

export interface OffenerVorgang {
  titel: string;
  /** Der wartende Ablauf — nach dem Wechsel fragt „Stand prüfen“ nach ihm. */
  ablauf: string | null;
  status: OffenerStatus;
  session_id: string;
  /** ISO-Zeitpunkt der letzten Änderung. */
  geaendert: string;
}

const STATUS: ReadonlySet<unknown> = new Set(['wartet_auftrag', 'wartet_person']);

/** Nur wohlgeformte Einträge — eine unerwartete Antwort wird nie zu einem Wechsel. */
export function offeneVorgaengeLesen(roh: unknown): OffenerVorgang[] {
  const liste = (roh as { vorgaenge?: unknown } | null)?.vorgaenge;
  if (!Array.isArray(liste)) throw new Error('Vorgänge: Antwort ohne Liste');
  return liste.filter((v): v is OffenerVorgang =>
    !!v && typeof v === 'object'
    && typeof v.titel === 'string'
    && (v.ablauf === null || typeof v.ablauf === 'string')
    && STATUS.has(v.status)
    && isValidSessionId(v.session_id)
    && typeof v.geaendert === 'string' && !Number.isNaN(Date.parse(v.geaendert)));
}


// ── AS-4c (Plan 2026-11-09 R3): Wiederkehr mit Vorgang- oder Auftragskennung ──────────────────

/** Die Kennung, mit der eine Gastseite (Benachrichtigung, Link) zurückführt: genau eine. */
export type WiederkehrKennung = { vorgang: string } | { auftrag: string };

/** Ein Vorgang der Wiederkehr — wie bei `/offen`, aber jeder offene Status (läuft, wartet …). */
export type WiederkehrVorgang = Omit<OffenerVorgang, 'status'> & { status: string };

const VORGANG_FORM = /^[0-9a-fA-F-]{8,64}$/;
const AUFTRAG_FORM = /^[A-Za-z0-9_.:-]{1,128}$/;
const STATUS_FORM = /^[a-z_]{1,30}$/;

/** Genau eine wohlgeformte Kennung (wie das Backend sie annimmt) — oder `null`. */
export function wiederkehrKennung(roh: unknown): WiederkehrKennung | null {
  if (!roh || typeof roh !== 'object') return null;
  const { vorgang, auftrag } = roh as { vorgang?: unknown; auftrag?: unknown };
  if (vorgang !== undefined && auftrag !== undefined) return null;
  if (typeof vorgang === 'string' && VORGANG_FORM.test(vorgang)) return { vorgang };
  if (typeof auftrag === 'string' && AUFTRAG_FORM.test(auftrag)) return { auftrag };
  return null;
}

/** Nur eine wohlgeformte Antwort wird ein Wechsel — sonst `null`. */
export function wiederkehrLesen(roh: unknown): WiederkehrVorgang | null {
  const v = roh as Partial<WiederkehrVorgang> | null;
  return v && typeof v === 'object'
    && typeof v.titel === 'string'
    && (v.ablauf === null || typeof v.ablauf === 'string')
    && typeof v.status === 'string' && STATUS_FORM.test(v.status)
    && isValidSessionId(v.session_id)
    && typeof v.geaendert === 'string' && !Number.isNaN(Date.parse(v.geaendert))
    ? { titel: v.titel, ablauf: v.ablauf, status: v.status, session_id: v.session_id as string,
        geaendert: v.geaendert }
    : null;
}


// ── AS-Ud (Plan 2026-11-09 §5j): „Meine Vorgänge“ ─────────────────────────────────────────────

/** Ein eigener, nicht abgeschlossener Vorgang eines anderen Gesprächs (`POST /api/ui/vorgaenge/liste`);
 *  `id` nur zum Löschen. */
export type EigenerVorgang = WiederkehrVorgang & {
  id: string;
  /** Querschnitts-Review Q-7: der Status des Laufs (feiner als `status`); fehlt ohne Lauf. */
  lauf_status?: string;
};

/** Nur wohlgeformte Einträge — eine unerwartete Antwort wird nie zu einem Wechsel oder Löschen. */
export function eigeneVorgaengeLesen(roh: unknown): EigenerVorgang[] {
  const liste = (roh as { vorgaenge?: unknown } | null)?.vorgaenge;
  if (!Array.isArray(liste)) throw new Error('Vorgänge: Antwort ohne Liste');
  return liste.flatMap((e: unknown) => {
    const { id, lauf_status: lauf } = (e ?? {}) as { id?: unknown; lauf_status?: unknown };
    const v = wiederkehrLesen(e);
    if (!v || typeof id !== 'string' || !VORGANG_FORM.test(id)) return [];
    return [{ id, ...v, ...(typeof lauf === 'string' && STATUS_FORM.test(lauf) ? { lauf_status: lauf } : {}) }];
  });
}
