import { describe, expect, it } from 'vitest';

import { strukturHinweise } from './entwurf-pruefung';
import type { Baum, EntwurfKnoten } from './entwurf-regeln';

/** Paket R4 (TB-4, Entscheid R-E11): Struktur-Hinweise nach dem Leitfaden — nur Warnungen. */
let nr = 0;
function k(titel: string, kinder?: EntwurfKnoten[]): EntwurfKnoten {
  nr++;
  return { id: `k${nr}`, titel, ...(kinder ? { kinder } : {}) };
}
const oben = (n: number, kinder?: () => EntwurfKnoten[]): Baum =>
  Array.from({ length: n }, (_v, i) => k(`Thema ${i + 1}`, kinder?.()));
const codes = (baum: Baum) => strukturHinweise(baum).map((h) => h.code);

describe('strukturHinweise', () => {
  it('ein Baum nach dem Leitfaden hat keine Hinweise', () => {
    expect(strukturHinweise(oben(6, () => [k('A'), k('B'), k('C')]))).toEqual([]);
  });

  it('oben weniger als 5 oder mehr als 15 Punkte', () => {
    expect(strukturHinweise(oben(3))).toEqual([{ code: 'oben', anzahl: 3 }]);
    expect(codes(oben(16))).toEqual(['oben']);
  });

  it('genau ein Unterpunkt, und mehr als 12', () => {
    const baum = [...oben(5), k('Optik', [k('Linsen')]), k('Mechanik', Array.from({ length: 13 }, (_v, i) => k(`M${i}`)))];
    expect(strukturHinweise(baum)).toEqual([
      { code: 'einzelkind', titel: 'Optik' },
      { code: 'breit', titel: 'Mechanik', anzahl: 13 },
    ]);
  });

  it('mehr als drei Ebenen', () => {
    const baum = [...oben(5), k('Tief', [k('a', [k('b', [k('c')]), k('b2')]), k('a2')])];
    expect(codes(baum)).toContain('tief');
  });

  it('Jahreszahl, Klassenstufe, Format oder Sammelpunkt im Namen', () => {
    const baum = [...oben(3), k('Schuljahr 2024/25'), k('2023'), k('Klasse 7'), k('Arbeitsblätter'), k('Sonstiges')];
    expect(strukturHinweise(baum).flatMap((h) => (h.code === 'name' ? [h.titel] : [])))
      .toEqual(['Schuljahr 2024/25', '2023', 'Klasse 7', 'Arbeitsblätter', 'Sonstiges']);
  });

  it('Querschnitts-Review, Befund 6: ein Jahr IM Thema ist kein Hinweis (Geschichte, Politik)', () => {
    const baum = [...oben(3), k('Revolution 1848'), k('Weimarer Republik 1918–1933'), k('Agenda 2030')];
    expect(codes(baum)).toEqual([]);
  });

  it('doppelte Titel unter Geschwistern, ohne Groß/Klein', () => {
    expect(codes([...oben(4), k('Licht'), k('licht ')])).toEqual(['doppelt']);
  });

  it('höchstens zehn Hinweise — der Rest als Zahl', () => {
    const viele = Array.from({ length: 14 }, (_v, i) => k(`Klasse ${i + 1}`));
    const hinweise = strukturHinweise(viele);
    expect(hinweise).toHaveLength(11);
    expect(hinweise.at(-1)).toEqual({ code: 'weitere', anzahl: 4 });
  });
});
