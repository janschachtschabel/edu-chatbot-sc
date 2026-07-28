import {
  AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, HostListener, Injector,
  OnDestroy, OnInit, ViewEncapsulation, afterNextRender, effect, inject, input, output, signal,
  viewChild,
} from '@angular/core';

import {
  ChatShellComponent, GuideBoot, GuideNav, GuideSuggestionPayload, HeaderNavButton, HostBridges,
  ICONS, PanelState, RoutingDebugPayload, SafeSvgPipe, applyPrimaryColor, BOERDI_LOGO_DATA_URL,
  headerNavHrefWithBsid, headerNavIconSvg, resolveMergedPageContext,
} from '@boerdi/ui';

/**
 * BoerdiChatWidget — Floating Action Button + aufklappbares Chat-Panel, die
 * Hülle des Custom Elements `<boerdi-chat>`:
 *
 *     <boerdi-chat
 *       api-url="https://api.wlo.de"
 *       page-context='{"thema":"eiszeit"}'
 *       position="bottom-right"
 *       initial-state="collapsed"
 *       primary-color="#1c4587">
 *     </boerdi-chat>
 *
 * Panel-Layout 420×820 (Chat einspaltig), responsive bis Vollbild auf Mobile.
 *
 * Port von ALT `widget/widget.component.ts` (693 Z.). Diese Datei ist bewusst
 * nur noch **Element-Kontrakt + Verdrahtung**: die Zustandsmaschine liegt in
 * `PanelState`, der Config-Boot in `GuideBoot`, die Lotsen-Navigation in
 * `GuideNav`, die Host-Seiten-Brücken in `HostBridges` und die Bootstrap-
 * Entscheidungen in `widget-init.ts` (§3: eine Änderungs-Ursache je Datei).
 *
 * DOKUMENTIERTE GRÖSSEN-AUSNAHME (328 statt ≤300 Z., wie
 * `chat-shell.component.ts`): die Datei hat genau eine Änderungs-Ursache — den
 * Element-Kontrakt. Rund 100 Zeilen davon sind die 18 Inputs/4 Outputs samt ihrer
 * Doku (die `input()`-Deklarationen MÜSSEN in der Komponentenklasse stehen),
 * weitere ~50 die vier Seam-Literale. FOLLOW-UP, nicht dringend: die Seam-
 * Literale nach `widget-contexts.ts` ziehen (Muster `shell/shell-contexts.ts`) —
 * das brächte die Datei unter die Schwelle, ohne Verhalten zu ändern.
 *
 * simplify (gegenüber ALT):
 *  - Signals statt plain Felder + `NgZone`/`cdr.markForCheck()` — im zoneless
 *    Betrieb plant ein Signal-Write die Prüfung selbst. Public-API-Aufrufe der
 *    Host-Seite wirken damit ohne Zone-Reentry.
 *  - `primary-color` geht durch `applyPrimaryColor` (Allowlist-Validierung)
 *    statt durch ein rohes `@HostBinding` — der Wert kommt von der Host-Seite.
 *  - Shadow DOM (8-1-Entscheid): Host-Seiten-Stile können nicht hereinbluten.
 */
