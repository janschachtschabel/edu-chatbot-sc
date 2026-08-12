import { describe, expect, it } from 'vitest';

import { resolveCardsVisible, SHOW_CARDS_MODES } from './cards-visible';

/**
 * U2b — welche der beiden vorhandenen Darstellungen greift?
 *
 * Gemessen 2026-08-09: BEIDE existieren schon. `result-groups` rendert Icon +
 * Titel als Textlink (null `<img>`), `card-list` die Kacheln mit Vorschaubild.
 * Diese Funktion entscheidet nur, welche — sie erfindet keine dritte.
 *
 * Der wichtigste Fall ist der dritte Block: jedes Bestands-Embed muss bei
 * unverändertem Markup exakt so aussehen wie vorher.
 */
describe('resolveCardsVisible', () => {
  it('„immer" gewinnt gegen Größe und Layout-Attribut', () => {
    expect(resolveCardsVisible('small', 'always', true)).toBe(true);
    expect(resolveCardsVisible('large', 'always', true)).toBe(true);
  });

  it('„nie" gewinnt ebenfalls — auch groß bleiben es Textlinks', () => {
    expect(resolveCardsVisible('large', 'never', false)).toBe(false);
    expect(resolveCardsVisible('small', 'never', true)).toBe(false);
  });

  describe('„auto" (Vorgabe)', () => {
    it('hält das Bestandsverhalten: inline-result-grouping="false" ⇒ Kacheln', () => {
      // So kam man vor U2b an den flachen Kachel-Grid. Wer das Attribut heute
      // gesetzt hat, darf durch U2b nicht auf einmal Textlinks sehen.
      expect(resolveCardsVisible('small', 'auto', false)).toBe(true);
    });

    it('sonst entscheidet die Größe: klein ⇒ Textlinks, groß ⇒ Kacheln', () => {
      expect(resolveCardsVisible('small', 'auto', true)).toBe(false);
      expect(resolveCardsVisible('large', 'auto', true)).toBe(true);
    });

    it('die Vorgabe-Kombination ist der heutige Standard: Textlinks', () => {
      // Kein `size`, kein `show-cards`, `inline-result-grouping` auf Vorgabe.
      expect(resolveCardsVisible('small', 'auto', true)).toBe(false);
    });
  });

  it('kennt genau drei Modi — die Liste speist `_attrEnum`', () => {
    expect([...SHOW_CARDS_MODES]).toEqual(['auto', 'always', 'never']);
  });
});
