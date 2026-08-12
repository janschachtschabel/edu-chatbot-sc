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
  let data: { ok?: boolean; block?: unknown };
  try {
    const res = await doFetch(`${basis}/auth/ticket`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket }),
    });
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