@Component({
  selector: 'boerdi-chat-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  encapsulation: ViewEncapsulation.ShadowDom,
  imports: [ChatShellComponent, SafeSvgPipe],
  templateUrl: './widget.component.html',
  styleUrl: './widget.component.scss',
})
export class WidgetComponent implements OnInit, AfterViewInit, OnDestroy {
  // ── Host-Attribut-Kontrakt (§5.5) ───────────────────────────────
  readonly apiUrl = input('');
  readonly pageContext = input<string | Record<string, unknown>>('');
  readonly position = input<'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'>('bottom-right');
  readonly initialState = input<'collapsed' | 'expanded'>('collapsed');
  /** Akzentfarbe (CSS-Hex/-Farbe). Leer/ungesetzt → der `:host`-CSS-Default
   *  `#1c4587` greift. Alternativ kann der Host die CSS-Variable selbst setzen
   *  (`boerdi-chat { --boerdi-primary: red; }`) — das funktioniert nur, solange
   *  `primary-color` NICHT zusätzlich gesetzt ist (Inline-Style gewinnt). */
  readonly primaryColor = input('');
  readonly persistSession = input<boolean | string>(true);
  readonly sessionKey = input('boerdi_session_id');
  /** Cookie-Domain für Session-Sharing über Subdomains, z.B.
   *  `.wirlernenonline.de`. Leer = rein localStorage (origin-isoliert). */
  readonly sessionCookieDomain = input('');
  /** Cookie-Lebensdauer in Sekunden (Default 30 Tage). */
  readonly sessionCookieMaxAge = input<number | string>(30 * 24 * 60 * 60);
  /** Komma-getrennte Whitelist der Hosts, an die das Widget die Session-ID per
   *  `?bsid=…` weitergeben darf. Bare Domains (`openeduhub.net`) oder ganze
   *  Hostnamen; Subdomain-Match automatisch. Ergänzt die Backend-Liste, kann
   *  sie aber nicht kürzen. Leer = nur die Backend-Liste. */
  readonly trustedDomains = input('');
  readonly greeting = input('');
  readonly autoContext = input<boolean | string>(true);
  /** Debug-Umschalter in der Kopfzeile zeigen. */
  readonly showDebugButton = input<boolean | string>(true);
  /** Vorlese-/Mikro-Buttons zeigen (zusätzlich an die Backend-Capability
   *  gekoppelt, siehe `ChatShellComponent.languageButtonsVisible`). */
  readonly showLanguageButtons = input<boolean | string>(true);
  /** Bei `true` werden Link-Klicks abgefangen: keine Navigation, stattdessen
   *  feuert `linkClicked` mit path+search. Default: normal navigieren. */
  readonly interceptEduSharingLinks = input<boolean | string>(false);
  /** Lotsen-Treffer als `badboerdi:guide-suggestion` + Output emittieren. */
  readonly emitGuideSuggestion = input<boolean | string>(false);
  /** Routing-Debug als `badboerdi:routing-debug` + Output emittieren. */
  readonly emitRoutingDebug = input<boolean | string>(false);
  /** `false` = flaches Karten-Grid mit Pagination statt der Ergebnis-Boxen
   *  (8-2i). Hier durchgereicht, weil das Attribut sonst nur an der Shell
   *  existiert und am echten Embed wirkungslos wäre — dieselbe Falle wie das
   *  tote `data-position` (8-5); von e2e/chat.spec.ts gefunden. */
  readonly inlineResultGrouping = input<boolean | string>(true);

  // ── Outputs (Host-Integration, siehe docs/05-widget-javascript-api.md) ──
  /** Abgefangener Link (nur mit `intercept-edu-sharing-links`). */
  readonly linkClicked = output<string>();
  /** Spiegelt `badboerdi:guide-suggestion` für Angular-Konsumenten. */
  readonly guideSuggestion = output<GuideSuggestionPayload>();
  /** Spiegelt `badboerdi:routing-debug` für Angular-Konsumenten. */
  readonly routingDebug = output<RoutingDebugPayload>();
  /** MCP-Suchmetadaten jedes Bot-Turns (immer aktiv, kein Opt-in). */
  readonly queryMeta = output<unknown>();

  /** Die Chat-Shell — wir brauchen die Instanz (nicht nur das Element) für
   *  Kopfzeilen-Zustand und Public-Methoden (ALT `@ViewChild('chat')`).
   *  Der Template-Ref heißt `#chat` und nicht `#shell`: ein Ref-Name verdeckt im
   *  Template gleichnamige Klassenfelder — `shell()` wäre dann nicht aufrufbar. */
  readonly shell = viewChild<ChatShellComponent>('chat');

  /** Logo als Data-URL — in Web Components zuverlässiger als Inline-SVG per
   *  `[innerHTML]`, das der Browser-Sanitizer in Custom Elements strippen kann. */
  readonly boerdiLogo = BOERDI_LOGO_DATA_URL;
  readonly ICONS = ICONS;

  /** Aufgelöster Seitenkontext (auto + manuell), an die Shell durchgereicht. */
  readonly resolvedPageContext = signal<Record<string, unknown>>({});

  private readonly hostEl = inject<ElementRef<HTMLElement>>(ElementRef);
  /** Für `afterNextRender` außerhalb des Konstruktor-Injektionskontexts. */
  private readonly injector = inject(Injector);

  /** Auf/Zu-Zustandsmaschine (`panel-state.ts`). */
  private readonly panel = new PanelState({
    sessionId: () => this.shell()?.sessionId,
    scrollToLatest: () => this.shell()?.scrollToLatest(),
    focusInput: () => this.shell()?.focusInput(),
    focusFab: () => {
      (this.root().querySelector('.boerdi-fab') as HTMLElement | null)?.focus?.();
    },
    // 8-6: Angulars Render-Hook statt ALTs doppeltem requestAnimationFrame.
    // Er ist an die Prüfung gekoppelt, nicht an den Compositor — dadurch ist das
    // Panel garantiert schon sichtbar (nicht mehr `display: none`) und der Hook
    // läuft auch in einem Tab, der gerade keine Frames zeichnet.
    afterRender: (cb) => afterNextRender(cb, { injector: this.injector }),
  });

