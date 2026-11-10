/**
 * Seiten-Ping einer Führung (Paket AS-7b, Plan 2026-11-09 §5m, F-4).
 *
 * Wartet ein Ablauf-Schritt `seite` auf die Ankunft (`ui.ablauf.status === 'wartet_seite'`), schickt
 * die Shell nach einem Seitenaufruf diesen unsichtbaren Zug (`page_event: 'ablauf_seite'`). Das
 * Backend beantwortet ihn im frühen Knoten `ablauf_seite`: passt die Seite, geht der Lauf weiter und
 * die Antwort erscheint; sonst ist sie leer. Wie der Kontext-Ping: keine Nutzer- oder Lade-Blase,
 * höchstens einmal je Seitenaufruf, Fehler still. Den Kontext teilt er mit dem Kontext-Ping.
 */
import { fehlerKurz } from '../obs/fehler-kurz';
import { sitzungsWache } from '../session/session-id';
import type { ContextGreetingContext } from './context-greeting.controller';

/** Das `page_event` des Pings (Backend: `domain/hintergrund_zug.ABLAUF_SEITE`). */
export const SEITEN_PING = 'ablauf_seite';

export class SeitenPing {
  private _gesendet = false;

  constructor(private readonly ctx: ContextGreetingContext) {}

  /** Eine neue Seite (SPA-Navigation, Review AS-7b Befund 4): der Ping darf wieder hinaus. */
  zuruecksetzen(): void {
    this._gesendet = false;
  }

  /** Schickt den Ping — `true`, wenn eine Antwort erschien. */
  async senden(): Promise<boolean> {
    if (this.ctx.isLoading() || this._gesendet) return false;
    this._gesendet = true;
    const veraltet = sitzungsWache(() => this.ctx.sessionId());
    this.ctx.setLoading(true);
    let gezeigt = false;
    try {
      const resp = await this.ctx.sendMessage('[ablauf-seite]', { page_event: SEITEN_PING });
      if (veraltet()) return false;
      if ((resp.content || '').trim()) {
        const id = this.ctx.addBotMessage(
          resp.content, false, resp.cards, resp.quick_replies, resp.ui,
          resp.pagination, resp.query_metas, resp.web_links,
          resp.display_rules, resp.topic_page,
        );
        this.ctx.setScrollTarget(id);
        this.ctx.setLatestDebug(resp.debug, resp.ui);
        gezeigt = true;
      }
    } catch (err) {
      if (veraltet()) return false;
      console.debug('boerdi: Seiten-Ping gescheitert —', fehlerKurz(err));
    }
    this.ctx.setLoading(false);
    return gezeigt;
  }
}
