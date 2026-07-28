// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { HostBridges, HostBridgesContext } from './host-bridges';

/**
 * Charakterisierung der Host-Seiten-Brücken. ALT hat die Listener-Verdrahtung
 * bewusst NICHT gepinnt („reine DOM-Registrierung") und stattdessen den
 * Rewrite-Kern direkt getestet (Block „Outgoing-Link-Rewrite"). Der Kern liegt
 * hier in `session/link-handoff.ts` und ist dort gepinnt — deshalb testet diese
 * Spec genau das ALT-Loch: **wo** der Listener hängt (Scope!), dass `destroy()`
 * wirklich abräumt und dass der URL-Watcher nur bei echtem Wechsel feuert.
 *
 * Der Scope ist load-bearing: hing der Handler am `document` (ALT vor dem Fix),
 * fing er JEDEN Klick der Host-Seite ab und brach deren Navigation.
 */
const VALID_SID = 'bb-6f9619ff-8b86-4d01-b42d-00cf4fc964ff';

interface Harness {
  bridges: HostBridges;
  host: HTMLElement;
  shadow: ShadowRoot;
  pageActions: unknown[];
  queryMetas: unknown[];
  urlChanges: number;
  intercepted: string[];
}

function mk(opts: { intercept?: boolean | string } = {}): Harness {
  // Shadow-Root wie in der echten Hülle (ShadowDom-Encapsulation): NUR so
  // reproduziert der Test das Event-Retargeting, an dem der Rewrite live
  // gescheitert ist (Listener am Host sieht `<host>` statt des Anchors).
  const host = document.createElement('div');
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: 'open' });
  const h: Harness = {
    bridges: null as unknown as HostBridges,
    host, shadow: null as unknown as ShadowRoot,
    pageActions: [], queryMetas: [], urlChanges: 0, intercepted: [],
  };
  const ctx: HostBridgesContext = {
    clickScope: () => shadow,
    sessionId: () => VALID_SID,
    trustedDomains: () => ['partner.example'],
    interceptEduSharingLinks: () => opts.intercept ?? false,
    onInterceptedLink: (p) => h.intercepted.push(p),
    onPageAction: (pa) => h.pageActions.push(pa),
    onQueryMeta: (d) => h.queryMetas.push(d),
    onUrlChange: () => { h.urlChanges++; },
  };
  h.bridges = new HostBridges(ctx);
  h.shadow = shadow;
  return h;
}

function anchorIn(parent: HTMLElement, href: string): HTMLAnchorElement {
  const a = document.createElement('a');
  a.href = href;
  parent.appendChild(a);
  return a;
}

/** Klick ohne echte Navigation: kein MouseEvent, damit jsdom nicht versucht,
 *  dem href zu folgen (ALT-Muster im Rewrite-Block). `composed: true`, damit das
 *  Event die Shadow-Grenze überquert wie ein echter Klick. */
function clickOn(el: Element): void {
  el.dispatchEvent(new Event('click', { bubbles: true, composed: true }));
}

describe('HostBridges Klick-Rewrite (Scope + Teardown)', () => {
  let h: Harness;
  beforeEach(() => { history.replaceState({}, '', '/'); h = mk(); h.bridges.init(); });
  afterEach(() => { h.bridges.destroy(); document.body.innerHTML = ''; });

  it('Link INNERHALB des Widget-Shadow-Roots bekommt die bsid', () => {
    const a = anchorIn(h.shadow as unknown as HTMLElement, 'https://partner.example/pfad');
    clickOn(a);
    expect(a.href).toContain(`bsid=${VALID_SID}`);
  });

  it('Link AUSSERHALB des Widgets bleibt unberührt (Scope-Fix)', () => {
    const outside = anchorIn(document.body, 'https://partner.example/pfad');
    clickOn(outside);
    expect(outside.href).toBe('https://partner.example/pfad');
  });

  it('destroy() nimmt den Listener wieder ab', () => {
    h.bridges.destroy();
    const a = anchorIn(h.shadow as unknown as HTMLElement, 'https://partner.example/pfad');
    clickOn(a);
    expect(a.href).toBe('https://partner.example/pfad');
  });

  it('Intercept-Modus reicht path+search durch statt zu navigieren', () => {
    const i = mk({ intercept: 'true' });
    i.bridges.init();
    clickOn(anchorIn(i.shadow as unknown as HTMLElement, window.location.origin + '/edu-sharing/components/render?id=1'));
    expect(i.intercepted).toEqual(['/edu-sharing/components/render?id=1']);
    i.bridges.destroy();
  });
});

describe('HostBridges window-Events', () => {
  let h: Harness;
  beforeEach(() => { h = mk(); h.bridges.init(); });
  afterEach(() => { h.bridges.destroy(); document.body.innerHTML = ''; });

  it('page-action mit `action` wird durchgereicht, ohne verworfen', () => {
    window.dispatchEvent(new CustomEvent('badboerdi:page-action', { detail: { action: 'navigate', payload: {} } }));
    window.dispatchEvent(new CustomEvent('badboerdi:page-action', { detail: { payload: {} } }));
    window.dispatchEvent(new CustomEvent('badboerdi:page-action', { detail: null }));
    expect(h.pageActions).toEqual([{ action: 'navigate', payload: {} }]);
  });

  it('query-meta wird durchgereicht, leeres detail verworfen', () => {
    window.dispatchEvent(new CustomEvent('badboerdi:query-meta', { detail: { tool: 'search' } }));
    window.dispatchEvent(new CustomEvent('badboerdi:query-meta', { detail: null }));
    expect(h.queryMetas).toEqual([{ tool: 'search' }]);
  });

  it('destroy() nimmt beide window-Listener ab', () => {
    h.bridges.destroy();
    window.dispatchEvent(new CustomEvent('badboerdi:page-action', { detail: { action: 'x' } }));
    window.dispatchEvent(new CustomEvent('badboerdi:query-meta', { detail: { a: 1 } }));
    expect(h.pageActions).toHaveLength(0);
    expect(h.queryMetas).toHaveLength(0);
  });
});

describe('HostBridges SPA-URL-Watcher (T17)', () => {
  let h: Harness;
  beforeEach(() => {
    vi.useFakeTimers();
    history.replaceState({}, '', '/');
    h = mk();
    h.bridges.init();
  });
  afterEach(() => { h.bridges.destroy(); vi.useRealTimers(); document.body.innerHTML = ''; });

  it('href-Wechsel meldet einmal; ohne Wechsel kein weiterer Aufruf', () => {
    history.replaceState({}, '', '/neu');
    vi.advanceTimersByTime(1500);
    expect(h.urlChanges).toBe(1);
    vi.advanceTimersByTime(4500);
    expect(h.urlChanges).toBe(1);
  });

  it('destroy() räumt den Interval auf', () => {
    h.bridges.destroy();
    history.replaceState({}, '', '/noch-neuer');
    vi.advanceTimersByTime(5000);
    expect(h.urlChanges).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });
});