  /** Studio-Config + Trusted-Domains (`guide-boot.ts`). */
  private readonly guide = new GuideBoot({
    apiUrl: () => this.apiUrl(),
    attrTrustedDomains: () => this.trustedDomains(),
  });

  /** Lotsen-Navigation mit Zustimmung (`guide-nav.ts`). */
  private readonly guideNav = new GuideNav({
    guideMode: () => this.guide.guideMode(),
    trustedDomains: () => this.guide.trustedDomains(),
    sessionId: () => this.shell()?.sessionId,
  });

  /** Brücken zur Host-Seite (`host-bridges.ts`). */
  private readonly bridges = new HostBridges({
    clickScope: () => this.root(),
    sessionId: () => this.shell()?.sessionId,
    trustedDomains: () => this.guide.trustedDomains(),
    interceptEduSharingLinks: () => this.interceptEduSharingLinks(),
    onInterceptedLink: p => this.linkClicked.emit(p),
    onPageAction: pa => this.handlePageAction(pa),
    onQueryMeta: d => this.queryMeta.emit(d),
    onUrlChange: () => this.refreshPageContext(true),
  });

  /** Wurzel des eigenen Baums: der Shadow-Root, sonst das Host-Element. Ein
   *  Listener am HOST bekäme durch Event-Retargeting nur `<boerdi-chat>` als
   *  `target` zu sehen — siehe `HostBridgesContext.clickScope`. */
  private root(): ParentNode & EventTarget {
    const host = this.hostEl.nativeElement;
    return host.shadowRoot ?? host;
  }

  /** Hat der `initial-state`-Effect seinen ersten Lauf gesehen? Entspricht ALTs
   *  `!changes['initialState'].firstChange`: der Boot-Wert wird von
   *  `ngOnInit`/`initExpanded` entschieden (das wertet auch ?bsid= und eine
   *  laufende Tour aus), erst spätere Attribut-Änderungen schalten um. */
  private _initialStateSeen = false;

  constructor() {
    effect(() => applyPrimaryColor(this.hostEl.nativeElement, this.primaryColor()));
    // `initial-state` zur Laufzeit umsetzen: Angular Custom Elements mappen ein
    // gesetztes HTML-Attribut auf den Input, also kann die Host-Seite per
    // `setAttribute('initial-state', 'expanded')` öffnen bzw. schließen. Beide
    // Wege (Attribut + Public-API) sind erlaubt und idempotent.
    effect(() => {
      const open = this.initialState() === 'expanded';
      if (!this._initialStateSeen) {
        this._initialStateSeen = true;
        return;
      }
      this.panel.setExpanded(open);
    });
    // Guide-Env in den Chat-Client nachziehen, sobald die Shell gemountet ist.
    // Sie hängt am Lazy-Gate und existiert beim Auflösen des Config-Boots
    // meist noch nicht; ohne dieses Nachziehen sendete ihr Client dauerhaft
    // `guide_mode: false` und überschriebe damit den Backend-Default `True`
    // (ALT hatte den `ApiService` als DI-Singleton, unabhängig vom Chat).
    effect(() => {
      const shell = this.shell();
      if (shell) shell.setGuideEnv(this.guide.guideMode(), this.guide.guideHost());
    });
  }

  // ── Template-Sicht ──────────────────────────────────────────────
  readonly expanded = this.panel.expanded;
  readonly everExpanded = this.panel.everExpanded;
  readonly hintActive = this.panel.hintActive;
  readonly headerNavButtons = this.guide.headerNavButtons;
  readonly configGreeting = this.guide.configGreeting;
  readonly startReplies = this.guide.startReplies;
  readonly tourReply = this.guide.tourReply;
  /** Vom Bot vorgeschlagenes Navigationsziel; `null` blendet das Banner aus. */
  readonly guideNavTarget = this.guideNav.target;

  /** Gemergte Whitelist für die Shell (klassifiziert Inline-Markdown-Links:
   *  trusted → same-tab + `?bsid=`, extern → `target=_blank`). */
  get parsedTrustedHostList(): string[] {
    return this.guide.trustedDomains();
  }

  ngOnInit(): void {
    // Auto-Open-Entscheidung (initial-state / ?bsid= / laufende Tour).
    this.panel.initExpanded(this.initialState());
    this.refreshPageContext(false);
    // Allow-Liste + Studio-Config async holen — non-blocking, Fehler sind
    // kein Show-Stopper (siehe GuideBoot).
    void this.guide.load();
  }

