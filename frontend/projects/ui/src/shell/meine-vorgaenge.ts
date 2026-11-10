/**
 * „Meine Vorgänge“ (Paket AS-Ud, Plan 2026-11-09 §5j) — ohne DOM.
 *
 * Die angemeldete Person sieht ihre nicht abgeschlossenen Vorgänge in **anderen** Gesprächen
 * (alle offenen, Sicherung 20), setzt einen fort oder löscht ihn nach einer Rückfrage. Wie bei „Gespräch
 * fortsetzen“ (`fortsetzen.ts`) sind die Kennungen der Gespräche Geheimnisse: sie kommen nur aus der
 * geprüften Antwort für diese Anmeldung, liegen nur im Speicher und gelten nur, solange dasselbe
 * Gespräch und derselbe Zugangsblock gelten, mit denen gefragt wurde.
 */

import { signal } from '@angular/core';

import type { EigenerVorgang } from '../stream/offene-vorgaenge';

export type { EigenerVorgang } from '../stream/offene-vorgaenge';

export type ListenStand = 'laedt' | 'bereit' | 'fehler';

export interface MeineVorgaengeContext {
  /** `POST /api/ui/vorgaenge/liste`; wirft bei jedem Fehler. */
  abrufen: (sessionId: string) => Promise<EigenerVorgang[]>;
  /** `POST /api/ui/vorgaenge/loeschen`; wirft bei jedem Fehler (auch 404). `laeuftWeiter`: ein
   *  Auftrag läuft bei der b-api weiter (Querschnitts-Review Q-6). */
  loeschen: (sessionId: string, vorgangId: string) => Promise<{ laeuftWeiter?: boolean } | void>;
  sessionId: () => string;
  block: () => string | null;
}

/** Was die Statuszeile des Panels sagt (Schlüssel + Titel des Vorgangs). */
export interface VorgangMeldung {
  readonly schluessel: 'vorgaenge.geloescht' | 'vorgaenge.geloeschtAuftragWeiter' | 'vorgaenge.loeschFehler';
  readonly titel: string;
}

export class MeineVorgaengeController {
  readonly offen = signal(false);
  readonly stand = signal<ListenStand>('laedt');
  readonly liste = signal<readonly EigenerVorgang[]>([]);
  /** Der Vorgang, dessen Löschen gerade nachgefragt wird. */
  readonly frage = signal<string | null>(null);
  readonly loescht = signal<string | null>(null);
  readonly meldung = signal<VorgangMeldung | null>(null);
  /** Jede Abfrage zählt; eine ältere Antwort gilt nicht mehr. */
  private _lauf = 0;

  constructor(private readonly ctx: MeineVorgaengeContext) {}

  async umschalten(): Promise<void> {
    if (this.offen()) {
      this.schliessen();
      return;
    }
    this.offen.set(true);
    this.meldung.set(null);
    await this.laden();
  }

  schliessen(): void {
    this.offen.set(false);
    this.frage.set(null);
  }

  async laden(): Promise<void> {
    const lauf = ++this._lauf;
    const sid = this.ctx.sessionId();
    const block = this.ctx.block();
    this.stand.set('laedt');
    this.frage.set(null);
    try {
      const liste = await this.ctx.abrufen(sid);
      if (!this._gilt(lauf, sid, block)) return;
      this.liste.set(liste.filter((v) => v.session_id !== sid));
      this.stand.set('bereit');
    } catch {
      if (this._gilt(lauf, sid, block)) this.stand.set('fehler');
    }
  }

  fragen(id: string): void {
    this.frage.set(id);
  }

  nichtLoeschen(): void {
    this.frage.set(null);
  }

  /** Löscht nach der Rückfrage; `true` bei Erfolg. Scheitert es (auch 404: schon weg oder nicht
   *  mehr eigen), sagt die Meldung es, und die Liste wird neu geladen. */
  async loeschen(id: string): Promise<boolean> {
    const v = this.liste().find((e) => e.id === id);
    if (!v || this.loescht()) return false;
    const sid = this.ctx.sessionId();
    this.loescht.set(id);
    try {
      const ergebnis = await this.ctx.loeschen(sid, id);
      this.liste.update((l) => l.filter((e) => e.id !== id));
      const schluessel = ergebnis?.laeuftWeiter ? 'vorgaenge.geloeschtAuftragWeiter' : 'vorgaenge.geloescht';
      this.meldung.set({ schluessel, titel: v.titel });
      return true;
    } catch {
      this.meldung.set({ schluessel: 'vorgaenge.loeschFehler', titel: v.titel });
      await this.laden();
      return false;
    } finally {
      this.loescht.set(null);
      this.frage.set(null);
    }
  }

  /** Abgemeldet, neuer Block, Neustart: alles weg; eine laufende Antwort gilt nicht mehr. */
  vergessen(): void {
    this._lauf++;
    this.schliessen();
    this.liste.set([]);
    this.stand.set('laedt');
    this.meldung.set(null);
  }

  private _gilt(lauf: number, sid: string, block: string | null): boolean {
    return lauf === this._lauf && this.ctx.sessionId() === sid && this.ctx.block() === block;
  }
}
