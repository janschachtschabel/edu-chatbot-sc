import { describe, expect, it } from 'vitest';

import { ICONS } from '../icons/icons';
import { inlineDocFallbackLabel, inlineDocFontSize, inlineDocIcon } from './inline-doc';

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
    expect(inlineDocIcon('unbekannt')).toBe(ICONS.description);
    expect(inlineDocIcon('')).toBe(ICONS.description);
  });
});

describe('inlineDocFallbackLabel', () => {
  it('mappt kind → Label, sonst „Inhalt"', () => {
    expect(inlineDocFallbackLabel('lernpfad')).toBe('Lernpfad');
    expect(inlineDocFallbackLabel('ki_material')).toBe('Material');
    expect(inlineDocFallbackLabel('edit')).toBe('Bearbeitete Version');
    expect(inlineDocFallbackLabel('bericht')).toBe('Bericht');
    expect(inlineDocFallbackLabel('remix')).toBe('Remix');
    expect(inlineDocFallbackLabel('x')).toBe('Inhalt');
  });
});
