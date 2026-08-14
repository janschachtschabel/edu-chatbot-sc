import {
  AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, HostListener, Injector,
  OnDestroy, OnInit, ViewEncapsulation, afterNextRender, computed, effect, inject, input,
  output, signal,
  viewChild,
} from '@angular/core';

import {
  ChatShellComponent, GuideBoot, GuideNav, GuideSuggestionPayload, HeaderNavButton, HostBridges,
  ICONS, PanelState, RoutingDebugPayload, SafeSvgPipe, TranslationParams, WidgetLanguage,
  _attrEnum,
  _attrJsonObject,
  _attrJsonStringArray,
  PANEL_SIZE_STEPS,
  applyPrimaryColor, BOERDI_LOGO_DATA_URL, headerNavHrefWithBsid, headerNavIconSvg,
  pickLocalized,
  resolveMergedPageContext, resolveTheme,
} from '@boerdi/ui';

/** Erlaubte Werte von `embed-mode` (U1). `panel` = die freischwebende Hülle mit
 *  FAB und Kopfzeile; `frameless` = der Einbau IN eine fremde Oberfläche. */
const EMBED_MODES = ['panel', 'frameless'] as const;

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
 * DOKUMENTIERTE GRÖSSEN-AUSNAHME (465 statt ≤300 Z., wie
 * `chat-shell.component.ts`): die Datei hat genau eine Änderungs-Ursache — den
 * Element-Kontrakt. Rund 130 Zeilen davon sind die 23 Inputs/4 Outputs samt ihrer
 * Doku (die `input()`-Deklarationen MÜSSEN in der Komponentenklasse stehen),
 * weitere ~55 die fünf Seam-Literale. FOLLOW-UP, mit C1-c fälliger geworden: die
 * Seam-Literale nach `widget-contexts.ts` ziehen (Muster
 * `shell/shell-contexts.ts`) — das brächte die Datei unter die Schwelle, ohne
 * Verhalten zu ändern.
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
  // Die Klasse trägt den NORMALISIERTEN Modus ans Host-Element, damit `:host`
  // ihn stylen kann. Bewusst keine `:host([embed-mode="frameless"])`-Regel:
  // CSS-Attributselektoren vergleichen exakt, `_attrEnum` toleriert dagegen
  // Schreibweise und Leerzeichen — `embed-mode="FRAMELESS"` griffe im
  // TypeScript und im CSS nicht. Dieselbe Klasse von Fehler wie das tote
  // `data-position` (8-5), nur andersherum.
  host: {
    '[class.boerdi-frameless]': 'frameless()',
    '[class.boerdi-large]': 'sizeStep() === "large"',
    // U4a: `theme` als Inline-Stil und nicht — wie die beiden Zeilen darüber —
    // als Klasse mit CSS-Regel dahinter. An `frameless`/`large` hängen jeweils
    // viele Regeln, hier ist es genau EINE Deklaration mit einem Wert; eine
    // Klasse wäre ein Umweg über ein Stylesheet, das nichts weiter tut.
    // `null` (= `auto`) entfernt die Eigenschaft wieder, sodass `color-scheme`
    // erbt — der Zustand, in dem das Widget bis U4a immer war.
    '[style.color-scheme]': 'colorScheme()',
  },
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
  /** Begrüßungstext dieses Einbaus. Gesetzt schlägt er die Studio-Config
   *  (`welcome-config.yaml`), leer gilt sie. */
  readonly greeting = input('');
  /**
   * `start-replies` — die Einstiegs-Chips dieses Einbaus, als **JSON-Array**:
   * `start-replies='["Was kannst du?","Suche starten"]'`. Gesetzt schlägt es
   * die Studio-Config, wie `greeting` es für den Text tut.
   *
   * `[]` ist eine Aussage und heißt „keine Chips" — nur die Begrüßung. Nicht
   * gesetzt heißt dagegen „die Studio-Vorgabe gilt"; ohne diesen Unterschied
   * ließen sich die Chips gar nicht abschalten.
   *
   * JSON und nicht komma-getrennt, weil die Beschriftungen ganze Sätze sind
   * und regelmäßig Kommas enthalten.
   */
  readonly startReplies = input('');
  /**
   * `show-welcome` — `false` startet mit LEEREM Chat: keine Startnachricht,
   * keine Einstiegs-Chips, auch nicht nach „Neu starten".
   *
   * Für Einbettungen, die den Chat selbst anmoderieren und deshalb keine
   * zweite Begrüßung wollen. Betrifft NUR diese statische Nachricht — die
   * Kontext-Begrüßung des Backends hängt am Seitenkontext und bleibt.
   */
  readonly showWelcome = input<boolean | string>(true);
  readonly autoContext = input<boolean | string>(true);
  /** Debug-Umschalter in der Kopfzeile zeigen. */
  readonly showDebugButton = input<boolean | string>(true);
  /** Vorlese-/Mikro-Buttons zeigen (zusätzlich an die Backend-Capability
   *  gekoppelt, siehe `ChatShellComponent.languageButtonsVisible`). */
  readonly showLanguageButtons = input<boolean | string>(true);
  /** Bei `true` werden Link-Klicks abgefangen: keine Navigation, stattdessen
   *  feuert `linkClicked` mit path+search. Default: normal navigieren. */
  readonly interceptEduSharingLinks = input<boolean | string>(false);
  /** Lotsen-Treffer als `boerdi:guide-suggestion` + Output emittieren. */
  readonly emitGuideSuggestion = input<boolean | string>(false);
  /** Routing-Debug als `boerdi:routing-debug` + Output emittieren. */
  readonly emitRoutingDebug = input<boolean | string>(false);
  /** `false` = flaches Karten-Grid mit Pagination statt der Ergebnis-Boxen
   *  (8-2i). Hier durchgereicht, weil das Attribut sonst nur an der Shell
   *  existiert und am echten Embed wirkungslos wäre — dieselbe Falle wie das
   *  tote `data-position` (8-5); von e2e/chat.spec.ts gefunden. */
  readonly inlineResultGrouping = input<boolean | string>(true);
  /** Sprache der Oberfläche (`de`/`en`). Leer = die Seite entscheidet: nächstes
   *  `[lang]` im DOM, sonst der Browser, sonst Deutsch. Eine Nutzerwahl über
   *  den Umschalter schlägt dieses Attribut — sonst spränge die Sprache beim
   *  nächsten Rendern zurück (C1-c). */
  readonly language = input('');
  /** Einbettungs-Modus (U1). `frameless` gibt Rahmen und Navigation an die
   *  Gastanwendung ab: kein FAB, keine Kopfzeile, kein Panel-Rahmen — nur
   *  Verlauf und Eingabezeile, im Container des Hosts.
   *
   *  Bewusst `embed-mode` und nicht „headless": headless heißt üblicherweise
   *  ganz ohne Oberfläche; hier ist sie da, nur ohne Rahmen. */
  readonly embedMode = input('');
  /**
   * Welche Maschine antwortet: `pattern` (Bestand) oder `agent` (freie
   * Werkzeugschleife). Leer = die Vorgabe aus `01-base/engine`, und das ist der
   * Normalfall — der Umschalter gehört redaktionell ins Studio.
   *
   * Warum es ihn trotzdem als Host-Attribut gibt: eine Einbettung ohne
   * Chat-Rahmen (Browser-Plugin, edu-sharing) will die Schleife oft, ohne dass
   * deshalb der ganze Chatbot umgestellt wird. Und A/B messen lässt sich nur,
   * was sich JE EINBAU unterscheiden kann.
   *
   * Reist als Kopfzeile `X-Boerdi-Engine` (siehe `ChatApiClient.setEngine`), die
   * das Backend undeklariert liest — der eingefrorene Vertrag bleibt unberührt.
   * Ein unbekannter Wert fällt dort auf die Vorgabe zurück und bricht nichts.
   */
  readonly engine = input('');
  /**
   * `result-schema` — in welcher Form dieser Einbau sein Ergebnis erwartet
   * (Nutzer-Entscheid 2026-08-14). Ein JSON-Schema als **Zeichenkette**, denn
   * so und nicht anders kommen Attribute eines Custom Elements herein.
   *
   * Leer = kein Ergebnis, und das ist der Normalfall. Gesetzt bekommt der
   * Gastgeber je Zug ein `boerdi:agent-result` — dafür gelten zwei Bedingungen,
   * die er kennen muss: es wirkt nur mit `engine="agent"`, und es kostet dort
   * einen zusätzlichen Modellzug je Nachricht (2–9 s gemessen).
   */
  readonly resultSchema = input('');
  /** Anfangs-Größenstufe (U2a): `small` (Vorgabe) oder `large`. Nur der START —
   *  danach gehört die Stufe dem Panel, weil der Umschalter in der Eingabezeile
   *  sie verändert. Rahmenlos hat sie keine Wirkung auf die Maße (die stellt der
   *  Host), speist aber die Kachel-Regel aus U2b. */
  readonly size = input('');
  /** Kachel-Regel (U2b): `auto` (Vorgabe) | `always` | `never`. `auto` heißt —
   *  klein Textlinks, groß Kacheln; Bestands-Embeds mit
   *  `inline-result-grouping="false"` behalten ihre Kacheln. Wird unverändert an
   *  die Shell durchgereicht, die entscheidet (`resolveCardsVisible`). */
  readonly showCards = input('');
  /** Farbschema (U4a): `auto` (Vorgabe) | `light` | `dark`. `auto` heißt, dass
   *  das Widget nichts setzt und dem `color-scheme` der Gastseite folgt — das
   *  Verhalten, das es seit dem M3-Theme hat. Für Gastseiten gedacht, die
   *  selbst keins setzen: dort entschied bis hierher der Browser allein, und
   *  ein hell gestaltetes Portal bekam im Dunkelmodus des Betriebssystems ein
   *  dunkles Widget. */
  readonly theme = input('');
  /** edu-sharing-Ticket der Gastgeberseite — die Betriebsform „das Repositorium
   *  bettet ein": die Seite kennt die angemeldete Person und reicht ihren
   *  Ausweis herein (dieselbe Konvention, die der md-editor als `?ticket=…`
   *  konsumiert). Einmal gelesen, dann aus dem DOM getilgt (`ngOnInit`) — ein
   *  Ticket darf nirgends liegenbleiben. Den Tausch gegen einen Zugangsblock
   *  macht die Shell (`session/ticket-login.ts`), sobald die Anmelde-Adresse
   *  aus dem Config-Bündel da ist. */
  readonly ticket = input('');

  // ── Outputs (Host-Integration, siehe docs/05-widget-javascript-api.md) ──
  /** Abgefangener Link (nur mit `intercept-edu-sharing-links`). */
  readonly linkClicked = output<string>();
  /** Spiegelt `boerdi:guide-suggestion` für Angular-Konsumenten. */
  readonly guideSuggestion = output<GuideSuggestionPayload>();
  /** Spiegelt `boerdi:routing-debug` für Angular-Konsumenten. */
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

  /** Das in `ngOnInit` EINMAL eingesammelte Ticket. Ein eigenes Signal statt
   *  des Inputs, weil das Attribut danach getilgt wird — die Custom-Element-
   *  Brücke setzte den Input dabei auf leer zurück, und die Shell bekäme das
   *  Ticket nie zu sehen. */
  readonly ticketOnce = signal('');

  private readonly hostEl = inject<ElementRef<HTMLElement>>(ElementRef);

  /** Sprache dieses Widgets (`widget-language.ts`): Auflösung aus den vier
   *  Quellen, Umschalter, Merken. Eigene Instanz statt Root-Singleton — zwei
   *  Widgets auf einer Seite dürfen verschiedene Sprachen sprechen. */
  private readonly lang = new WidgetLanguage({
    attribute: () => this.language(),
    hostElement: () => this.hostEl.nativeElement,
  });
  /** Kurzform fürs Template. Als Arrow gebunden, damit `{{ t('…') }}` auch
   *  ohne `this` funktioniert. */
  protected readonly t = (key: string, params?: TranslationParams): string =>
    this.lang.i18n.t(key, params);
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
    // Sprache auflösen — im Effect und nicht in `ngOnInit`, damit ein zur
    // Laufzeit gesetztes `language`-Attribut wirkt (derselbe Weg wie bei
    // `initial-state`). Der Effect liest `language()`, die übrigen drei Quellen
    // sind Momentaufnahmen; `resolve()` ist idempotent.
    effect(() => this.lang.resolve());
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
    // Dasselbe Nachziehen für die Maschinen-Wahl, und aus demselben Grund: die
    // Shell hängt am Lazy-Gate. Ein eigener Effect statt einer Zeile im obigen —
    // dieser läuft auch, wenn das Attribut zur Laufzeit umgestellt wird, was
    // das Bedienpult der Demo-Seiten genau tut.
    effect(() => {
      const shell = this.shell();
      if (shell) shell.setEngine(this.engine());
    });
    // Und dasselbe für das Ergebnis-Schema. Eigener Effect statt einer Zeile
    // im obigen: er hängt an `resultSchema()`, nicht an `engine()` — ein zur
    // Laufzeit gesetztes Attribut soll ab dem nächsten Zug gelten, ohne dass
    // die Maschinen-Wahl sich bewegt haben muss.
    effect(() => {
      const shell = this.shell();
      if (shell) shell.setResultSchema(_attrJsonObject(this.resultSchema()));
    });
    // Der wartende Auftrag, sobald es eine Shell gibt. Dieselbe Nachzieh-Naht
    // wie oben und aus demselben Grund: die Shell hängt am Lazy-Gate. Der
    // Merker ist bewusst KEIN Signal — dieser Effect soll an `shell()` hängen,
    // nicht am Auftrag, sonst liefe er beim Setzen ein zweites Mal.
    effect(() => {
      const shell = this.shell();
      const auftrag = this._wartenderAuftrag;
      if (shell && auftrag) {
        this._wartenderAuftrag = null;
        void shell.startTask(auftrag);
      }
    });
  }

  // ── Template-Sicht ──────────────────────────────────────────────
  readonly expanded = this.panel.expanded;
  readonly everExpanded = this.panel.everExpanded;
  /** U1: rahmenlos = der Host stellt den Rahmen. */
  readonly frameless = computed(
    () => _attrEnum(this.embedMode(), EMBED_MODES, 'panel') === 'frameless',
  );
  /** Ob der Chat gemountet sein soll. Im Panel-Betrieb entscheidet das
   *  Lazy-Mount-Gate (erst beim ersten Öffnen); rahmenlos MUSS er sofort da
   *  sein — es gibt keinen FAB, der das Gate je öffnen würde. */
  readonly chatMounted = computed(() => this.everExpanded() || this.frameless());
  /** U2a: aktuelle Größenstufe — Anfangswert aus `size`, danach vom Umschalter. */
  readonly sizeStep = this.panel.sizeStep;
  /** U4a: `color-scheme` fürs Host-Element, `null` = erben (siehe `host`). */
  readonly colorScheme = computed(() => resolveTheme(this.theme()));
  readonly hintActive = this.panel.hintActive;
  readonly headerNavButtons = this.guide.headerNavButtons;
  /** C1-g1b: die Wahl zwischen deutscher und englischer Fassung faellt HIER,
   *  nicht im Server (C1-g1a) — die Sprache ist zur Laufzeit umschaltbar, der
   *  Boot-Abruf laeuft nur einmal. Als `computed` folgen Chips und Kopfzeile
   *  dem Umschalter; die Begruessung landet einmalig als NACHRICHT im Verlauf
   *  und behaelt danach ihre Sprache — so wie jede andere Nachricht auch. */
  readonly configGreeting = computed(() => pickLocalized(
    this.guide.configGreeting(), this.guide.configGreetingEn(), this.activeLocale()));
  /** Die Chips, die die Shell wirklich bekommt: Host-Attribut vor Studio-Config
   *  — dieselbe Rangfolge wie beim Begrüßungstext (`greeting() || …` im
   *  Template). `null` heißt „Attribut nicht gesetzt"; ein leeres Array heißt
   *  „ausdrücklich keine" und darf deshalb NICHT auf die Config zurückfallen.
   *  Der Host-Weg kennt keine zweite Sprache: wer je Einbau vorgibt, gibt genau
   *  das vor, was dort stehen soll. */
  readonly resolvedStartReplies = computed(() => {
    const vomHost = _attrJsonStringArray(this.startReplies());
    return vomHost ?? pickLocalized(
      this.guide.startReplies(), this.guide.startRepliesEn(), this.activeLocale());
  });
  /** Beide Fassungen gehen an die Shell — sie vergleicht den geklickten Chip
   *  gegen BEIDE, weil ein Sprachwechsel den Verlauf nicht nachuebersetzt. */
  readonly tourReply = this.guide.tourReply;
  readonly tourReplyEn = this.guide.tourReplyEn;
  /** C5-c2: Herkunft des MCP-Servers für die WLO-Anmeldung (aus demselben
   *  Boot-Abruf). Leer = diese Anlage bietet keine Anmeldung an. */
  readonly mcpAuthBase = this.guide.mcpAuthBase;
  /** Vom Bot vorgeschlagenes Navigationsziel; `null` blendet das Banner aus. */
  readonly guideNavTarget = this.guideNav.target;
  /** Aktive Sprache — die Shell braucht sie, um ihren Markdown-Cache beim
   *  Wechsel zu verwerfen (C1-c). */
  readonly activeLocale = this.lang.i18n.locale;
  /** Kürzel und zugänglicher Name des Sprach-Umschalters (beide: Zielsprache). */
  readonly languageSwitchCode = this.lang.switchCode;
  readonly languageSwitchLabel = this.lang.switchLabel;

  /** Gemergte Whitelist für die Shell (klassifiziert Inline-Markdown-Links:
   *  trusted → same-tab + `?bsid=`, extern → `target=_blank`). */
  get parsedTrustedHostList(): string[] {
    return this.guide.trustedDomains();
  }

  ngOnInit(): void {
    // Ticket einsammeln und das Attribut TILGEN, bevor irgendetwas anderes
    // läuft — die md-editor-Regel „ein Ticket darf nirgends liegenbleiben",
    // hier fürs DOM statt für die Adresszeile: Serialisierung, Inspektion und
    // fremde Skripte der Gastseite sollen es nicht länger sehen als nötig.
    // (Das Tilgen setzt über die Element-Brücke den Input zurück, deshalb
    // wandert der Wert vorher in `ticketOnce`.)
    const ticket = this.ticket().trim();
    if (ticket) {
      this.ticketOnce.set(ticket);
      this.hostEl.nativeElement.removeAttribute('ticket');
    }
    // Auto-Open-Entscheidung (initial-state / ?bsid= / laufende Tour).
    this.panel.initExpanded(this.initialState());
    // U2a: `size` ist die ANFANGS-Stufe. Bewusst hier und nicht in einem
    // Effect wie `language`/`initial-state` — die Stufe ist danach vom
    // Umschalter bedienbar, und ein Effect würde jede Handbedienung beim
    // nächsten Signal-Lauf wieder überschreiben.
    this.panel.initSize(_attrEnum(this.size(), PANEL_SIZE_STEPS, 'small'));
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

  /** U2a — Umschaltwunsch aus der Eingabezeile. Die Shell hält keinen eigenen
   *  Größen-Zustand; die Maße kennt das Panel. */
  toggleSize(): void {
    this.panel.toggleSize();
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

  /** **Public API** — Seitenkontext von außen ergänzen (V4). MERGT: Felder, die
   *  hier nicht vorkommen, bleiben stehen. */
  updateContext(ctx: Record<string, unknown>): void {
    this.shell()?.updateContext(ctx);
  }

  /** **Public API** — Seitenkontext ERSETZEN, wie bei einer erkannten
   *  Navigation: alte IDs fallen weg, das Ping-Gate wird zurückgesetzt, und
   *  eine Kontext-Begrüßung darf wieder angeboten werden.
   *
   *  Für Einbettungen, in denen sich `location.href` nie ändert — eine
   *  Erweiterungs-Seitenleiste zeigt einen fremden Tab an, ohne selbst zu
   *  navigieren. Dort greift weder der URL-Wächter noch das Attribut
   *  (`page-context` wird nur in `ngOnInit` gelesen), und `updateContext` ließe
   *  die Sammlung des vorigen Tabs stehen (Befund der Plugin-Entwickler
   *  2026-08-14). */
  replaceContext(ctx: Record<string, unknown>): void {
    this.shell()?.onSpaContextChange(ctx);
  }

  /** Auftrag, der auf die Shell wartet. Im Panel-Modus wird sie erst beim
   *  ersten Öffnen gemountet; ein `startTask` davor liefe sonst ins Leere —
   *  und ein still verschluckter Startbefehl ist schlimmer als gar keiner. */
  private _wartenderAuftrag: string | null = null;

  /** **Public API** — den Chat mit einem Auftrag des Gastgebers starten.
   *
   *  „Hier ist die Sammlung, hier der Seitentext, leg los" — danach ist es eine
   *  gewöhnliche Unterhaltung (Nutzer-Entscheid 2026-08-14). Den Kontext gebt
   *  ihr davor mit `replaceContext()` bzw. dem `page-context`-Attribut.
   *
   *  Öffnet das Panel, wenn es zu ist: ein Auftrag, dessen Antwort niemand
   *  sieht, ist keiner. */
  startTask(text: string): void {
    const auftrag = (text ?? '').trim();
    if (!auftrag) return;
    const shell = this.shell();
    if (shell) {
      void shell.startTask(auftrag);
      return;
    }
    this._wartenderAuftrag = auftrag;
    this.panel.setExpanded(true);
  }

  /** Web-Tour starten (Klick auf den Eulen-Kopf). No-op solange die Shell lädt. */
  startTour(): void {
    void this.shell()?.startTour();
  }

  /** Sprach-Umschalter in der Kopfzeile. Die Wahl wird gemerkt und schlägt
   *  danach Attribut, Host-Seite und Browser. */
  toggleLanguage(): void {
    this.lang.toggle();
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
  /** Beschriftung des Kopfzeilen-Knopfs in der aktiven Sprache (C1-g1b).
   *  Leeres `label_en` heisst „nicht gepflegt" → die deutsche. */
  headerNavLabel(b: HeaderNavButton): string {
    return pickLocalized(b?.label || '', b?.label_en || '', this.activeLocale());
  }

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
