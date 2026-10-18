import { describe, expect, it } from 'vitest';

import { kurzberichtAus, messbedingungenAus, stufe } from './eval-auswertung';

/**
 * Paket 13 (F1): die Auswertung v2 im Studio — Farbstufe einer Note und die Teile des
 * frei geformten `summary`, die das Lauf-Detail liest.
 */
describe('eval-auswertung (Paket 13, F1)', () => {
  it('ordnet Noten den vier Stufen zu, ohne Daten „leer“', () => {
    expect(stufe(5)).toBe('sehr-gut');
    expect(stufe(4.5)).toBe('sehr-gut');
    expect(stufe(4.49)).toBe('gut');
    expect(stufe(3.5)).toBe('gut');
    expect(stufe(3.49)).toBe('mittel');
    expect(stufe(2.5)).toBe('mittel');
    expect(stufe(2.49)).toBe('schwach');
    expect(stufe(1)).toBe('schwach');
    expect(stufe(null)).toBe('leer');
    expect(stufe(undefined)).toBe('leer');
  });

  it('liest Messbedingungen nur, wenn sie ein Objekt sind', () => {
    expect(messbedingungenAus({ messbedingungen: { maschine: 'agent' } })?.maschine)
      .toBe('agent');
    expect(messbedingungenAus({ messbedingungen: 'kaputt' })).toBeNull();
    expect(messbedingungenAus({})).toBeNull();
  });

  it('liest den Kurzbericht oder seinen Ausfall', () => {
    expect(kurzberichtAus({ kurzbericht: { text: 'Solide.', baustellen: [] } }))
      .toEqual({ text: 'Solide.', baustellen: [], fehler: '' });
    expect(kurzberichtAus({ kurzbericht_fehler: 'Judge weg' }))
      .toEqual({ text: '', baustellen: [], fehler: 'Judge weg' });
    expect(kurzberichtAus({})).toBeNull();
  });
});
