import { describe, expect, it } from 'vitest';

import { ICONS } from '../icons/icons';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { inlineDocFallbackLabel, inlineDocFontSize, inlineDocIcon } from './inline-doc';

/** Deutscher Übersetzer — pinnt den bisherigen Wortlaut über den Katalog. */
const t = createTranslator(DE, DE);

/** Charakterisierung der Inline-Document-Helfer — Verbatim-Port der
 *  ALT-`ChatComponent`-Methoden (Erwartungen aus dem ALT-Quelltext). */
describe('inlineDocFontSize', () => {
  it('liest inline_documents.font_size_percent, klammert [70,100], Default 85', () => {
    expect(inlineDocFontSize({ inline_documents: { font_size_percent: 90 } })).toBe(90);
    expect(inlineDocFontSize({ inline_documents: { font_size_percent: '80' } })).toBe(80); // String → parseInt
    expect(inlineDocFontSize({ inline_documents: { font_size_percent: 50 } })).toBe(70); // < Min
    expect(inlineDocFontSize({ inline_documents: { font_size_percent: 150 } })).toBe(100); // > Max
    expect(inlineDocFontSize({})).toBe(85);
    expect(inlineDocFontSize(null)).toBe(85);
    expect(inlineDocFontSize({ inline_documents: { font_size_percent: 'abc' } })).toBe(85); // NaN → Default
  });
});

describe('inlineDocIcon', () => {
  it('mappt kind (case-insensitiv) → Icon, sonst description', () => {
    expect(inlineDocIcon('lernpfad')).toBe(ICONS.route);
    expect(inlineDocIcon('KI_MATERIAL')).toBe(ICONS.article);
    expect(inlineDocIcon('edit')).toBe(ICONS.edit);
    expect(inlineDocIcon('bericht')).toBe(ICONS.description);
    expect(inlineDocIcon('remix')).toBe(ICONS.refresh);
    // Die Schreib-Abnahme zeigt VORGESCHLAGENE Änderungen, keine erledigten.
    // Deshalb `edit_note` und bewusst nicht `check`: ein Haken behauptete, es
    // sei schon geschehen — genau das, was die Box verhindern soll.
    expect(inlineDocIcon('schreib_vorschau')).toBe(ICONS.edit_note);
    expect(inlineDocIcon('unbekannt')).toBe(ICONS.description);
    expect(inlineDocIcon('')).toBe(ICONS.description);
  });
});

describe('inlineDocFallbackLabel', () => {
  it('mappt kind → Label, sonst „Inhalt"', () => {
    expect(inlineDocFallbackLabel('lernpfad', t)).toBe('Lernpfad');
    expect(inlineDocFallbackLabel('ki_material', t)).toBe('Material');
    expect(inlineDocFallbackLabel('edit', t)).toBe('Bearbeitete Version');
    expect(inlineDocFallbackLabel('bericht', t)).toBe('Bericht');
    expect(inlineDocFallbackLabel('remix', t)).toBe('Remix');
    expect(inlineDocFallbackLabel('x', t)).toBe('Inhalt');
  });

  it('nimmt die Labels aus dem Übersetzer (C1-b3)', () => {
    const en = createTranslator(
      { 'inlineDoc.kind.lernpfad': 'Learning path', 'inlineDoc.kind.fallback': 'Content' },
      DE,
    );
    expect(inlineDocFallbackLabel('lernpfad', en)).toBe('Learning path');
    expect(inlineDocFallbackLabel('x', en)).toBe('Content');
    // Rückfall je Schlüssel: was Englisch nicht kennt, kommt deutsch.
    expect(inlineDocFallbackLabel('remix', en)).toBe('Remix');
  });
});
