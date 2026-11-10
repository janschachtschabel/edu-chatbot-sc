import { describe, expect, it } from 'vitest';

import { ohneMarkdownEscapes, splitSentences, stripMarkdown } from './tts-text';

/**
 * Charakterisierung der TTS-Text-Helfer — Verbatim-Port aus ALT
 * chat-text-utils.ts (dort kein Standalone-Spec). Gepinnt: Markdown-Strip
 * (Bold/Italic/Link/Header/Backtick) + Satz-Split inkl. Kurzfragment-Merge
 * (<20 Zeichen) und Leer-Eingabe.
 */
describe('stripMarkdown', () => {
  it('entfernt Bold/Italic/Link/Header/Backtick-Marker', () => {
    expect(stripMarkdown('**fett**')).toBe('fett');
    expect(stripMarkdown('*kursiv*')).toBe('kursiv');
    expect(stripMarkdown('[Titel](https://x.de)')).toBe('Titel');
    expect(stripMarkdown('## Überschrift')).toBe('Überschrift');
    expect(stripMarkdown('`code` und ~x~')).toBe('code und x');
  });

  it('kombiniert mehrere Marker in einem Text', () => {
    expect(stripMarkdown('**Hallo** [Welt](u), ## Titel')).toBe('Hallo Welt, Titel');
  });
});

describe('splitSentences', () => {
  it('teilt an Satzende-Zeichen (beide Sätze ≥20 Zeichen → kein Merge)', () => {
    expect(splitSentences('Das ist der erste vollständige Satz. Und hier folgt der zweite Satz.')).toEqual([
      'Das ist der erste vollständige Satz.',
      'Und hier folgt der zweite Satz.',
    ]);
  });

  it('mergt Kurzfragmente (<20 Zeichen) an den vorigen Satz', () => {
    expect(splitSentences('Das ist ein langer erster Satz hier. Ja.')).toEqual([
      'Das ist ein langer erster Satz hier. Ja.',
    ]);
  });

  it('Leer-Eingabe → leeres Array', () => {
    expect(splitSentences('')).toEqual([]);
  });

  it('Text ohne Satzende bleibt ein Chunk', () => {
    expect(splitSentences('kein Satzende')).toEqual(['kein Satzende']);
  });
});

describe('ohneMarkdownEscapes (AS-3b)', () => {
  it('löst die Escapes eingesetzter Werte auf — vorgelesen ohne Rückstrich', () => {
    expect(ohneMarkdownEscapes('https\\:\\/\\/x\\.de \\(a\\)')).toBe('https://x.de (a)');
    expect(stripMarkdown('Notiert\\: **Optik\\.**')).toBe('Notiert: Optik.');
  });
});

describe('ohneMarkdownEscapes — Entitäten (Querschnitts-Review Gruppe E)', () => {
  it('löst auch die Klammer- und Dollar-Entitäten eingesetzter Werte auf', () => {
    expect(ohneMarkdownEscapes('Brüche &#40;Klasse 6&#41; &#91;a\\.b&#93; &#36;5'))
      .toBe('Brüche (Klasse 6) [a.b] $5');
    expect(ohneMarkdownEscapes('&#60;script&#62;')).toBe('&#60;script&#62;');   // nur diese fünf
  });
});

describe('stripMarkdown — Formeln (Querschnitts-Review Gruppe E, Befund 5)', () => {
  it('liest Formeln ohne Begrenzer und ohne LaTeX-Befehle', () => {
    expect(stripMarkdown('Rechne \\(\\frac{1}{2}\\cdot x\\).')).toBe('Rechne 1/2 · x.');
    expect(stripMarkdown('\\[\\sqrt{2} \\approx 1,41\\]')).toBe('√2 ≈ 1,41');
    expect(stripMarkdown('\\(\\alpha + \\beta\\)')).toBe('α + β');
  });
});
