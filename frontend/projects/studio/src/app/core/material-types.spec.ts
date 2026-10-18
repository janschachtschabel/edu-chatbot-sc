import { describe, expect, it } from 'vitest';

import {
  type MaterialTyp, aliaseFuer, fehlendeAliase, pruefe, vorrang,
} from './material-types';

/**
 * Materialformate (Paket 14, D1): Prüfregeln wie der Server und die Querbezüge, die die
 * Vorschau zeigt — Aliase aus `type-aliases`, Vorrang aus `persona-priorities`.
 */
const TYPEN: readonly MaterialTyp[] = [
  { id: 'arbeitsblatt', label: 'Arbeitsblatt', label_en: 'Worksheet', emoji: '📝',
    category: 'didaktisch', structure: '# Arbeitsblatt' },
  { id: 'faktenblatt', label: 'Faktenblatt', label_en: '', emoji: '📊',
    category: 'analytisch', structure: '' },
];
const ALIASE = { arbeitsblatt: 'arbeitsblatt', aufgabenblatt: 'arbeitsblatt', worksheet: 'arbeitsblatt',
  faktenblatt: 'infoblatt' };

describe('material-types (Paket 14, D1)', () => {
  it('nimmt einen gültigen neuen Typ an', () => {
    expect(pruefe(TYPEN, { ...TYPEN[0], id: 'quiz', label: 'Quiz' }, null)).toEqual([]);
  });

  it('verlangt eine Kennung aus a–z, Ziffern und Unterstrich', () => {
    expect(pruefe(TYPEN, { ...TYPEN[0], id: 'Quiz-Neu' }, null)).toContain('id.format');
    expect(pruefe(TYPEN, { ...TYPEN[0], id: '' }, null)).toContain('id.format');
  });

  it('weist eine doppelte Kennung ab, nicht aber den eigenen Eintrag beim Bearbeiten', () => {
    expect(pruefe(TYPEN, { ...TYPEN[1], id: 'arbeitsblatt' }, null)).toContain('id.doppelt');
    expect(pruefe(TYPEN, TYPEN[0], 'arbeitsblatt')).toEqual([]);
  });

  it('verlangt einen Namen und eine bekannte Kategorie', () => {
    const fehler = pruefe(TYPEN, { ...TYPEN[0], id: 'x', label: '  ', category: 'kreativ' }, null);
    expect(fehler).toEqual(expect.arrayContaining(['label.leer', 'kategorie']));
  });

  it('listet die Aliase eines Typs, sortiert', () => {
    expect(aliaseFuer('arbeitsblatt', ALIASE)).toEqual(['arbeitsblatt', 'aufgabenblatt', 'worksheet']);
  });

  it('meldet Chip-Texte ohne passenden Alias — sie fielen still auf „auto“', () => {
    expect(fehlendeAliase(TYPEN[0], ALIASE)).toEqual([]);
    // „Faktenblatt“ zeigt auf einen anderen Typ — das zählt als fehlend.
    expect(fehlendeAliase(TYPEN[1], ALIASE)).toEqual(['Faktenblatt']);
    expect(fehlendeAliase({ ...TYPEN[0], label: ' Arbeitsblatt ' }, ALIASE)).toEqual([]);
  });

  it('sagt, für wen ein Typ Vorrang hat', () => {
    expect(vorrang(TYPEN[1], ['P-ENT', 'P-RED'])).toEqual({ fall: 'nur', personas: ['P-ENT', 'P-RED'] });
    expect(vorrang(TYPEN[0], ['P-ENT'])).toEqual({ fall: 'ausser', personas: ['P-ENT'] });
  });

  it('ohne analytische Zielgruppen steht ein analytischer Typ für niemanden vorn (Review #9)', () => {
    expect(vorrang(TYPEN[1], [])).toEqual({ fall: 'keine', personas: [] });
    expect(vorrang(TYPEN[0], [])).toEqual({ fall: 'alle', personas: [] });
  });
});
