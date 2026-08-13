import {
  AfterViewChecked, ChangeDetectionStrategy, ChangeDetectorRef, Component, computed, effect,
  ElementRef, inject, input, OnChanges, OnDestroy, OnInit, output, signal, viewChild,
} from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';

import { CardListComponent } from '../cards/card-list.component';
import { resolveCardsVisible, SHOW_CARDS_MODES } from '../cards/cards-visible';
import { DebugPanelComponent } from '../debug/debug-panel.component';
import { _attrEnum, _attrIsTrue, PanelSizeStep } from '../element/attr';
import { ChatResponse, DebugInfo, PreparedWriteOut } from '../grouping/message-types';
import { ResultGroupsComponent } from '../grouping/result-groups.component';
import { SwimlanesComponent } from '../grouping/swimlanes.component';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { DEFAULT_LOCALE, Locale } from '../i18n/locale';
import { InlineDocumentsComponent } from '../inline-doc/inline-documents.component';
import { QuickRepliesComponent } from '../chips/quick-replies.component';
import { BOERDI_LOGO_DATA_URL } from '../branding/boerdi-logo';
import { SHELL_PRINT } from '../print/print-gates';
import { ChatApiClient } from '../stream/chat-api';
import { formatPhaseLabel } from '../stream/phase-label';
import {
  browseCollection, generateLearningPath, loadMore, showContentText, showMoreCards,
} from '../controllers/collection-actions';
import { ContextGreetingController } from '../controllers/context-greeting.controller';
import { TourController } from '../controllers/tour.controller';
import { SpeechService } from '../speech/speech.service';
import { CORE_TRUSTED_DOMAINS } from '../session/trusted-host';
import { runSignIn } from '../session/sign-in-flow';
import { authButtonState } from '../session/auth-button';
import { clearAccessBlock, readAccessBlock } from '../session/mcp-access';
import { runTicketLogin } from '../session/ticket-login';
import { runPreparedWrite } from '../session/prepared-write';
import {
  InputRoutingContext, guideQuickReplyTarget, resolveGuideNavTarget, routeQuickReply,
} from './input-routing';
import {
  GuideSuggestionPayload, RoutingDebugPayload, maybeDispatchGuideNavigate,
  maybeDispatchGuideSuggestion, maybeDispatchRoutingDebug,
} from '../host-events/host-events';
import { dispatchHostEvent, HOST_EVENTS } from '../host-events/event-names';
import { SendMessageContext, runSendMessage } from './send-message';
import { ControllerContexts, ShellHost, buildControllerContexts } from './shell-contexts';
import { LifecycleContext, ShellLifecycle } from './lifecycle';
import { MessageStore } from './message-store';
import { ScrollFollowController } from './scroll-follow';
import { ShellRender } from './shell-render';

/**
 * Chat-Shell-Komponente — der Integrator des Widget-Chats. RE-ARCHITEKTUR (kein
 * Verbatim): ALT `ChatComponent` ist ein 1480-Z.-Monolith; dessen Logik liegt
 * längst in Modulen (tour/context-greeting/collection-actions/speech/stream/
 * host-events/input-routing/lifecycle/scroll-follow/message-store/shell-render).
 * Hier bleiben nur: die Turn-Maschinerie (8-4S-d2a: `_host`-Seam [8-4S-d1] → 3
 * Controller, `SendMessageContext` [8-4S-c], `_onResult`), dünne Input-Routing-
 * Delegates (8-4S-d2b → `input-routing.ts`), die Lebenszyklus-/Scroll-Delegates
 * (8-4S-e) und die Template-Verdrahtung (8-4S-f: `render`/`print`-Sichten + die
 * Host-Flag-Getter, die das Row-Template liest).
 *
 * Zwei bewusste zoneless-Anpassungen ggü. ALT (kein Verhaltensunterschied):
 * `isLoading`/`latestDebug`/`showDebug`/`userInput` sind Signals statt plain
 * fields; der Verlauf lebt im `MessageStore` (8-4S-f0) statt in privaten
 * Component-Methoden — Bodies + Gates dort verbatim aus ALT :1273-1321.
 *
 * GRÖSSE: ~573 Z. — dokumentierte Ausnahme der ≤300-Invariante. Der Integrator
 * enthält KEINE Business-Logik (die liegt in Modulen), sondern nur: 4 deklarative
 * Wiring-Seam-Literale (`_host`/`_sendCtx`/`_routingCtx`/`_lifecycleCtx`, ~85 Z.),
 * die Template-Sicht (Sub-Komponenten-Imports + Flag-Getter + Delegates, ~90 Z.),
 * die Sammlungs-Aktions-Delegates (8-2i, ~30 Z.) und dünne Angular-Hooks/
 * Public-API-Delegates. Er liest top-to-bottom kohärent
 * und hat EINE Änderungs-Ursache: „die Verdrahtung der Shell ändert sich" (§3:
 * "split by responsibility, not line count"). Vor diesem Slice wurde der
 * State-Core planmäßig nach `message-store.ts` ausgelagert (8-4S-f0), damit das
 * Template nicht auf eine schon große Datei draufsattelt.
 */
