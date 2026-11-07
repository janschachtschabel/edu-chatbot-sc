/**
 * Anmeldung über das Ticket der Gastgeberseite — der stille Bruder von
 * `sign-in-flow.ts`.
 *
 * Der Fall: eine edu-sharing-Seite bettet das Widget ein und reicht ihm im
 * Attribut `ticket` den Ausweis der Person, die dort schon angemeldet ist
 * (dieselbe Konvention, die der md-editor als `?ticket=…` konsumiert). Das
 * Widget tauscht ihn beim MCP-Server gegen einen gewöhnlichen Zugangsblock
 * (`POST /auth/ticket`) — danach ist NICHTS mehr besonders: derselbe Speicher,
 * dieselbe Kopfzeile je Zug, derselbe Abmelde-Knopf wie nach der
 * OAuth-Anmeldung.
 *
 * Warum tauschen statt das Ticket behalten: ein rohes Ticket ist ein lebender
 * Repository-Ausweis, ein Block ist nur gegen unseren MCP-Server brauchbar und
 * dort widerrufbar. Das Ticket verlässt dieses Modul genau einmal — zur
 * Tauschstelle — und wird nirgends abgelegt.
 *
 * **Still, mit Absicht.** Die OAuth-Anmeldung spricht im Chat, weil eine
 * Person sie angeklickt hat; dieser Vorgang läuft ungefragt bei jedem Laden
 * der Seite. Ein Satz je Neuladen wäre Lärm, und ein Fehlschlag hat schon
 * eine ehrliche Anzeige: der Anmelde-Knopf bleibt auf „Anmelden" stehen —
 * derselbe Rückfall auf die Handanmeldung, den der md-editor „hybrid
 * fallback" nennt. Für die Betreiberseite bleibt eine `console.warn`-Zeile
 * (in der Shell), damit ein abgelaufenes Ticket-Template auffindbar ist.
 *
 * Läuft auch dann, wenn schon ein Block hinterlegt ist: das Ticket der Seite
 * benennt, wer HIER angemeldet ist, und diese Identität schlägt einen
 * mitgebrachten Rest aus einer früheren Sitzung (md-editor-Regel: „that one
 * may belong to an earlier or different identity"). Scheitert der Tausch,
 * bleibt der vorhandene Block unangetastet.
 */

import { writeAccessBlock } from './mcp-access';

/** Die fünf Ausgänge — `done` ist der einzige, der etwas verändert hat. */
export type TicketLoginOutcome = 'done' | 'no-ticket' | 'unavailable' | 'rejected' | 'unreachable' | 'store-failed';

/** Was der Vorgang von der Shell braucht (deferred Arrows wie beim Anmelden). */
export interface TicketLoginContext {
  /** Das Attribut, von der Hülle eingesammelt. Leer = nichts zu tun. */
  ticket: () => string;
  /** Herkunft des MCP-Servers (öffentliches Config-Bündel). Leer = kein Tausch möglich. */
  mcpAuthBase: () => string;
  /** Nur für den Test. */
  fetchImpl?: typeof fetch;
  /** Nur für den Test: das Warten vor dem zweiten Versuch. */
  warten?: (ms: number) => Promise<void>;
}

/** Längste Wartezeit vor dem zweiten Versuch nach einer 503 — länger wartet der Tausch nicht. */
export const ZWEITER_VERSUCH_MAX_MS = 15_000;

/** Die Wartezeit einer 503 `upstream_unreachable` (Rumpf `retryAfter`, sonst `Retry-After`), gedeckelt. */
async function wartezeitMs(res: Response): Promise<number> {
  let sekunden = Number(res.headers.get('retry-after'));
  try {
    const rumpf = (await res.json()) as { retryAfter?: unknown };
    if (typeof rumpf?.retryAfter === 'number') sekunden = rumpf.retryAfter;
  } catch {
    /* kein JSON — dann der Kopf */
  }
  const ms = Number.isFinite(sekunden) && sekunden > 0 ? sekunden * 1000 : 10_000;
  return Math.min(ms, ZWEITER_VERSUCH_MAX_MS);
}

/**
 * Ticket gegen Zugangsblock tauschen und ablegen.
 *
 * Wirft nie; jeder Ausgang ist ein Wort, das die Shell protokollieren kann.
 * `rejected` heisst „der Server hat entschieden" (Ticket abgelaufen, Ausgabe
 * abgeschaltet, Drossel), `unreachable` „er war nicht zu fragen" — der
 * Unterschied entscheidet, wo jemand suchen muss.
 */
export async function runTicketLogin(ctx: TicketLoginContext): Promise<TicketLoginOutcome> {
  const ticket = (ctx.ticket() || '').trim();
  if (!ticket) return 'no-ticket';
  const basis = (ctx.mcpAuthBase() || '').trim().replace(/\/+$/, '');
  if (!basis) return 'unavailable';

  const doFetch = ctx.fetchImpl ?? fetch;
  const tauschen = () => doFetch(`${basis}/auth/ticket`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket }),
  });
  let data: { ok?: boolean; block?: unknown };
  try {
    let res = await tauschen();
    // MCP-Stand 2026-11-07: 503 `upstream_unreachable` = edu-sharing hat die Prüfung nicht
    // beantwortet — kein Urteil über das Ticket. Behalten und nach der Wartezeit EINMAL erneut.
    if (res.status === 503) {
      await (ctx.warten ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms))))(await wartezeitMs(res));
      res = await tauschen();
      if (res.status === 503) return 'unreachable';
    }
    // 404 = diese Anlage gibt keine Blöcke aus (Betriebsentscheidung, kein
    // Fehler) — dieselbe Bedeutung wie eine leere Anmelde-Adresse.
    if (res.status === 404) return 'unavailable';
    if (!res.ok) return 'rejected';
    data = (await res.json()) as { ok?: boolean; block?: unknown };
  } catch {
    return 'unreachable';
  }

  if (!data?.ok || typeof data.block !== 'string') return 'rejected';
  // `writeAccessBlock` prüft die Form noch einmal und lehnt ab, was kein
  // Block ist — ein Server, der etwas anderes schickt, landet nicht im
  // Speicher, sondern in diesem Ausgang.
  return writeAccessBlock(data.block) ? 'done' : 'store-failed';
}

/** Eine Sperre für frühe Züge, bis der Tausch endet (Paket 10, Kurzaudit S-4) —
 *  höchstens `fristMs`, damit eine Anlage ohne Anmeldung nicht jeden Zug aufhält. */
export function anmeldeSperre(fristMs = 5_000): { sperre: Promise<void>; freigeben: () => void } {
  let freigeben!: () => void;
  const sperre = new Promise<void>((resolve) => { freigeben = resolve; });
  setTimeout(freigeben, fristMs);
  return { sperre, freigeben };
}
