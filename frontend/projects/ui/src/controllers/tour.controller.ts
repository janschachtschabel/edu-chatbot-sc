/**
 * Webseiten-Tour (geführte Besucherführung) — Verbatim-Port aus ALT
 * `chat/tour.controller.ts` (dort extrahiert aus chat.component.ts,
 * Frontend-Split Welle 3). NEU: Imports umgehängt (`WloCard` → `../cards`,
 * Response-Modell → `../grouping/message-types`); Bodies unverändert.
 *
 * Ablauf: Startbutton → `startTour()`. Navigation pro Schritt läuft über die
 * `__guide__`-Quick-Reply-Buttons (Shell). Nach jedem Seitenwechsel feuert ein
 * unsichtbarer Tick (`sendTourTick`), damit der Bot die Ankunft erkennt.
 *
 * Bewusst KEIN `@Injectable`-Singleton, sondern plain class mit
 * Komponenten-Lebenszeit (Muster: MarkdownRenderer/SpeechService): der
 * Tick-Guard `_tourTicked` ist Per-Page-Load-State der einen Chat-Instanz.
 * Live-Zustand der Chat-Shell kommt als `TourContext` mit deferred Arrows
 * herein; das localStorage-Tour-Flag bleibt hier im Modul (jsdom-kompatibel).
 */
import { WloCard } from '../cards/card-types';
import {
  ChatResponse,
  DebugInfo,
  InlineDocument,
  PaginationInfo,
  QueryMetaEntry,
  TopicPageView,
  WebLink,
} from '../grouping/message-types';

/** Exakter Text des Start-Chips, der die Web-Tour direkt startet. */
export const TOUR_START_LABEL = 'Web-Tour starten';
/** localStorage-Key des Tour-Flags (überlebt den WP-Reload). */
const TOUR_FLAG_KEY = 'boerdi_tour_active';

/** Live-Zustand/Seiteneffekte der Chat-Shell, die der Tour-Cluster braucht —
 *  als deferred Arrows (Muster: `MarkdownRenderContext`). */
export interface TourContext {
  /** `ApiService.sendMessage` mit LIVE-`sessionId` der Shell. */
  sendMessage: (message: string, env: any) => Promise<ChatResponse>;
  /** `parsedPageContext` — Seiten-Kontext für `tourEnv`. */
  pageContext: () => Record<string, any>;
  /** Globales `isLoading`-Flag der Shell (Turn-Serialisierung). */
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  /** Message-State-Reducer der Shell (Signaturen unverändert). */
  addUserMessage: (content: string) => void;
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[],
    quickReplies?: string[], debug?: DebugInfo,
    pagination?: PaginationInfo | null, queryMetas?: QueryMetaEntry[],
    webLinks?: WebLink[], inlineDocuments?: InlineDocument[],
    displayRules?: Record<string, any>, topicPage?: TopicPageView | null,
  ) => string;
  removeMessage: (id: string) => void;
  /** Setzt `scrollTargetId` (konsumiert in `ngAfterViewChecked`). */
  setScrollTarget: (id: string) => void;
  /** Setzt `latestDebug` (Debug-Panel). */
  setLatestDebug: (debug: DebugInfo) => void;
}

export class TourController {
  /** Verhindert Doppel-Ticks pro Page-Load. */
  private _tourTicked = false;

  constructor(private readonly ctx: TourContext) {}

  isTourFlagSet(): boolean {
    try { return localStorage.getItem(TOUR_FLAG_KEY) === '1'; }
    catch { return false; }
  }

  setTourFlag(on: boolean): void {
    try {
      if (on) localStorage.setItem(TOUR_FLAG_KEY, '1');
      else localStorage.removeItem(TOUR_FLAG_KEY);
    } catch { /* ignore */ }
  }

  /** environment-Override für Tour-Requests (tour_action + page_context). */
  tourEnv(action: 'start' | 'tick'): any {
    const env: any = { tour_action: action };
    const pageContext = this.ctx.pageContext();
    if (Object.keys(pageContext).length) {
      env.page_context = pageContext;
    }
    return env;
  }

  /** Liest resp.tour und pflegt das localStorage-Flag.
   *  - `resp.tour` vorhanden → Flag = `tour.active`.
   *  - `resp.tour` FEHLT → es lief keine Tour mehr in dieser Antwort (z.B.
   *    der Nutzer hat mitten in der Tour etwas anderes getippt → Backend hat
   *    die Tour beendet und normal geantwortet). Flag sofort löschen, sonst
   *    würde das Widget bei der nächsten Navigation noch einmal fälschlich
   *    auto-öffnen. */
  applyTourState(resp: ChatResponse): void {
    const tour = (resp as any).tour;
    this.setTourFlag(!!(tour && typeof tour === 'object' && tour.active));
  }

  /** Rendert eine Tour-Bot-Antwort wie eine normale Bot-Bubble. */
  private renderTourResponse(resp: ChatResponse): void {
    const id = this.ctx.addBotMessage(
      resp.content, false, resp.cards, resp.quick_replies, resp.debug,
      resp.pagination, resp.query_metas, resp.web_links,
      resp.inline_documents, resp.display_rules, resp.topic_page,
    );
    this.ctx.setScrollTarget(id);
    this.ctx.setLatestDebug(resp.debug);
  }

  /** Startet die geführte Web-Tour (Klick auf den Startbutton). */
  async startTour(): Promise<void> {
    if (this.ctx.isLoading()) return;
    this.ctx.addUserMessage(TOUR_START_LABEL);
    this.ctx.setLoading(true);
    const loadingId = this.ctx.addBotMessage('', true);
    this.ctx.setScrollTarget(loadingId);
    try {
      const resp = await this.ctx.sendMessage('Web-Tour starten', this.tourEnv('start'));
      this.ctx.removeMessage(loadingId);
      this.setTourFlag(true);
      this.applyTourState(resp);
      this.renderTourResponse(resp);
    } catch {
      this.ctx.removeMessage(loadingId);
      this.ctx.addBotMessage('Entschuldigung, die Tour konnte gerade nicht gestartet werden. Bitte versuch es nochmal.');
    }
    this.ctx.setLoading(false);
  }

  /** Unsichtbarer Tour-Tick beim Page-Load: meldet die aktuelle Seite ohne
   *  User-Bubble. Rendert nur die Bot-Antwort, falls sie Inhalt hat. */
  async sendTourTick(): Promise<void> {
    if (this.ctx.isLoading() || this._tourTicked) return;
    this._tourTicked = true;
    this.ctx.setLoading(true);
    const loadingId = this.ctx.addBotMessage('', true);
    this.ctx.setScrollTarget(loadingId);
    try {
      const resp = await this.ctx.sendMessage('[tour-tick]', this.tourEnv('tick'));
      this.ctx.removeMessage(loadingId);
      this.applyTourState(resp);
      const hasContent = !!(resp.content || '').trim()
        || !!(resp.quick_replies && resp.quick_replies.length);
      if (hasContent) this.renderTourResponse(resp);
    } catch {
      this.ctx.removeMessage(loadingId);
      // Tick-Fehler beim Page-Load still schlucken (kein Error-Bubble).
    }
    this.ctx.setLoading(false);
  }
}