@Component({
  selector: 'boerdi-chat-shell',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './chat-shell.component.html',
  styleUrl: './chat-shell.component.scss',
  imports: [
    SafeSvgPipe, CardListComponent, DebugPanelComponent, InlineDocumentsComponent,
    QuickRepliesComponent, ResultGroupsComponent, SwimlanesComponent,
  ],
})
export class ChatShellComponent implements OnInit, OnChanges, AfterViewChecked, OnDestroy {
  /** State-Core: Verlauf + Reducer (8-4S-b, Modul seit 8-4S-f0). */
  private readonly _store = new MessageStore();
  /** Nachrichten-Verlauf (bot/user Bubbles) — Single Source of Truth (Template). */
  readonly messages = this._store.messages;
  /** Turn-Serialisierung: true während ein Chat-Turn läuft. ALT: plain field. */
  readonly isLoading = signal(false);
  /** Letzter Debug-/Telemetrie-Block fürs Debug-Panel. ALT: plain field. */
  readonly latestDebug = signal<DebugInfo | null>(null);

  // ── Turn-/Integrations-Zustand (8-4S-d2a) ───────────────────────
  /** Session-ID des Chats (aufgelöst in `ngOnInit`, 8-4S-e; Tests setzen direkt). */
  sessionId = '';
  /** Rohtext des Eingabefelds. ALT: plain field; hier Signal (zoneless). */
  readonly userInput = signal('');
  /** Seiten-Kontext (JSON-Attribut/SPA-Watcher) — Envs für Tour/Ping/Turn. */
  private parsedPageContext: Record<string, any> = {};
  /** Backend-Sprach-Capability (STT/TTS). Optimistisch true; `ngOnInit` (8-4S-e)
   *  fragt `/speech/status` ab und korrigiert. Signal → zoneless-CD ohne markForCheck. */
  readonly speechBackendEnabled = signal(true);
  /** Session per Cross-Origin-`?bsid=`-Handoff übernommen (steuert den Tour-Tick). */
  private _resumedViaBsid = false;
  /** Sichtbarkeit des Debug-Panels. ALT: plain field. */
  readonly showDebug = signal(false);
  /** Host-Callback für page_action (neben Output + window-Event). */
  onPageAction: ((pa: { action: string; payload: any }) => void) | null = null;

  /** `[emit-guide-suggestion]` — passive Top-1-Emission (host-events). */
  readonly emitGuideSuggestion = input<boolean | string>(false);
  /** `[emit-routing-debug]` — Routing-Telemetrie-Emission (host-events). */
  readonly emitRoutingDebug = input<boolean | string>(false);
  /** Jede backend-`page_action` (Host- + Widget-Integration). */
  readonly pageAction = output<{ action: string; payload: any }>();
  /** Top-1-Lotsen-Treffer pro Turn (gated durch `emitGuideSuggestion`). */
  readonly guideSuggestion = output<GuideSuggestionPayload>();
  /** Routing-Telemetrie pro Turn (gated durch `emitRoutingDebug`). */
  readonly routingDebug = output<RoutingDebugPayload>();

  /** Exakter Start-Chip-Text, der die Web-Tour startet (statt zu senden).
   *  Studio-pflegbar (welcome-config.tour_reply); leer → kein Chip startet. */
  readonly tourReply = input('');
  /** C1-g1b: die englische Fassung desselben Chips. Die Weiche vergleicht
   *  gegen BEIDE, weil ein Sprachwechsel den Verlauf nicht nachuebersetzt. */
  readonly tourReplyEn = input('');
  /** C5-c2: Herkunft des MCP-Servers für die WLO-Anmeldung, aus dem
   *  öffentlichen Config-Bündel durchgereicht. Leer = keine Anmeldung möglich;
   *  der Chip sagt das dann, statt ein leeres Fenster zu öffnen. */
  readonly mcpAuthBase = input('');
  /** Ticket der Gastgeberseite (Attribut `ticket`, von der Hülle einmal
   *  eingesammelt und aus dem DOM getilgt). Nicht leer → stiller Tausch gegen
   *  einen Zugangsblock, sobald `mcpAuthBase` aus dem Config-Bündel da ist
   *  (`session/ticket-login.ts`). */
  readonly ticket = input('');
  /** Vom Widget durchgereichte Trusted-Hosts-Whitelist (Same-Tab-Nav-Gate). */
  readonly trustedHosts = input<string[]>([]);
  /** ALT-Compat-Konstante (seit Welle E immer true): Lotsen-Modus aktiv. */
  readonly guideModeActive = true;

  // ── Lebenszyklus-/Session-Inputs (8-4S-e) ───────────────────────
  /** API-Basis-URL (z.B. "https://api.wlo.de") — wird zu …/api normalisiert. */
  readonly apiUrl = input('');
  /** Optionaler Seitenkontext (JSON-String oder Objekt). */
  readonly pageContext = input<string | Record<string, any>>('');
  /** Session in localStorage/Cookie persistieren (Chat überlebt Page-Loads). */
  readonly persistSession = input<boolean | string>(true);
  /** Storage-/Cookie-Schlüssel der persistierten Session-ID. */
  readonly sessionKey = input('boerdi_session_id');
  /** Cookie-Domain fürs Cross-Subdomain-Sharing (leer = nur localStorage). */
  readonly sessionCookieDomain = input('');
  /** Cookie-Lebensdauer in Sekunden (Default 30 Tage). */
  readonly sessionCookieMaxAge = input<number | string>(30 * 24 * 60 * 60);
  /** Begrüßungstext-Override (leer → Studio-Config/Default). */
  readonly greeting = input('');
  /** Einstiegs-Quick-Replies (Studio-pflegbar; leer → hardkodierte Default-4). */
  readonly startReplies = input<string[]>([]);
  /** `show-language-buttons` — Host-Wunsch nach Mikro-/Vorlese-Buttons. Wirkt nur
   *  zusammen mit der Backend-Capability (siehe `languageButtonsVisible`). */
  readonly showLanguageButtons = input<boolean | string>(false);
  /** `show-debug-button` — Debug-Umschalter in der Panel-Kopfzeile (8-5c).
   *  Die Widget-Hülle liest `debugButtonVisible`, ALT `chatRef?.debugButtonVisible`. */
  readonly showDebugButton = input<boolean | string>(false);

