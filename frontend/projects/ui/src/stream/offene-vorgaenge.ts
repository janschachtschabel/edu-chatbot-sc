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
