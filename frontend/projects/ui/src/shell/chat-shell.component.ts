import {
  AfterViewChecked, ChangeDetectionStrategy, ChangeDetectorRef, Component, computed, effect,
  ElementRef, inject, input, OnChanges, OnDestroy, OnInit, output, signal, untracked, viewChild,
} from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';

import { type ModulRegister, UI_MODUL_REGISTER } from '@boerdi/ui-module';
import { TREFFERLISTE } from '@boerdi/ui-module/_vertrag/modul-namen';

import { CardListComponent } from '../cards/card-list.component';
import { resolveCardsVisible, SHOW_CARDS_MODES } from '../cards/cards-visible';
import { DebugPanelHuelleComponent } from '../debug/debug-panel-huelle.component';
import { _attrEnum, _attrIsTrue, PanelSizeStep } from '../element/attr';
import { type AblaufStand, ChatMessage, ChatResponse, DebugInfo, PreparedWriteOut, QueryMetaEntry, UiInfo } from '../grouping/message-types';
import { ResultGroupsComponent } from '../grouping/result-groups.component';
import { WebLinksComponent } from '../grouping/web-links.component';
import { SwimlanesComponent } from '../grouping/swimlanes.component';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { DEFAULT_LOCALE, Locale } from '../i18n/locale';

/** Form einer Ablauf-Kennung (wie `ablauf.ID_FORM` im Backend). */
const ABLAUF_KENNUNG = /^[a-z][a-z0-9_]{0,39}$/;
/** Frühe Grenzen der Startdaten (das Backend nimmt höchstens 20 Schlüssel, Review AS-4b, 13). */
export const START_SCHLUESSEL_MAX = 20;
export const START_JSON_MAX = 16_000;

/** AS-4b: Kennung und Startdaten der Gastseite — als reines JSON kopiert, oder `null`. Leere Daten
 *  zählen als keine (Review AS-4b, Befund 9: sonst wiese das Backend einen Knopf-Ablauf ab). */
export function ablaufStartPruefen(
  id: unknown, daten?: unknown,
): { ablauf: string; start?: Record<string, unknown> } | null {
  const ablauf = typeof id === 'string' ? id.trim() : '';
  if (!ABLAUF_KENNUNG.test(ablauf)) return null;
  if (daten === undefined || daten === null) return { ablauf };
  if (typeof daten !== 'object' || Array.isArray(daten)) return null;
  let json: string;
  try {
    json = JSON.stringify(daten);
  } catch {
    return null;   // zyklisch oder nicht serialisierbar
  }
  if (json.length > START_JSON_MAX) return null;
  const start = JSON.parse(json) as Record<string, unknown>;
  const zahl = Object.keys(start).length;
  if (zahl > START_SCHLUESSEL_MAX) return null;
  return zahl ? { ablauf, start } : { ablauf };
}
import { UiBloeckeComponent } from '../ui-bloecke/ui-bloecke.component';
import { alsBeantwortet, offeneFragenSchliessen, wiederOffen } from '../ui-bloecke/fragen-status';
import { Vormerkungen } from '../ui-bloecke/vormerkungen';
import { NACHLADE_INDEX } from '../ui-bloecke/nachlade-index';
import { erzeugeLader } from '../ui-bloecke/nachladen';
import { modulDarstellbar } from '../ui-bloecke/modul-darstellbar';
import type { ShellAntworten, ShellTreffer, ShellVormerken } from '../ui-bloecke/widget-modul-host';
import { QuickRepliesComponent } from '../chips/quick-replies.component';
import { BOERDI_LOGO_DATA_URL } from '../branding/boerdi-logo';
import { SHELL_PRINT } from '../print/print-gates';
import { ChatApiClient, type UiAntwortAnfrage } from '../stream/chat-api';
import { ZUG_POST_FRIST_MS } from '../stream/stream-client';
import { formatPhaseLabel } from '../stream/phase-label';
import {
  browseCollection, editCollectionAsDraft, generateLearningPath, loadMore, showContentText, showMoreCards,
  ablageSchritt,
  auftragAbbrechen,
  auftragAbholen,
  auftragStand,
  dokumentLesen,
  themenbaumZweig,
} from '../controllers/collection-actions';
import { ContextGreetingController } from '../controllers/context-greeting.controller';
import { SeitenPing } from '../controllers/seiten-ping';
import { type AblaufSeite, fuehrungsChips } from '../widget/fuehrung-angebote';

/** AS-7b: der Pfad der Gastseite (ohne Fenster: die Wurzel). */
function _aktuellerPfad(): string {
  try { return window.location.pathname; } catch { return '/'; }
}
import { FUEHRUNG_QR_PREFIX } from '../chips/guide-qr';
import { TourController } from '../controllers/tour.controller';
import { SpeechService } from '../speech/speech.service';
import { CORE_TRUSTED_DOMAINS } from '../session/trusted-host';
import { runSignIn } from '../session/sign-in-flow';
import { authButtonState } from '../session/auth-button';
import { FortsetzenController, type OffenerVorgang, fortsetzenDatum } from './fortsetzen';
import { type WiederkehrKennung, wiederkehrKennung } from '../stream/offene-vorgaenge';
import { sitzungsWache } from '../session/session-id';