  /** U2a — Größen-Umschalter in der Eingabezeile. Zwei getrennte Eingänge statt
   *  eines: `sizeToggleVisible` beantwortet „gibt es hier überhaupt etwas zu
   *  verändern" (rahmenlos und in der Studio-Vorschau: nein), `sizeStep` nur
   *  „wie heißt der Knopf gerade". Ein Eingang für beides wäre eine Zeichenkette
   *  mit zweitem, unsichtbarem Auftrag. */
  readonly sizeToggleVisible = input<boolean | string>(false);
  readonly sizeStep = input<PanelSizeStep>('small');
  /** Der Umschaltwunsch geht nach OBEN: die Maße kennt das Panel, nicht die
   *  Shell. Sie hält deshalb bewusst keinen eigenen Größen-Zustand. */
  readonly sizeToggle = output<void>();

  /** U2b — `show-cards`: `auto` (Vorgabe) | `always` | `never`. Entscheidet
   *  zusammen mit `sizeStep` und `inline-result-grouping`, welche der beiden
   *  vorhandenen Trefferdarstellungen greift. Siehe `resolveCardsVisible`. */
  readonly showCards = input('');

  /** Übersetzer der Hülle (C1-b2). Bewusst PFLICHT und nicht mit deutschem
   *  Default: eine vergessene Bindung wäre sonst eine still einsprachige
   *  Oberfläche statt eines Übersetzungsfehlers. Nur die Funktion, nicht die
   *  `I18n`-Instanz — die Shell übersetzt, sie schaltet nicht um. */
  readonly translate = input.required<TranslateFn>();
  /** Kurzform fürs Template. Als Arrow gebunden, damit `{{ t('…') }}` ohne
   *  `this` funktioniert; der Signal-Read liegt in `I18n.t` und macht jede
   *  Auswertung von selbst reaktiv. */
  protected readonly t = (key: string, params?: TranslationParams): string =>
    this.translate()(key, params);
  /** Aktive Sprache (C1-c). Die Shell übersetzt über `[translate]` — dieser
   *  Input trägt keinen Text, sondern das **Ereignis** Sprachwechsel: der
   *  Markdown-Cache muss dann fallen (siehe `ngOnChanges`). */
  readonly locale = input<Locale>(DEFAULT_LOCALE);

  private readonly _cdr = inject(ChangeDetectorRef);
  private readonly _sanitizer = inject(DomSanitizer);
  /** Template-Anker: Auto-Follow-Container + Eingabefeld fürs Refokussieren. */
  private readonly _inputField = viewChild<ElementRef<HTMLInputElement>>('inputField');
  private readonly _messagesContainer = viewChild<ElementRef<HTMLElement>>('messagesContainer');

  /** Chat-API-Client. Tests ersetzen ihn nach Konstruktion (Muster ALT
   *  `comp.api`-Swap) — deshalb liest der Host ihn deferred. baseUrl setzt
   *  `ngOnInit` (8-4S-e) aus `[apiUrl]`. */
  private _api = new ChatApiClient();

  /** Scroll-/Auto-Follow-Controller (8-4S-e2). Container-Seam = der Messages-
   *  ViewChild aus dem Row-Template. */
  private readonly _scroll = new ScrollFollowController({
    container: () => this._messagesContainer()?.nativeElement,
  });

  // ── Template-Sicht (8-4S-f3) ────────────────────────────────────
  // Das Row-Template liest ausschließlich über diese Felder/Getter — die Logik
  // liegt in `shell-render.ts` bzw. `print/print-gates.ts`.

  /** Render-/Link-Sicht: Markdown-Renderer + bsid/Trust + Renderer-Kontexte. */
  readonly render = new ShellRender({
    bypassSecurityTrustHtml: (html) => this._sanitizer.bypassSecurityTrustHtml(html),
    sessionId: () => this.sessionId,
    trustedDomains: () => this._effectiveTrustedDomains(),
    inlineResultGrouping: () => this.inlineResultGroupingBool,
    t: (key, params) => this.t(key, params),
  });
  /** Druck-Gates + -Trigger (Lernpfad-/Canvas-Leisten, InlineDocument-Box). */
  readonly print = SHELL_PRINT;
  /** Stabile Referenz für `[renderMarkdown]` der InlineDocument-Box — als Feld,
   *  damit OnPush nicht bei jedem CD-Tick einen neuen Input-Wert sieht. */
  readonly renderBotMarkdown = (content: string) => this.render.markdown(content, 'bot');
  /** Inline-SVG-Icons (kein Icon-Font → kein externer Request, DSGVO). */
  readonly ICONS = ICONS;
  /** Bot-Avatar als Inline-Data-URL (kein externes Asset). */
  readonly boerdiLogo = BOERDI_LOGO_DATA_URL;

