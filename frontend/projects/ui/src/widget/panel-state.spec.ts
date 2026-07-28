// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PanelState, PanelStateContext } from './panel-state';

/**
 * Charakterisierung der Panel-Zustandsmaschine. Übernimmt die ALT-Blöcke
 * „WidgetComponent Öffnen/Schließen Public API" (spec:477-509), „Owl-Hint"
 * (511-540) und „Escape-to-close (A11y)" (281-303).
 *
 * ALT hat den `requestAnimationFrame`-Pfad bewusst NICHT gepinnt („Layout-/
 * Paint-Timing in jsdom nicht ehrlich"). Hier ist daraus der `afterRender`-Seam
 * geworden (8-6), der im Test synchron ausgeführt wird: das pinnt die
 * *Verdrahtung* (welcher Seam nach Öffnen/Schließen läuft), nicht das Timing —
 * und deckt damit den Fokus-Rückgabe-Pfad ab, der in ALT ungetestet war.
 */
function mkCtx(sessionId: () => string | undefined = () => 'bb-x') {
  const calls: string[] = [];
  const ctx: PanelStateContext = {
    sessionId,
    scrollToLatest: () => calls.push('scroll'),
    focusInput: () => calls.push('focusInput'),
    focusFab: () => calls.push('focusFab'),
    // Im Test synchron: pinnt die Verdrahtung, nicht das Render-Timing.
    afterRender: (cb) => { calls.push('afterRender'); cb(); },
  };
  return { ctx, calls };
}

const VALID_SID = 'bb-6f9619ff-8b86-4d01-b42d-00cf4fc964ff';

describe('PanelState Öffnen/Schließen', () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState({}, '', '/');
  });
  afterEach(() => localStorage.clear());

  it('initExpanded: "expanded" öffnet und setzt den everExpanded-Latch', () => {
    const p = new PanelState(mkCtx().ctx);
    p.initExpanded('expanded');
    expect(p.expanded()).toBe(true);
    expect(p.everExpanded()).toBe(true);
  });

  it('initExpanded: ohne bsid/Tour bleibt es zu (Lazy-Mount-Gate zu)', () => {
    const p = new PanelState(mkCtx().ctx);
    p.initExpanded('collapsed');
    expect(p.expanded()).toBe(false);
    expect(p.everExpanded()).toBe(false);
  });

  it('initExpanded öffnet bei gültiger ?bsid= (delegiert an computeInitialExpanded)', () => {
    history.replaceState({}, '', `/?bsid=${VALID_SID}`);
    const p = new PanelState(mkCtx().ctx);
    p.initExpanded('collapsed');
    expect(p.expanded()).toBe(true);
  });

  it('everExpanded-Latch bleibt nach dem Schließen bestehen', () => {
    const p = new PanelState(mkCtx().ctx);
    p.setExpanded(true);
    p.setExpanded(false);
    expect(p.expanded()).toBe(false);
    expect(p.everExpanded()).toBe(true);
  });

  it('toggle wechselt den Zustand, doppelte open-Aufrufe sind idempotent', () => {
    const { ctx, calls } = mkCtx();
    const p = new PanelState(ctx);
    p.toggle();
    expect(p.expanded()).toBe(true);
    p.setExpanded(true);   // No-Op: kein zweiter Scroll/Fokus
    expect(calls.filter(c => c === 'scroll')).toHaveLength(1);
    p.toggle();
    expect(p.expanded()).toBe(false);
  });

  it('Öffnen scrollt ans Ende und fokussiert das Eingabefeld', () => {
    const { ctx, calls } = mkCtx();
    new PanelState(ctx).setExpanded(true);
    expect(calls).toContain('scroll');
    expect(calls).toContain('focusInput');
  });

  it('Schließen gibt den Fokus an den FAB zurück (A11y)', () => {
    const { ctx, calls } = mkCtx();
    const p = new PanelState(ctx);
    p.setExpanded(true);
    p.setExpanded(false);
    expect(calls.at(-1)).toBe('focusFab');
    expect(calls).toContain('afterRender');
  });
});

describe('PanelState Escape-to-close (A11y)', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => localStorage.clear());

  it('Escape schließt das offene Panel', () => {
    const p = new PanelState(mkCtx().ctx);
    p.setExpanded(true);
    p.onEscape();
    expect(p.expanded()).toBe(false);
  });

  it('Escape bei geschlossenem Panel ist ein No-Op', () => {
    const { ctx, calls } = mkCtx();
    const p = new PanelState(ctx);
    p.onEscape();
    expect(p.expanded()).toBe(false);
    expect(calls).toHaveLength(0);   // kein Render-Hook, kein Fokus-Sprung
  });
});

describe('PanelState Owl-Hint', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });
  afterEach(() => { vi.useRealTimers(); localStorage.clear(); });

  it('hintet pro Session genau einmal: 3s an, dann aus; gleiche Session nie wieder', () => {
    const p = new PanelState(mkCtx(() => VALID_SID).ctx);
    p.setExpanded(true);
    expect(p.hintActive()).toBe(true);
    vi.advanceTimersByTime(3000);
    expect(p.hintActive()).toBe(false);
    expect(localStorage.getItem('boerdi_owl_hint_session')).toBe(VALID_SID);

    // Neues Widget, gleiche Session → kein Hint mehr.
    const p2 = new PanelState(mkCtx(() => VALID_SID).ctx);
    p2.setExpanded(true);
    expect(p2.hintActive()).toBe(false);
  });

  it('pollt auf die sessionId: Hint kommt, sobald die Shell bereit ist', () => {
    // Box statt `let`: die Seam liest die Session pro Aufruf frisch, der Test
    // muss sie also nach dem Konstruktor noch setzen können.
    const session: { id?: string } = {};
    const p = new PanelState(mkCtx(() => session.id).ctx);
    p.setExpanded(true);
    expect(p.hintActive()).toBe(false);   // noch keine Session
    session.id = VALID_SID;
    vi.advanceTimersByTime(200);
    expect(p.hintActive()).toBe(true);
  });

  it('gibt nach ~4s Polling auf (kein Endlos-Timer)', () => {
    const p = new PanelState(mkCtx(() => undefined).ctx);
    p.setExpanded(true);
    vi.advanceTimersByTime(10_000);
    expect(p.hintActive()).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });
});
