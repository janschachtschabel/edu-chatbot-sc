import { HOST_EVENTS } from '../host-events/event-names';
import { maybeRewriteOutgoingLink } from '../session/link-handoff';

/** Tick-Abstand des SPA-URL-Watchers (ALT ngOnInit 287). */
const URL_WATCH_INTERVAL_MS = 1500;

/** Seams der Brücken zur Host-Seite — alle deferred, damit async nachgeladene
 *  Trusted-Domains sofort greifen (ALT baut den Klick-Kontext pro Klick frisch). */
export interface HostBridgesContext {
  /** Scope des Klick-Listeners. `null` → `document`.
   *
   *  MUSS der Shadow-Root sein, wenn die Hülle Shadow DOM nutzt: bei Events aus
   *  einem Shadow-Tree wird `event.target` für Listener AUSSERHALB des Trees auf
   *  den Host retargetiert. Ein Listener am Host bekäme also `<boerdi-chat>`
   *  statt des Anchors, und die Anchor-Suche in `link-handoff.ts` findet nichts
   *  (live nachgemessen: `target=BOERDI-CHAT`, `composedPath()[0]=A`, kein
   *  bsid-Rewrite). Der Scope bleibt korrekt eng — der Shadow-Root enthält
   *  ausschließlich Widget-Inhalt. */
  clickScope: () => EventTarget | null;
  /** Session-ID aus der Chat-Shell (Quelle der Wahrheit für die bsid). */
  sessionId: () => string | undefined;
  /** Gemergte Trusted-Domain-Liste (Backend + Host-Attribut). */
  trustedDomains: () => string[];
  /** `intercept-edu-sharing-links` (roher Attributwert). */
  interceptEduSharingLinks: () => boolean | string;
  /** Abgefangener Link im Intercept-Modus (path+search) → Output `linkClicked`. */
  onInterceptedLink: (pathAndSearch: string) => void;
  /** page_action aus dem window-Fallback-Event. */
  onPageAction: (pa: { action: string; payload: any }) => void;
  /** query-meta aus dem window-Event → Output `queryMeta`. */
  onQueryMeta: (detail: unknown) => void;
  /** SPA-Navigation erkannt — der Aufrufer löst den Seitenkontext neu auf. */
  onUrlChange: () => void;
}

/**
 * HostBridges — alles, was die Widget-Hülle an der Host-Seite verdrahtet:
 * der bsid-Rewrite ausgehender Klicks, die beiden window-Event-Fallbacks und
 * der SPA-URL-Watcher. Port von ALT `widget.component.ts`
 * (ngAfterViewInit 307-367, ngOnDestroy 369-386, _checkUrlChange 295-305,
 * _maybeRewriteOutgoingLink 440-449).
 *
 * `init()` gehört in `ngAfterViewInit`, `destroy()` in `ngOnDestroy` — jeder
 * Listener wird an genau dem Element wieder abgenommen, an dem er hängt.
 *
 * Warum window-Events als Fallback: reicht die Angular-`@Output()`-Bindung der
 * Chat-Shell nicht durch (möglich, wenn die Hülle als Custom Element den
 * Event-Fluss neu wrappt), kommt dieselbe page_action über das CustomEvent an,
 * das die Shell immer zusätzlich feuert.
 */
export class HostBridges {
  private _onPageActionEvent?: (e: Event) => void;
  private _onQueryMetaEvent?: (e: Event) => void;
  private _onHostClick?: (e: Event) => void;
  /** Wohin der Klick-Listener gehängt wurde — gespeichert, damit `destroy()`
   *  ihn am SELBEN Ziel wieder abnimmt. */
  private _clickScope?: EventTarget;
  /** Letzte gesehene URL — Basis des SPA-Navigations-Vergleichs. */
  private _lastHref = '';
  private _urlWatcher: ReturnType<typeof setInterval> | null = null;

  constructor(private readonly ctx: HostBridgesContext) {}