  /** `inline-result-grouping` — Layout der Treffer: `true` (Default) rendert die
   *  Themenseiten-/Sammlungs-/Materialien-Boxen + Such-CTA, `false` den
   *  klassischen flachen Tile-Grid mit Pagination.
   *
   *  ABWEICHUNG von ALT (bewusst, Nutzer-Entscheid 2026-07-25): dort ist das seit
   *  Welle E eine auf `true` eingefrorene Compat-Hülle (chat.component.ts:201) —
   *  wodurch ALTs eigener Flat-Card-Block hinter `!inlineResultGroupingBool`
   *  unerreichbar wurde („Die View-Conditionals werden separat aufgeräumt").
   *  Hier wieder ein echtes Attribut, damit der 8-2i-Grid nutzbar ist; der
   *  Default `true` hält das Verhalten für alle bestehenden Embeds identisch. */
  readonly inlineResultGrouping = input<boolean | string>(true);

  // Welle-E-Compat-Hüllen: in ALT waren das Host-Attribute, seit Welle E sind
  // die Schalter entfernt und die Getter konstant (ALT 199-203). Bleiben als
  // benannte Gates im Template, damit die ALT-Bedingungen lesbar bleiben.
  readonly quickRepliesEnabledBool = true;
  readonly cardsEnabledBool = true;
  readonly hideCards = false;

  /** Aufgelöstes `inline-result-grouping` (Custom-Element-Attribute kommen als
   *  String herein — gleiche Koerzierung wie alle Bool-Attribute des Widgets). */
  get inlineResultGroupingBool(): boolean {
    return _attrIsTrue(this.inlineResultGrouping());
  }

  /** U2a — Größen-Umschalter zeigen? Gleiche Koerzierung wie oben. */
  get sizeToggleVisibleBool(): boolean {
    return _attrIsTrue(this.sizeToggleVisible());
  }

  /** Beschriftung des Größen-Knopfs — benennt das ZIEL, nicht den Ist-Zustand. */
  get sizeToggleLabel(): string {
    return this.t(this.sizeStep() === 'large' ? 'widget.size.smaller' : 'widget.size.larger');
  }

  /** U2b — Kacheln mit Vorschaubild (`true`) oder Textlinks in Boxen (`false`).
   *  Die Rangfolge steht in `resolveCardsVisible`; hier wird nur das
   *  Host-Attribut normalisiert. */
  get cardsVisible(): boolean {
    return resolveCardsVisible(
      this.sizeStep(),
      _attrEnum(this.showCards(), SHOW_CARDS_MODES, 'auto'),
      this.inlineResultGroupingBool,
    );
  }

  /** Mikro-/Vorlese-Buttons: Host-Wunsch UND Backend-Capability. Ohne die
   *  zweite Bedingung zeigte das Widget bei B-API-Anbindung ohne Speech
   *  Buttons, die nichts tun (ALT 1256-1259). */
  get languageButtonsVisible(): boolean {
    const hostWants = this.showLanguageButtons() === true || this.showLanguageButtons() === 'true';
    return hostWants && this.speechBackendEnabled();
  }

  /** Debug-Umschalter in der Panel-Kopfzeile sichtbar? Verbatim ALT
   *  chat.component.ts:1249-1252 — reiner Host-Wunsch, keine Capability
   *  dahinter (das Debug-Panel rendert clientseitig). */
  get debugButtonVisible(): boolean {
    return this.showDebugButton() === true || this.showDebugButton() === 'true';
  }

  // Speech-Zustand fürs Template + die Widget-Hülle (ALT 104-107 liest
  // `chatRef?.isSpeaking`): dünne Getter auf den SpeechService.
  get isRecording(): boolean { return this._speech.isRecording; }
  get isSpeaking(): boolean { return this._speech.isSpeaking; }
  get recordingSeconds(): number { return this._speech.recordingSeconds; }
  /** Vorlese-Automatik an? Liest die Widget-Kopfzeile für den Icon-Wechsel. */
  get autoSpeak(): boolean { return this._speech.autoSpeak; }

  /** Live-Accessor-Seam für die Controller-Contexts (8-4S-d1). Objekt-Literal
   *  deferred Arrows (Muster ALT `_collectionActionsCtx`): jeder Zugriff geht
   *  LIVE gegen den aktuellen Shell-Zustand. */
  private readonly _host: ShellHost = {
    api: () => this._api,
    sessionId: () => this.sessionId,
    pageContext: () => this.parsedPageContext,
    isLoading: () => this.isLoading(),
    setLoading: (v) => this.isLoading.set(v),
    messages: () => this.messages(),
    updateMessages: (u) => this._store.update(u),
    addUserMessage: (content) => this._store.addUserMessage(content),
    addBotMessage: (...args) => this._store.addBotMessage(...args),
    removeMessage: (id) => this._store.removeMessage(id),
    setScrollTarget: (id) => { this._scroll.setScrollTarget(id); },
    setLatestDebug: (debug) => this.latestDebug.set(debug),
    dispatchPageAction: (pa) => this.dispatchPageAction(pa),
    messagesContainer: () => this._messagesContainer()?.nativeElement,
    emitGuideSuggestion: () => this.emitGuideSuggestion(),
    emitRoutingDebug: () => this.emitRoutingDebug(),
    emitGuideSuggestionOutput: (p) => this.guideSuggestion.emit(p),
    emitRoutingDebugOutput: (p) => this.routingDebug.emit(p),
    // Zoneless-Äquivalent zu ALT `NgZone.run`: fn ausführen, dann re-rendern.
    runInZone: (fn) => { try { return fn(); } finally { this._cdr.markForCheck(); } },
    onTranscript: (text) => { this.userInput.set(text); this.sendMessage(); },
    t: (key, params) => this.t(key, params),
  };

