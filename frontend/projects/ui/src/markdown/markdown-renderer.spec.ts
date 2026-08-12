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
