// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ShellRender } from './shell-render';

/**
 * Render-/Link-Kontext der Chat-Shell (8-4S-f2). Gepinnt wird die VERDRAHTUNG
 * der schon einzeln getesteten Bausteine (MarkdownRenderer 8-2, trusted-host
 * V5, displayContent 8-2g) an den Live-Zustand: dass Session-ID + effektive
 * Trusted-Liste bei JEDEM Zugriff frisch gelesen werden (ALT `_groupingCtx`/
 * `_markdownRenderer`-Muster mit deferred Arrows) und dass `clearCache` die
 * Bubble-Neuberechnung nach einer Trusted-Hosts-Änderung freigibt.
 */

function make(over: Partial<{ sessionId: string; trusted: string[]; persist: boolean }> = {}) {
  const state = {
    sessionId: over.sessionId ?? 'bb-11111111-2222-3333-4444-555555555555', trusted: over.trusted ?? [],
    persist: over.persist ?? true,
  };
  const render = new ShellRender({
    bypassSecurityTrustHtml: (html) => html,
    sessionId: () => state.sessionId,
    bsidKennung: () => (state.persist ? state.sessionId : ''),
    trustedDomains: () => ['wirlernenonline.de', ...state.trusted],
    inlineResultGrouping: () => true,
    t: createTranslator(DE, DE),
  });
  return { render, state };
}

// Paket 19, Review zu H-4: ohne `persist-session` reiste die Kennung trotzdem als
// `?bsid=` zu vertrauten Hosts — das WLO-Widget dort (persist an) legte sie ab.
describe('ShellRender — kein bsid ohne persist (H-4)', () => {
  it('withBsid, Karten-/Gruppen-Kontext und Markdown-Links bleiben ohne bsid', () => {
    const { render } = make({ persist: false });
    expect(render.withBsid('https://wirlernenonline.de/x')).toBe('https://wirlernenonline.de/x');
    expect(render.groupingCtx.withBsid('https://wirlernenonline.de/x')).not.toContain('bsid=');
    expect(render.resultGroupsCtx.withBsid('https://wirlernenonline.de/x')).not.toContain('bsid=');
    expect(String(render.markdown('[a](https://wirlernenonline.de/x)', 'bot'))).not.toContain('bsid=');
  });

  it('mit persist wie bisher', () => {
    const { render } = make();
    expect(render.withBsid('https://wirlernenonline.de/x')).toContain('bsid=');
  });
});

describe('ShellRender — Markdown', () => {
  it('rendert Bot-Markdown zu HTML (SafeHtml über den bypass-Seam)', () => {
    const { render } = make();
    expect(String(render.markdown('**fett**', 'bot'))).toContain('<strong>fett</strong>');
  });

  it('cached identische Inputs (gleiche Instanz → kein innerHTML-Neuschreiben)', () => {
    const { render } = make();
    expect(render.markdown('gleich', 'bot')).toBe(render.markdown('gleich', 'bot'));
  });

  it('clearCache: nach Trusted-Hosts-Wechsel wird neu gerendert', () => {
    const { render, state } = make();
    const before = render.markdown('[x](https://neu.example/a)', 'bot');
    state.trusted.push('neu.example');
    expect(render.markdown('[x](https://neu.example/a)', 'bot')).toBe(before); // Cache-Hit
    render.clearCache();
    expect(render.markdown('[x](https://neu.example/a)', 'bot')).not.toBe(before);
  });
});

describe('ShellRender — Trust + Links (live gelesen)', () => {
  it('isHostTrusted prüft gegen die AKTUELLE Liste', () => {
    const { render, state } = make();
    expect(render.isHostTrusted('fremd.example')).toBe(false);
    state.trusted.push('fremd.example');
    expect(render.isHostTrusted('fremd.example')).toBe(true);
  });

  it('withBsid hängt die AKTUELLE Session-ID an Trusted-URLs', () => {
    const { render, state } = make();
    expect(render.withBsid('https://wirlernenonline.de/x')).toContain('bsid=' + state.sessionId);
    state.sessionId = 'bb-99999999-8888-7777-6666-555555555555';
    expect(render.withBsid('https://wirlernenonline.de/x')).toContain('bsid=' + state.sessionId);
  });

  it('withBsid lässt Nicht-Trusted-URLs unangetastet (keine Session-Leakage)', () => {
    const { render } = make();
    expect(render.withBsid('https://fremd.example/x')).toBe('https://fremd.example/x');
  });

  it('externalLinkWarning warnt nur außerhalb der Trusted-Liste', () => {
    const { render } = make();
    expect(render.externalLinkWarning('https://wirlernenonline.de/x')).toBe('');
    expect(render.externalLinkWarning('https://fremd.example/x')).toBe('Achtung! Externe URL.');
  });
});

describe('ShellRender — Kontext-Objekte + displayContent', () => {
  it('resultGroupsCtx trägt withBsid/externalLinkWarning/isTrustedHost der Instanz', () => {
    const { render } = make();
    expect(render.resultGroupsCtx.withBsid('https://wirlernenonline.de/x')).toContain('bsid=');
    expect(render.resultGroupsCtx.externalLinkWarning('https://fremd.example')).toBe('Achtung! Externe URL.');
    expect(render.resultGroupsCtx.isTrustedHost('wirlernenonline.de')).toBe(true);
  });

  it('displayContent strippt bei aktivem Grouping die doppelten Bullet-Links', () => {
    const { render } = make();
    const msg: ChatMessage = {
      id: 'm', sender: 'bot', timestamp: new Date(),
      content: 'Intro\n- [Artikel](https://wirlernenonline.de/a)\nSchluss',
      webLinks: [{ title: 'Artikel', url: 'https://wirlernenonline.de/a' }],
    };
    const out = render.displayContent(msg);
    expect(out).toContain('Intro');
    expect(out).toContain('Schluss');
    expect(out).not.toContain('](https://wirlernenonline.de/a)');
  });
});