  private readonly _contexts: ControllerContexts = buildControllerContexts(this._host);
  private readonly _tour = new TourController(this._contexts.tour);
  private readonly _contextGreeting = new ContextGreetingController(this._contexts.contextGreeting);
  private readonly _speech = new SpeechService(this._contexts.speech);

  /** Lebenszyklus-Seam (8-4S-e4). Objekt-Literal deferred Arrows (Muster `_host`);
   *  jeder Zugriff geht LIVE gegen den aktuellen Shell-Zustand/Input. */
  private readonly _lifecycleCtx: LifecycleContext = {
    api: () => this._api,
    apiUrl: () => this.apiUrl(),
    pageContextInput: () => this.pageContext(),
    persistSession: () => this.persistSession(),
    sessionKey: () => this.sessionKey(),
    sessionCookieDomain: () => this.sessionCookieDomain(),
    sessionCookieMaxAge: () => this.sessionCookieMaxAge(),
    greeting: () => this.greeting(),
    startReplies: () => this.startReplies(),
    sessionId: () => this.sessionId,
    setSessionId: (id) => { this.sessionId = id; },
    resumedViaBsid: () => this._resumedViaBsid,
    setResumedViaBsid: (v) => { this._resumedViaBsid = v; },
    parsedPageContext: () => this.parsedPageContext,
    setParsedPageContext: (ctx) => { this.parsedPageContext = ctx; },
    setSpeechEnabled: (v) => this.speechBackendEnabled.set(v),
    setMessages: (msgs) => this._store.set(msgs),
    updateMessages: (u) => this._store.update(u),
    addUserMessage: (content) => this._store.addUserMessage(content),
    addBotMessage: (...args) => this._store.addBotMessage(...args),
    setLatestDebug: (d) => this.latestDebug.set(d),
    tour: this._tour,
    contextGreeting: this._contextGreeting,
    scrollToLatest: () => this._scroll.scrollToLatest(),
    t: (key, params) => this.t(key, params),
  };
  private readonly _lifecycle = new ShellLifecycle(this._lifecycleCtx);

  /** Turn-Lebenszyklus-Seam (8-4S-c). */
  private readonly _sendCtx: SendMessageContext = {
    currentInput: () => this.userInput(),
    clearInput: () => this.userInput.set(''),
    isLoading: () => this.isLoading(),
    setLoading: (v) => this.isLoading.set(v),
    addUserMessage: (content) => this._store.addUserMessage(content),
    addBotMessage: (...args) => this._store.addBotMessage(...args),
    removeMessage: (id) => this._store.removeMessage(id),
    updateLoadingPhase: (id, label) => this._store.updateLoadingPhase(id, label),
    setScrollTarget: (id) => { this._scroll.setScrollTarget(id); },
    focusInput: () => this.focusInput(),
    pageContextEnv: () => Object.keys(this.parsedPageContext).length
      ? { page_context: this.parsedPageContext } : undefined,
    stream: (msg, onEvent, env, action, actionParams) =>
      this._api.stream(this.sessionId, msg, onEvent, env as any, action, actionParams),
    post: (msg, env, action, actionParams) =>
      this._api.post(this.sessionId, msg, env as any, action, actionParams),
    formatPhaseLabel: (evt) => formatPhaseLabel(evt, (k, p) => this.t(k, p)),
    onResult: (resp, msg) => this._onResult(resp, msg),
    t: (key, params) => this.t(key, params),
  };

  /** Input-Routing-Seam (8-4S-d2b). */
  private readonly _routingCtx: InputRoutingContext = {
    tourReply: () => this.tourReply(),
    tourReplyEn: () => this.tourReplyEn(),
    guideModeActive: this.guideModeActive,
    trustedDomains: () => this._effectiveTrustedDomains(),
    sessionId: () => this.sessionId,
    startTour: () => { this.startTour(); },
    // Der Klick IST die Nutzergeste, ohne die der Browser das Anmeldefenster
    // blockt — deshalb wird hier synchron gestartet und nicht erst nach einem
    // Rundlauf zum Backend. `void`, weil der Vorgang sein Ergebnis selbst in
    // den Verlauf schreibt; die Weiche wartet nicht darauf.
    signIn: () => { this._signInAndRefresh(); },
    // Spread erhält die Aufruf-Arität (1 Arg für Text/Label, 3 für Action-Pill),
    // sonst würden trailing `undefined` weitergereicht — verhaltensgleich, aber
    // die Aufrufer-Signatur bliebe unsauber.
    sendMessage: (...args) => { this.sendMessage(...args); },
  };

  // ── Turn-Ausführung (8-4S-d2a) ──────────────────────────────────
  /** Einen Chat-Turn senden. `text` leer → Eingabefeld; optionale Direct-
   *  Action (Card-Buttons/Action-Pills). Delegiert an den Orchestrator (8-4S-c),
   *  der Stream/Fallback/Fehler abwickelt und `_onResult` als Erfolgs-Hook ruft. */
  sendMessage(text?: string, action?: string, actionParams?: Record<string, any>): Promise<void> {
    return runSendMessage(text, action, actionParams, this._sendCtx);
  }

