// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { GuideNav, GuideNavContext } from './guide-nav';

/**
 * Charakterisierung der Lotsen-Navigation. Übernimmt den ALT-Block
 * „WidgetComponent Lotsen-Banner (handlePageAction)" (spec:123-162).
 *
 * ALT konnte den Navigations-Zweig nicht ehrlich testen („jsdom kann nicht
 * navigieren") und pinnte nur bis zur Delegation. Hier ist der Zweig hinter
 * einem Setter-Spy auf `window.location.href` sichtbar — damit ist auch der
 * T7-Guard (fail-closed) am echten Aufrufpfad geprüft, nicht nur als Funktion.
 */
const VALID_SID = 'bb-6f9619ff-8b86-4d01-b42d-00cf4fc964ff';

function mk(opts: { guideMode?: boolean; trusted?: string[] } = {}) {
  const ctx: GuideNavContext = {
    guideMode: () => opts.guideMode ?? true,
    trustedDomains: () => opts.trusted ?? ['trusted.example'],
    sessionId: () => VALID_SID,
  };
  return new GuideNav(ctx);
}

/** Navigations-Ziele einsammeln, ohne jsdom navigieren zu lassen. */
function captureNavigation(): string[] {
  const seen: string[] = [];
  const original = Object.getOwnPropertyDescriptor(window, 'location');
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: {
      ...window.location,
      set href(v: string) { seen.push(v); },
      get href() { return 'http://localhost/'; },
    },
  });
  afterEach(() => {
    if (original) Object.defineProperty(window, 'location', original);
  });
  return seen;
}

afterEach(() => vi.unstubAllGlobals());

describe('GuideNav handlePageAction', () => {
  it('navigate setzt das Ziel und trimmt die URL', () => {
    const g = mk();
    g.handlePageAction({ action: 'navigate', payload: { url: '  https://x.example/a  ', label: 'Ziel' } });
    expect(g.target()).toEqual({ url: 'https://x.example/a', label: 'Ziel' });
  });

  it('Label-Fallback-Kette: label → title → URL', () => {
    const g = mk();
    g.handlePageAction({ action: 'navigate', payload: { url: 'https://x.example', title: 'Titel' } });
    expect(g.target()?.label).toBe('Titel');
    g.handlePageAction({ action: 'navigate', payload: { url: 'https://y.example' } });
    expect(g.target()?.label).toBe('https://y.example');
  });

  it('ignoriert leere URLs, fremde Actions, null-Payloads und null-Actions', () => {
    const g = mk();
    g.handlePageAction({ action: 'navigate', payload: { url: '   ' } });
    g.handlePageAction({ action: 'open_canvas', payload: { url: 'https://x.example' } });
    g.handlePageAction({ action: 'navigate', payload: null });
    g.handlePageAction(null);
    expect(g.target()).toBeNull();
  });

  it('ohne Lotsen-Modus kein Banner', () => {
    const g = mk({ guideMode: false });
    g.handlePageAction({ action: 'navigate', payload: { url: 'https://x.example' } });
    expect(g.target()).toBeNull();
  });

  it('cancel blendet das Banner aus', () => {
    const g = mk();
    g.handlePageAction({ action: 'navigate', payload: { url: 'https://x.example', label: 'Z' } });
    g.cancel();
    expect(g.target()).toBeNull();
  });
});

describe('GuideNav confirm (T7-Guard am echten Aufrufpfad)', () => {
  const navigated = captureNavigation();

  it('trusted http(s)-Ziel wird navigiert', () => {
    const g = mk();
    g.handlePageAction({ action: 'navigate', payload: { url: 'https://trusted.example/lernen' } });
    g.confirm();
    expect(navigated.at(-1)).toContain('trusted.example/lernen');
    expect(g.target()).toBeNull();
  });

  it('untrusted Host und javascript:-Schema werden NICHT navigiert (fail-closed)', () => {
    const before = navigated.length;
    const g = mk();
    g.handlePageAction({ action: 'navigate', payload: { url: 'https://evil.example/phish' } });
    g.confirm();
    g.handlePageAction({ action: 'navigate', payload: { url: 'javascript:alert(1)' } });
    g.confirm();
    expect(navigated).toHaveLength(before);
  });

  it('confirm ohne Ziel ist ein No-Op', () => {
    const before = navigated.length;
    mk().confirm();
    expect(navigated).toHaveLength(before);
  });
});
