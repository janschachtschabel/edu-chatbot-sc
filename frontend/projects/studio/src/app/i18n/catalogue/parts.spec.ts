import { describe, expect, it } from 'vitest';

import { STUDIO_PARTS } from './parts';

/**
 * Der Split in Teilkataloge (C1-d3b) bringt eine Gefahr mit, die es vorher
 * nicht gab: `de.ts` setzt die Teile mit `Object.assign` zusammen, und derselbe
 * Schlüssel in zwei Teilen überschreibt still den ersten. In beiden Sprachen
 * gleichermassen — `en.spec.ts` prüft Schlüsselgleichheit DE↔EN und bliebe
 * dabei grün, während ein Text spurlos verschwindet.
 *
 * Deshalb ist `STUDIO_PARTS` eine EINE Liste von `{ de, en }`-Paaren und nicht
 * zwei Listen: so kann ein neuer Teil nicht versehentlich nur in einer Sprache
 * eingehängt werden, und diese Prüfung deckt jeden künftigen Teil ohne
 * Nacharbeit ab.
 */
describe('STUDIO_PARTS', () => {
  it('kein Schlüssel steht in zwei Teilkatalogen', () => {
    for (const sprache of ['de', 'en'] as const) {
      const gesehen = new Set<string>();
      const doppelt: string[] = [];
      for (const teil of STUDIO_PARTS) {
        for (const key of Object.keys(teil[sprache])) {
          if (gesehen.has(key)) doppelt.push(key);
          gesehen.add(key);
        }
      }
      expect(doppelt, `doppelte Schlüssel im ${sprache}-Katalog`).toEqual([]);
    }
  });

  it('jeder Teil trägt in beiden Sprachen dieselben Schlüssel', () => {
    // Die globale Prüfung in `en.spec.ts` sagt nur, DASS etwas fehlt; diese
    // sagt, in welchem Teil — bei sechs Teilen der Unterschied zwischen einem
    // Blick und einer Suche.
    for (const [index, teil] of STUDIO_PARTS.entries()) {
      expect(Object.keys(teil.en).sort(), `Teil ${index}`)
        .toEqual(Object.keys(teil.de).sort());
    }
  });

  it('kein Teil ist leer', () => {
    // Ein leerer Teil wäre ein halb fertiger Umbau, den keine andere Prüfung
    // bemerkt: schlüsselgleich ist er, doppelt ist er nicht.
    for (const [index, teil] of STUDIO_PARTS.entries()) {
      expect(Object.keys(teil.de).length, `Teil ${index} ist leer`).toBeGreaterThan(0);
    }
  });
});
