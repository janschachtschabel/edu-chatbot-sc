import { describe, expect, it } from 'vitest';

import { schriftProzent } from './schrift-skala';

/** Übernommen aus der früheren Dokument-Box (`inlineDocFontSize`, ALT-Port). */
describe('schriftProzent', () => {
  it('liest inline_documents.font_size_percent, klammert [70,100], Vorgabe 85', () => {
    expect(schriftProzent({ inline_documents: { font_size_percent: 90 } })).toBe(90);
    expect(schriftProzent({ inline_documents: { font_size_percent: '80' } })).toBe(80); // Text → parseInt
    expect(schriftProzent({ inline_documents: { font_size_percent: 50 } })).toBe(70);
    expect(schriftProzent({ inline_documents: { font_size_percent: 150 } })).toBe(100);
    expect(schriftProzent({})).toBe(85);
    expect(schriftProzent(null)).toBe(85);
    expect(schriftProzent({ inline_documents: { font_size_percent: 'abc' } })).toBe(85);
  });
});
