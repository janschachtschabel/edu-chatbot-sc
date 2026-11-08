/**
 * „Gespräch fortsetzen“ (Paket K2a, Plan 2026-11-08, Entscheid F2).
 *
 * Nach der Anmeldung oder beim Öffnen fragt das Widget das Backend (`POST /api/ui/vorgaenge/offen`),
 * ob ein Ablauf der Person in einem **anderen** Gespräch wartet — auf einen b-api-Auftrag oder auf
 * ihre Antwort. Dann zeigt die Hülle einen Hinweis mit „Fortsetzen“; der wechselt auf das Gespräch
 * des Vorgangs und lädt dessen Verlauf (`ShellLifecycle.wechseln`).
 *
 * Die Kennung des anderen Gesprächs ist dessen Geheimnis: Sie kommt nur aus der geprüften Antwort für
 * die angemeldete Person, liegt nur im Speicher dieses Controllers und wird erst beim Wechsel — wie
 * jede eigene Kennung — abgelegt. Gefragt wird einmal je Gespräch und Anmeldung.
 */

import { signal } from '@angular/core';

import type { OffenerVorgang } from '../stream/offene-vorgaenge';

export type { OffenerVorgang } from '../stream/offene-vorgaenge';

/** „7. Nov., 09:30“ in der Sprache des Widgets; ein kaputtes Datum bleibt leer. */
export function fortsetzenDatum(iso: string, locale: string): string {
  const zeit = Date.parse(iso);
  if (Number.isNaN(zeit)) return '';
  try {
    return new Intl.DateTimeFormat(locale, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    }).format(new Date(zeit));
  } catch {
    return new Date(zeit).toISOString().slice(0, 10);
  }
}

export interface FortsetzenContext {
  /** Fragt das Backend; wirft bei jedem Fehler. */
  abrufen: (sessionId: string) => Promise<OffenerVorgang[]>;
  sessionId: () => string;
  /** Der Zugangsblock, mit dem gefragt wird — das Angebot gilt nur für ihn (Review K2a, Befund 2). */
  block: () => string | null;
}

export class FortsetzenController {
  /** Der jüngste wartende Vorgang in einem anderen Gespräch — oder nichts. */
  readonly angebot = signal<OffenerVorgang | null>(null);
  private _gefragtFuer = '';
  private _blockDesAngebots: string | null = null;

  constructor(private readonly ctx: FortsetzenContext) {}

  /** Einmal je Gespräch fragen (nach der Anmeldung, beim Öffnen). Fehler bleiben still: der
   *  Hinweis ist eine Bequemlichkeit, das Gespräch geht ohne ihn weiter. */
  async pruefen(): Promise<void> {
    const sid = this.ctx.sessionId();
    if (!sid || sid === this._gefragtFuer) return;
    this._gefragtFuer = sid;
    const block = this.ctx.block();
    try {
      const liste = await this.ctx.abrufen(sid);
      // Wechselte das Gespräch oder die Anmeldung inzwischen, gilt die Antwort nicht mehr.
      if (this.ctx.sessionId() !== sid || this.ctx.block() !== block) return;
      this._blockDesAngebots = block;
      this.angebot.set(liste.find((v) => v.session_id !== sid) ?? null);
    } catch {
      /* still — kein Angebot */
    }
  }

  /** Das Angebot — nur, solange derselbe Block gilt, mit dem gefragt wurde (Review K2a, Befund 2:
   *  meldet die Gastseite eine andere Person an, darf deren Klick nicht in das Gespräch der ersten
   *  führen). Ein fremdes Angebot wird dabei verworfen. */
  gueltiges(): OffenerVorgang | null {
    const v = this.angebot();
    if (v && this.ctx.block() !== this._blockDesAngebots) {
      this.vergessen();
      return null;
    }
    return v;
  }

  /** Den Hinweis schließen (× oder nach dem Wechsel). */
  verwerfen(): void {
    this.angebot.set(null);
  }

  /** Abgemeldet, neuer Block, Neustart: Angebot weg, beim nächsten Anlass neu fragen. */
  vergessen(): void {
    this.angebot.set(null);
    this._gefragtFuer = '';
    this._blockDesAngebots = null;
  }
}
