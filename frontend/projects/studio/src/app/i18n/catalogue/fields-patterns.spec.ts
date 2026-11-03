import { describe, expect, it } from 'vitest';

import { FIELDS_PATTERNS } from './fields-patterns';

/**
 * Review U1-d2 (2026-11-03): Das Feld `tools` schlägt seit U1-d2 auch `ui_entscheidung` vor.
 * Der Hilfetext nannte nur WLO-Werkzeuge — die drei Bedingungen des Moduls standen nirgends:
 * Das Widget muss es melden, `mcp` muss in den Quellen stehen, und die Degradation nimmt es weg.
 */
describe('Hilfetexte Muster', () => {
  const de = FIELDS_PATTERNS.de as Record<string, string>;
  const en = FIELDS_PATTERNS.en as Record<string, string>;

  it('nennt im Feld „tools“ die Bedingungen der UI-Module (de)', () => {
    const hint = de['feld.PatternFrontmatter.tools.hint'];
    expect(hint).toContain('ui_entscheidung');
    expect(hint).toContain('Widget');
    expect(hint).toContain('mcp');
    expect(hint).toContain('Pflichtangabe');
  });

  it('nennt im Feld „tools“ die Bedingungen der UI-Module (en)', () => {
    const hint = en['feld.PatternFrontmatter.tools.hint'];
    expect(hint).toContain('ui_entscheidung');
    expect(hint).toContain('widget');
    expect(hint).toContain('mcp');
    expect(hint).toContain('required detail');
  });
});
