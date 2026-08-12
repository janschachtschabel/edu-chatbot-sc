// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { signal } from '@angular/core';

import { GuideBoot, GuideBootContext } from './guide-boot';

/**
 * Charakterisierung des Config-Boots. Übernimmt die ALT-Blöcke „WidgetComponent
 * initGuideMode Response-Mapping" (spec:351-403) und „Trusted-Domain-Merge"
 * (88-121) — dort über die Komponente + `_backendTrustedDomains`-Poke, hier
 * über die echte `load()`-Antwort bzw. `trustedDomains()`.
 *
 * Boundary: nur `fetch` gestubbt (ALT-Muster). Das Mapping selbst ist in
 * `guide-mode-config.spec.ts` gepinnt; hier zählt Fetch → Signal → Cache.
 */
function mk(attr = '', apiUrl = '') {
  const ctx: GuideBootContext = {
    apiUrl: () => apiUrl,
    attrTrustedDomains: () => attr,
  };
  return { boot: new GuideBoot(ctx) };
}

const okFetch = (data: unknown) => vi.fn().mockResolvedValue({ ok: true, json: async () => data });

afterEach(() => vi.unstubAllGlobals());

describe('GuideBoot load()', () => {
  it('normalisiert trusted_domains und invalidiert den Merge-Cache', async () => {
    vi.stubGlobal('fetch', okFetch({ trusted_domains: ['HTTPS://A.Example/x', '', '*.b.de'] }));
    const { boot } = mk();
    expect(boot.trustedDomains()).toEqual([]);     // Cache vor dem Boot gefüllt
    await boot.load();
    expect(boot.trustedDomains()).toEqual(['a.example', 'b.de']);
  });

  it('mappt header_nav in das Signal (Einträge ohne url gefiltert)', async () => {
    vi.stubGlobal('fetch', okFetch({
      header_nav: [{ id: 'x1', label: 'X', url: 'https://x', new_tab: 1 }, { label: 'ohne-url' }, null],
    }));
    const { boot } = mk();
    await boot.load();
    expect(boot.headerNavButtons()).toEqual([
      { id: 'x1', label: 'X', label_en: '', icon: 'explore', url: 'https://x', new_tab: true },
    ]);
  });

  it('mappt welcome: blank greeting lässt den Fallback aktiv, quick_replies getrimmt', async () => {
    vi.stubGlobal('fetch', okFetch({
      welcome: { greeting: '   ', quick_replies: [' a ', '', 42], tour_reply: 'Zeig mir die Seite' },
    }));
    const { boot } = mk();
    await boot.load();
    expect(boot.configGreeting()).toBe('');
    expect(boot.startReplies()).toEqual(['a', '42']);   // C13: getrimmt + leer-gefiltert
    expect(boot.tourReply()).toBe('Zeig mir die Seite');
  });

  it('legt die englische Fassung in eigene Signale (C1-g1b)', async () => {
    vi.stubGlobal('fetch', okFetch({
      welcome: {
        greeting: 'Moin', greeting_en: 'Hello',
        quick_replies: ['Tour'], quick_replies_en: ['Tour EN'],
        tour_reply: 'Tour', tour_reply_en: 'Tour EN',
      },
      header_nav: [{ id: 'h', label: 'Start', label_en: 'Home', url: 'https://x' }],
    }));
    const { boot } = mk();
    await boot.load();
    // Beide Fassungen liegen nebeneinander — die Wahl trifft der Verbraucher,
    // weil die Sprache zur Laufzeit umschaltbar ist.
    expect(boot.configGreeting()).toBe('Moin');
    expect(boot.configGreetingEn()).toBe('Hello');
    expect(boot.startRepliesEn()).toEqual(['Tour EN']);
    expect(boot.tourReplyEn()).toBe('Tour EN');
    expect(boot.headerNavButtons()[0].label_en).toBe('Home');
  });

  it('non-ok-Antwort: keine Config-Übernahme, aber guideMode=true + guideHost', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    const { boot } = mk();
    await boot.load();
    expect(boot.headerNavButtons()).toEqual([]);
    expect(boot.guideMode()).toBe(true);
    // Das Guide-Env schreibt die Hülle per Effect in die Shell (sie mountet
    // lazy) — hier zählt, dass der Hostname bereitsteht.
    expect(boot.guideHost()).toBe(window.location.hostname.toLowerCase());
  });

  it('Backend nicht erreichbar: Boot läuft trotzdem durch (kein Show-Stopper)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const { boot } = mk();
    await expect(boot.load()).resolves.toBeUndefined();
    expect(boot.guideModeAvailable()).toBe(true);
    expect(boot.guideHost()).toBeTruthy();
  });

  it('strippt Trailing-Slashes der api-url für den Config-Fetch', async () => {
    const f = vi.fn().mockRejectedValue(new Error('offline'));
    vi.stubGlobal('fetch', f);
    await mk('', 'https://api.example///').boot.load();
    expect(f).toHaveBeenCalledWith('https://api.example/api/config/guide-mode');
  });
});

describe('GuideBoot trustedDomains()', () => {
  it('merged Backend-Liste zuerst, Attribut additiv, Duplikate raus', async () => {
    vi.stubGlobal('fetch', okFetch({ trusted_domains: ['wlo.example', 'shared.example'] }));
    const { boot } = mk('shared.example, dev.local');
    await boot.load();
    expect(boot.trustedDomains()).toEqual(['wlo.example', 'shared.example', 'dev.local']);
  });

  it('normalisiert Attribut-Einträge (Protokoll, Pfad, *.-Präfix, Case)', () => {
    expect(mk('HTTPS://Sub.Example.COM/pfad *.foo.de').boot.trustedDomains())
      .toEqual(['sub.example.com', 'foo.de']);
  });

  it('reagiert auf beide Quellen (ALT-Abweichung: Attribut wirkt auch nachträglich)', async () => {
    // ALT hielt einen Null-Cache, den nur der Config-Boot invalidierte: ein
    // später gesetztes `trusted-domains` wirkte nie. Jetzt ist es ein
    // `computed` — beide Quellen sind live.
    const attr = signal('');
    const boot = new GuideBoot({ apiUrl: () => '', attrTrustedDomains: () => attr() });
    expect(boot.trustedDomains()).toEqual([]);

    attr.set('neu.example');
    expect(boot.trustedDomains()).toEqual(['neu.example']);

    vi.stubGlobal('fetch', okFetch({ trusted_domains: ['backend.example'] }));
    await boot.load();
    expect(boot.trustedDomains()).toEqual(['backend.example', 'neu.example']);
  });

  it('liefert bei unveränderten Quellen dieselbe Instanz (computed-Memoisierung)', () => {
    const { boot } = mk('a.example');
    expect(boot.trustedDomains()).toBe(boot.trustedDomains());
  });
});
