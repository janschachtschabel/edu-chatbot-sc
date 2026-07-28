import { describe, it, expect } from 'vitest';
import { printMdToHtml, safePrintHref } from './print-utils';

/**
 * Charakterisierungstests für ``printMdToHtml`` — den (vormals 3× inline
 * duplizierten) Markdown→HTML-Renderer der Druckfenster (Frontend-Split
 * Welle 2, Schritt 7, 2026-07-09). Die Print-Pfade selbst
 * (``printLearningPath``/``printCanvasMaterial``/``printMarkdownDocument``)
 * bleiben ungenetzt (window.open in ein Zweitfenster ist in jsdom nicht
 * ehrlich fakebar) — gepinnt wird hier die pure String-Transformation.
 *
 * Verhalten ist strikt an die chat.component-Referenz gebunden (Diff-
 * Befund siehe Modul-Kopf von ``print-utils.ts``): ``blockquotes: false``
 * pinnt das IST-Verhalten der alten ``_printMarkdown``-Kopie.
 */
describe('printMdToHtml (Print-Markdown-Renderer)', () => {
  it('Headings (+1 Level, Cap 6), Bold/Italic, OL/LI-Divs, Plain-Text → <p>', () => {
    const html = printMdToHtml([
      '# Titel',
      '###### Tief',
      '**fett** und *kursiv*',
      '1. erstens',
      '- punkt',
      'normal',
    ].join('\n'));
    expect(html).toContain('<h2>Titel</h2>');                 // # → h2 (Print-h1 = Doc-Titel)
    expect(html).toContain('<h6>Tief</h6>');                  // Cap bei h6
    expect(html).toContain('<strong>fett</strong>');
    expect(html).toContain('<em>kursiv</em>');
    expect(html).toContain('<div class="ol"><span class="n">1.</span> erstens</div>');
    expect(html).toContain('<div class="li"><span class="b">•</span> punkt</div>');
    expect(html).toContain('<p>normal</p>');
  });

  it('Blockquote-Modus: default → <blockquote>; blockquotes:false (alter _printMarkdown-Pfad) → escaped <p>', () => {
    expect(printMdToHtml('> Zitat')).toBe('<blockquote>Zitat</blockquote>');
    // IST-Verhalten der InlineDocument-Kopie: kein &gt;-Restore, kein bq-Branch.
    expect(printMdToHtml('> Zitat', { blockquotes: false })).toBe('<p>&gt; Zitat</p>');
  });

  it('Links: target=_blank + rel=noopener, URL-Doublequote encoded (A4-XSS-Fix); HTML wird escaped', () => {
    const html = printMdToHtml('Siehe [Seite](https://x.example/p?q="v\') dazu <script>alert(1)</script>');
    // NOTE: pinnt IST-Verhalten — '"' bricht als %22 nicht mehr aus dem
    // double-quoted href aus (A4-Fix 2026-06-10); "'" bleibt roh, weil
    // encodeURIComponent Single-Quotes nicht encodet (im href harmlos).
    expect(html).toContain(
      '<a href="https://x.example/p?q=%22v\'" target="_blank" rel="noopener">Seite</a>',
    );
    expect(html).not.toContain('<script');
    expect(html).toContain('&lt;script&gt;');
  });
});

/**
 * Print-hrefs (Audit 2026-07-09): die Card-Links im Lernpfad-Druckfenster
 * wurden nur ``esc()``-t, ohne Protokoll-Check → ein ``javascript:``-URI
 * landete klickbar im Druckfenster (das die Host-Origin erbt). ``safePrintHref``
 * lässt nur http(s) durch (sonst ``''`` = kein Link).
 */
describe('safePrintHref (Print-Link-Guard)', () => {
  it('lässt http(s) durch (getrimmt)', () => {
    expect(safePrintHref('https://x.example/p')).toBe('https://x.example/p');
    expect(safePrintHref('http://x.example/p')).toBe('http://x.example/p');
    expect(safePrintHref('  https://x.example/p  ')).toBe('https://x.example/p');
  });
  it('blockt javascript:/data:/mailto: und leere Werte → ""', () => {
    expect(safePrintHref('javascript:alert(1)')).toBe('');
    expect(safePrintHref('data:text/html,<script>alert(1)</script>')).toBe('');
    expect(safePrintHref('mailto:a@b.de')).toBe('');
    expect(safePrintHref('')).toBe('');
    expect(safePrintHref(null)).toBe('');
    expect(safePrintHref(undefined)).toBe('');
  });
});
