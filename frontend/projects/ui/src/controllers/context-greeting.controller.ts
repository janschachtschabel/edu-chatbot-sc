/**
 * Kontext-Begrüßungs-Ping (Seitenkontext-Feature) — Verbatim-Port aus ALT
 * `chat/context-greeting.controller.ts`. Gegenstück zu `TourController` für die
 * proaktive, backend-getriebene Begrüßung, wenn der Nutzer eine Session auf
 * einer erkannten WLO-Seite (Sammlung/Inhalt/Themenseite) fortsetzt. NEU:
 * Imports umgehängt (`WloCard` → `../cards`, Response-Modell →
 * `../grouping/message-types`); Bodies unverändert.
 *
 * Ablauf: beim Fortsetzen feuert die Shell EINEN unsichtbaren Ping
 * (`sendContextPing`) mit `env.page_event='context_open'` — ohne User-Bubble.
 * Das Backend entscheidet session-gated, ob es begrüßt; nur bei Inhalt wird
 * eine Bot-Bubble gerendert. Kein Auto-Open. Ping-Guard `_pinged` ist
 * Per-Page-Load-State; Live-Zustand kommt als `ContextGreetingContext`.
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

/** Live-Zustand/Seiteneffekte der Chat-Shell, die der Kontext-Ping braucht. */
export interface ContextGreetingContext {
  /** `ApiService.sendMessage` mit LIVE-`sessionId` der Shell. */
  sendMessage: (message: string, env: any) => Promise<ChatResponse>;
  /** `parsedPageContext` — Seiten-Kontext für den Ping. */
  pageContext: () => Record<string, any>;
  /** Globales `isLoading`-Flag der Shell (Turn-Serialisierung). */
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[],
    quickReplies?: string[], debug?: DebugInfo,
    pagination?: PaginationInfo | null, queryMetas?: QueryMetaEntry[],
    webLinks?: WebLink[], inlineDocuments?: InlineDocument[],
    displayRules?: Record<string, any>, topicPage?: TopicPageView | null,
  ) => string;
  removeMessage: (id: string) => void;
  setScrollTarget: (id: string) => void;
  setLatestDebug: (debug: DebugInfo) => void;
}

export class ContextGreetingController {
  /** Verhindert Doppel-Pings pro Page-Load. */
  private _pinged = false;

  constructor(private readonly ctx: ContextGreetingContext) {}

  /** Erlaubt einen erneuten Ping — z.B. nach SPA-Navigation auf eine neue
   *  Seite. Das Backend dedupliziert pro Seite, sodass eine bereits begrüßte
   *  Seite auch nach dem Reset leer bleibt. */
  resetForNewPage(): void {
    this._pinged = false;
  }

  /** Unsichtbarer Kontext-Ping: fragt eine proaktive Begrüßung an, OHNE eine
   *  User- ODER Loading-Bubble zu erzeugen. Das ist ein Hintergrund-Ping —
   *  ein Spinner wäre falsche UX, und ein Loading-Bubble würde bei bereits
   *  begrüßten Seiten (Backend liefert leer) kurz aufflackern. Die Begrüßung
   *  erscheint still nur dann, wenn die Antwort tatsächlich Inhalt hat.
   *  `isLoading` bleibt gesetzt (Turn-Serialisierung wie beim Tour-Tick).
   *
   *  `event` sagt dem Backend, WELCHER Fall vorliegt: beim Fortsetzen ist eine
   *  leere History das Zeichen für einen verirrten Ping, beim ersten Laden ist
   *  sie der Normalzustand. Nur der Fortsetzungs-Fall wird dort noch daran
   *  gemessen.
   *
   *  Rückgabe: ob eine Nachricht gerendert wurde. Der Erstaufruf-Pfad hängt
   *  seine Standard-Begrüßung daran auf — so sieht die Person in jedem Fall
   *  genau eine Nachricht. */
  async sendContextPing(
    event: 'context_open' | 'context_open_initial' = 'context_open',
  ): Promise<boolean> {
    if (this.ctx.isLoading() || this._pinged) return false;
    this._pinged = true;
    this.ctx.setLoading(true);
    let rendered = false;
    try {
      const resp = await this.ctx.sendMessage('[context-open]', {
        page_event: event,
        page_context: this.ctx.pageContext(),
      });
      const hasContent = !!(resp.content || '').trim()
        || !!(resp.quick_replies && resp.quick_replies.length);
      if (hasContent) {
        const id = this.ctx.addBotMessage(
          resp.content, false, resp.cards, resp.quick_replies, resp.debug,
          resp.pagination, resp.query_metas, resp.web_links,
          resp.inline_documents, resp.display_rules, resp.topic_page,
        );
        this.ctx.setScrollTarget(id);
        this.ctx.setLatestDebug(resp.debug);
        rendered = true;
      }
    } catch {
      // Ping-Fehler still schlucken (kein Error-Bubble). Beim Erstaufruf holt
      // der Aufrufer daraufhin die normale Begrüßung nach.
    }
    this.ctx.setLoading(false);
    return rendered;
  }
}
