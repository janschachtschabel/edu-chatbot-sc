/**
 * Die Frist des Zugangsblocks (Plan 2026-11-07, R1/CB-9).
 *
 * Seit dem MCP-Stand vom 07.11.2026 laufen Ticket- und Widget-Blöcke nach 12 Stunden ab; das
 * Backend meldet die Frist je Zug (`auth_expires_at`). Danach antwortet der Server mit 401, und
 * der nächste Zug liefe anonym. Zwei Wege, je nach Anmeldung:
 *
 * - **Seiten-Ticket:** ein Tausch VOR dem Ablauf verlängert nichts (MCP R1), also gleich DANACH
 *   neu tauschen — still, wie der erste Tausch.
 * - **Passwort-Anmeldung (OAuth):** zehn Minuten vorher ein Satz mit dem Anmelde-Chip, damit die
 *   Person nicht mitten in einer Änderung aus der Anmeldung fällt.
 *
 * Ein Zeitgeber je Frist; eine neue Frist ersetzt die alte. Läuft der Tab im Hintergrund und der
 * Zeitgeber feuert zu spät, fängt der 401-Weg (`auth_invalid`) es auf.
 */

/** So lange vor dem Ablauf kommt der Hinweis. */
export const HINWEIS_VORLAUF_MS = 10 * 60_000;
/** So lange nach dem Ablauf wird das Ticket neu getauscht (die Uhren von Server und Browser). */
export const TAUSCH_NACHLAUF_MS = 5_000;

export interface AnmeldeFristWege {
  /** Gibt es ein Seiten-Ticket, das neu getauscht werden darf (nicht abgemeldet)? */
  ticketWeg: () => boolean;
  /** Nach dem Ablauf: das Ticket neu tauschen. */
  neuTauschen: () => void;
  /** Kurz vor dem Ablauf: der Hinweis mit Anmelde-Chip. */
  hinweisen: () => void;
  /** Nur für den Test. */
  jetzt?: () => number;
}

export class AnmeldeFrist {
  private uhr: ReturnType<typeof setTimeout> | null = null;
  private frist = '';

  constructor(private readonly wege: AnmeldeFristWege) {}

  /** Eine Frist aus der Antwort übernehmen. Dieselbe Frist noch einmal ändert nichts. */
  planen(iso: string | null | undefined): void {
    if (!iso || iso === this.frist) return;
    const ablauf = Date.parse(iso);
    if (Number.isNaN(ablauf)) return;
    this.vergessen();
    this.frist = iso;
    const rest = ablauf - (this.wege.jetzt ?? Date.now)();
    if (this.wege.ticketWeg()) {
      this.uhr = setTimeout(() => this.wege.neuTauschen(), Math.max(0, rest) + TAUSCH_NACHLAUF_MS);
    } else if (rest > 0) {
      this.uhr = setTimeout(() => this.wege.hinweisen(), Math.max(0, rest - HINWEIS_VORLAUF_MS));
    }
  }

  /** Abgemeldet, abgewiesen oder das Widget geht: keine Frist mehr. */
  vergessen(): void {
    if (this.uhr !== null) clearTimeout(this.uhr);
    this.uhr = null;
    this.frist = '';
  }
}