  /** Erfolgs-Seiteneffekte eines Turns — ALT `sendMessage`-Tail (522-560):
   *  Tour-Flag pflegen (getippte Trigger-Phrase startet die Tour über diesen
   *  Pfad), Debug-Panel füttern, query-meta broadcasten, page_action
   *  weiterreichen, Host-Events (Lotsen-Navigate/Suggestion/Routing) feuern und
   *  bei aktivem autoSpeak die Antwort vorlesen. */
  private _onResult(resp: ChatResponse, userMessage: string): void {
    this._tour.applyTourState(resp);
    this.latestDebug.set(resp.debug);
    if (resp.query_metas?.length) {
      dispatchHostEvent(HOST_EVENTS.queryMeta, { queries: resp.query_metas });
    }
    this.dispatchPageAction(resp.page_action);
    maybeDispatchGuideNavigate(userMessage, resp.cards, this._contexts.hostEvents);
    maybeDispatchGuideSuggestion(userMessage, resp.cards, this._contexts.hostEvents);
    maybeDispatchRoutingDebug(userMessage, resp.debug, this._contexts.hostEvents);
    if (resp.prepared_write) this._executePreparedWrite(resp.prepared_write);
    if (this._speech.autoSpeak && resp.content) {
      this._speech.autoSpeakText(resp.content);
    }
  }

  /** Die eine bestätigte Änderung absetzen, die dieser Zug mitgebracht hat (E4).
   *
   *  Absichtlich NICHT abgewartet: der Zug ist zu Ende, seine Antwort steht schon
   *  im Verlauf, und das Eingabefeld darf nicht auf ein fremdes Repositorium
   *  warten. Der Vorgang schreibt sein Ergebnis selbst als Blase — in jedem der
   *  fünf Fälle, auch im gescheiterten (`session/prepared-write.ts`). */
  private _executePreparedWrite(write: PreparedWriteOut): void {
    runPreparedWrite(write, {
      origin: () => (typeof window !== 'undefined' ? window.location?.origin || '' : ''),
      say: (text) => { this._store.addBotMessage(text); this._cdr.markForCheck(); },
      translate: (key, params) => this.t(key, params),
      // Der Vorgang fängt alles Eigene ab und endet immer in einem Satz. Bleibt
      // nur, was hier hereingereicht wird — dann gäbe es ohne diesen Zweig eine
      // unbeachtete Zusage statt eines Eintrags, dem jemand nachgehen kann.
    }).catch(err => console.error('vorbereitete Änderung: Vorgang gescheitert', err));
  }

  /** page_action an alle Hörer: Host-Callback + Angular-Output + window-Event.
   *  MUSS aus jedem API-Pfad laufen, sonst aktualisiert die Canvas nicht.
   *  Verbatim aus ALT chat.component.ts:1075-1080. */
  private dispatchPageAction(pa: { action: string; payload: any } | null | undefined): void {
    if (!pa) return;
    if (this.onPageAction) this.onPageAction(pa);
    this.pageAction.emit(pa);
    dispatchHostEvent(HOST_EVENTS.pageAction, pa);
  }

  /** Eingabefeld refokussieren — nach jedem Turn (intern) und wenn die
   *  Widget-Hülle das Panel öffnet (ALT `chatRef?.inputField?.…focus()`;
   *  hier eine Methode statt eines öffentlichen ViewChild). */
  focusInput(): void {
    setTimeout(() => this._inputField()?.nativeElement?.focus(), 100);
  }

  // ── Input-Routing (8-4S-d2b) ────────────────────────────────────
  // Weiche + T-3-Resolver in `input-routing.ts`; hier dünne Delegates über den
  // `_routingCtx`. Der window-Sprung bleibt hier (Seiteneffekt der Komponente).

  /** WLO-Anmeldung starten (Klick auf den `__auth__`-Chip, C5-c2). Der Ausgang
   *  landet als Bot-Blase im Verlauf — die Live-Region der Nachrichtenliste
   *  sagt ihn damit auch ohne Blick auf den Bildschirm an. */
  private startSignIn(): Promise<void> {
    return runSignIn({
      mcpAuthBase: () => this.mcpAuthBase(),
      apiUrl: () => this.apiUrl(),
      origin: () => (typeof window !== 'undefined' ? window.location?.origin || '' : ''),
      say: (text) => { this._store.addBotMessage(text); },
      translate: (key, params) => this.t(key, params),
    });
  }

  /** Ob ein Zugangsblock hinterlegt ist. Ein Signal, weil `sessionStorage`
   *  keine kennt: ohne es bliebe der Knopf im zoneless Betrieb nach dem
   *  Abmelden auf „Abmelden" stehen. Gesetzt beim Bau (der Block überlebt das
   *  Neuladen des Tabs) und nach jedem An-/Abmelden. */
  private readonly _hasAccessBlock = signal(readAccessBlock() !== null);

  /** Welches Ticket schon getauscht wurde — der Effect unten feuert bei jedem
   *  Signal-Lauf, der Tausch soll je Wert genau einmal laufen. */
  private _ticketTried = '';

