// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import { headerNavHrefWithBsid, headerNavIconSvg, parseGuideModeConfig } from './guide-mode-config';
import { ICONS } from '../icons/icons';

/**
 * Charakterisierung des Guide-Mode-Config-Mappings + der Header-Nav-Helfer.
 * Übernimmt die ALT-Blöcke „WidgetComponent Header-Nav" (spec:201-233) und den
 * Mapping-Teil von „initGuideMode Response-Mapping" (spec:351-404) — dort über
 * die Komponente + `fetch`-Stub, hier direkt gegen die puren Funktionen (das
 * Fetch-Verhalten selbst pinnt `guide-boot.spec.ts`).
 */
const VALID_SID = 'bb-6f9619ff-8b86-4d01-b42d-00cf4fc964ff';
const TRUSTED = ['trusted.example'];

describe('parseGuideModeConfig', () => {
  it('fehlende Felder bleiben null (Signal wird nicht angetastet)', () => {
    expect(parseGuideModeConfig({})).toEqual({
      trustedDomains: null, headerNav: null, greeting: null, startReplies: null, tourReply: null,
    });
    expect(parseGuideModeConfig(null).trustedDomains).toBeNull();
  });

  it('normalisiert trusted_domains und filtert leere Einträge', () => {
    expect(parseGuideModeConfig({ trusted_domains: ['HTTPS://A.Example/x', '', '*.b.de'] }).trustedDomains)
      .toEqual(['a.example', 'b.de']);
  });

  it('mappt header_nav: ohne url gefiltert, icon-Default explore, new_tab koerziert', () => {
    const nav = parseGuideModeConfig({
      header_nav: [
        { id: 'home', label: 'Start', url: 'https://x.example', new_tab: 1 },
        { id: 'kaputt', label: 'ohne url' },
        { url: 'https://y.example' },
      ],
    }).headerNav;
    expect(nav).toEqual([
      { id: 'home', label: 'Start', icon: 'explore', url: 'https://x.example', new_tab: true },
      { id: '', label: '', icon: 'explore', url: 'https://y.example', new_tab: false },
    ]);
  });

  it('mappt welcome: greeting nur non-blank, quick_replies getrimmt + leer-gefiltert', () => {
    const cfg = parseGuideModeConfig({
      welcome: { greeting: '  Moin  ', quick_replies: [' Tour ', '', 'Suche'], tour_reply: '' },
    });
    expect(cfg.greeting).toBe('  Moin  ');       // NOTE: pinnt IST — ungetrimmt übernommen
    expect(cfg.startReplies).toEqual(['Tour', 'Suche']);   // C13: getrimmt
    expect(cfg.tourReply).toBe('');              // jeder String zählt, auch ''
    expect(parseGuideModeConfig({ welcome: { greeting: '   ' } }).greeting).toBeNull();
  });
});

describe('headerNavIconSvg', () => {
  it('bekannter Name → Icon, unbekannt → explore-Fallback', () => {
    expect(headerNavIconSvg('refresh')).toBe(ICONS.refresh);
    expect(headerNavIconSvg('gibtsnicht')).toBe(ICONS.explore);
    expect(headerNavIconSvg(undefined)).toBe(ICONS.explore);
  });
});

describe('headerNavHrefWithBsid', () => {
  const btn = (url: string) => ({ id: '', label: '', icon: 'explore', url, new_tab: false });

  beforeEach(() => history.replaceState({}, '', '/'));

  it('leere URL → "#", ohne gültige Session bleibt die URL unverändert', () => {
    expect(headerNavHrefWithBsid(btn('  '), VALID_SID, TRUSTED)).toBe('#');
    expect(headerNavHrefWithBsid(btn('https://trusted.example/x'), '', TRUSTED))
      .toBe('https://trusted.example/x');
  });

  it('trusted Host + Session → bsid; untrusted/mailto bleiben unverändert', () => {
    expect(headerNavHrefWithBsid(btn('https://trusted.example/x'), VALID_SID, TRUSTED))
      .toContain(`bsid=${VALID_SID}`);
    expect(headerNavHrefWithBsid(btn('https://evil.example/x'), VALID_SID, TRUSTED))
      .toBe('https://evil.example/x');
    expect(headerNavHrefWithBsid(btn('mailto:info@example.org'), VALID_SID, TRUSTED))
      .toBe('mailto:info@example.org');
  });

  it('bsid wird bewusst AUCH same-origin angehängt (anders als Click-Rewrite)', () => {
    // NOTE: pinnt IST-Verhalten — Widget-Auto-Open & Tour keyen auf ?bsid=.
    const href = headerNavHrefWithBsid(
      btn(window.location.origin + '/start'), VALID_SID, [window.location.hostname],
    );
    expect(href).toContain('bsid=');
  });

  it('vorhandene bsid wird nicht überschrieben', () => {
    expect(headerNavHrefWithBsid(btn('https://trusted.example/x?bsid=alt'), VALID_SID, TRUSTED))
      .toContain('bsid=alt');
  });
});
