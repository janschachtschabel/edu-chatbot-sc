import { describe, expect, it } from 'vitest';

import { AREA_SCHEMAS } from '../schema-form/area-schemas.fixture';
import { rootField, type SchemaField } from '../schema-form/schema-to-fields';
import { patternFieldTabs } from './pattern-field-tabs';

const PATTERN_ROOT = rootField(AREA_SCHEMAS['03-patterns']);

describe('patternFieldTabs', () => {
  it('hat ALTs fünf Reiter in ALTs Reihenfolge und Beschriftung', () => {
    // PatternEditor.tsx:400-406 — identity/output/tools/slots/instructions.
    expect(patternFieldTabs(PATTERN_ROOT).map((t) => t.label)).toEqual([
      'Identität', 'Antwort-Form', 'Tools & Wissen', 'Slots & Degradation', 'Anweisungen',
    ]);
  });

  it('gibt jedem Feld des echten Schemas genau einen Reiter', () => {
    // Die Prüfung, die ALT nicht hatte: dort blieben `short_purpose`,
    // `output_mode` und `card_text_link_required` in KEINEM Reiter und waren
    // damit unerreichbar. Ein Reiter-Schnitt darf nichts verschlucken.
    const assigned = patternFieldTabs(PATTERN_ROOT).flatMap((t) => t.paths);
    const expected = [
      'frontmatter.id', 'frontmatter.label', 'frontmatter.short_purpose', 'frontmatter.priority',
      'frontmatter.default_tone', 'frontmatter.default_length', 'frontmatter.response_type',
      'frontmatter.core_rule', 'frontmatter.when_to_use', 'frontmatter.when_not_to_use',
      'frontmatter.trigger_phrases', 'frontmatter.discriminators', 'frontmatter.output_mode',
      'frontmatter.sources', 'frontmatter.rag_areas', 'frontmatter.tools',
      'frontmatter.precondition_slots', 'frontmatter.card_text_link_required',
      'frontmatter.quick_replies_mode', 'frontmatter.forbidden_phrases',
      'frontmatter.anti_patterns', 'body',
    ];
    expect([...assigned].sort()).toEqual([...expected].sort());
    expect(new Set(assigned).size).toBe(assigned.length);
  });

  it('fängt ein Feld auf, das die Tabelle nicht kennt', () => {
    // Ein neues Schema-Feld darf nicht unsichtbar werden — dieselbe Regel wie
    // beim „Weitere"-Korb der Material-Typen (reference-catalogs.ts).
    const withNew: SchemaField = {
      ...PATTERN_ROOT,
      children: [
        ...(PATTERN_ROOT.children ?? []).map((child) =>
          child.key === 'frontmatter'
            ? {
                ...child,
                children: [
                  ...(child.children ?? []),
                  {
                    key: 'brandneu', label: 'brandneu', kind: 'text' as const,
                    required: false, nullable: false, blank: '',
                  },
                ],
              }
            : child,
        ),
      ],
    };
    const tabs = patternFieldTabs(withNew);
    const extra = tabs.find((t) => t.label === 'Weitere');
    expect(extra?.paths).toEqual(['frontmatter.brandneu']);
  });

  it('zeigt „Weitere" nicht, wenn alles zugeordnet ist', () => {
    expect(patternFieldTabs(PATTERN_ROOT).map((t) => t.label)).not.toContain('Weitere');
  });

  it('lässt einen Reiter weg, dessen Felder das Schema nicht hat', () => {
    // Ein leerer Reiter behauptet Inhalt, den es nicht gibt.
    const onlyBody: SchemaField = {
      ...PATTERN_ROOT,
      children: (PATTERN_ROOT.children ?? []).filter((child) => child.key === 'body'),
    };
    expect(patternFieldTabs(onlyBody).map((t) => t.label)).toEqual(['Anweisungen']);
  });
});