  ngAfterViewInit(): void {
    // Panel beim Boot schon offen (initial-state / ?bsid= / laufende Tour)?
    // → einmaligen Owl-Hinweis anstoßen. `initExpanded` umgeht `setExpanded`
    //   bewusst, also muss der Hinweis hier ausgelöst werden (ALT 310).
    if (this.everExpanded()) this.panel.showOwlHintIfDue();
    this.bridges.init();
  }

  ngOnDestroy(): void {
    this.bridges.destroy();
  }

  // ── Öffnen/Schließen ────────────────────────────────────────────

  /** FAB- und Schließen-Button. */
  toggle(): void {
    this.panel.toggle();
  }

  /** A11y: Escape schließt das offene Panel. Der Listener sitzt am Host, feuert
   *  also nur bei Fokus im Widget — nicht bei Escape irgendwo auf der Seite. */
  @HostListener('keydown.escape')
  onEscapeKey(): void {
    this.panel.onEscape();
  }

  /** **Public API** — Chat-Panel öffnen. Vom Custom Element exponiert, sodass
   *  die Host-Seite `document.querySelector('boerdi-chat').openChatbot()`
   *  aufrufen kann. Scrollt ans Ende des Verlaufs und fokussiert die Eingabe. */
  openChatbot(): void {
    this.panel.setExpanded(true);
  }

  /** **Public API** — Chat-Panel schließen (FAB wieder sichtbar). */
  closeChatbot(): void {
    this.panel.setExpanded(false);
  }

  /** **Public API** — zwischen offen/zu umschalten. */
  toggleChatbot(): void {
    this.panel.toggle();
  }

  /** **Public API** — aktueller Zustand (für Hosts mit eigenem Trigger). */
  isChatbotOpen(): boolean {
    return this.panel.expanded();
  }

  /** **Public API** — neue Session starten (V4-Reset). */
  resetSession(): void {
    this.shell()?.resetSession();
  }

  /** **Public API** — Seitenkontext von außen aktualisieren (V4). */
  updateContext(ctx: Record<string, unknown>): void {
    this.shell()?.updateContext(ctx);
  }

  /** Web-Tour starten (Klick auf den Eulen-Kopf). No-op solange die Shell lädt. */
  startTour(): void {
    void this.shell()?.startTour();
  }

  // ── Lotsen-Banner ───────────────────────────────────────────────
  // Logik in `guide-nav.ts` (inkl. T7-Guard); hier nur die Template-Delegates.

  /** Backend-`page_action`. Nur `navigate` landet im Banner — alle anderen
   *  Actions verteilt die Shell als CustomEvents an die Host-Seite. */
  handlePageAction(pa: { action: string; payload: any }): void {
    this.guideNav.handlePageAction(pa);
  }

  /** „Bring mich hin" — verlässt die Seite im aktuellen Tab (wenn freigegeben). */
  confirmGuideNav(): void {
    this.guideNav.confirm();
  }

  /** „Hier bleiben" — Banner wegblenden. */
  cancelGuideNav(): void {
    this.guideNav.cancel();
  }

  // ── Kopfzeilen-Nav ──────────────────────────────────────────────

  /** Icon-SVG eines Nav-Buttons (Delegate — `guide-mode-config.ts`). */
  headerNavIcon(b: HeaderNavButton): string {
    return headerNavIconSvg(b?.icon);
  }

  /** Ziel-URL eines Nav-Buttons inkl. bsid (Delegate). Bewusst AUCH
   *  same-origin, anders als der Klick-Rewrite: das Auto-Open des Widgets und
   *  die Tour keyen auf `?bsid=`. */
  headerNavHref(b: HeaderNavButton): string {
    return headerNavHrefWithBsid(b, this.shell()?.sessionId || '', this.guide.trustedDomains());
  }

  // ── Intern ──────────────────────────────────────────────────────

  /** Seitenkontext (neu) auflösen. `notify` nur bei SPA-Navigation: dann bekommt
   *  die Shell ihn zusätzlich gemeldet und bietet ggf. eine Kontext-Begrüßung
   *  an — beim Boot reicht die Input-Bindung (ALT ngOnInit vs. _checkUrlChange). */
  private refreshPageContext(notify: boolean): void {
    try {
      const merged = resolveMergedPageContext(this.autoContext(), this.pageContext());
      this.resolvedPageContext.set(merged);
      if (notify) this.shell()?.onSpaContextChange(merged);
    } catch { /* ignore — Navigation darf das Widget nie brechen */ }
  }
}
