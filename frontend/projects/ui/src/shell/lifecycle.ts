/**
 * Shell-Lifecycle (8-4S-e4) — die Lebenszyklus-Orchestrierung der Chat-Shell aus
 * ALT `ngOnInit`/`showGreeting`/`restart`/`resetSession`/`updateContext`/
 * `onSpaContextChange` (+ Resume-/Tour-Tick-/Kontext-Ping-Sequenzierung), hinter
 * einem `LifecycleContext` gebündelt, damit die Komponente nur dünne Angular-Hooks
 * + Public-API-Delegates hält. Nutzt die bereits gepinnten Bausteine
 * session-boot/history-restore + die Controller (tour/context-greeting). Bodies
 * verbatim aus ALT chat.component.ts (258-315, 322-344, 402-415, 717-766,
 * 1262-1270). KEINE Logik-Änderung.
 */
import { WloCard } from '../cards/card-types';
import { ContextGreetingController } from '../controllers/context-greeting.controller';
import { TourController } from '../controllers/tour.controller';
import { ChatMessage, DebugInfo, PaginationInfo, QueryMetaEntry, WebLink } from '../grouping/message-types';
import { deleteSessionCookie, generateSessionId, writeSessionEverywhere } from '../session/session-id';
import { ChatApiClient } from '../stream/chat-api';
import { restoreHistory } from './history-restore';
import { bootSession } from './session-boot';

/** Default-Begrüßungstext (ALT 328-331) — das `greeting`-Input überschreibt ihn. */
const DEFAULT_GREETING =
  'Hey, schön dass du da bist! Ich bin Boerdi, die schlaue Eule von '
  + 'WissenLebtOnline.\nIch kann dir zeigen, wie du deine Wissens- oder '
  + 'Lerninhalte ins KI-Zeitalter bringst? Oder ich kann dir helfen '
  + 'vorhandene Inhalte in unserer Datenbasis zu finden.';

/** Default-Einstiegs-Quick-Replies (ALT 337-342) — `startReplies` überschreibt. */
const DEFAULT_REPLIES = [
  'Wie bringe ich meine Inhalte ins KI-Zeitalter?',
  'Ich suche Inhalte zu einem Thema.',
  'Führe mich systematisch durch die Webseite.',
  'Was ist WissenLebtOnline?',
];

/** Kürzere Reset-Begrüßung (ALT 409). */
const DEFAULT_RESET_GREETING = 'Hallo! Wie kann ich dir helfen?';

/** Live-Zustand/Aktionen der Shell, die der Lifecycle braucht (deferred Arrows +
 *  die Controller-Instanzen). Muster `ShellHost`/`SendMessageContext`. */
export interface LifecycleContext {
  api: () => ChatApiClient;
  // ── Widget-Inputs (live gelesen) ──
  apiUrl: () => string;
  pageContextInput: () => string | Record<string, any>;
  persistSession: () => boolean | string;
  sessionKey: () => string;
  sessionCookieDomain: () => string;
  sessionCookieMaxAge: () => number | string;
  greeting: () => string;
  startReplies: () => string[];
  // ── Session-Zustand ──
  sessionId: () => string;
  setSessionId: (id: string) => void;
  resumedViaBsid: () => boolean;
  setResumedViaBsid: (v: boolean) => void;
  // ── Seitenkontext ──
  parsedPageContext: () => Record<string, any>;
  setParsedPageContext: (ctx: Record<string, any>) => void;
  // ── Sprach-Capability ──
  setSpeechEnabled: (v: boolean) => void;
  // ── Message-API ──
  setMessages: (msgs: ChatMessage[]) => void;
  updateMessages: (updater: (msgs: ChatMessage[]) => ChatMessage[]) => void;
  addUserMessage: (content: string) => void;
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[], quickReplies?: string[],
    debug?: DebugInfo, pagination?: PaginationInfo | null,
    queryMetas?: QueryMetaEntry[], webLinks?: WebLink[],
  ) => string;
  setLatestDebug: (d: DebugInfo | null) => void;
  // ── Controller + Scroll ──
  tour: TourController;
  contextGreeting: ContextGreetingController;
  scrollToLatest: () => void;
}

export class ShellLifecycle {
  constructor(private readonly ctx: LifecycleContext) {}

  /** `ngOnInit`: Base-URL, Speech-Probe, pageContext-Parse, 3-Stufen-Session-
   *  Kaskade, dann Resume (History + afterResume) oder frische Begrüßung + Tour-
   *  Tick. Verbatim aus ALT 258-315. */
  init(): void {
    const apiUrl = this.ctx.apiUrl();
    if (apiUrl) this.ctx.api().setBaseUrl(apiUrl);

    // Speech-Capability optimistisch: fire-and-forget, UI startet mit Buttons.
    this.ctx.api().getSpeechEnabled()
      .then((ok) => { this.ctx.setSpeechEnabled(ok); })
      .catch(() => { /* optimistisch sichtbar lassen */ });

    const pc = this.ctx.pageContextInput();
    if (typeof pc === 'string' && pc.trim()) {
      try { this.ctx.setParsedPageContext(JSON.parse(pc)); }
      catch { this.ctx.setParsedPageContext({ raw: pc }); }
    } else if (typeof pc === 'object' && pc) {
      this.ctx.setParsedPageContext(pc as Record<string, any>);
    }

    const persist = this.ctx.persistSession() === true || this.ctx.persistSession() === 'true';
    const boot = bootSession({
      persist,
      sessionKey: this.ctx.sessionKey(),
      cookieDomain: this.ctx.sessionCookieDomain(),
      cookieMaxAge: this.ctx.sessionCookieMaxAge(),
    });
    this.ctx.setSessionId(boot.sessionId);
    if (boot.viaBsid) this.ctx.setResumedViaBsid(true);

    if (boot.resumed) {
      // Fortgeführte Session: History laden, dann Tour prüfen/fortsetzen.
      this._restoreHistory().then(() => this._afterResume());
    } else {
      this.showGreeting();
      this._maybeStartTourTick();
    }
  }

