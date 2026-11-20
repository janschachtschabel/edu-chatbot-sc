import { describe, expect, it } from 'vitest';

import { initialen } from './initialen';

/** Plan 2026-11-19 (E8): das Kürzel im Kreis neben dem Abmelde-Knopf. */
describe('initialen', () => {
  it('nimmt den ersten Buchstaben des ersten und des letzten Worts', () => {
    expect(initialen('Jan Schachtschabel')).toBe('JS');
    // Ein Mittelname zählt nicht — zwei Buchstaben passen in den Kreis.
    expect(initialen('Anna Maria Müller')).toBe('AM');
  });

  it('schreibt groß, auch Umlaute', () => {
    expect(initialen('jan schachtschabel')).toBe('JS');
    expect(initialen('özlem ünal')).toBe('ÖÜ');
    expect(initialen('Ärzte Übung')).toBe('ÄÜ');
  });

  it('gibt bei einem Wort einen Buchstaben', () => {
    expect(initialen('Lea')).toBe('L');
  });

  it('bleibt bei einem Zeichen je Wort, auch wo Großschreiben mehr daraus macht', () => {
    // Zweites Review B (6): „ß“ wird groß zu „SS“ — im Kreis zählt nur ein Buchstabe je Wort.
    expect(initialen('ßa')).toBe('S');
    expect(initialen('ßa Weiß')).toBe('SW');
  });

  it('gibt ohne Namen nichts — dann zeigt der Kreis das Personen-Symbol', () => {
    expect(initialen('')).toBe('');
    expect(initialen('   ')).toBe('');
  });

  it('übergeht Leerraum und Zeichen ohne Buchstaben', () => {
    expect(initialen('  Jan \t  Schachtschabel ')).toBe('JS');
    expect(initialen('„Jan“ (Schachtschabel)')).toBe('JS');
    expect(initialen('Jan –')).toBe('J');
    expect(initialen('— · —')).toBe('');
  });
});
