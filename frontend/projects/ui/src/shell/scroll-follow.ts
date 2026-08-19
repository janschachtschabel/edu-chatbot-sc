/**
 * Scroll-/Auto-Follow-Controller (8-4S-e2) — der DOM-Scroll-Cluster der Chat-
 * Shell als eigenständige Klasse (Muster `TourController`), damit die Komponente
 * schlank bleibt. Bündelt aufgeschobenes Scrollen (`ngAfterViewChecked`-Konsum),
 * das öffentliche `scrollToLatest` (WidgetComponent beim `openChatbot()`) und den
 * permanenten Tail-Follow-`MutationObserver`. Alle Bodies verbatim aus ALT
 * chat.component.ts (scrollToBottom 1323-1330, scrollToLatest 1342-1356,
 * _setupAutoFollowTail 1373-1398, scrollToMessage 1400-1409, ngAfterViewChecked
 * 417-426, Observer-Cleanup aus ngOnDestroy 433-440). KEINE Logik-Änderung.
 *
 * Container-Seam: das Messages-Container-Element (ViewChild) kommt als deferred
 * Arrow — solange das Row-Template (8-4S-f) nicht gerendert hat, liefert es
 * `undefined` und alle Scrolls sind bewusste No-Ops (wie in ALT vor erstem Render).
 */

/** Live-Zugriff auf das scrollbare Messages-Container-Element. */
export interface ScrollFollowContext {
  container: () => HTMLElement | null | undefined;
}

export class ScrollFollowController {
  /** Hat der User aktiv hoch-gescrollt? Dann hält der Auto-Follow NICHT mehr
   *  automatisch am Tail (sonst reißt jede Bot-Antwort ihn aus der alten Stelle).
   *  `scrollToLatest` (Reopen) resettet das Flag. */
  private _userScrolledAway = false;
  private _autoFollowObserver: MutationObserver | null = null;
  private _autoFollowScrollListener: (() => void) | null = null;
  /** Scroll ans Ende beim nächsten gerenderten View (erst NACH CD+Paint, wenn
   *  `scrollHeight` final ist). Gesetzt von `scrollToLatest`/History-Restore. */
  private _scrollToBottomOnNextRender = false;
  /** ID der Nachricht, zu der beim nächsten Render gescrollt werden soll. */
  private _scrollTargetId: string | null = null;

  constructor(private readonly ctx: ScrollFollowContext) {}

  /** Scroll-Ziel für den nächsten Render setzen (SendMessage-Seam). */
  setScrollTarget(msgId: string | null): void {
    this._scrollTargetId = msgId;
  }

  /** In `ngAfterViewChecked`: aufgeschobene Scroll-Wünsche einlösen — und den
   *  Tail-Follow scharfschalten, sobald der Container im DOM ist.
   *
   *  Aufgeschobene Wünsche: verbatim ALT chat.component.ts:417-426.
   *
   *  Das Scharfschalten ist **neu** (Befund 2026-08-19: „scrollt beim Antworten
   *  nicht mehr mit"). ALT hängte den Beobachter allein in `scrollToLatest`
   *  (chat.component.ts:1355) — und das lief nur, wenn jemand das Panel
   *  ÖFFNETE, ein Verlauf wiederhergestellt wurde oder der Host die API rief.
   *  Für ein Widget, das man immer erst aufklappt, genügte das. Startet das
   *  Panel dagegen schon offen (`initial-state="expanded"`, `?bsid=`, laufende
   *  Tour — `PanelState.initExpanded` setzt das Signal bewusst an `setExpanded`
   *  vorbei) oder steckt die Shell in einer Inline-Einbettung ohne Panel, dann
   *  hängte sich der Beobachter nie ein und die Ansicht blieb beim ersten Satz
   *  stehen.
   *
   *  Der Tail-Follow gehört zum LEBEN der Ansicht, nicht zu einer einzelnen
   *  Scroll-Anweisung. Der Aufruf ist idempotent und ohne Container ein No-Op,
   *  kostet in der Prüfschleife also nichts. */
  afterViewChecked(): void {
    this._setupAutoFollowTail();
    if (this._scrollTargetId) {
      this.scrollToMessage(this._scrollTargetId);
      this._scrollTargetId = null;
    }
    if (this._scrollToBottomOnNextRender) {
      this.scrollToBottom();
      this._scrollToBottomOnNextRender = false;
    }
  }

  /** Container ans Ende scrollen; toleriert "noch nicht im DOM". Verbatim ALT 1323-1330. */
  scrollToBottom(): void {
    try {
      const el = this.ctx.container();
      if (el) el.scrollTop = el.scrollHeight;
    } catch {
      // Container noch nicht im DOM (z.B. vor erstem Render) — bewusster No-Op.
    }
  }

  /** **Public** — auf die letzte Nachricht setzen + Auto-Follow (re)aktivieren.
   *  User-Scroll-Intention zurücksetzen; sofort + gestufte Retries für async
   *  gerenderte Inhalte (History-Restore). Verbatim ALT 1342-1356. */
  scrollToLatest(): void {
    this._scrollToBottomOnNextRender = true;
    this._userScrolledAway = false;
    this.scrollToBottom();
    setTimeout(() => this.scrollToBottom(), 0);
    setTimeout(() => this.scrollToBottom(), 200);
    setTimeout(() => this.scrollToBottom(), 800);
    this._setupAutoFollowTail();
  }

  /** Permanenter MutationObserver, der den Container am Tail hält, bis der User
   *  aktiv hochscrollt (Toleranz 60px). Idempotent. Verbatim ALT 1373-1398. */
  private _setupAutoFollowTail(): void {
    if (this._autoFollowObserver) return;
    const container = this.ctx.container();
    if (!container || typeof MutationObserver === 'undefined') return;

    const SCROLL_TOLERANCE_PX = 60;
    this._autoFollowScrollListener = () => {
      const max = container.scrollHeight - container.clientHeight;
      const distFromBottom = max - container.scrollTop;
      this._userScrolledAway = distFromBottom > SCROLL_TOLERANCE_PX;
    };
    container.addEventListener('scroll', this._autoFollowScrollListener, { passive: true });

    this._autoFollowObserver = new MutationObserver(() => {
      if (this._userScrolledAway) return;
      container.scrollTop = container.scrollHeight;
    });
    this._autoFollowObserver.observe(container, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  /** Zu einer Nachricht scrollen (`msg-<id>`). Verbatim ALT 1400-1409. */
  private scrollToMessage(msgId: string): void {
    try {
      const el = document.getElementById('msg-' + msgId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch {
      // Element (noch) nicht im DOM — bewusster No-Op, Scroll ist Komfort-Feature.
    }
  }

  /** Auto-Follow-Observer + Scroll-Listener trennen (in `ngOnDestroy`).
   *  Verbatim ALT ngOnDestroy 433-440 (ohne `_speech.destroy()` — das bleibt
   *  Sache der Komponente). */
  destroy(): void {
    try { this._autoFollowObserver?.disconnect(); } catch { /* ignore */ }
    this._autoFollowObserver = null;
    try {
      const el = this.ctx.container();
      if (this._autoFollowScrollListener && el) {
        el.removeEventListener('scroll', this._autoFollowScrollListener);
      }
    } catch { /* ignore */ }
    this._autoFollowScrollListener = null;
  }
}
