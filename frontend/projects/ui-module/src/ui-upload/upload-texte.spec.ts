import { describe, expect, it } from 'vitest';

import { groesse, texte } from './upload-texte';

describe('Texte ui_upload (U3-1a)', () => {
  it('jede Warnung und jede Rolle gibt es auf Deutsch und Englisch, nicht gleich', () => {
    const de = texte('de');
    const en = texte('en');
    expect(Object.keys(en.warnung).sort()).toEqual(Object.keys(de.warnung).sort());
    for (const k of Object.keys(de.warnung) as (keyof typeof de.warnung)[]) {
      expect(de.warnung[k](3)).not.toBe(en.warnung[k](3));
    }
    expect(Object.keys(en.rolle).sort()).toEqual(Object.keys(de.rolle).sort());
  });

  it('Einzahl und Mehrzahl, Zahlen je Sprache formatiert', () => {
    expect(texte('de').dateien(1)).toBe('1 Datei');
    expect(texte('de').dateien(1234)).toBe('1.234 Dateien');
    expect(texte('en').dateien(1234)).toBe('1,234 files');
    expect(texte('en').ordner(1)).toBe('1 folder');
  });

  it('Größen in kB und MB mit einer Nachkommastelle', () => {
    expect(groesse('de', 1_500_000)).toBe('1,5 MB');
    expect(groesse('en', 1_500_000)).toBe('1.5 MB');
    expect(groesse('de', 12_300)).toBe('12 kB');
    expect(groesse('de', 10)).toBe('1 kB');
  });
});
