import { describe, expect, it } from 'vitest';

import { splitSentences, stripMarkdown } from './tts-text';

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
