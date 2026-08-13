import { describe, expect, it } from 'vitest';

import { AREA_SCHEMAS } from './area-schemas.fixture';
import { formSections } from './form-sections';
import type { JsonSchema } from './json-schema';
import { pickFields } from './pick-fields';
import { rootField } from './schema-to-fields';

/** Abschnitts-Beschriftungen eines Schemas, in Reihenfolge. */
function labels(schema: JsonSchema): string[] {
  return formSections(rootField(schema)).map((s) => s.key);
}

describe('formSections — der Schnitt', () => {
  it('gibt jedem Block einen eigenen Abschnitt', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        a: { type: 'object', properties: { x: { type: 'string' } } },
        b: { type: 'object', properties: { y: { type: 'string' } } },
      },
    };
    expect(labels(schema)).toEqual(['a', 'b']);
  });

  it('sammelt die einfachen Felder in EINEN führenden Abschnitt', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        eins: { type: 'string' },
        block_a: { type: 'object', properties: { x: { type: 'string' } } },
        zwei: { type: 'boolean' },
        block_b: { type: 'object', properties: { y: { type: 'string' } } },
      },
    };
    // Der Sammel-Abschnitt trägt keinen Config-Schlüssel — die Ansicht setzt
    // dort ihre eigene Beschriftung ein.
    expect(labels(schema)).toEqual(['', 'block_a', 'block_b']);
    const [sammel] = formSections(rootField(schema));
    expect((sammel.field.children ?? []).map((c) => c.key)).toEqual(['eins', 'zwei']);
  });

  it('steigt durch eine einzelne Hülle hindurch', () => {
    // Die meisten Bereiche packen alles in einen Block (`display_rules:`).
    // Ohne diesen Schritt gäbe es genau einen Abschnitt — nutzlos.
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        display_rules: {
          type: 'object',
          properties: {
            gruppe_a: { type: 'object', properties: { x: { type: 'string' } } },
            gruppe_b: { type: 'object', properties: { y: { type: 'string' } } },
          },
        },
      },
    };
    expect(labels(schema)).toEqual(['gruppe_a', 'gruppe_b']);
  });

  it('lässt die Hülle nicht in jedem Abschnitt mitlaufen', () => {
    // Sonst stünde über JEDEM Abschnitt derselbe Name „display_rules", plus
    // eine Einrückung, die nichts gliedert. Ein Abschnitt beginnt deshalb
    // HINTER der Hülle; `basePath` sagt, wo im Dokument er sitzt.
    const [erster] = formSections(rootField(AREA_SCHEMAS['01-base/display-rules']));
    expect(erster.basePath).toEqual(['display_rules']);
    expect(erster.field.label).toBe('');
    expect((erster.field.children ?? []).map((c) => c.key)).not.toContain('display_rules');
  });

  it('bleibt ohne Hülle an der Wurzel', () => {
    const sections = formSections(rootField(AREA_SCHEMAS['01-base/safety-config']));
    expect(sections.map((s) => s.basePath)).toEqual(sections.map(() => []));
  });

  it('vergibt auch neben einem Feld namens „basics" eindeutige Kennungen', () => {
    // Die Kennung ist die `track`-Grundlage — zwei gleiche werfen beim Zeichnen.
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        einfach: { type: 'string' },
        basics: { type: 'object', properties: { x: { type: 'string' } } },
        weiteres: { type: 'object', properties: { y: { type: 'string' } } },
      },
    };
    const ids = formSections(rootField(schema)).map((s) => s.id);
    expect(new Set(ids).size, 'zwei Abschnitte mit derselben Kennung').toBe(ids.length);
  });

  it('gliedert gar nicht, wenn dabei weniger als zwei Abschnitte herauskämen', () => {
    // Ein einziges Aufklapp-Element um das ganze Formular ist nur ein Klick mehr.
    const nurSkalare: JsonSchema = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' } },
    };
    expect(formSections(rootField(nurSkalare))).toEqual([]);

    const einBlock: JsonSchema = {
      type: 'object',
      properties: { nur_einer: { type: 'object', properties: { x: { type: 'string' } } } },
    };
    expect(formSections(rootField(einBlock))).toEqual([]);
  });

  it('verliert kein Feld — die Abschnitte zusammen sind das ganze Formular', () => {
    // Die tragende Zusage. Ein Schnitt, der etwas verschluckt, wäre schlimmer
    // als die lange Wand: das Feld sähe aus, als gäbe es es nicht mehr.
    // Geprüft ohne die Gruppierungs-Regel nachzubauen: alle Pfade zusammen an
    // `pickFields` gereicht müssen wieder den vollen Baum ergeben.
    for (const area of Object.keys(AREA_SCHEMAS)) {
      const root = rootField(AREA_SCHEMAS[area]);
      const sections = formSections(root);
      if (sections.length === 0) continue;

      const alle = sections.flatMap((s) => s.paths);
      expect(new Set(alle).size, `${area}: ein Pfad in zwei Abschnitten`).toBe(alle.length);
      expect(pickFields(root, new Set(alle)), `${area}: Feld fehlt`).toEqual(root);
    }
  });
});

describe('formSections — an den echten Bereichen', () => {
  it('zerlegt „Identität & Schutz" in Sammel-Abschnitt plus Blöcke', () => {
    const namen = labels(AREA_SCHEMAS['01-base/safety-config']);
    expect(namen[0]).toBe(''); // security_level, crisis_pattern, threat_pattern
    expect(namen).toContain('escalation');
    expect(namen).toContain('rate_limits');
    expect(namen).toContain('logging');
    expect(namen.length).toBeGreaterThanOrEqual(6);
  });

  it('zerlegt die Anzeige-Regeln durch ihre Hülle hindurch', () => {
    const namen = labels(AREA_SCHEMAS['01-base/display-rules']);
    expect(namen).toContain('inline_documents');
    expect(namen).toContain('quick_replies');
    expect(namen).not.toContain('display_rules'); // die Hülle selbst nicht
  });

  it('lässt kurze Bereiche in Ruhe', () => {
    // `01-base/widget-modes` hat zwei Zahlen in einer Hülle — dafür braucht es
    // keine Gliederung.
    expect(formSections(rootField(AREA_SCHEMAS['01-base/widget-modes']))).toEqual([]);
  });
});