  /** Anmeldung über das Ticket der Gastgeberseite (Attribut `ticket`).
   *
   *  Ein Effect und kein `ngOnInit`-Schritt, weil die zweite Zutat später
   *  kommt: `mcpAuthBase` beginnt leer und wird erst vom Config-Abruf der
   *  Hülle gesetzt. Still, mit Absicht — der Knopf zeigt das Ergebnis, und
   *  ein Fehlschlag lässt ihn auf „Anmelden" stehen (Rückfall auf die
   *  Handanmeldung); die `console.warn`-Zeile ist für die Betreiberseite,
   *  deren Ticket-Template sonst unbemerkt abgelaufen bliebe. */
  private readonly _ticketLogin = effect(() => {
    const ticket = this.ticket().trim();
    const basis = this.mcpAuthBase().trim();
    if (!ticket || !basis || this._ticketTried === ticket) return;
    this._ticketTried = ticket;
    void runTicketLogin({ ticket: () => ticket, mcpAuthBase: () => basis }).then((ausgang) => {
      if (ausgang === 'done') {
        this._hasAccessBlock.set(readAccessBlock() !== null);
        this._cdr.markForCheck();
      } else {
        console.warn('WLO-Anmeldung über das Seiten-Ticket nicht gelungen:', ausgang);
      }
    });
  });

  /** Was der Knopf in der Fußzeile zeigt — Entscheidung in `session/auth-button`. */
  readonly authButton = computed(() => authButtonState(this.mcpAuthBase(), this._hasAccessBlock()));

  /** Klick auf den Anmelde-/Abmelde-Knopf.
   *
   *  Abmelden räumt NUR den Zugangsblock, nicht das Gespräch — dafür sitzt der
   *  Neustart-Knopf daneben. Anmelden startet SYNCHRON: der Klick ist die
   *  Nutzergeste, ohne die der Browser das Anmeldefenster blockt. */
  onAuthClick(): void {
    if (this.authButton() === 'signOut') {
      clearAccessBlock();
      this._hasAccessBlock.set(false);
      this._store.addBotMessage(this.t('auth.signedOut'));
      return;
    }
    this._signInAndRefresh();
  }

  /** Anmelden und danach den Knopf nachziehen. Beide Auslöser — dieser Knopf
   *  und der `__auth__`-Chip — laufen hier durch, sonst stünde der Knopf nach
   *  einer Anmeldung über den Chip weiter auf „Anmelden". */
  private _signInAndRefresh(): void {
    void this.startSignIn().then(() => this._hasAccessBlock.set(readAccessBlock() !== null));
  }

  /** Klick auf einen Standard-Quick-Reply (Tour-Start | Action-Pill | Text). */
  onQuickReply(reply: string): void {
    routeQuickReply(reply, this._routingCtx);
  }

  /** Klick auf einen Guide-Quick-Reply (`__guide__|…`) — Same-Tab-Navigation. */
  onGuideQuickReply(qr: string): void {
    const url = guideQuickReplyTarget(qr, this._routingCtx);
    if (url) this.onGuideNavigate(url);
  }

  /** Bot-getriebene „Bring mich hin"-Navigation — T-3-fail-closed über den
   *  Resolver; nur der window-Sprung ist hier (Verbatim ALT 1093-1097). */
  onGuideNavigate(url: string | undefined): void {
    const finalUrl = resolveGuideNavTarget(url, this._routingCtx);
    if (!finalUrl) return;
    try { window.location.href = finalUrl; }
    catch { window.open(finalUrl, '_self', 'noopener'); }
  }

  /** Enter (ohne Shift) sendet; Shift+Enter erlaubt Zeilenumbruch. */
  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  /** Debug-Panel ein-/ausblenden. */
  toggleDebug(): void {
    this.showDebug.update(v => !v);
  }

  // ── Sammlungs-Aktionen + Pagination (8-2i) ──────────────────────
  // Dünne Delegates auf `controllers/collection-actions.ts` über den in 8-4S-d1
  // gebauten Context; die Card-List meldet nur, WAS geklickt wurde.

  /** „Inhalte" — Sammlung im Chat auflisten (ALT `browseCollection`). */
  browseCollection(nodeId: string, title: string): Promise<void> {
    return browseCollection(nodeId, title, this._contexts.collectionActions);
  }

  /** „Lernpfad" — Lernpfad aus der Sammlung generieren. */
  generateLearningPath(nodeId: string, title: string): Promise<void> {
    return generateLearningPath(nodeId, title, this._contexts.collectionActions);
  }

  /** „Inhalt anzeigen" — Volltext des Materials im Chat öffnen (M17).
   *  Beide Karten-Oberflächen melden hierher: die Gruppen-Box (Default) und
   *  das Flach-Grid. */
  showContentText(nodeId: string, title: string): Promise<void> {
    return showContentText(nodeId, title, this._contexts.collectionActions);
  }

  /** „Mehr anzeigen" — schon geladene Karten aufdecken (client-seitig). */
  showMoreCards(msgId: string): void {
    showMoreCards(msgId, this._contexts.collectionActions);
  }

  /** „Weitere laden" — nächste Seite aus der Sammlung holen (server-seitig). */
  loadMoreCards(msgId: string): Promise<void> {
    return loadMore(msgId, this._contexts.collectionActions);
  }

  // ── Sprache (8-4S-f3) ───────────────────────────────────────────
  // Dünne Delegates; Aufnahme-/TTS-Logik liegt in `speech.service.ts`.

  /** Mikro-Aufnahme starten/stoppen (Transkript geht als Turn raus). */
  toggleRecording(): Promise<void> {
    return this._speech.toggleRecording();
  }

