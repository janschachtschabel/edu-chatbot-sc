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
import type { TranslateFn } from '../i18n/i18n';
import { deleteSessionCookie, generateSessionId, writeSessionEverywhere } from '../session/session-id';
import { ChatApiClient } from '../stream/chat-api';
import { restoreHistory } from './history-restore';
import { bootSession } from './session-boot';

/** Katalog-Schlüssel der vier Einstiegs-Quick-Replies (ALT 337-342) — greifen
 *  nur, wenn `startReplies` leer ist. Die Reihenfolge ist die von ALT. */
const DEFAULT_REPLY_KEYS = [
  'greeting.reply.aiAge',
  'greeting.reply.search',
  'greeting.reply.tour',
  'greeting.reply.about',
];

/**
 * Welche Backend-Seitenarten das Ping-Gate unten erreichen soll. Ein
 * Backend-Test liest DIESE Liste und vergleicht sie mit `_GREETABLE_KINDS` —
 * kommt dort eine Art dazu, ohne dass das Gate sie erreicht, meldet er sich.
 * Ohne den Abgleich passierte einfach still gar nichts.
 *
 * ACHTUNG, nicht offensichtlich: `home` und `external` setzt der Erkenner NIE
 * — die entscheidet das Backend am Hostnamen, und beim Erkenner heissen sie
 * `other`. Das Gate darf sie deshalb nicht abfragen, sondern muss den
 * unentschiedenen Fall durchlassen.
 */
export const PING_COVERS_BACKEND_KINDS = [
  'collection', 'content', 'topic', 'search', 'home', 'external',
] as const;

/**
 * Ist diese Seite einen Kontext-Ping wert? „Könnte begrüßbar sein", nicht „ist
 * begrüßbar" — die endgültige Entscheidung trifft das Backend.
 *
 * Ein Ping, den das Backend leer beantwortet, kostet einen Rundlauf; ein Ping,
 * der ausbleibt, kostet die Meldung ganz. Deshalb hier grosszügig, aber nicht
 * blind: ohne Suchbegriff bzw. ohne Hostnamen kann das Backend nichts sagen.
 */
export function shouldSendContextPing(pc: Record<string, any>): boolean {
  if (pc['collection_id'] || pc['node_id']) return true;
  const kind = pc['page_kind'];
  if (kind === 'collection' || kind === 'content' || kind === 'topic') return true;
  if (kind === 'search') return !!pc['search_query'];
  // Unentschieden: hier — und nur hier — entscheidet der Hostname zwischen
  // eigener Startseite und fremder Seite.
  if (!kind || kind === 'other') return !!pc['page_host'];
  return false;  // `subject` (Fachportal) bleibt bewusst stumm.
}

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
  /** `show-welcome` — soll es die statische Startnachricht überhaupt geben?
   *  `false` heißt: leerer Chat. Betrifft NUR sie; die Kontext-Begrüßung des
   *  Backends hat ihren eigenen Weg (Seitenkontext) und bleibt unberührt. */
  showWelcome: () => boolean;
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
  /** Übersetzer für die Rückfall-Begrüßungen (C1-b4). Sie greifen nur, wenn
   *  Host bzw. Studio-Config nichts liefern — der redaktionelle Regelfall
   *  bleibt deutsch (Zweisprachigkeit der Config ist bewusst vertagt). */
  t: TranslateFn;
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
      void this._greetOnFirstLoad();
      this._maybeStartTourTick();
    }
  }

  /** Zentrale Begrüßung mit Einstiegs-Quick-Replies. Verbatim aus ALT 322-344,
   *  davor das Tor aus `show-welcome` (2026-08-14).
   *
   *  Der Ausstieg sitzt HIER und nicht bei den drei Aufrufern, weil sie alle
   *  dasselbe meinen — Erstaufruf, Neustart, leerer Verlauf. Ein Tor je
   *  Aufrufer wäre dreimal dieselbe Bedingung und beim vierten vergessen. */
  showGreeting(): void {
    if (!this.ctx.showWelcome()) return;
    const text = this.ctx.greeting() || this.ctx.t('greeting.default');
    const replies = (this.ctx.startReplies() && this.ctx.startReplies().length)
      ? this.ctx.startReplies()
      : DEFAULT_REPLY_KEYS.map(k => this.ctx.t(k));
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
    // Eigener Text (`greeting.reset`), deshalb ein eigenes Tor — geleert wird
    // trotzdem, nur die Nachricht bleibt aus.
    if (!this.ctx.showWelcome()) return;
    this.ctx.addBotMessage(this.ctx.greeting() || this.ctx.t('greeting.reset'));
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

  /** Session-gated Kontext-Ping, wenn die Seite einen wert ist. Kein Auto-Open. */
  private _maybeSendContextPing(): void {
    if (!shouldSendContextPing(this.ctx.parsedPageContext() || {})) return;
    setTimeout(() => this.ctx.contextGreeting.sendContextPing(), 0);
  }

  /** Erstaufruf: die Begrüßung zurückstellen, bis der Kontext-Ping geantwortet
   *  hat. Hat er Inhalt, IST er die Begrüßung; sonst kommt die normale. So
   *  sieht die Person in JEDEM Fall genau eine Nachricht — auch wenn der Ping
   *  leer bleibt oder scheitert (Ansatz C aus dem Plan; A hätte bei Ping-
   *  Ausfall gar keine Begrüßung ergeben, B ein sichtbares Flackern).
   *
   *  Während der Ping läuft, ist der Verlauf leer — das Eingabefeld steht
   *  derweil auf `chat.input.thinking` und ist gesperrt (`isLoading`), die
   *  Wartezeit ist also sichtbar und nicht als Fehler lesbar. */
  private async _greetOnFirstLoad(): Promise<void> {
    // Läuft eine Tour, gehört ihr die erste Nachricht; der Kontext-Ping würde
    // über `isLoading` mit dem Tour-Tick kollidieren (dieselbe Sequenzierung
    // wie im Resume-Pfad).
    const tourOwnsTheOpener = this.ctx.tour.isTourFlagSet() || this.ctx.resumedViaBsid();
    if (tourOwnsTheOpener || !shouldSendContextPing(this.ctx.parsedPageContext() || {})) {
      this.showGreeting();
      return;
    }
    let rendered = false;
    try {
      rendered = await this.ctx.contextGreeting.sendContextPing('context_open_initial');
    } catch {
      // Ping-Fehler still schlucken — aber NIE ohne Begrüßung dastehen.
    }
    if (!rendered) this.showGreeting();
  }

  private _cookieCfg() {
    return {
      sessionKey: this.ctx.sessionKey(),
      cookieDomain: this.ctx.sessionCookieDomain(),
      cookieMaxAge: this.ctx.sessionCookieMaxAge(),
    };
  }
}
