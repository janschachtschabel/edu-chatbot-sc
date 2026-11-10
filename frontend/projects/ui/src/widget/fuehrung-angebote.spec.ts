import { describe, expect, it } from 'vitest';

import { MAX_ANGEBOTE, ablaufSeitenAus, fuehrungsChips } from './fuehrung-angebote';
import { parseGuideModeConfig } from './guide-mode-config';

/**
 * AS-7b (Plan 2026-11-09 §5m, F-7): Abläufe mit Auslöser `seite` stehen im Boot-Bündel
 * (`ablauf_seiten`). Passt die Seite beim Öffnen, bietet das Widget sie als Chip unter der
 * Begrüßung an — ein Start per Knopf (`ablauf_starten`), nie von selbst.
 */
const ROH = [
  { id: 'fuehrung', titel: { de: 'Führung | Mitmachen', en: 'Tour' }, muster: ['/mitmachen*'] },
  { id: 'fach', titel: { de: 'Fach' }, muster: ['/fach/*'] },
];

describe('fuehrung-angebote (AS-7b)', () => {
  it('liest nur gültige Einträge', () => {
    expect(ablaufSeitenAus(ROH)).toHaveLength(2);
    expect(ablaufSeitenAus([{ id: 'Böse Kennung', titel: { de: 'x' }, muster: ['/'] },
                            { id: 'ok', titel: 'kein objekt', muster: ['/'] },
                            { id: 'leer', titel: { de: 'x' }, muster: [] },
                            { id: 'zahl', titel: { de: 'x' }, muster: [1] }])).toEqual([]);
    expect(ablaufSeitenAus('kaputt')).toBeNull();
  });

  it('der Boot-Parser übernimmt das Feld', () => {
    expect(parseGuideModeConfig({ ablauf_seiten: ROH }).ablaufSeiten).toHaveLength(2);
    expect(parseGuideModeConfig({}).ablaufSeiten).toBeNull();
  });

  it('passt die Seite, entsteht ein Start-Chip in der Sprache — ohne Trennzeichen im Titel', () => {
    const seiten = ablaufSeitenAus(ROH)!;
    expect(fuehrungsChips(seiten, '/mitmachen/', 'de')).toEqual([
      '__action__|Führung / Mitmachen|ablauf_starten|{"ablauf":"fuehrung"}']);
    expect(fuehrungsChips(seiten, '/mitmachen/', 'en')[0]).toContain('|Tour|');
    expect(fuehrungsChips(seiten, '/fach/', 'en')[0]).toContain('|Fach|');   // Rückfall auf Deutsch
    expect(fuehrungsChips(seiten, '/home/', 'de')).toEqual([]);
  });

  it('höchstens wenige Angebote', () => {
    const viele = Array.from({ length: 5 }, (_, i) => ({ id: `a${i}`, titel: { de: `A${i}` }, muster: ['/*'] }));
    expect(fuehrungsChips(ablaufSeitenAus(viele)!, '/x', 'de')).toHaveLength(MAX_ANGEBOTE);
  });
});