  /** Zentrale Begrüßung mit Einstiegs-Quick-Replies. Verbatim aus ALT 322-344. */
  showGreeting(): void {
    const text = this.ctx.greeting() || DEFAULT_GREETING;
    const replies = (this.ctx.startReplies() && this.ctx.startReplies().length)
      ? this.ctx.startReplies()
      : DEFAULT_REPLIES;
    this.ctx.addBotMessage(text, false, undefined, replies);
  }

  /** Frische Session + Begrüßung (Header-Restart). Verbatim aus ALT 1262-1270. */
  restart(): void {
    const id = generateSessionId();
    this.ctx.setSessionId(id);
    writeSessionEverywhere(id, this._cookieCfg());
    this.ctx.setMessages([]);
    this.ctx.setLatestDebug(null);
    this.showGreeting();
  }

  /** Public API: Session leeren und frisch starten. Verbatim aus ALT 402-410. */
  resetSession(): void {
    try { localStorage.removeItem(this.ctx.sessionKey()); } catch { /* ignore */ }
    deleteSessionCookie(this.ctx.sessionKey(), this.ctx.sessionCookieDomain());
    const id = generateSessionId();
    this.ctx.setSessionId(id);
    writeSessionEverywhere(id, this._cookieCfg());
    this.ctx.setMessages([]);
    this.ctx.setLatestDebug(null);
    this.ctx.addBotMessage(this.ctx.greeting() || DEFAULT_RESET_GREETING);
  }

  /** Public API: Seitenkontext zur Laufzeit ergänzen (SPA ohne Reload).
   *  Verbatim aus ALT 413-415. */
  updateContext(c: Record<string, any>): void {
    this.ctx.setParsedPageContext({ ...this.ctx.parsedPageContext(), ...c });
  }

  /** SPA-Navigation: Seitenkontext ERSETZEN (nicht mergen — stale IDs raus),
   *  Ping-Gate zurücksetzen, adressierbare Seite → Kontext-Begrüßung anbieten.
   *  Verbatim aus ALT 746-753. */
  onSpaContextChange(newContext: Record<string, any>): void {
    this.ctx.setParsedPageContext({ ...newContext });
    this.ctx.contextGreeting.resetForNewPage();
    this._maybeSendContextPing();
  }

  /** History-Restore mit einem aus dem Lifecycle-Kontext gebauten Sub-Kontext. */
  private _restoreHistory(): Promise<void> {
    return restoreHistory({
      loadHistory: (sid, limit) => this.ctx.api().loadHistory(sid, limit),
      sessionId: () => this.ctx.sessionId(),
      showGreeting: () => this.showGreeting(),
      updateMessages: (u) => this.ctx.updateMessages(u),
      addUserMessage: (content) => this.ctx.addUserMessage(content),
      addBotMessage: (...args) => this.ctx.addBotMessage(...args),
      scrollToLatest: () => this.ctx.scrollToLatest(),
    });
  }

  /** Resumed-Pfad: erst Tour prüfen/fortsetzen (Flag ODER ?bsid=-Handoff),
   *  DANACH — nur wenn keine Tour aktiv — die Kontext-Begrüßung. Sequenziert
   *  (await), damit die Pings nicht über `isLoading` kollidieren. Verbatim 733-739. */
  private async _afterResume(): Promise<void> {
    if (this.ctx.tour.isTourFlagSet() || this.ctx.resumedViaBsid()) {
      try { await this.ctx.tour.sendTourTick(); } catch { /* Tick-Fehler still */ }
    }
    if (!this.ctx.tour.isTourFlagSet()) {
      this._maybeSendContextPing();
    }
  }

  /** Nach (Re)Start: läuft eine Tour (Flag) ODER kam die Session per ?bsid=,
   *  EINEN Tick feuern, sobald der initiale Render durch ist. Verbatim 717-726. */
  private _maybeStartTourTick(): void {
    if (this.ctx.tour.isTourFlagSet() || this.ctx.resumedViaBsid()) {
      setTimeout(() => this.ctx.tour.sendTourTick(), 0);
    }
  }

  /** Session-gated Kontext-Ping, wenn die aktuelle Seite adressierbar ist
   *  (Sammlung/Inhalt/Themenseite). Kein Auto-Open. Verbatim aus ALT 759-766. */
  private _maybeSendContextPing(): void {
    const pc = this.ctx.parsedPageContext() || {};
    const kind = pc['page_kind'];
    const addressable = !!pc['collection_id'] || !!pc['node_id']
      || kind === 'collection' || kind === 'content' || kind === 'topic';
    if (!addressable) return;
    setTimeout(() => this.ctx.contextGreeting.sendContextPing(), 0);
  }

  private _cookieCfg() {
    return {
      sessionKey: this.ctx.sessionKey(),
      cookieDomain: this.ctx.sessionCookieDomain(),
      cookieMaxAge: this.ctx.sessionCookieMaxAge(),
    };
  }
}
