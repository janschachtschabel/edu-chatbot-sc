// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import {
  headerNavHrefWithBsid, headerNavIconSvg, parseGuideModeConfig, pickLocalized,
} from './guide-mode-config';
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
      greetingEn: null, startRepliesEn: null, tourReplyEn: null, mcpAuthBase: null,
    });
    expect(parseGuideModeConfig(null).trustedDomains).toBeNull();
  });

  // C5-c2: Herkunft des MCP-Servers für die WLO-Anmeldung.
  it('übernimmt die MCP-Herkunft, den LEEREN Wert eingeschlossen', () => {
    // Leer ist eine Aussage („diese Anlage bietet keine Anmeldung an") und
    // muss deshalb ein vorhandenes Signal überschreiben — anders als ein
    // fehlendes Feld, das nur „stand nicht in der Antwort" heisst.
    expect(parseGuideModeConfig({ mcp_auth_base: 'https://mcp.example' }).mcpAuthBase)
      .toBe('https://mcp.example');
    expect(parseGuideModeConfig({ mcp_auth_base: '  ' }).mcpAuthBase).toBe('');
    expect(parseGuideModeConfig({ mcp_auth_base: 42 }).mcpAuthBase).toBeNull();
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
      { id: 'home', label: 'Start', label_en: '', icon: 'explore', url: 'https://x.example', new_tab: true },
      { id: '', label: '', label_en: '', icon: 'explore', url: 'https://y.example', new_tab: false },
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

  // ── C1-g1b: die englische Fassung reist getrennt mit ────────────────────
  // Der Server loest die Sprache NICHT auf (C1-g1a) — das Widget waehlt, weil
  // es zur Laufzeit umschalten kann.

  it('mappt welcome: die englischen Felder nach denselben Regeln', () => {
    const cfg = parseGuideModeConfig({
      welcome: {
        greeting: 'Moin', greeting_en: 'Hello',
        quick_replies: ['Tour'], quick_replies_en: [' Tour EN ', ''],
        tour_reply: 'Tour', tour_reply_en: 'Tour EN',
      },
    });
    expect(cfg.greetingEn).toBe('Hello');
    expect(cfg.startRepliesEn).toEqual(['Tour EN']);
    expect(cfg.tourReplyEn).toBe('Tour EN');
  });

  it('mappt header_nav: label_en getrimmt, fehlend zu ""', () => {
    const nav = parseGuideModeConfig({
      header_nav: [{ id: 'home', label: 'Start', label_en: '  Home  ',
                     url: 'https://x.example' }],
    }).headerNav;
    expect(nav?.[0].label_en).toBe('Home');
  });
});

describe('pickLocalized', () => {
  it('englisch gepflegt → englisch', () => {
    expect(pickLocalized('Start', 'Home', 'en')).toBe('Home');
  });

  it('englisch leer heisst „nicht gepflegt" → deutsch', () => {
    // Dieselbe Regel wie im Backend-Loader (C1-g1a): ein leeres Feld ist kein
    // leerer Text, sondern die Ansage „nimm das deutsche".
    expect(pickLocalized('Start', '', 'en')).toBe('Start');
  });

  it('deutsche Oberflaeche nimmt nie das englische Feld', () => {
    expect(pickLocalized('Start', 'Home', 'de')).toBe('Start');
  });

  it('gilt genauso fuer Listen', () => {
    expect(pickLocalized(['a'], ['A'], 'en')).toEqual(['A']);
    expect(pickLocalized(['a'], [], 'en')).toEqual(['a']);
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
  const btn = (url: string) => ({
    id: '', label: '', label_en: '', icon: 'explore', url, new_tab: false,
  });

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
