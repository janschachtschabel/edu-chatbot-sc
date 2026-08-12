// @vitest-environment jsdom
import { afterEach, describe, it, expect, vi } from 'vitest';
import { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { printCanvasMaterial, printLearningPath, printMdToHtml, safePrintHref } from './print-utils';

/**
 * Charakterisierungstests für ``printMdToHtml`` — den (vormals 3× inline
 * duplizierten) Markdown→HTML-Renderer der Druckfenster (Frontend-Split
 * Welle 2, Schritt 7, 2026-07-09). Gepinnt ist hier zuerst die pure
 * String-Transformation; seit C1-b4 zusätzlich der Text des geschriebenen
 * Druckfensters — über dieselbe `window.open`-Attrappe, die `print-gates.spec`
 * schon benutzt (nur die Browser-Grenze ist gefälscht, der Modul-Pfad läuft
 * echt bis ins geschriebene HTML).
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

/**
 * C1-b4: das Druckfenster spricht die Sprache des Nutzers. Es ist ein zweites
 * Dokument ohne Angular — Beschriftung, Fußzeile, Pop-up-Hinweis, die
 * `lang`-Auszeichnung UND das Datumsformat müssen alle mitziehen, sonst steht
 * ein englischer Text unter einer deutschen Kopfzeile mit deutschem Datum.
 */
describe('Druckfenster: Oberflächentexte, Sprache, Datumsformat (C1-b4)', () => {
  const t = createTranslator(DE, DE);
  const SENTINEL = '<!-- boerdi:printable-canvas|arbeitsblatt|Bruchrechnen -->';

  function bot(content: string, fields: Partial<ChatMessage> = {}): ChatMessage {
    return { id: 'm1', sender: 'bot', content, timestamp: new Date(), ...fields } as ChatMessage;
  }

  /** Nur die Browser-Grenze wird gefälscht; `null` erzwingt den Pop-up-Zweig. */
  function captureOpen(blocked = false): { written: string[]; alerts: string[] } {
    const written: string[] = [];
    const alerts: string[] = [];
    const fakeWin = {
      document: { open: () => {}, write: (h: string) => { written.push(h); }, close: () => {} },
    };
    vi.stubGlobal('open', () => (blocked ? null : fakeWin));
    vi.stubGlobal('alert', (m: string) => { alerts.push(m); });
    return { written, alerts };
  }

  afterEach(() => vi.unstubAllGlobals());

  it('Canvas-Material: Knopf, Kopf-Datum und Fußzeile kommen aus dem Übersetzer', () => {
    const { written } = captureOpen();
    const en = createTranslator({
      'print.button': '🖨 Print / Save as PDF',
      'print.footer': 'Created with BadBoerdi · WirLernenOnline.de · {date}',
    }, DE);
    printCanvasMaterial(bot(SENTINEL + '\n# Aufgabe 1'), en);
    expect(written[0]).toContain('🖨 Print / Save as PDF');
    expect(written[0]).toContain('Created with BadBoerdi');
    // Titel und Typ stehen im Backend-Sentinel und bleiben unübersetzt.
    expect(written[0]).toContain('<title>Bruchrechnen – BadBoerdi</title>');
  });

  it('Lernpfad: Überschrift und die gezählte Quellen-Zeile kommen aus dem Übersetzer', () => {
    const { written } = captureOpen();
    const en = createTranslator({
      'print.learningPath': 'Learning path',
      'print.usedContents': 'Sources used ({count})',
    }, DE);
    printLearningPath(bot('**Lernpfad:** los', { cards: [{ title: 'A' }, { title: 'B' }] as never }), en);
    expect(written[0]).toContain('<title>Learning path – BadBoerdi</title>');
    expect(written[0]).toContain('<h2>Sources used (2)</h2>');
  });

  it('die Dokumentsprache folgt dem Katalog — sonst liest ein Screenreader Englisch auf Deutsch vor', () => {
    const { written } = captureOpen();
    printLearningPath(bot('**Lernpfad:** los'), createTranslator({ 'format.htmlLang': 'en' }, DE));
    expect(written[0]).toContain('<html lang="en">');
  });

  it('das Datum folgt dem Katalog-Tag: de-DE schreibt „2. August", en-GB „2 August"', () => {
    const deutsch = captureOpen();
    printCanvasMaterial(bot(SENTINEL), t);
    expect(deutsch.written[0]).toMatch(/\d{1,2}\.\s\w+\s\d{4}/);

    vi.unstubAllGlobals();
    const englisch = captureOpen();
    printCanvasMaterial(bot(SENTINEL), createTranslator({ 'format.dateLocale': 'en-GB' }, DE));
    expect(englisch.written[0]).not.toMatch(/\d{1,2}\.\s\w+\s\d{4}/);
  });

  it('der Datums-Tag des Katalogs ist für Intl brauchbar (C1-c ergänzt hier Englisch)', () => {
    // Ein Tippfehler im Katalog wäre sonst eine RangeError beim Klick auf
    // „Drucken" — der Katalog ist Code, also fängt das ein Test und kein
    // try/catch im Druckpfad.
    expect(() => new Intl.DateTimeFormat(DE['format.dateLocale'])).not.toThrow();
  });

  it('blockiertes Pop-up: der Hinweis kommt aus dem Übersetzer, je Druckart eigener Text', () => {
    const material = captureOpen(true);
    printCanvasMaterial(bot(SENTINEL), createTranslator({ 'print.popupBlockedMaterial': 'Please allow pop-ups.' }, DE));
    expect(material.alerts).toEqual(['Please allow pop-ups.']);
    expect(material.written).toEqual([]);

    vi.unstubAllGlobals();
    const lernpfad = captureOpen(true);
    printLearningPath(bot('**Lernpfad:** los'), createTranslator({ 'print.popupBlockedLearningPath': 'Allow pop-ups for the path.' }, DE));
    expect(lernpfad.alerts).toEqual(['Allow pop-ups for the path.']);
  });
});