  /** Alle Brücken aufbauen. */
  init(): void {
    this._onPageActionEvent = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.action) this.ctx.onPageAction(detail);
    };
    window.addEventListener(HOST_EVENTS.pageAction, this._onPageActionEvent);

    this._onQueryMetaEvent = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail) this.ctx.onQueryMeta(detail);
    };
    window.addEventListener(HOST_EVENTS.queryMeta, this._onQueryMetaEvent);

    // Outgoing-Link-Rewrite für den Cross-TLD-Session-Handoff.
    //
    // Handler IMMER registrieren, auch wenn die Trusted-Liste noch leer ist:
    // `GuideBoot.load()` füllt sie async, und würden wir auf die volle Liste
    // warten, käme der Handler bei langsamem Backend nie zustande. Die
    // Trusted-Prüfung passiert pro Klick im Handler — leere Liste = früher
    // Ausstieg = Kosten 0.
    //
    // Scope auf den Widget-Shadow-Root (nicht `document`): sonst
    // fängt der Handler JEDEN Klick der Host-Seite ab und bricht deren
    // Navigation (SPA-Routing, gebundene Klick-Handler). So greift der Rewrite
    // nur in Karten, Inline-Markdown-Links und Lotsen-CTAs. Side-Effect:
    // Host-Seiten-Links bekommen kein automatisches `?bsid=` mehr — Hosts, die
    // das brauchen, ergänzen es selbst per JS.
    this._onHostClick = (e: Event) => this._rewriteClick(e);
    const scope = this.ctx.clickScope() || document;
    scope.addEventListener('click', this._onHostClick, true);
    this._clickScope = scope;

    // SPA-URL-Watcher (Seitenkontext, T17): edu-sharing ist eine Angular-SPA —
    // ohne Watcher bliebe der page_context nach In-App-Navigation stale.
    try {
      this._lastHref = window.location.href;
      this._urlWatcher = setInterval(() => this._checkUrlChange(), URL_WATCH_INTERVAL_MS);
    } catch { /* ignore — Watcher ist best-effort */ }
  }

  /** Alles wieder abnehmen (`ngOnDestroy`). */
  destroy(): void {
    if (this._urlWatcher !== null) {
      clearInterval(this._urlWatcher);
      this._urlWatcher = null;
    }
    if (this._onPageActionEvent) {
      window.removeEventListener(HOST_EVENTS.pageAction, this._onPageActionEvent);
      this._onPageActionEvent = undefined;
    }
    if (this._onQueryMetaEvent) {
      window.removeEventListener(HOST_EVENTS.queryMeta, this._onQueryMetaEvent);
      this._onQueryMetaEvent = undefined;
    }
    if (this._onHostClick) {
      (this._clickScope || document).removeEventListener('click', this._onHostClick, true);
      this._onHostClick = undefined;
    }
  }

  /** Delegate — Rewrite-Logik in `session/link-handoff.ts`. Kontext pro Klick
   *  frisch gebaut; try/catch wie im Original: nie User-Klicks brechen. */
  private _rewriteClick(e: Event): void {
    try {
      maybeRewriteOutgoingLink(e, {
        interceptEduSharingLinks: this.ctx.interceptEduSharingLinks(),
        trustedDomains: this.ctx.trustedDomains(),
        sessionId: this.ctx.sessionId(),
        onInterceptedLink: p => this.ctx.onInterceptedLink(p),
      });
    } catch { /* never break user clicks */ }
  }

  /** Hat sich die URL seit dem letzten Tick geändert (SPA-Navigation)? */
  private _checkUrlChange(): void {
    let href = '';
    try { href = window.location.href; } catch { return; }
    if (!href || href === this._lastHref) return;
    this._lastHref = href;
    try {
      this.ctx.onUrlChange();
    } catch { /* ignore — Navigation darf das Widget nie brechen */ }
  }
}