  /** Bot-Antwort vorlesen (bzw. laufende Ausgabe stoppen). */
  speakText(text: string): void {
    this._speech.speakText(text);
  }

  /** Vorlese-Automatik an/aus — Button in der Widget-Kopfzeile (ALT
   *  `chatRef?.toggleAutoSpeak()`, chat.component.ts:937-939). */
  toggleAutoSpeak(): void {
    this._speech.toggleAutoSpeak();
  }

  /** Lotsen-Env (`guide_mode` + Host) für jede Anfrage setzen. Die Entscheidung
   *  trifft die Widget-Hülle beim Config-Boot (ALT: gemeinsamer `ApiService` via
   *  DI; hier besitzt die Shell ihren Client, daher dieser Delegate). */
  setGuideEnv(guideMode: boolean, host: string): void {
    this._api.setGuideEnv(guideMode, host);
  }

  /** Welche Maschine diesen Einbau beantwortet (`''` = Vorgabe des Backends).
   *  Delegate wie `setGuideEnv` — die Entscheidung trifft die Widget-Hülle aus
   *  ihrem Host-Attribut, der Client trägt sie an jedem Zug mit. */
  setEngine(mode: string): void {
    this._api.setEngine(mode);
  }

  /** Startet die geführte Web-Tour. Delegate — Logik in `tour.controller.ts`. */
  startTour(): Promise<void> {
    return this._tour.startTour();
  }

  /** Effektive Trust-Liste: Kern-WLO-Domains (immer trusted) + `[trustedHosts]`. */
  private _effectiveTrustedDomains(): string[] {
    const dynamic = this.trustedHosts();
    return [...CORE_TRUSTED_DOMAINS, ...(Array.isArray(dynamic) ? dynamic : [])];
  }

  // ── Lebenszyklus + Public API (8-4S-e5) ─────────────────────────
  // Dünne Angular-Hooks + Host-API; Logik in `lifecycle.ts`/`scroll-follow.ts`.

  /** Boot: Base-URL/Speech/pageContext/Session-Kaskade + Resume vs. Begrüßung. */
  ngOnInit(): void {
    this._lifecycle.init();
    // C1-f1: Die Sprache, die das Widget ANZEIGT, ist auch die, in der das
    // Backend antworten soll. Ohne das schickte `environment.locale` den
    // Browser (`navigator.language`) — ein englisch gestelltes Widget bekam
    // eine deutsche Antwort.
    this._api.setUiLocale(this.locale());
  }

  /** Markdown-Cache verwerfen, wenn sich etwas ändert, das im **gerenderten
   *  HTML** steckt, aber nicht im Cache-Key (`sender|session|text`):
   *
   *  - Trusted-Hosts (async vom Host/Backend): sonst behielten gecachte Bubbles
   *    ihr `target="_blank"` und ihre bsid-freien hrefs für jetzt vertraute
   *    Hosts. Verbatim ALT 214-222.
   *  - Sprache (C1-c): die Icon-Labels des Renderers und die Extern-Warnung
   *    sind übersetzt; ohne Reset bliebe der Verlauf nach dem Umschalten in der
   *    alten Sprache stehen. In C1-b3 gefunden, mit dem Umschalter fällig. */
  ngOnChanges(changes: {
    trustedHosts?: { previousValue?: string[]; currentValue?: string[]; firstChange?: boolean };
    locale?: { previousValue?: Locale; currentValue?: Locale; firstChange?: boolean };
  }): void {
    const hosts = changes.trustedHosts;
    if (hosts && !hosts.firstChange
      && JSON.stringify(hosts.previousValue || []) !== JSON.stringify(hosts.currentValue || [])) {
      this.render.clearCache();
    }
    const sprache = changes.locale;
    if (sprache && !sprache.firstChange && sprache.previousValue !== sprache.currentValue) {
      this.render.clearCache();
      this._api.setUiLocale(this.locale());  // C1-f1: ab dem nächsten Zug
    }
  }

  /** Aufgeschobene Scroll-Wünsche einlösen (erst nach CD+Paint, finale Höhe). */
  ngAfterViewChecked(): void {
    this._scroll.afterViewChecked();
  }

  /** Auto-Follow-Observer + Speech-Cluster (Mikro/TTS, Privacy!) beim Zerstören
   *  trennen. Verbatim-Teilung aus ALT ngOnDestroy 428-446. */
  ngOnDestroy(): void {
    this._scroll.destroy();
    this._speech.destroy();
  }

  /** Public API: frische Session + Begrüßung (Header-Restart). */
  restart(): void {
    this._lifecycle.restart();
  }

  /** Public API: Session leeren und frisch starten (Host-Seite). */
  resetSession(): void {
    this._lifecycle.resetSession();
  }

  /** Public API: Seitenkontext zur Laufzeit ergänzen (SPA ohne Reload). */
  updateContext(ctx: Record<string, any>): void {
    this._lifecycle.updateContext(ctx);
  }

  /** Public API: SPA-Navigation — Seitenkontext ersetzen + Kontext-Ping anbieten. */
  onSpaContextChange(newContext: Record<string, any>): void {
    this._lifecycle.onSpaContextChange(newContext);
  }

  /** **Public** — auf die letzte Nachricht scrollen (WidgetComponent beim Öffnen). */
  scrollToLatest(): void {
    this._scroll.scrollToLatest();
  }
}
