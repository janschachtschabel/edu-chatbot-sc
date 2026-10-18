import { describe, expect, it } from 'vitest';

import { nutzungStufen, stufeVon } from './nutzung-stufen';

/**
 * Farbstufen der Nutzung (Studio-Rundgang 2026-10-18): aus den vorkommenden Zahlen abgeleitet,
 * mit runden Grenzen — statt „<5“ steht die genaue Zahl in der Zelle, die Legende nennt die
 * Bereiche (wie die Notenstufen der Evaluation).
 */
describe('nutzungStufen', () => {
  it('teilt bis zum Höchstwert in höchstens vier runde Bereiche', () => {
    expect(nutzungStufen([1, 3, 5, 15, 21])).toEqual([
      { von: 1, bis: 4 }, { von: 5, bis: 9 }, { von: 10, bis: 14 }, { von: 15, bis: null },
    ]);
  });

  it('rundet den Schritt zum nächsten runden Wert, damit der Verlauf trägt (19 → Schritte zu 5)', () => {
    // Abgerundet (4,75 → 2) fielen 6 bis 19 alle in die dunkelste Stufe.
    expect(nutzungStufen([1, 7, 19])).toEqual([
      { von: 1, bis: 4 }, { von: 5, bis: 9 }, { von: 10, bis: 14 }, { von: 15, bis: null },
    ]);
  });

  it('nimmt bei großen Zahlen runde Schritte', () => {
    expect(nutzungStufen([3, 180, 412])).toEqual([
      { von: 1, bis: 99 }, { von: 100, bis: 199 }, { von: 200, bis: 299 }, { von: 300, bis: null },
    ]);
  });

  it('gibt kleinen Zahlen je Wert eine Stufe statt doppelter Grenzen', () => {
    expect(nutzungStufen([1, 2, 3])).toEqual([
      { von: 1, bis: 1 }, { von: 2, bis: 2 }, { von: 3, bis: null },
    ]);
  });

  it('kennt ohne Züge keine Stufe', () => {
    expect(nutzungStufen([0, 0])).toEqual([]);
  });
});

describe('stufeVon', () => {
  const stufen = nutzungStufen([1, 21]);

  it('ordnet eine Zahl ihrem Bereich zu, 1-basiert; null bleibt 0', () => {
    expect(stufeVon(0, stufen)).toBe(0);
    expect(stufeVon(1, stufen)).toBe(1);
    expect(stufeVon(9, stufen)).toBe(2);
    expect(stufeVon(21, stufen)).toBe(4);
  });
});
