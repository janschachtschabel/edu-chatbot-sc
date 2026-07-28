import { signal } from '@angular/core';

import { computeInitialExpanded } from './widget-init';

/** localStorage-Schlüssel des einmaligen Owl-Hinweises (ALT
 *  `WidgetComponent.OWL_HINT_KEY`). Wert = die gehintete Session-ID. */
const OWL_HINT_KEY = 'boerdi_owl_hint_session';

/** Seams, die die Zustandsmaschine beim Öffnen/Schließen braucht — alle als
 *  deferred Arrows, damit jeder Zugriff live gegen den echten Zustand geht. */
export interface PanelStateContext {
  /** Session-ID der Chat-Shell. `undefined`/`''` = noch nicht bereit (der
   *  Owl-Hinweis pollt dann kurz nach). */
  sessionId: () => string | undefined;
  /** Nachrichten-Liste ans Ende scrollen (nach dem Öffnen). */
  scrollToLatest: () => void;
  /** Eingabefeld fokussieren (nach dem Öffnen). */
  focusInput: () => void;
  /** Floating-Button fokussieren (nach dem Schließen). */
  focusFab: () => void;
  /** `cb` ausführen, NACHDEM Angular gerendert hat.
   *
   *  8-6: ALT stapelte hier zwei `requestAnimationFrame` — unter zone.js war die
   *  Prüfung am Ende des Klick-Turns schon gelaufen, das DOM also aktuell. Im
   *  zoneless Betrieb gilt das nicht mehr, und rAF ist zusätzlich die falsche
   *  Uhr: in einem nicht komponierenden Tab (Hintergrund-Tab, verborgenes Panel)
   *  feuert es überhaupt nicht — live nachgemessen. Solange das Panel noch
   *  `display: none` trägt, ist ein `focus()` darin ein stiller No-Op.
   *  Die Hülle liefert hier `afterNextRender`. */
  afterRender: (cb: () => void) => void;
}

/**
 * PanelState — die Auf/Zu-Zustandsmaschine der Widget-Hülle: `expanded`,
 * der `everExpanded`-Lazy-Mount-Latch und der einmalige Owl-Hinweis.
 * Port von ALT `widget.component.ts` (setExpanded 499-545, Public API 476-494,
 * Escape 460-463, _maybeShowOwlHint 551-568).
 *
 * simplify: ALT hält `expanded`/`everExpanded`/`hintActive` als plain Felder und
 * stößt Change-Detection per `cdr.markForCheck()` + `zone.run()` an (nötig, weil
 * Host-Seiten die Public API außerhalb der Angular-Zone aufrufen). Hier sind alle
 * drei Signals — im zoneless Betrieb plant ein Signal-Write die Prüfung selbst.
 * Der `markForCheck`-Seam entfällt damit ersatzlos; Verhalten identisch.
 */
export class PanelState {
  /** Panel offen? Steuert `.expanded` + `.boerdi-panel--hidden` im Template. */
  readonly expanded = signal(false);
  /** Lazy-Mount-Latch: beim allerersten Öffnen `true` und dann konstant, damit
   *  die Chat-Shell im DOM bleibt und ihren Zustand (Nachrichten, Karten) über
   *  ein Collapse hinweg behält. Wer das Widget nie öffnet, zahlt nichts. */
  readonly everExpanded = signal(false);
  /** Owl-Kopf wackelt + Sprechblase (3 s, einmal pro Session). */
  readonly hintActive = signal(false);

  private _owlHintDone = false;
  private _owlHintTries = 0;

  constructor(private readonly ctx: PanelStateContext) {}

  /** Boot-Entscheidung (ALT ngOnInit 260-266): initial-state / ?bsid= /
   *  laufende Tour. Bewusst NICHT über `setExpanded` — beim Boot gibt es noch
   *  nichts zu scrollen und keinen Fokus zu setzen. */
  initExpanded(initialState: 'collapsed' | 'expanded'): void {
    const open = computeInitialExpanded(initialState);
    this.expanded.set(open);
    if (open) this.everExpanded.set(true);
  }

  /** Zentraler Setter — alle Öffnen/Schließen-Pfade (Toggle-Button, Public API,
   *  `initial-state`-Attribut) laufen hier zusammen. Verbatim ALT 499-545. */
  setExpanded(open: boolean): void {
    if (this.expanded() === open) return;
    this.expanded.set(open);
    if (open) this.everExpanded.set(true);

    // Beim Öffnen: Nachrichten-Liste ans Ende scrollen, damit der User die
    // letzten Bot-Antworten sieht (wichtig für `openChatbot()`-Aufrufe vom
    // Host — sonst wäre der lange zurückliegende Verlauf-Anfang sichtbar).
    // Beides erst NACH dem Rendern: vorher trägt das Panel noch
    // `display: none` (Scroll-Höhe 0, `focus()` wirkungslos).
    if (open) {
      this._maybeShowOwlHint();
      try {
        this.ctx.afterRender(() => {
          try { this.ctx.scrollToLatest(); } catch { /* ignore */ }
          // A11y: Fokus ins Eingabefeld, sobald das Panel sichtbar ist —
          // Tastatur-Nutzer können sofort tippen, ohne erst hinzutabben.
          try { this.ctx.focusInput(); } catch { /* ignore */ }
        });
      } catch { /* ignore */ }
    } else {
      // A11y: Fokus zurück auf den FAB — er wird beim Schließen erst neu
      // gerendert, existiert also vorher gar nicht.
      try {
        this.ctx.afterRender(() => {
          try { this.ctx.focusFab(); } catch { /* ignore */ }
        });
      } catch { /* ignore */ }
    }
  }

  /** Umschalten (FAB- und Schließen-Button). */
  toggle(): void {
    this.setExpanded(!this.expanded());
  }

  /** A11y: Escape schließt das offene Panel — Tastatur-Nutzer erwarten das.
   *  Der Listener sitzt am Host-Element, feuert also nur bei Fokus im Widget. */
  onEscape(): void {
    if (this.expanded()) this.setExpanded(false);
  }

  /** Owl-Hinweis anstoßen, falls fällig. Öffentlich, weil die Hülle ihn auf den
   *  Auto-Open-Pfaden (`?bsid=`, laufende Tour) selbst auslösen muss: dort setzt
   *  `initExpanded` die Signals direkt und `setExpanded` läuft nie (ALT 310). */
  showOwlHintIfDue(): void {
    this._maybeShowOwlHint();
  }

  /** Einmaliger Owl-Hinweis beim ersten Öffnen einer Session: Kopf wackelt +
   *  Sprechblase 3 s, dann weg. Das localStorage-Flag hängt an der Session-ID —
   *  „Neuer Chat" (neue ID) hintet erneut, Reopen/Reload derselben Session
   *  nicht. Verbatim ALT 551-568. */
  private _maybeShowOwlHint(): void {
    if (this._owlHintDone) return;
    const sid = this.ctx.sessionId();
    if (!sid) {
      // Shell/sessionId noch nicht bereit → kurz später erneut (max ~4 s).
      if (this._owlHintTries++ < 20) setTimeout(() => this._maybeShowOwlHint(), 200);
      return;
    }
    this._owlHintDone = true;
    let last = '';
    try { last = localStorage.getItem(OWL_HINT_KEY) || ''; } catch { /* ignore */ }
    if (last === sid) return;  // diese Session schon gehinted
    try { localStorage.setItem(OWL_HINT_KEY, sid); } catch { /* ignore */ }
    this.hintActive.set(true);
    setTimeout(() => this.hintActive.set(false), 3000);
  }
}