/** Wie eine Wiederkehr ausging — die Gastseite (Widget) merkt sich danach, ob sie fertig ist. */
export type WiederkehrAusgang = 'gefunden' | 'nichts' | 'anmeldung' | 'fehler' | 'verworfen' | 'ungueltig';
import {
  clearAccessBlock, clearSignedOut, isSignedOut, markSignedOut, readAccessBlock,
} from '../session/mcp-access';
import { AnmeldeFrist } from '../session/anmelde-frist';
import { AUTH_QR_MARKER } from '../chips/auth-qr';
import { anmeldeSperre, runTicketLogin } from '../session/ticket-login';
import { runPreparedWrite } from '../session/prepared-write';
import {
  InputRoutingContext, guideQuickReplyTarget, resolveGuideNavTarget, routeQuickReply,
} from './input-routing';
import {
  GuideSuggestionPayload, RoutingDebugPayload, maybeDispatchGuideNavigate,
  maybeDispatchGuideSuggestion, maybeDispatchRoutingDebug,
} from '../host-events/host-events';
import { dispatchHostEvent, HOST_EVENTS } from '../host-events/event-names';
import { antwortAusVerlaufHolen } from './antwort-aus-verlauf';
import { fokusZurueckholen } from './fokus-nach-dem-zug';
import { SendMessageContext, runSendMessage } from './send-message';
import { ControllerContexts, ShellHost, buildControllerContexts } from './shell-contexts';
import { LifecycleContext, ShellLifecycle } from './lifecycle';
import { fehlerKurz } from '../obs/fehler-kurz';
import { AblaufLeisteComponent } from './ablauf-leiste.component';
import { type EigenerVorgang, MeineVorgaengeController } from './meine-vorgaenge';
import { MeineVorgaengeComponent } from './meine-vorgaenge.component';
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
    AblaufLeisteComponent, SafeSvgPipe, CardListComponent, DebugPanelHuelleComponent,
    QuickRepliesComponent, ResultGroupsComponent, SwimlanesComponent, UiBloeckeComponent,
    WebLinksComponent, MeineVorgaengeComponent,
  ],
})
export class ChatShellComponent implements OnInit, OnChanges, AfterViewChecked, OnDestroy {
  /** State-Core: Verlauf + Reducer (8-4S-b, Modul seit 8-4S-f0). */
  private readonly _store = new MessageStore();
  /** Nachrichten-Verlauf (bot/user Bubbles) — Single Source of Truth (Template). */
  readonly messages = this._store.messages;
  /** Turn-Serialisierung: true während ein Chat-Turn läuft. ALT: plain field. */
  readonly isLoading = signal(false);
  /** Paket AS-8b (Plan 2026-11-09 §5n, P-10): Probe der Studio-Vorschau — Etikett, kein
   *  „Meine Vorgänge“, kein „Gespräch fortsetzen“ (das Backend antwortete dort 409). */
  readonly probe = signal(false);
  /** Letzter Debug-/Telemetrie-Block fürs Debug-Panel. ALT: plain field. Seit
   *  Paket 18C/D nur mit Freigabe (Studio) — sonst bleibt er `null`. */
  readonly latestDebug = signal<DebugInfo | null>(null);
  /** `ui` der jüngsten Antwort: was das Debug-Panel ohne Debug-Block zeigt. */
  readonly latestUi = signal<UiInfo | null>(null);
  /** Paket AS-Ub: der Stand des Laufs aus der jüngsten **Serverantwort** (live und nach dem
   *  Neuladen — der Verlauf trägt ihn an der letzten). Lokale Blasen (Hinweise, Fehler, Anmeldung)
   *  tragen kein `ui` und zählen nicht — sonst verschwände die Leiste mitten im Lauf (Review AS-Ub,
   *  Befund 1). Ohne Stand an der jüngsten Serverantwort: keine Leiste (Lauf beendet). */
  readonly ablaufStand = computed(() => {
    const msgs = this.messages();
    let antworten = 0;
    let stand: AblaufStand | null = null;
    for (const m of msgs) {
      if (m.sender !== 'bot' || m.isLoading || !m.ui) continue;
      antworten++;
      stand = m.ui.ablauf ?? null;
    }
    // Zweites Review, Z-1: nach der Anmeldung nachgeladen — gilt, bis eine neue Serverantwort kommt
    const nach = this._standNachAnmeldung();
    if (nach && antworten <= nach.antworten) stand = nach.stand;
    // Z-8: abgemeldet ist die Leiste eines persönlichen Laufs weg (ihr Abbruch liefe anonym ins Leere)
    return stand?.persoenlich && !this._hasAccessBlock() ? null : stand;
  });
  /** Z-1: der Stand aus dem Nachladen nach einer Anmeldung, mit der Zahl der Serverantworten zu
   *  diesem Zeitpunkt — eine spätere Antwort gilt vor ihm. */
  private readonly _standNachAnmeldung = signal<{ stand: AblaufStand | null; antworten: number } | null>(null);
  /** K2b: ein Auftragsschritt mit `warten: gesperrt` wartet — das Eingabefeld zeigt den Hinweis als
   *  Platzhalter, bis eine Antwort ohne die Marke kommt. Bewusst eine WEICHE Sperre (zweites Review
   *  K2b): das Feld bleibt bedienbar, damit eine Krisennachricht immer getippt werden kann; anderes
   *  Getippte beantwortet das Backend mit dem Hinweis samt Knöpfen. Nach dem Neuladen zunächst ohne
   *  Hinweis — die nächste Antwort setzt ihn wieder. */
  readonly eingabeGesperrt = signal(false);

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
  /** `[emit-query-meta]` — `boerdi:query-meta` an `window` und der Ausgang
   *  `queryMeta` (Paket 19, Audit 2026-10-31 N-6). Suchbegriff und Such-URL
   *  gingen bis dahin ungefragt an jedes Skript der Gastseite; jetzt wie
   *  `emit-guide-suggestion`/`emit-routing-debug` nur auf Ansage. */
  readonly emitQueryMeta = input<boolean | string>(false);
  /** Jede backend-`page_action` (Host- + Widget-Integration). */
  readonly pageAction = output<{ action: string; payload: any }>();
  /** Top-1-Lotsen-Treffer pro Turn (gated durch `emitGuideSuggestion`). */
  readonly guideSuggestion = output<GuideSuggestionPayload>();
  /** Routing-Telemetrie pro Turn (gated durch `emitRoutingDebug`). */
  readonly routingDebug = output<RoutingDebugPayload>();
  /** MCP-Suchmetadaten jedes Zugs mit Suche — der Weg zur Widget-Hülle statt
   *  über `window` (Paket 19, N-6); gated durch `emitQueryMeta`. */
  readonly queryMeta = output<{ queries: QueryMetaEntry[] }>();
  /** Das maschinenlesbare Ergebnis eines Zuges (2026-08-14). Feuert NUR, wenn
   *  der Gastgeber ein `result_schema` erklärt hat — ungated, anders als
   *  `guideSuggestion`/`routingDebug`: das Schema IST hier schon die Ansage. */
  readonly agentResult = output<{ result: Record<string, any> | null; stop_reason: string }>();

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
  /** AS-7b (F-7): Abläufe mit Auslöser `seite` aus dem Boot-Bündel. Die Begrüßung stellt die
   *  passenden als Start-Chips vorn hin — gerechnet beim Zeigen aus dem aktuellen Pfad (Review AS-7b,
   *  Befund 4: nach einer SPA-Navigation stand sonst der Chip der alten Seite da). */
  readonly fuehrungsAngebote = input<AblaufSeite[]>([]);
  /** `show-welcome` — `false` startet mit LEEREM Verlauf: keine Startnachricht,
   *  keine Einstiegs-Chips. Für Einbettungen, die den Chat selbst anmoderieren
   *  (Browser-Plugin, edu-sharing-Seite) und keine zweite Begrüßung wollen.
   *  Die Kontext-Begrüßung des Backends hängt am Seitenkontext und bleibt. */
  readonly showWelcome = input<boolean | string>(true);
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
  private readonly _element: ElementRef<HTMLElement> = inject(ElementRef);
  /** Template-Anker: Auto-Follow-Container + Eingabefeld fürs Refokussieren. */
  private readonly _inputField = viewChild<ElementRef<HTMLInputElement>>('inputField');
  private readonly _messagesContainer = viewChild<ElementRef<HTMLElement>>('messagesContainer');

