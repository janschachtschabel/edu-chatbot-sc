/**
 * Vorgemerkte Modul-Antworten (Paket U2, Plan 2026-11-04 T-10).
 *
 * Ein abfragendes Modul wie der Strukturentwurf merkt seinen Stand vor (`host.vormerken`). Tippt
 * die Person eine Nachricht, solange der Block offen ist, geht der Stand als `ui_antwort` mit —
 * der Block wird `beantwortet` statt `veraltet`, und keine Bearbeitung geht verloren. Gilt nur für
 * offene Blöcke; der jüngste gewinnt (es gibt ohnehin höchstens einen offenen je Antwort, und
 * jeder Zug macht ältere `veraltet`).
 */
import type { ChatMessage } from '../grouping/message-types';

export interface Vormerkung {
  readonly nachrichtId: string;
  readonly blockId: string;
  readonly daten: Record<string, unknown>;
}

export class Vormerkungen {
  private readonly eintraege = new Map<string, Vormerkung>();

  setzen(auftrag: { readonly nachrichtId: string; readonly blockId: string; readonly daten: Record<string, unknown> | null }): void {
    const schluessel = `${auftrag.nachrichtId}\u0000${auftrag.blockId}`;
    this.eintraege.delete(schluessel);                 // neu einreihen: die jüngste steht hinten
    if (auftrag.daten) this.eintraege.set(schluessel, { ...auftrag, daten: auftrag.daten });
  }

  /** Die Vormerkung für den nächsten getippten Zug — nur, solange ihr Block offen ist. */
  fuerZug(msgs: readonly ChatMessage[]): Vormerkung | null {
    const offen = (v: Vormerkung) => msgs.some((m) => m.id === v.nachrichtId && (m.ui?.ui_bloecke ?? [])
      .some((b) => b.block_id === v.blockId && b.art === 'abfragen' && b.status === 'offen'));
    return [...this.eintraege.values()].reverse().find(offen) ?? null;
  }
}
