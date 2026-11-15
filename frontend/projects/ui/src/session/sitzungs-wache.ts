/**
 * Die Wache der Anmeldung aus der Sitzung der Seite (Plan 2026-11-15, SA-13).
 *
 * Ein Block aus der Sitzung gilt für die Person, die beim Tausch auf der Seite angemeldet
 * war. Die Seite kann danach jemand anderen zeigen, ohne neu zu laden: Abmelden, Anmelden
 * und Ummelden laufen im Repository als Wechsel innerhalb derselben Seite. Die Wache fragt
 * deshalb vor jedem Abruf, der den Block trägt, wer gerade angemeldet ist:
 *
 * - **dieselbe Person:** nichts.
 * - **Gast:** der Block fällt weg, ein Satz sagt es.
 * - **jemand anderes:** der Block fällt weg, es wird neu getauscht.
 * - **vorher Gast, jetzt eine Person:** es wird getauscht — wer sich nach dem Laden der
 *   Seite im Repository anmeldet, ist ohne Neuladen auch im Chat angemeldet.
 * - **keine Antwort:** kein Urteil. Der Block bleibt, der Server entscheidet wie bisher.
 *
 * Nicht ihr Fall: ein Block, der nicht aus der Sitzung stammt (Anmeldung von Hand), und ein
 * Tab, in dem sich jemand im Chat abgemeldet hat (`aktiv()` ist dann falsch).
 *
 * Rein bis auf den Zugangsspeicher (`mcp-access`); alles andere reicht die Shell herein.
 */

import { clearAccessBlock, readAccessBlock, sessionBlockOwner } from './mcp-access';
import { ANONYMOUS_AUTHORITY } from './prepared-write';

/** Frist der Frage „wer ist da“. Länger hält die Wache einen Abruf dafür nicht auf. */
export const WACHE_FRAGE_MS = 3_000;
/** So lange wartet ein Abruf auf einen Tausch, den die Wache angestoßen hat. Danach geht er
 *  ohne Anmeldung hinaus; der Tausch läuft weiter. */
export const WACHE_TAUSCH_MS = 5_000;
/** So lange gilt eine Antwort des Repositorys: eine Folge von Abrufen fragt einmal. */
export const WACHE_FRISCH_MS = 2_000;
/** Nach einem gescheiterten Tausch versucht es die Wache so lange nicht von selbst wieder —
 *  sonst kostete ein falsch eingerichteter Weg bei jedem Zug zwei Abrufe. */
export const TAUSCH_PAUSE_MS = 5 * 60_000;
/** Ausgänge, die sich ohne Eingriff des Betriebs nicht ändern: der Weg ist nicht eingerichtet,
 *  die Seite nicht freigegeben, der Tausch nennt eine andere Person. Bis zum Neuladen (oder
 *  einem Klick auf „Anmelden“) versucht es die Wache dann nicht mehr von selbst. */
const ENDGUELTIG: readonly string[] = ['unavailable', 'not-allowed', 'mismatch'];

export interface SitzungsWacheWege {
  /** Gilt der Sitzungs-Weg auf dieser Seite, und darf von selbst getauscht werden (nicht im
   *  Chat abgemeldet, Widget nicht entfernt)? */
  aktiv: () => boolean;
  /** Wer ist auf der Seite angemeldet (`authorityName`)? `null` = keine Aussage. */
  fragen: () => Promise<string | null>;
  /** Der Block ist weg: Knopf, Fristen und Listen der Person nachziehen. */
  verworfen: () => void;
  /** Die Sitzung der Seite neu tauschen. `true`: ein Block ist da. */
  tauschen: () => Promise<boolean>;
  /** Der Satz „deine Anmeldung gilt nicht mehr“. */
  sagen: () => void;
  /** Nur für den Test. */
  jetzt?: () => number;
  /** Nur für den Test: das Warten auf den Tausch. */
  warten?: (ms: number) => Promise<void>;
}

/** Ein Block, der nicht aus der Sitzung der Seite stammt (Hand-Anmeldung, Ticket). */
const fremderBlock = (): boolean => readAccessBlock() !== null && sessionBlockOwner() === null;

export class SitzungsWache {
  private lauf: Promise<void> | null = null;
  private stand = Number.NEGATIVE_INFINITY;
  private pauseBis = 0;

  constructor(private readonly wege: SitzungsWacheWege) {}

  /** Vor einem Abruf, der den Block trägt. Wirft nie. Gleichzeitige Aufrufe teilen sich einen
   *  Lauf — sonst ginge der zweite hinaus, während der erste noch neu tauscht. */
  pruefen(): Promise<void> {
    if (this.lauf) return this.lauf;
    const lauf = this.einmal()
      .catch(() => undefined)
      .finally(() => { if (this.lauf === lauf) this.lauf = null; });
    this.lauf = lauf;
    return lauf;
  }

  /** Ein Tausch der Sitzung endete — gleich, wer ihn anstieß (Laden, Klick, Frist, die Wache
   *  selbst). `ausgang` ist das Wort aus `runSessionLogin`.
   *  - `done`: die Seite wurde eben gefragt, die Antwort ist frisch; eine Pause endet.
   *  - `no-session`: ebenso frisch (ein Gast).
   *  - sonst: Pause — sonst versuchte es die Wache beim nächsten Abruf gleich wieder, auf Kosten
   *    des Anmelde-Budgets der Adresse am MCP-Server. */
  getauscht(ausgang: string): void {
    if (ausgang === 'done') {
      this.stand = this.jetzt();
      this.pauseBis = 0;
    } else if (ausgang === 'no-session') {
      this.stand = this.jetzt();
    } else if (ausgang !== 'off') {
      this.pauseBis = ENDGUELTIG.includes(ausgang)
        ? Number.POSITIVE_INFINITY : this.jetzt() + TAUSCH_PAUSE_MS;
    }
  }

  private jetzt(): number {
    return (this.wege.jetzt ?? Date.now)();
  }

  private async einmal(): Promise<void> {
    if (!this.wege.aktiv() || fremderBlock()) return;
    if (this.jetzt() - this.stand < WACHE_FRISCH_MS) return;
    const person = await this.wege.fragen();
    if (person === null) return;   // keine Aussage — auch nicht als frisch gemerkt
    this.stand = this.jetzt();
    // Während der Frage kann sich jemand abgemeldet oder von Hand angemeldet haben.
    if (!this.wege.aktiv() || fremderBlock()) return;

    const gehalten = sessionBlockOwner()?.authority ?? null;
    if (person === gehalten) return;
    const hatte = gehalten !== null;
    if (hatte) {
      // Gast oder jemand anderes: der Block gehört nicht mehr zu dieser Seite.
      clearAccessBlock();
      this.wege.verworfen();
    }
    if (person === ANONYMOUS_AUTHORITY) {
      if (hatte) this.wege.sagen();
      return;
    }
    if (this.jetzt() < this.pauseBis) {
      if (hatte) this.wege.sagen();
      return;
    }
    // Die Pause setzt `getauscht` — die Shell meldet dort den Ausgang jedes Tauschs.
    const tausch = this.wege.tauschen().then((gelungen) => {
      if (!gelungen && hatte) this.wege.sagen();
    }, () => undefined);
    const warten = this.wege.warten ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
    await Promise.race([tausch, warten(WACHE_TAUSCH_MS)]);
  }
}