  /** Chat-API-Client. Tests ersetzen ihn nach Konstruktion (Muster ALT
   *  `comp.api`-Swap) — deshalb liest der Host ihn deferred. baseUrl setzt
   *  `ngOnInit` (8-4S-e) aus `[apiUrl]`. */
  private _api = new ChatApiClient();
  /** Die UI-Module dieses Bündels — ihre Namen meldet der Client dem Backend (Review U1-d1). */
  private readonly _modulRegister = inject(UI_MODUL_REGISTER);

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
    bsidKennung: () => this.uebergabeKennung(),
    trustedDomains: () => this._effectiveTrustedDomains(),
    inlineResultGrouping: () => this.inlineResultGroupingBool,
    t: (key, params) => this.t(key, params),
    modulRegister: () => this._modulRegister,
  });
  /** Druck-Gates + -Trigger (Lernpfad-/Canvas-Leisten). */
  readonly print = SHELL_PRINT;
  /** Stabile Referenz für `[renderMarkdown]` von `<boerdi-ui-bloecke>` — als Feld,
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

  /** Paket U1-c2: was die Trefferliste (UI-Modul) von der Shell braucht — stabil als Feld, damit
   *  OnPush nicht bei jedem Durchlauf einen neuen Eingabewert sieht. */
  protected readonly modulTreffer: ShellTreffer = {
    kontext: this.render.resultGroupsCtx,
    kacheln: () => this.cardsVisible,
    beschaeftigt: () => this.isLoading(),
    volltext: (nodeId, title) => void this.showContentText(nodeId, title),
    sammlung: (nodeId, title) => void this.browseCollection(nodeId, title),
    lernpfad: (nodeId, title) => void this.generateLearningPath(nodeId, title),
    alsEntwurf: (nodeId, title) => void editCollectionAsDraft(nodeId, title, this._contexts.collectionActions),
    zweig: (nodeId) => this._mitAbbruch((signal) => themenbaumZweig(nodeId, this._contexts.collectionActions, signal)),
    hochladen: (blockId, datei, onFortschritt) => this._mitAbbruch(
      (signal) => dokumentLesen(blockId, datei, onFortschritt, this._contexts.collectionActions, signal)),
    ablegen: (blockId, schritt) => this._mitAbbruch(
      (signal) => ablageSchritt(blockId, schritt, this._contexts.collectionActions, signal)),
    auftrag: (schritt) => schritt.schritt === 'abholen'
      ? auftragAbholen(schritt.ablauf, this._contexts.collectionActions)
      : schritt.schritt === 'abbrechen'
        ? auftragAbbrechen(schritt.ablauf, this._contexts.collectionActions)
        : this._mitAbbruch((signal) => auftragStand(schritt.ablauf, schritt.kuerzel, this._contexts.collectionActions, signal)),
    mehrLaden: (nachrichtId) => void this.loadMoreCards(nachrichtId),
  };

  /** Paket U1-d1: die Antwort eines abfragenden Moduls als nächster Zug — `text` wird die
   *  Nutzerblase, `ui_antwort` geht mit. Der Block ist danach beantwortet; jede andere offene
   *  Frage wird mit dem Zug veraltet (`addUserMessage`). Während eines Zugs nimmt die Shell keine
   *  Antwort an (das Modul sperrt seinen Knopf dann ohnehin). Kam der Zug nie beim Server an
   *  (kein `connected`, keine Antwort), ist die Frage wieder offen (Review U1-d1, Befund 7). */
  protected readonly modulAntworten: ShellAntworten = ({ nachrichtId, blockId, daten, text }) => {
    const blase = text.trim();
    if (this.isLoading() || !blase) {
      console.warn('boerdi: Modul-Antwort verworfen —', this.isLoading() ? 'ein Zug läuft' : 'ohne Text');
      return;
    }
    // Querschnitts-Review FE-2: ein inzwischen veralteter Block (ein Zug kam dazwischen) antwortet nicht
    // mehr — sonst stünde eine Blase im Chat, deren `ui_antwort` das Backend verwirft.
    if (!this.blockOffen(nachrichtId, blockId)) {
      console.warn('boerdi: Modul-Antwort verworfen — der Block ist nicht mehr offen');
      return;
    }
    this._store.update((msgs) => alsBeantwortet(msgs, nachrichtId, blockId, daten));
    // `runSendMessage` direkt statt `sendMessage`: nur es sagt, ob der Server den Zug angenommen hat.
    void runSendMessage(blase, undefined, undefined, this._sendCtx, { block_id: blockId, daten }).then((angenommen) => {
      if (!angenommen) this._store.update((msgs) => wiederOffen(msgs, nachrichtId, blockId));
    });
  };

  private blockOffen(nachrichtId: string, blockId: string): boolean {
    const msg = this.messages().find((m) => m.id === nachrichtId);
    return !!msg?.ui?.ui_bloecke?.some((b) => b.block_id === blockId && b.status === 'offen');
  }

  /** Paket U2 (Plan 2026-11-04, T-10): vorgemerkte Antworten offener Blöcke (Strukturentwurf) —
   *  sie gehen mit der nächsten getippten Nachricht mit (`sendMessage`). */
  private readonly _vormerkungen = new Vormerkungen();
  protected readonly modulVormerken: ShellVormerken = (auftrag) => this._vormerkungen.setzen(auftrag);
  /** U3-0: lädt die Bündel nachgeladener Module von der Widget-Adresse des Backends (gelesen beim
   *  Laden, denn `api-url` kommt erst nach dem Start). Einer je Shell: jedes Bündel lädt einmal. */
  protected readonly modulNachladen = erzeugeLader(() => this._api.apiBasis(), NACHLADE_INDEX);

  /** Trägt die Nachricht eine Trefferliste, die ihr Modul zeigt? Dann zeigt es die Boxen — die
   *  bisherigen schweigen; bei einer fremden Hauptversion (nur Textfassung) bleiben sie. */
  protected hatTrefferliste(msg: ChatMessage): boolean {
    return modulDarstellbar(msg, TREFFERLISTE, this._modulRegister);
  }

  /** Für die Druck-Tore im Template (`print.hatDokumentBox(msg, modulRegister)`). */
  protected get modulRegister(): ModulRegister {
    return this._modulRegister;
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
    // Nur der Tour-Start legt hierüber eine Blase an — ein Zug der Person wie im Eingabefeld:
    // offene Fragen schließen (Review U1). Tour-Tick und Kontext-Ping legen keine an.
    addUserMessage: (content) => {
      this._store.update(offeneFragenSchliessen);
      this._store.addUserMessage(content);
    },
    addBotMessage: (...args) => this._store.addBotMessage(...args),
    removeMessage: (id) => this._store.removeMessage(id),
    setScrollTarget: (id) => { this._scroll.setScrollTarget(id); },
    setLatestDebug: (debug, ui) => this._setzeLetzte(debug, ui),
    setEingabeGesperrt: (gesperrt) => this.eingabeGesperrt.set(gesperrt),
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
  /** AS-7b: der Seiten-Ping einer wartenden Führung (teilt den Kontext mit dem Kontext-Ping). */
  private readonly _seitenPing = new SeitenPing(this._contexts.contextGreeting);
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
    fuehrungsChips: () => fuehrungsChips(this.fuehrungsAngebote(), _aktuellerPfad(), this.locale()),
    seitenPingWartet: () => this.ablaufStand()?.status === 'wartet_seite',
    showWelcome: () => _attrIsTrue(this.showWelcome()),
    sessionId: () => this.sessionId,
    setSessionId: (id) => { this.sessionId = id; },
    resumedViaBsid: () => this._resumedViaBsid,
    setResumedViaBsid: (v) => { this._resumedViaBsid = v; },
    parsedPageContext: () => this.parsedPageContext,
    setParsedPageContext: (ctx) => { this.parsedPageContext = ctx; },
    hasUserMessages: () => this._store.messages().some((m) => m.sender === 'user'),
    setSpeechEnabled: (v) => this.speechBackendEnabled.set(v),
    setMessages: (msgs) => this._store.set(msgs),
    updateMessages: (u) => this._store.update(u),
    addUserMessage: (content, fromHost) => this._store.addUserMessage(content, fromHost),
    addBotMessage: (...args) => this._store.addBotMessage(...args),
    setLatestDebug: (d, ui) => this._setzeLetzte(d, ui),
    isLoading: () => this.isLoading(),
    setLoading: (v) => this.isLoading.set(v),
    setVerlaufBereit: (v) => this._verlaufBereit.set(v),
    gastAuftragWartet: () => this._wartendeAuftraege.length > 0,
    tour: this._tour,
    contextGreeting: this._contextGreeting,
    seitenPing: (neueSeite) => {
      if (neueSeite) this._seitenPing.zuruecksetzen();
      return this.ablaufStand()?.status === 'wartet_seite' ? this._seitenPing.senden() : Promise.resolve(false);
    },
    scrollToLatest: () => this._scroll.scrollToLatest(),
    t: (key, params) => this.t(key, params),
  };
  private readonly _lifecycle = new ShellLifecycle(this._lifecycleCtx);
  /** Paket RB-3 (Review AS-4b, Befund 4): `false`, solange der Verlauf einer fortgesetzten Sitzung
   *  lädt — Aufträge der Gastseite warten (`_mussWarten`), sonst stünde ihre Blase vor dem alten
   *  Gespräch. */
  private readonly _verlaufBereit = signal(true);
  /** Nach dem Laden: zuerst ein wartender Auftrag der Gastseite (Paket 10, H-2),
   *  dann ein zurückgestellter Seitengruß (Review Paket 7, C-5) — der wartet so
   *  hinter dem Auftrag, statt ihm den Zug wegzunehmen. Zuletzt ein Fokus, der
   *  aufs gesperrte Feld traf (`focusInput`). */
  private readonly _nachDemLaden = effect(() => {
    if (this.isLoading()) return;
    // Auch der Wechsel auf „Verlauf lädt“ löst einen Lauf aus — harmlos: Gruß und Fokus warten nur,
    // solange ein Zug lief (Review RB-3, Kleinigkeit 7).
    const verlaufDa = this._verlaufBereit();
    untracked(() => {
      if (verlaufDa) this._auftragNachholen();
      this._lifecycle.loadingEnded();
      this._fokusNachholen();
    });
  });

  /** Turn-Lebenszyklus-Seam (8-4S-c). */
  private readonly _sendCtx: SendMessageContext = {
    currentInput: () => this.userInput(),
    vomGastgeber: () => this._hostTurn,
    clearInput: () => this.userInput.set(''),
    setInput: (text) => this.userInput.set(text),
    sessionId: () => this.sessionId,
    isLoading: () => this.isLoading(),
    setLoading: (v) => this.isLoading.set(v),
    // Jeder Zug der Person schließt offene Fragen (U1-d1) — wie im Backend (`services/ui_antwort`).
    addUserMessage: (content) => {
      this._store.update(offeneFragenSchliessen);
      this._store.addUserMessage(content, this._hostTurn);
    },
    addBotMessage: (...args) => this._store.addBotMessage(...args),
    removeMessage: (id) => this._store.removeMessage(id),
    updateLoadingPhase: (id, label) => this._store.updateLoadingPhase(id, label),
    appendStreamText: (id, text, pos) => this._store.appendStreamText(id, text, pos),
    clearStreamText: (id) => this._store.clearStreamText(id),
    setScrollTarget: (id) => { this._scroll.setScrollTarget(id); },
    // Nach einem Zug nicht von der Gastseite weg (Paket 10, L-9).
    focusInput: () => { if (fokusZurueckholen(this._element.nativeElement)) this.focusInput(); },
    pageContextEnv: () => Object.keys(this.parsedPageContext).length
      ? { page_context: this.parsedPageContext } : undefined,
    stream: (msg, onEvent, env, action, actionParams, uiAntwort, ...mehr) =>
      this._api.stream(this.sessionId, msg, onEvent, env as any, action, actionParams, uiAntwort, ...mehr),
    // Review zu M-15: der POST-Rückfall eines Zugs hat keine Fortschrittsrahmen
    // und kann ein ganzer Agent-Lauf sein — eigene, längere Frist.
    post: (msg, env, action, actionParams, uiAntwort, ...mehr) =>
      this._api.post(this.sessionId, msg, env as any, action, actionParams, ZUG_POST_FRIST_MS, uiAntwort,
        ...mehr),
    formatPhaseLabel: (evt) => formatPhaseLabel(evt, (k, p) => this.t(k, p)),
    onResult: (resp, msg) => this._onResult(resp, msg),
    t: (key, params) => this.t(key, params),
    probe: () => this.probe(),
    answerFromHistory: async (msg, nachfrage) => {
      // Die Sitzung des Zuges, nicht die beim jeweiligen Abruf (Review C-3).
      const sitzung = this.sessionId;
      // Je Nachfrage ein Abbruch (Paket 9): wird das Widget entfernt, endet auch
      // der laufende Abruf, und eine späte Antwort erreicht `_onResult` nicht mehr.
      const steuerung = new AbortController();
      this._nachfragen.add(steuerung);
      try {
        return await antwortAusVerlaufHolen(
          (signal) => this._api.fetchHistory(sitzung, 6, signal), msg, sitzung, {
            nachId: nachfrage.nachId,
            abgebrochen: () => this._zerstoert || nachfrage.abgebrochen(),
            signal: steuerung.signal,
          });
      } finally {
        this._nachfragen.delete(steuerung);
      }
    },
  };
  /** Das Widget ist entfernt — eine laufende Nachfrage im Verlauf hört auf. */
  private _zerstoert = false;
  /** Laufende Nachfragen im Verlauf und Zweige des Themenbaums — beim Entfernen abgebrochen
   *  (Paket 9; Zweige seit Review U1 gesamt). */
  private readonly _nachfragen = new Set<AbortController>();

  /** Einen Abruf mit eigenem Abbruch starten, der mit dem Widget endet. */
  private async _mitAbbruch<T>(abruf: (signal: AbortSignal) => Promise<T>): Promise<T> {
    // Ein entferntes Widget startet nichts mehr (Review U3-3b, Befund 2: sonst lief ein Stapel weiter).
    if (this._zerstoert) throw new DOMException('Widget entfernt', 'AbortError');
    const steuerung = new AbortController();
    this._nachfragen.add(steuerung);
    try {
      return await abruf(steuerung.signal);
    } finally {
      this._nachfragen.delete(steuerung);
    }
  }

  /** Input-Routing-Seam (8-4S-d2b). */
  private readonly _routingCtx: InputRoutingContext = {
    tourReply: () => this.tourReply(),
    tourReplyEn: () => this.tourReplyEn(),
    guideModeActive: this.guideModeActive,
    trustedDomains: () => this._effectiveTrustedDomains(),
    // Nur für die `?bsid=`-Übergabe der Lotsen-Navigation — ohne persist leer (H-4).
    sessionId: () => this.uebergabeKennung(),
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
   *  der Stream/Fallback/Fehler abwickelt und `_onResult` als Erfolgs-Hook ruft.
   *  `uiAntwort` (U1-d1): Antwort auf einen abfragenden UI-Block (`modulAntworten`). */
  sendMessage(
    text?: string, action?: string, actionParams?: Record<string, any>, uiAntwort?: UiAntwortAnfrage,
  ): Promise<void> {
    // U2 (T-10): eine getippte Nachricht (Eingabefeld, Schnellantwort) nimmt den vorgemerkten
    // Stand eines offenen Blocks mit — der Block wird beantwortet statt veraltet. Kam der Zug nie an,
    // ist er wieder offen (wie `modulAntworten`). Ein Auftrag des Gastgebers (`startTask`) ist keine
    // Nachricht der Person und nimmt nichts mit (Review U2, Befund 5).
    const getippt = !action && !uiAntwort && !this._hostTurn && !this.isLoading()
      && !!(text ?? this.userInput()).trim();
    const mit = getippt ? this._vormerkungen.fuerZug(this.messages()) : null;
    if (!mit) return runSendMessage(text, action, actionParams, this._sendCtx, uiAntwort).then(() => undefined);
    this._store.update((msgs) => alsBeantwortet(msgs, mit.nachrichtId, mit.blockId, mit.daten));
    return runSendMessage(text, undefined, undefined, this._sendCtx, { block_id: mit.blockId, daten: mit.daten })
      .then((angenommen) => {
        if (!angenommen) this._store.update((msgs) => wiederOffen(msgs, mit.nachrichtId, mit.blockId));
      });
  }

  /** Gilt die Blase des laufenden Zuges als Auftrag des Gastgebers?
   *
   *  Ein Merker und kein Parameter, weil `runSendMessage` die Blase selbst
   *  anlegt (`ctx.addUserMessage`). Das ist gefahrlos: der Aufruf steht dort
   *  VOR dem ersten `await`, läuft also synchron innerhalb von `startTask` —
   *  zwischen Setzen und Lesen kann kein zweiter Zug dazwischenkommen. */
  private _hostTurn = false;

  /** **Public API** — einen Auftrag des Gastgebers als Zug starten.
   *
   *  Für Einbettungen, die den Chat auf ein Thema setzen wollen: „hier ist die
   *  Sammlung, hier der Seitentext, leg los" (Nutzer-Entscheid 2026-08-14).
   *  Danach ist es eine gewöhnliche Unterhaltung — der Auftrag ist der erste
   *  Zug, nicht ein Modus.
   *
   *  Der Satz erscheint im Verlauf, aber als eigene Auftrags-Blase: die Person
   *  hat ihn nicht gesagt. Unsichtbar wäre bequemer und unehrlich — sie sähe
   *  eine Antwort auf eine Frage, die sie nie gestellt hat. */
  startTask(text: string): Promise<void> {
    const auftrag = (text ?? '').trim();
    if (!auftrag) return Promise.resolve();
    // Paket 10 (Audit H-2): läuft noch ein Zug — beim Erstaufruf meist der
    // Kontext-Ping —, fiele der Auftrag am `isLoading`-Tor still weg. Er wartet,
    // bis das Laden endet; das Promise erfüllt sich erst mit seinem Zug.
    if (this._mussWarten()) {
      return new Promise((fertig) => this._wartendeAuftraege.push({
        starte: () => this.startTask(auftrag), fertig, sid: this.sessionId }));
    }
    return this._alsGastgeber(() => this.sendMessage(auftrag));
  }

  /** **Public API** (AS-4b, Plan 2026-11-09 E2 A) — einen Ablauf mit Startdaten starten.
   *
   *  Die Gastseite gibt die Kennung des Ablaufs und ihre Daten (`{sammlung: <nodeId>}`); der Zug
   *  geht als Direktaktion `ablauf_starten` mit `{ablauf, start}` hinaus. Das Backend nimmt Daten
   *  bei einem Ablauf mit dem Auslöser „Gastseite“ (seit AS-5a auch „KI schlägt vor“, dann ohne
   *  die Rechte der Gastseite) und prüft sie gegen dessen Startschema —
   *  sie sind Eingaben, nie Rechte. Hier nur: eine gültige Kennung, ein reines Objekt (als JSON
   *  kopiert: keine Funktionen, keine Prototypen). Sonst startet nichts.
   *
   *  Sichtbar als Auftrags-Blase des Gastgebers, wie `startTask`; wartet wie dieser auf einen
   *  laufenden Zug. */
  startAblauf(id: string, daten?: Record<string, unknown>): Promise<void> {
    const geprueft = ablaufStartPruefen(id, daten);
    if (!geprueft) {
      // Review AS-4b, Befund 7: nicht still — aber ohne Werte (Daten der Gastseite)
      console.warn('boerdi-chat: startAblauf — ungültige Kennung oder Startdaten; der Ablauf startet nicht.');
      return Promise.resolve();
    }
    const { ablauf, start } = geprueft;
    // `quelle`: die Bremse „läuft schon“ (Review AS-4b, Befund 1) — und, nur beim Auslöser
    // „Gastseite“, die Herkunft, mit der Kennungen an lesende Werkzeuge dürfen (Entscheid AS-4a, RB)
    const params: Record<string, unknown> = start
      ? { ablauf, start, quelle: 'gastseite' } : { ablauf, quelle: 'gastseite' };
    if (this._mussWarten()) {
      return new Promise((fertig) => this._wartendeAuftraege.push({
        starte: () => this.startAblauf(ablauf, start), fertig, sid: this.sessionId }));
    }
    return this._alsGastgeber(
      () => this.sendMessage(this.t('chat.hostAblauf'), 'ablauf_starten', params));
  }

  /** Paket AS-Ub: „Abbrechen“ in der Ablauf-Leiste — eine Direktaktion; das Backend fragt nach,
   *  bevor es den Lauf (samt Auftrag) beendet (U-5). */
  onAblaufAbbrechen(): void {
    void this.sendMessage(this.t('ablauf.leiste.abbrechen'), 'ablauf_abbrechen', {});
  }

  /** Ein Auftrag der Gastseite wartet während eines Zugs und, in einer fortgesetzten Sitzung, bis
   *  der Verlauf da ist (Paket RB-3). */
  private _mussWarten(): boolean {
    return this.isLoading() || !this._verlaufBereit();
  }

  /** Einen Zug als Auftrag des Gastgebers senden — der Merker gilt nur, solange die Blase
   *  entsteht. Im `finally`, nicht nach dem `await`: die Blase entsteht synchron, und ein
   *  Merker, der bis zum Ende des Zuges stünde, färbte die nächste getippte Nachricht mit. */
  private _alsGastgeber(senden: () => Promise<void>): Promise<void> {
    this._hostTurn = true;
    try {
      return senden();
    } finally {
      this._hostTurn = false;
    }
  }

  /** Aufträge und Abläufe des Gastgebers, die während eines Zugs kamen — in ihrer Reihenfolge
   *  (H-2). */
  private readonly _wartendeAuftraege: { starte: () => Promise<void>; fertig: () => void; sid: string }[] = [];

  /** Den nächsten wartenden Auftrag starten; die übrigen folgen je nach Zugende. */
  private _auftragNachholen(): void {
    let naechster = this._wartendeAuftraege.shift();
    // Querschnitts-Review AS-4, Befund 2: ein Auftrag gehört zu dem Gespräch, in dem er kam —
    // wechselte es inzwischen (Wiederkehr, Neustart), verfällt er, statt im falschen zu laufen.
    // (Leer: eingereiht, bevor die Shell ihr Gespräch hatte — gehört zu keinem anderen.)
    while (naechster && naechster.sid && naechster.sid !== this.sessionId) {
      console.warn('boerdi-chat: ein wartender Auftrag der Seite verfällt — das Gespräch wechselte.');
      naechster.fertig();
      naechster = this._wartendeAuftraege.shift();
    }
    if (naechster) void naechster.starte().then(naechster.fertig);
  }

  /** Erfolgs-Seiteneffekte eines Turns — ALT `sendMessage`-Tail (522-560):
   *  Tour-Flag pflegen (getippte Trigger-Phrase startet die Tour über diesen
   *  Pfad), Debug-Panel füttern, query-meta broadcasten, page_action
   *  weiterreichen, Host-Events (Lotsen-Navigate/Suggestion/Routing) feuern und
   *  bei aktivem autoSpeak die Antwort vorlesen. */
  /** Debug-Panel füttern — Debug-Block und `ui` der jüngsten Antwort zusammen. */
  private _setzeLetzte(debug: DebugInfo | null | undefined, ui?: UiInfo | null): void {
    this.latestDebug.set(debug ?? null);
    this.latestUi.set(ui ?? null);
  }

  private _onResult(resp: ChatResponse, userMessage: string): void {
    this._tour.applyTourState(resp);
    this._setzeLetzte(resp.debug, resp.ui);
    // Paket 19 (Audit 2026-10-31 N-33): erst, was der Zug selbst verlangt —
    // Schreibvorgang, abgewiesene Anmeldung, Vorlesen —, dann die Rückrufe und
    // Ereignisse der Gastseite. Ein werfender Rückruf nahm sonst alles danach mit.
    this.eingabeGesperrt.set(resp.eingabe_gesperrt === true);
    if (resp.prepared_write) this._executePreparedWrite(resp.prepared_write);
    if (resp.auth_invalid) this._anmeldungAbgewiesen();
    else this._frist.planen(resp.auth_expires_at);
    if (this._speech.autoSpeak && resp.content) {
      this._speech.autoSpeakText(resp.content);
    }
    try {
      this._meldeAnDieGastseite(resp, userMessage);
    } catch (err) {
      console.error('boerdi: Rückruf der Gastseite gescheitert —', fehlerKurz(err));
    }
  }

  /** Was die Gastseite von einem Zug erfährt — Rückrufe, Ausgänge, Ereignisse. */
  private _meldeAnDieGastseite(resp: ChatResponse, userMessage: string): void {
    // Review zu N-6: Output UND window-Ereignis nur mit `emit-query-meta` — die
    // Hülle macht den Output über Angular Elements zum DOM-Ereignis am Element.
    if (resp.query_metas?.length && _attrIsTrue(this.emitQueryMeta())) {
      const nutzlast = { queries: resp.query_metas };
      this.queryMeta.emit(nutzlast);
      dispatchHostEvent(HOST_EVENTS.queryMeta, nutzlast);
    }
    this.dispatchPageAction(resp.page_action);
    maybeDispatchGuideNavigate(userMessage, resp.cards, this._contexts.hostEvents);
    maybeDispatchGuideSuggestion(userMessage, resp.cards, this._contexts.hostEvents);
    maybeDispatchRoutingDebug(userMessage, resp, this._contexts.hostEvents);
    this._reportAgentResult(resp);
  }

  /** Das maschinenlesbare Ergebnis an den Gastgeber melden (2026-08-14).
   *
   *  Dieselbe Bedingung wie im Backend (`nodes/persist.py`): gemeldet wird,
   *  sobald es ein Ergebnis ODER einen Ende-Grund gibt. Der Grund allein ist
   *  keine leere Meldung, sondern die Auskunft „dieser Zug gab keins her — und
   *  hier ist, warum". Ohne Schema setzt das Backend beide nicht, und dann
   *  bleibt es hier still: ein Ereignis bei jeder Antwort wäre ein Signal, das
   *  nichts bedeutet. */
  private _reportAgentResult(resp: ChatResponse): void {
    const grund = resp.result_stop_reason || '';
    if (resp.result == null && !grund) return;
    const nutzlast = { result: resp.result ?? null, stop_reason: grund };
    dispatchHostEvent(HOST_EVENTS.agentResult, nutzlast);
    this.agentResult.emit(nutzlast);
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
    }).catch(err => console.error('vorbereitete Änderung: Vorgang gescheitert', fehlerKurz(err)));
  }

  /** page_action an alle Hörer: Host-Callback + Angular-Output + window-Event.
   *  MUSS aus jedem API-Pfad laufen, sonst aktualisiert die Canvas nicht.
   *  Verbatim aus ALT chat.component.ts:1075-1080. */
  private dispatchPageAction(pa: { action: string; payload: any } | null | undefined): void {
    if (!pa) return;
    // Review zu N-33: ein werfender Rückruf der Gastseite nimmt Output und
    // Ereignis nicht mit.
    try {
      if (this.onPageAction) this.onPageAction(pa);
    } catch (err) {
      console.error('boerdi: onPageAction der Gastseite gescheitert —', fehlerKurz(err));
    }
    this.pageAction.emit(pa);
    dispatchHostEvent(HOST_EVENTS.pageAction, pa);
  }

  /** Eingabefeld refokussieren — nach jedem Turn (intern) und wenn die
   *  Widget-Hülle das Panel öffnet (ALT `chatRef?.inputField?.…focus()`;
   *  hier eine Methode statt eines öffentlichen ViewChild).
   *
   *  Ein gesperrtes Feld nimmt keinen Fokus an. Beim ersten Öffnen läuft aber
   *  meist der Kontext-Ping (`isLoading`) — der Auftrag wartet dann, bis das
   *  Laden endet (`_nachDemLaden`), statt still zu verfallen. */
  focusInput(): void {
    const vorher = this._fokusZiel();
    setTimeout(() => {
      const feld = this._inputField()?.nativeElement;
      // CI-Befund PR #46: hat die Person den Fokus in den 100 ms selbst gesetzt (in einen Block
      // der Antwort, auf die Gastseite), bleibt er dort.
      const jetzt = this._fokusZiel();
      if (jetzt && jetzt !== vorher && jetzt !== document.body && jetzt !== feld) return;
      if (feld?.disabled && this.isLoading()) this._fokusWartet = true;
      else feld?.focus();
    }, 100);
  }

  /** Wo der Fokus gerade steht — im Shadow DOM des Widgets über dessen Wurzel gefragt (dort ist
   *  `document.activeElement` der Wirt), sonst auf der Seite. */
  private _fokusZiel(): Element | null {
    const wurzel = this._element.nativeElement.getRootNode() as Document | ShadowRoot;
    return wurzel.activeElement ?? document.activeElement;
  }

  private _fokusWartet = false;

  /** Den wartenden Fokus-Auftrag einlösen — mit derselben Vorsicht wie nach
   *  einem Zug: nicht von der Gastseite weg (Paket 10, L-9). */
  private _fokusNachholen(): void {
    if (!this._fokusWartet) return;
    this._fokusWartet = false;
    if (fokusZurueckholen(this._element.nativeElement)) this.focusInput();
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

  /** Paket K2a: „Gespräch fortsetzen“ — ein Ablauf der angemeldeten Person wartet in einem anderen
   *  Gespräch. Gefragt wird, sobald ein Block da ist und kein Zug läuft (einmal je Gespräch). */
  readonly fortsetzen = new FortsetzenController({
    abrufen: (sid) => this._api.offeneVorgaenge(sid),
    sessionId: () => this.sessionId,
    block: () => readAccessBlock(),
  });
  /** Paket AS-Ud (Plan 2026-11-09 §5j): „Meine Vorgänge“ — die eigenen, nicht abgeschlossenen
   *  Vorgänge anderer Gespräche; der Knopf steht nur mit Anmeldung neben dem Anmelde-Knopf. Gilt
   *  wie das Angebot oben nur für das Gespräch und den Block, mit denen gefragt wurde. */
  readonly meineVorgaenge = new MeineVorgaengeController({
    abrufen: (sid) => this._api.eigeneVorgaenge(sid),
    loeschen: async (sid, id) => {
      const gespraech = this.meineVorgaenge.liste().find((v) => v.id === id)?.session_id;
      const ergebnis = await this._api.vorgangLoeschen(sid, id);
      // ein Hinweis „Gespräch fortsetzen“ auf genau diesen Vorgang führte jetzt ins Leere
      if (gespraech && this.fortsetzen.angebot()?.session_id === gespraech) this.fortsetzen.verwerfen();
      return ergebnis;
    },
    sessionId: () => this.sessionId,
    block: () => readAccessBlock(),
  });
  private readonly _vorgaengeKnopf = viewChild<ElementRef<HTMLButtonElement>>('vorgaengeKnopf');

  /** Zählt Anlässe, neu zu fragen, die kein anderes Signal trägt: ein neuer Block (Ticket-Tausch,
   *  Anmeldung — Review K2a, Befund 2/3), ein Neustart (Befund 8). */
  private readonly _fortsetzenAnlass = signal(0);
  private readonly _fortsetzenFragen = effect(() => {
    this._fortsetzenAnlass();
    if (!this._hasAccessBlock() || this.isLoading() || this.probe()) return;
    untracked(() => { void this.fortsetzen.pruefen().then(() => this._cdr.markForCheck()); });
  });

  /** Ein neuer Block oder ein neues Gespräch: altes Angebot weg, neu fragen. */
  private _fortsetzenNeu(): void {
    this._standNachAnmeldung.set(null);   // Z-1: galt dem alten Gespräch oder Block
    this.fortsetzen.vergessen();
    this.meineVorgaenge.vergessen();
    this._fortsetzenAnlass.update((n) => n + 1);
  }

  /** Datum des Angebots in der Sprache des Widgets. */
  fortsetzenDatum(v: OffenerVorgang): string {
    return fortsetzenDatum(v.geaendert, this.locale());
  }

  /** Klick auf „Fortsetzen“: auf das Gespräch des Vorgangs wechseln und seinen Verlauf laden. Wartet
   *  dort ein Auftrag, fragt „Stand prüfen“ gleich nach ihm — fertig heißt dann: das Ergebnis wird
   *  abgeholt und der Ablauf geht weiter; sonst kommen „läuft noch“ und die Knöpfe. */
  async onFortsetzen(): Promise<void> {
    const v = this.fortsetzen.gueltiges();
    if (!v || this.isLoading()) return;
    this.fortsetzen.verwerfen();
    // Review K2a, Befund 4: `wechseln` hält das Laden, bis der Verlauf da ist — sonst landete eine
    // getippte Nachricht vor ihm, und „Stand prüfen“ fiele danach still aus.
    await this._zumVorgang(v);
    this.focusInput();   // Befund 5: der geklickte Knopf ist weg — der Fokus nicht ins Leere
  }

  /** Auf das Gespräch eines Vorgangs wechseln (wenn es nicht schon dieses ist) und bei einem
   *  wartenden Auftrag „Stand prüfen“ fragen — für „Fortsetzen“ (K2a) und die Wiederkehr (AS-4c). */
  private async _zumVorgang(v: { session_id: string; status: string; ablauf: string | null },
  ): Promise<boolean> {
    const gewechselt = v.session_id === this.sessionId || await this._lifecycle.wechseln(v.session_id);
    // Review AS-Ud, Befund 1: die Liste „Meine Vorgänge“ galt dem alten Gespräch
    if (gewechselt) this.meineVorgaenge.vergessen();
    // Querschnitts-Review AS-4, Befund 5: der Hinweis „gesperrt“ gehört zum alten Gespräch
    if (gewechselt) this.eingabeGesperrt.set(false);
    if (gewechselt && v.status === 'wartet_auftrag' && v.ablauf) {
      const ablauf = v.ablauf;
      const pruefen = () => this.sendMessage(
        this.t('fortsetzen.pruefen'), 'ablauf_auftrag_pruefen', { ablauf });
      // Kam nach dem Wechsel schon ein anderer Zug in Gang, wartet „Stand prüfen“ vorn in der
      // Reihe statt still auszufallen (Review AS-4c, Befund 2) — ebenso hinter dem Verlauf.
      if (this._mussWarten()) {
        await new Promise<void>((fertig) => this._wartendeAuftraege.unshift({
          starte: pruefen, fertig, sid: this.sessionId }));
      } else {
        await pruefen();
      }
    }
    this._cdr.markForCheck();
    return gewechselt;
  }

  /** AS-4c (Review, Befund 5): eine Wiederkehr, die an der fehlenden Anmeldung scheiterte —
   *  nach der Anmeldung einmal neu versucht. Nur im Speicher. */
  private _wiederkehrWartet: { kennung: WiederkehrKennung;
    beimErgebnis?: (a: WiederkehrAusgang) => void } | null = null;

  /** Ob ein Zugangsblock da ist — eigene Naht für die Specs. */
  private _hatBlock(): boolean {
    return readAccessBlock() !== null;
  }

  /** Nach der Anmeldung: eine gescheiterte Wiederkehr einmal neu versuchen. */
  private _wiederkehrNachDerAnmeldung(): Promise<unknown> {
    const wartet = this._wiederkehrWartet;
    this._wiederkehrWartet = null;
    return wartet ? this.vorgangFortsetzen(wartet.kennung, wartet.beimErgebnis) : Promise.resolve();
  }

  /** **Public API** (AS-4c, Plan 2026-11-09 R3) — mit einer Vorgang- oder Auftragskennung der
   *  Gastseite (Benachrichtigung, Link) zur Arbeit zurückkehren.
   *
   *  Das Backend gibt das Gespräch nur der angemeldeten Besitzerin; fremd, unbekannt, abgelaufen
   *  und ohne Anmeldung sehen gleich aus. Gefunden: wechseln wie „Fortsetzen“ und bei einem
   *  Auftrag „Stand prüfen“. Nicht gefunden: eine Warnung in der Konsole, ohne die Kennung. */
  async vorgangFortsetzen(roh: { vorgang?: string; auftrag?: string },
    beimErgebnis?: (a: WiederkehrAusgang) => void): Promise<WiederkehrAusgang> {
    const kennung = wiederkehrKennung(roh);
    if (!kennung) {
      console.warn('boerdi-chat: vorgangFortsetzen — genau eine gültige Kennung (vorgang oder auftrag) nötig.');
      beimErgebnis?.('ungueltig');
      return 'ungueltig';
    }
    // Review PR #51 (Widget, Befund 2): wie `startTask` auch auf den Verlauf warten — sonst hinge
    // `restoreHistory` Begrüßung und alten Verlauf unter die neue Blase (derselbe Fehler wie RB-3)
    if (this._mussWarten()) {
      let ausgang: WiederkehrAusgang = 'verworfen';
      return new Promise((fertig) => this._wartendeAuftraege.push({
        starte: () => this.vorgangFortsetzen(kennung, beimErgebnis).then((a) => { ausgang = a; }),
        fertig: () => fertig(ausgang), sid: this.sessionId }));
    }
    const ausgang = await this._wiederkehr(kennung, beimErgebnis);
    // „anmeldung“ meldet erst der neue Versuch nach der Anmeldung (Nachprüfung Querschnitt AS-4,
    // Befund 6: sonst fehlte dem Widget der Merker nach einem gelungenen zweiten Versuch)
    if (ausgang !== 'anmeldung') beimErgebnis?.(ausgang);
    return ausgang;
  }

  private async _wiederkehr(kennung: WiederkehrKennung,
    beimErgebnis?: (a: WiederkehrAusgang) => void): Promise<WiederkehrAusgang> {
    // Review AS-4c, Befund 2: die Abfrage hält das Laden — sonst liefe ein getippter Zug im alten
    // Gespräch, und ohne Treffer bliebe die Warteschlange liegen. Das Ende des Ladens zieht den
    // nächsten wartenden Auftrag nach; `wechseln` und `sendMessage` setzen es gleich danach
    // (synchron) wieder. Querschnitts-Review AS-4, Befund 4: abbrechbar und nur für das Gespräch,
    // in dem gefragt wurde.
    const veraltet = sitzungsWache(() => this.sessionId);
    this.isLoading.set(true);
    let v = null;
    let status: number | null = null;
    try {
      v = await this._mitAbbruch((signal) => this._api.wiederkehr(this.sessionId, kennung, signal));
    } catch (e) {
      v = null;
      status = typeof (e as { status?: unknown })?.status === 'number' ? (e as { status: number }).status : 0;
    } finally {
      // ein Neustart hat das Laden selbst freigegeben — und vielleicht schon einen neuen Zug
      if (!veraltet()) this.isLoading.set(false);
    }
    if (veraltet() || this._zerstoert) return 'verworfen';
    if (!v) {
      console.warn('boerdi-chat: vorgangFortsetzen — nichts zum Fortsetzen (Anmeldung, Kennung oder Netz).');
      // Im Chat erklärt (Review AS-4c, Befund 5). Ohne Anmeldung (oder abgewiesen) weiß der Client
      // das ohnehin — kein Orakel; „nichts“ lautet für fremd, unbekannt und abgelaufen gleich; ein
      // Server- oder Netzfehler heißt „später“ (Querschnitts-Review AS-4, Befund 6).
      const ausgang: WiederkehrAusgang = !this._hatBlock() || status === 403 ? 'anmeldung'
        : status === 404 || status === null ? 'nichts' : 'fehler';
      if (ausgang === 'anmeldung') this._wiederkehrWartet = { kennung, beimErgebnis };
      const schluessel = { anmeldung: 'wiederkehr.anmelden', nichts: 'wiederkehr.nichts',
        fehler: 'wiederkehr.spaeter' }[ausgang];
      this._store.addBotMessage(this.t(schluessel), false, [],
        ausgang === 'anmeldung' ? [AUTH_QR_MARKER] : []);
      this._cdr.markForCheck();
      return ausgang;
    }
    // Review AS-4c, Befund 6: nur ein Angebot zu genau diesem Gespräch ist erledigt
    if (this.fortsetzen.angebot()?.session_id === v.session_id) this.fortsetzen.verwerfen();
    // ein gescheiterter Wechsel ist kein Ergebnis (Nachprüfung, Befund 8)
    return (await this._zumVorgang(v)) ? 'gefunden' : 'verworfen';
  }

  /** Zweites Review, Z-1: nach einer gelungenen Anmeldung den Stand des Laufs einmal nachholen —
   *  der Verlauf beim Start ging ohne Anmeldung hinaus (neuer Tab, Ticket-Tausch) und kannte ihn
   *  nicht. Die letzten Einträge genügen: der Stand hängt an den Antworten nach der letzten Frage.
   *  Fehler bleiben still (eine Anzeige); ohne Antwort im Ausschnitt bleibt alles, wie es ist. */
  private async _standNachladen(): Promise<void> {
    const sid = this.sessionId;
    const antworten = this.messages().filter((m) => m.sender === 'bot' && !m.isLoading && m.ui).length;
    try {
      const verlauf = await this._api.fetchHistory(sid, 5);
      if (sid !== this.sessionId) return;
      const letzte = [...verlauf].reverse().find((m) => m.role === 'assistant');
      if (!letzte) return;
      this._standNachAnmeldung.set({ stand: letzte.ui?.ablauf ?? null, antworten });
    } catch {
      /* still — die Leiste kommt mit der nächsten Antwort */
    }
  }

  /** AS-Ud: „Meine Vorgänge“ auf- oder zuklappen. */
  onVorgaengeUmschalten(): void {
    void this.meineVorgaenge.umschalten();
  }

  /** AS-Ud: Schließen im Panel (× oder Esc) — der Fokus zurück an den Knopf, der es öffnete. */
  onVorgaengeSchliessen(): void {
    this.meineVorgaenge.schliessen();
    this._vorgaengeKnopf()?.nativeElement.focus();
  }

  /** AS-Ud: „Fortsetzen“ in der Liste — wie der Hinweis „Gespräch fortsetzen“ (K2a). */
  async onVorgangFortsetzen(v: EigenerVorgang): Promise<void> {
    if (this.isLoading()) return;
    this.meineVorgaenge.schliessen();
    if (this.fortsetzen.angebot()?.session_id === v.session_id) this.fortsetzen.verwerfen();
    await this._zumVorgang(v);
    this.focusInput();   // das Panel ist zu — der Fokus nicht ins Leere
  }

  /** × am Hinweis: schließen, Fokus zurück in die Eingabe (Review K2a, Befund 5). */
  onFortsetzenSchliessen(): void {
    this.fortsetzen.verwerfen();
    this.focusInput();
  }

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
    // Plan 2026-11-07 (R2/CB-9): nach einem ausdrücklichen „Abmelden“ nicht von selbst neu.
    if (!ticket || this._ticketTried === ticket || isSignedOut()) return;
    // Paket 10 (Kurzaudit S-4): bis der Tausch endet, warten Züge — schon bevor die
    // Anmelde-Adresse da ist. Sonst gingen Kontext-Ping und frühe Aufträge anonym.
    if (!this._ticketSperre) {
      const { sperre, freigeben } = anmeldeSperre();
      this._ticketSperre = freigeben;
      this._api.warteAufAnmeldung(sperre);
    }
    if (!basis) return;
    this._ticketTried = ticket;
    void this._tauscheTicket(ticket, basis);
  });

  /** Ticket gegen Block tauschen; bis zum Ende warten die Züge (S-4). Gibt zurück, ob ein Block
   *  da ist. Auch nach Ablauf oder Abweisung des Blocks (Plan 2026-11-07, R1). */
  private _tauscheTicket(ticket: string, basis: string): Promise<boolean> {
    if (!this._ticketSperre) {
      const { sperre, freigeben } = anmeldeSperre();
      this._ticketSperre = freigeben;
      this._api.warteAufAnmeldung(sperre);
    }
    return runTicketLogin({ ticket: () => ticket, mcpAuthBase: () => basis }).then((ausgang) => {
      if (ausgang === 'done' && isSignedOut()) {
        // Review 2026-11-07 (Befund 6): während des Tauschs abgemeldet — der neue Block darf
        // nicht bleiben, sonst wäre die Person nach dem Abmelden wieder angemeldet.
        clearAccessBlock();
        this._hasAccessBlock.set(false);
        return false;
      }
      if (ausgang === 'done') {
        this._hasAccessBlock.set(readAccessBlock() !== null);
        this._fortsetzenNeu();   // K2a: ein neuer Block kann einer anderen Person gehören
        void this._standNachladen();   // Z-1: der Lauf der Person, nun angemeldet
        void this._wiederkehrNachDerAnmeldung();   // Querschnitts-Review AS-4, Befund 6
        this._cdr.markForCheck();
        return true;
      }
      console.warn('WLO-Anmeldung über das Seiten-Ticket nicht gelungen:', ausgang);
      return false;
    }).finally(() => {
      this._ticketSperre?.();
      this._ticketSperre = null;
    });
  }

  /** Das Seiten-Ticket noch einmal tauschen — wenn es eins gibt und niemand sich abgemeldet hat.
   *  `false`: kein Tausch möglich. Ein Tausch VOR dem Ablauf verlängert nichts (MCP R1). */
  private _ticketErneut(): Promise<boolean> {
    const ticket = this.ticket().trim();
    const basis = this.mcpAuthBase().trim();
    if (!ticket || !basis || isSignedOut() || this._zerstoert) return Promise.resolve(false);
    return this._tauscheTicket(ticket, basis);
  }

  /** Die Frist des Blocks (Plan 2026-11-07, R1): Ticket nach dem Ablauf neu tauschen, sonst kurz
   *  davor die Anmeldung anbieten. */
  private readonly _frist = new AnmeldeFrist({
    ticketWeg: () => Boolean(this.ticket().trim()) && !isSignedOut(),
    neuTauschen: () => {
      // Ein gelungener Tausch nach Ablauf gibt die Erneuerung nach einer Abweisung wieder frei —
      // sonst endete die zweite 12-h-Frist eines langen Tages im Satz statt im Tausch (Befund 8).
      void this._ticketErneut().then((neu) => { if (neu) this._ticketNachAbweisung = ''; });
    },
    hinweisen: () => {
      if (readAccessBlock() === null) return;
      this._store.addBotMessage(this.t('auth.expiresSoon'), false, [], [AUTH_QR_MARKER]);
      this._cdr.markForCheck();
    },
  });

  /** Ein Ticket wird nach einer Abweisung höchstens einmal je Wert neu getauscht — sonst liefe
   *  jeder Zug in denselben Kreis, wenn der Server das Ticket selbst nicht mehr annimmt. */
  private _ticketNachAbweisung = '';

  /** Gibt die Züge frei, die auf den Ticket-Tausch warten (S-4). */
  private _ticketSperre: (() => void) | null = null;

  /** Was der Knopf in der Fußzeile zeigt — Entscheidung in `session/auth-button`. */
  readonly authButton = computed(() => authButtonState(this.mcpAuthBase(), this._hasAccessBlock()));

  /** Der Server wies den Block ab (Paket 10, Kurzaudit A-3): weg damit, der Knopf
   *  bietet wieder „Anmelden“ an, und ein Satz sagt, warum. */
  private _anmeldungAbgewiesen(): void {
    clearAccessBlock();
    this._hasAccessBlock.set(false);
    this._frist.vergessen();
    this.fortsetzen.vergessen();
    this.meineVorgaenge.vergessen();
    // Nach einem Abmelden ist eine Abweisung keine Nachricht wert (Review 2026-11-07, Befund 8).
    if (isSignedOut()) return;
    // Plan 2026-11-07 (RB-1): ein Ticket-Block lief nach 12 h ab — still neu tauschen, einmal je
    // Ticket. Erst wenn das nicht geht, erfährt es die Person.
    const ticket = this.ticket().trim();
    if (ticket && ticket !== this._ticketNachAbweisung) {
      this._ticketNachAbweisung = ticket;
      void this._ticketErneut().then((neu) => {
        if (!neu) this._store.addBotMessage(this.t('auth.expired'));
        this._cdr.markForCheck();
      });
      return;
    }
    this._store.addBotMessage(this.t('auth.expired'));
  }

  /** Klick auf den Anmelde-/Abmelde-Knopf.
   *
   *  Abmelden räumt NUR den Zugangsblock, nicht das Gespräch — dafür sitzt der
   *  Neustart-Knopf daneben. Anmelden startet SYNCHRON: der Klick ist die
   *  Nutzergeste, ohne die der Browser das Anmeldefenster blockt. */
  onAuthClick(): void {
    if (this.authButton() === 'signOut') {
      // Plan 2026-11-07 (RB-2): das Backend widerruft den Block am MCP-Server. Hier sofort aus dem
      // Tab — er reist ausdrücklich mit, also schadet das Löschen dem Widerruf nicht.
      const block = readAccessBlock();
      clearAccessBlock();
      markSignedOut();
      this._frist.vergessen();
      this.fortsetzen.vergessen();
      this.meineVorgaenge.vergessen();
      this._hasAccessBlock.set(false);
      void (block ? this._api.abmelden(block) : Promise.resolve(false)).then((beendet) => {
        this._store.addBotMessage(this.t(beendet ? 'auth.signedOut' : 'auth.signedOutLocal'));
        this._cdr.markForCheck();
      });
      return;
    }
    this._signInAndRefresh();
  }

  /** Anmelden und danach den Knopf nachziehen. Beide Auslöser — dieser Knopf
   *  und der `__auth__`-Chip — laufen hier durch, sonst stünde der Knopf nach
   *  einer Anmeldung über den Chip weiter auf „Anmelden". */
  private _signInAndRefresh(): void {
    void this.startSignIn().then(() => {
      const angemeldet = readAccessBlock() !== null;
      // Eine Anmeldung von Hand hebt das Abmelden auf (R2/CB-9).
      if (angemeldet) clearSignedOut();
      this._hasAccessBlock.set(angemeldet);
      this._fortsetzenNeu();     // K2a: nach der Anmeldung fragen, mit diesem Block
      if (angemeldet) {
        void this._standNachladen();   // Z-1: der Lauf der Person, nun angemeldet (Review PR #51, W4)
        void this._wiederkehrNachDerAnmeldung();   // AS-4c, Befund 5
      }
    });
  }

  /** Klick auf einen Standard-Quick-Reply (Tour-Start | Action-Pill | Text). */
  onQuickReply(reply: string): void {
    routeQuickReply(reply, this._routingCtx);
  }

  /** Klick auf einen Guide-Quick-Reply (`__guide__|…`) — Same-Tab-Navigation. */
  onGuideQuickReply(qr: string): void {
    const url = guideQuickReplyTarget(qr, this._routingCtx);
    // AS-7b: der Weg einer Führung darf auf derselben Herkunft auch ohne Vertrauensliste gehen
    if (url) this.onGuideNavigate(url, qr.startsWith(FUEHRUNG_QR_PREFIX));
  }

  /** Bot-getriebene „Bring mich hin"-Navigation — T-3-fail-closed über den
   *  Resolver; nur der window-Sprung ist hier (Verbatim ALT 1093-1097). */
  onGuideNavigate(url: string | undefined, gleicheHerkunft = false): void {
    const finalUrl = resolveGuideNavTarget(url, this._routingCtx, gleicheHerkunft);
    if (!finalUrl) return;
    try { window.location.href = finalUrl; }
    catch { window.open(finalUrl, '_self', 'noopener'); }
  }

  /** Enter (ohne Shift) sendet; Shift+Enter erlaubt Zeilenumbruch. Während einer
   *  IME-Eingabe bestätigt Enter die Komposition und sendet nicht (Paket 10, L-9);
   *  Safari meldet sie nur über `keyCode` 229. */
  onKeydown(event: KeyboardEvent): void {
    if (event.isComposing || event.keyCode === 229) return;
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

  /** **Public** — die Kennung, die als `?bsid=` zu vertrauten Hosts reisen darf:
   *  die Sitzungs-ID nur mit `persist-session`, sonst `''` (Paket 19, Review zu
   *  H-4). Ohne persist soll die Kennung nirgends liegen bleiben — das WLO-Widget
   *  am Ziel (persist an) legte eine mitgereiste ID sonst bei sich ab. */
  uebergabeKennung(): string {
    const p = this.persistSession();
    return p === true || p === 'true' ? this.sessionId : '';
  }

  /** **Public** — laufende Aufnahme stoppen und verwerfen, ohne Transkription und
   *  ohne Senden (Paket 19, M-13). Die Widget-Hülle ruft es beim Zuklappen. */
  discardRecording(): void {
    this._speech.verwerfen();
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

  /** In welcher Form dieser Einbau sein Ergebnis erwartet (`null` = gar keins).
   *  Delegate wie `setEngine` — die Entscheidung trifft die Widget-Hülle aus
   *  ihrem Host-Attribut, der Client trägt sie an jedem Zug mit. */
  setResultSchema(schema: Record<string, any> | null): void {
    this._api.setResultSchema(schema);
  }

  /** N4: Gesamtanleitung fuer diese Einbettung — durchgereicht an den Client. */
  setMasterSkill(an: boolean | null): void {
    this._api.setMasterSkill(an);
  }

  /** O-C: gruppiert diese Anwendung die Treffer? Delegate wie `setEngine` —
   *  die Hülle löst ihr Host-Attribut auf, der Client trägt es an jedem Zug mit.
   *  Bis 2026-08-18 war der Schalter rein visuell und erreichte das Modell nie. */
  setInlineResultGrouping(an: boolean): void {
    this._api.setInlineResultGrouping(an);
  }

  /** O-A: was der Gastgeber erlaubt (`read-only` | `curate` | `full`). */
  setToolMode(modus: string): void {
    this._api.setToolMode(modus);
  }

  /** Paket AS-8b: diese Einbettung ist eine Probe der Studio-Vorschau (Trockenlauf). */
  setProbe(an: boolean): void {
    this.probe.set(an);
    this._api.setProbe(an);
  }

  /** **Public API** (O-B) — Schnellantworten fuer die naechsten Zuege hart
   *  setzen. `[]` oder `null` gibt sie wieder frei. */
  setQuickReplies(chips: string[] | null): void {
    this._api.setQuickReplies(chips);
  }

  /** **Public API** (O-B2) — Chip-Gesamtzahl des Mix-Modus: Host-Chips zuerst,
   *  das Modell fuellt bis zur Zahl auf. `null` = kein Mix (hartes
   *  Ueberschreiben wie bisher). Nur zusammen mit `setQuickReplies` wirksam. */
  setQuickRepliesMax(max: number | null): void {
    this._api.setQuickRepliesMax(max);
  }

  /** **Public API** (G1) — der Gastanwendung ihren Rahmen mitgeben: „so bist du
   *  hier zu verstehen". Der Text erscheint NICHT im Verlauf; er reist als
   *  System-Block mit und wirkt in beiden Maschinen.
   *
   *  `trigger` unterscheidet die beiden Fälle, nach denen gefragt wurde:
   *
   *  * `'next'` (Vorgabe) — der Rahmen wartet auf die nächste Eingabe der
   *    Person und reist dann unsichtbar mit. Das ist der ehrliche Weg: es
   *    entsteht kein Zug, den niemand ausgelöst hat.
   *  * `'now'` — zusätzlich sofort ein Zug. Der braucht einen sichtbaren Anlass,
   *    sonst sähe die Person eine Antwort auf eine Frage, die sie nie gestellt
   *    hat (dieselbe Entscheidung wie bei `startTask` oben). Deshalb `message`:
   *    die kurze Zeile, die als Auftrags-Blase erscheint, während die lange
   *    Anweisung unsichtbar bleibt. Ohne `message` steht der Anweisungstext
   *    selbst in der Blase — nie gar nichts. */
  setHostInstruction(
    text: string, opts?: { trigger?: 'next' | 'now'; message?: string },
  ): Promise<void> {
    const rahmen = (text ?? '').trim();
    this._api.setHostInstruction(rahmen || null);
    if (opts?.trigger !== 'now' || !rahmen) return Promise.resolve();
    return this.startTask((opts.message || '').trim() || rahmen);
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
    // Review U1-d1 (Plan §3.4): vor dem ersten Zug — das Backend bietet nur Modul-Werkzeuge an, die
    // dieses Widget zeigen kann.
    this._api.setUiModule(Object.keys(this._modulRegister));
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
      this._lifecycle.relocalizeWelcome();   // Startnachricht vor der ersten Frage
      this._lifecycle.regreetForLocale();    // Seitengruß in der neuen Sprache (Paket 7, T2)
    }
  }

  /** Aufgeschobene Scroll-Wünsche einlösen (erst nach CD+Paint, finale Höhe). */
  ngAfterViewChecked(): void {
    this._scroll.afterViewChecked();
  }

  /** Auto-Follow-Observer + Speech-Cluster (Mikro/TTS, Privacy!) beim Zerstören
   *  trennen. Verbatim-Teilung aus ALT ngOnDestroy 428-446. */
  ngOnDestroy(): void {
    this._zerstoert = true;
    this._frist.vergessen();
    for (const steuerung of this._nachfragen) steuerung.abort();
    // Wartende Aufträge gehen mit dem Widget; ihr Promise hängt nicht für immer.
    for (const wartend of this._wartendeAuftraege.splice(0)) wartend.fertig();
    this._scroll.destroy();
    this._speech.destroy();
  }

  /** Public API: frische Session + Begrüßung (Header-Restart). */
  restart(): void {
    this.eingabeGesperrt.set(false);
    this._lifecycle.restart();
    this._fortsetzenNeu();
  }

  /** Public API: Session leeren und frisch starten (Host-Seite). */
  resetSession(): void {
    this.eingabeGesperrt.set(false);
    this._lifecycle.resetSession();
    this._fortsetzenNeu();
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
