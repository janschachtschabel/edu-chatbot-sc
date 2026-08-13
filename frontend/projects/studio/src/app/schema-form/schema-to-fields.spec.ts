import { describe, expect, it } from 'vitest';

import { AREA_SCHEMAS } from './area-schemas.fixture';
import type { JsonSchema } from './json-schema';
import { rootField, type SchemaField } from './schema-to-fields';

/** Walk a field tree (children + list/map item templates). */
function walk(field: SchemaField, visit: (f: SchemaField, path: string) => void, at = ''): void {
  visit(field, at);
  for (const child of field.children ?? []) {
    walk(child, visit, at ? `${at}.${child.key}` : child.key);
  }
  if (field.item) walk(field.item, visit, `${at}[]`);
}

function child(field: SchemaField, key: string): SchemaField {
  const found = (field.children ?? []).find((c) => c.key === key);
  if (!found) throw new Error(`no child "${key}" in [${(field.children ?? []).map((c) => c.key)}]`);
  return found;
}

describe('rootField — scalar kinds', () => {
  const scalars: ReadonlyArray<readonly [string, string]> = [
    ['string', 'text'],
    ['integer', 'integer'],
    ['number', 'number'],
    ['boolean', 'boolean'],
  ];

  it.each(scalars)('maps type %s to kind %s', (type, kind) => {
    const schema: JsonSchema = { type: 'object', properties: { v: { type } } };
    expect(child(rootField(schema), 'v').kind).toBe(kind);
  });

  it('renders a string named "body" as multiline', () => {
    // the only long-form strings in the registry are LayerDocArea.body and
    // PatternArea.body — a whole markdown document behind a one-line input
    const schema: JsonSchema = { type: 'object', properties: { body: { type: 'string' } } };
    expect(child(rootField(schema), 'body').kind).toBe('multiline');
  });

  it('gibt auch den anderen Fliesstext-Schlüsseln eine Textfläche', () => {
    // Nutzer 2026-08-13: `structure` (Material-Formate, bis 729 Zeichen) stand
    // in einer fortlaufenden Zeile. Gemessen wurde der ganze Seed-Baum, nicht
    // nur der eine Fall — siehe MULTILINE_KEYS.
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        structure: { type: 'string' },
        description: { type: 'string' },
        label: { type: 'string' },
      },
    };
    const root = rootField(schema);
    expect(child(root, 'structure').kind).toBe('multiline');
    expect(child(root, 'description').kind).toBe('multiline');
    expect(child(root, 'label').kind).toBe('text'); // kurze Felder bleiben kurz
  });

  it('vererbt die Textfläche an die Elemente einer Fliesstext-Liste', () => {
    // `rules:` ist eine Liste langer Sätze; das ELEMENT hat keinen eigenen
    // Schlüssel, also kann nur der Listen-Schlüssel die Entscheidung tragen.
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        rules: { type: 'array', items: { type: 'string' } },
        tags: { type: 'array', items: { type: 'string' } },
      },
    };
    const root = rootField(schema);
    expect(child(root, 'rules').item?.kind).toBe('multiline');
    expect(child(root, 'tags').item?.kind).toBe('text');
  });

  it('labels a field with its raw config key, not a prettified title', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { quick_replies: { type: 'string', title: 'Quick Replies' } },
    };
    // the YAML tab shows `quick_replies`; the form must show the same name
    expect(child(rootField(schema), 'quick_replies').label).toBe('quick_replies');
  });

  it('carries the schema description as help text', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { v: { type: 'string', description: 'Wozu das gut ist' } },
    };
    expect(child(rootField(schema), 'v').description).toBe('Wozu das gut ist');
  });

  it('marks required children', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { id: { type: 'string' }, name: { type: 'string' } },
      required: ['id'],
    };
    expect(child(rootField(schema), 'id').required).toBe(true);
    expect(child(rootField(schema), 'name').required).toBe(false);
  });
});

describe('rootField — $ref resolution', () => {
  it('resolves a local $ref into $defs', () => {
    const schema: JsonSchema = {
      // `label` und nicht `greeting`: der echte Schlüssel trägt Fließtext und
      // wäre eine Textfläche — hier geht es um die $ref-Auflösung, nicht um
      // die Feldart.
      $defs: { Block: { type: 'object', properties: { label: { type: 'string' } } } },
      type: 'object',
      properties: { welcome: { $ref: '#/$defs/Block' } },
    };
    const welcome = child(rootField(schema), 'welcome');
    expect(welcome.kind).toBe('group');
    expect(child(welcome, 'label').kind).toBe('text');
  });

  it('follows a chain of $refs', () => {
    const schema: JsonSchema = {
      $defs: { A: { $ref: '#/$defs/B' }, B: { type: 'integer' } },
      type: 'object',
      properties: { v: { $ref: '#/$defs/A' } },
    };
    expect(child(rootField(schema), 'v').kind).toBe('integer');
  });

  it('degrades a dangling $ref to raw instead of throwing', () => {
    const schema: JsonSchema = { type: 'object', properties: { v: { $ref: '#/$defs/Nope' } } };
    expect(child(rootField(schema), 'v').kind).toBe('raw');
  });

  it('terminates on a self-referential $ref', () => {
    const schema: JsonSchema = {
      $defs: { Loop: { $ref: '#/$defs/Loop' } },
      type: 'object',
      properties: { v: { $ref: '#/$defs/Loop' } },
    };
    expect(child(rootField(schema), 'v').kind).toBe('raw');
  });
});

describe('rootField — anyOf (pydantic optionals)', () => {
  it('unwraps `X | None` to X and marks it nullable', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { v: { anyOf: [{ type: 'string' }, { type: 'null' }] } },
    };
    const field = child(rootField(schema), 'v');
    expect(field.kind).toBe('text');
    expect(field.nullable).toBe(true);
  });

  it('unwraps `list[str] | None` to a list', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        v: { anyOf: [{ type: 'array', items: { type: 'string' } }, { type: 'null' }] },
      },
    };
    const field = child(rootField(schema), 'v');
    expect(field.kind).toBe('list');
    expect(field.item?.kind).toBe('text');
  });

  it('falls back to raw for a union of several non-null types', () => {
    // real shape: LayerDocFrontmatter.version is `str | float | None`
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        version: { anyOf: [{ type: 'string' }, { type: 'number' }, { type: 'null' }] },
      },
    };
    const field = child(rootField(schema), 'version');
    expect(field.kind).toBe('raw');
    expect(field.nullable).toBe(true);
  });
});

describe('rootField — containers', () => {
  it('maps an array of objects to a list with a group template', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        rules: {
          type: 'array',
          items: { type: 'object', properties: { label: { type: 'string' } } },
        },
      },
    };
    const list = child(rootField(schema), 'rules');
    expect(list.kind).toBe('list');
    // Die Vererbung der Textfläche gilt nur für Listen VON Text, nicht für
    // Listen von Objekten — das Element ist hier eine Gruppe.
    expect(list.item?.kind).toBe('group');
    expect(child(list.item!, 'label').kind).toBe('text');
  });

  it('maps a typed additionalProperties object to a map', () => {
    const schema: JsonSchema = {
      type: 'object',
      additionalProperties: { type: 'object', properties: { mode: { type: 'string' } } },
    };
    const root = rootField(schema);
    expect(root.kind).toBe('map');
    expect(child(root.item!, 'mode').kind).toBe('text');
  });

  it('maps a free-form object (additionalProperties: true) to raw', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { expect: { type: 'object', additionalProperties: true } },
    };
    expect(child(rootField(schema), 'expect').kind).toBe('raw');
  });

  it('maps a schema with no type at all to raw', () => {
    const schema: JsonSchema = { type: 'object', properties: { v: {} } };
    expect(child(rootField(schema), 'v').kind).toBe('raw');
  });
});

describe('rootField — blank values for new entries', () => {
  it('uses the schema default when there is one', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { n: { type: 'integer', default: 50 } },
    };
    expect(child(rootField(schema), 'n').blank).toBe(50);
  });

  it('falls back to the type zero when there is no default', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        s: { type: 'string' },
        n: { type: 'integer' },
        b: { type: 'boolean' },
        l: { type: 'array', items: { type: 'string' } },
      },
    };
    const root = rootField(schema);
    expect(child(root, 's').blank).toBe('');
    expect(child(root, 'n').blank).toBe(0);
    expect(child(root, 'b').blank).toBe(false);
    expect(child(root, 'l').blank).toEqual([]);
  });

  it('builds a group blank from its children', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        rules: {
          type: 'array',
          items: {
            type: 'object',
            properties: { pattern: { type: 'string' }, priority: { type: 'integer', default: 50 } },
          },
        },
      },
    };
    expect(child(rootField(schema), 'rules').item?.blank).toEqual({ pattern: '', priority: 50 });
  });

  it('uses null as the blank for a nullable field', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { v: { anyOf: [{ type: 'string' }, { type: 'null' }] } },
    };
    expect(child(rootField(schema), 'v').blank).toBeNull();
  });
});

describe('rootField — against the real area schemas', () => {
  const areas = Object.keys(AREA_SCHEMAS);

  // 32 until 2026-08-11, then `01-base/pricing` (K3 cost monitoring) — a NEW
  // area with no ALT counterpart, so the number grows rather than being wrong.
  // 34 seit 2026-08-13: `01-base/engine` (der Umschalter Muster/Agent, A0–A6
  // vom 2026-08-12) fehlte in der Fixture, weil sie danach nicht neu erzeugt
  // worden war. Diese Zahl ist deshalb kein Zierrat — sie ist das Einzige, was
  // eine veraltete Fixture überhaupt bemerkbar macht.
  // Regenerate the fixture after adding one:
  //   cd backend && uv run python scripts/export_area_schemas.py
  it('covers all 34 distinct area models', () => {
    expect(areas).toHaveLength(34);
  });

  it.each(areas)('maps %s without throwing', (area) => {
    expect(() => rootField(AREA_SCHEMAS[area])).not.toThrow();
  });

  it('renders 01-base/welcome-config as a nested group', () => {
    const welcome = child(rootField(AREA_SCHEMAS['01-base/welcome-config']), 'welcome');
    expect(welcome.kind).toBe('group');
    // C1-g1a: die englische Fassung steht als `*_en` NEBEN dem deutschen Feld
    // (Nutzer-Entscheid 2026-08-04). Das generische Formular braucht dafür
    // keine Sonderbehandlung — genau das belegt diese Zeile.
    expect((welcome.children ?? []).map((c) => c.key)).toEqual([
      'greeting',
      'quick_replies',
      'tour_reply',
      'greeting_en',
      'quick_replies_en',
      'tour_reply_en',
    ]);
    expect(child(welcome, 'quick_replies').kind).toBe('list');
    expect(child(welcome, 'quick_replies_en').kind).toBe('list');
  });

  it('renders 05-knowledge/rag-config as a map (its model is a RootModel dict)', () => {
    const root = rootField(AREA_SCHEMAS['05-knowledge/rag-config']);
    expect(root.kind).toBe('map');
    expect(child(root.item!, 'mode').kind).toBe('text');
  });

  it('pins exactly which real fields fall back to the JSON editor', () => {
    // Every entry here is a model field the area really declares as free-form
    // (`dict[str, Any]`, `list[dict[str, Any]]`, `Any`) or as a multi-type
    // union — a fidelity port of ALT's genuinely heterogeneous YAML. They stay
    // editable, as JSON text, which is what makes `raw` acceptable at all.
    //
    // The list is pinned so that adding a shape the typed controls cannot
    // render becomes a deliberate act instead of a silently degraded editor.
    const raws: string[] = [];
    for (const area of areas) {
      walk(rootField(AREA_SCHEMAS[area]), (f, path) => {
        if (f.kind === 'raw') raws.push(`${area}:${path}`);
      });
    }
    expect(raws.sort()).toEqual([
      '01-base/base-persona:frontmatter.version', // str | float | None
      '01-base/classify-overrides:pattern_disambiguators_legacy[]', // list[dict[str, Any]]
      '01-base/classify-overrides:topic_overrides', // dict[str, Any]
      '01-base/context-actions:context_actions.pills[][].params',
      '01-base/policy:rules[].effect', // dict[str, Any]
      '01-base/policy:rules[].match', // dict[str, Any]
      '01-base/website-tour:website_tour.groups[].angebote', // Any
      '01-base/website-tour:website_tour.steps', // dict[str, Any]
      '04-entities/entities:entities[].discriminators[]',
      '04-entities/entities:entities[].negative_examples[]',
      '04-entities/entities:entities[].positive_examples[]',
      '04-intents/intents:intents[].discriminators[]',
      'eval/gold-flows:flows[].turns[].expect', // dict[str, Any]
    ]);
  });
});

describe('rootField — Auswahl und Vorschlagsliste (S3)', () => {
  it('macht aus einem geschlossenen Wertevorrat ein Auswahlfeld', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { mode: { type: 'string', 'x-choices': ['off', 'smart', 'always'] } },
    };
    const feld = child(rootField(schema), 'mode');
    expect(feld.kind).toBe('select');
    expect(feld.choices).toEqual(['off', 'smart', 'always']);
  });

  it('lässt ein Katalog-Feld ein Textfeld bleiben', () => {
    // Ein Muster entsteht durch Anlegen, ein RAG-Bereich durch Einlesen — wer
    // den Namen schon kennt, muss ihn tippen dürfen, bevor er im Katalog steht.
    const schema: JsonSchema = {
      type: 'object',
      properties: { crisis_pattern: { type: 'string', 'x-catalog': 'patterns' } },
    };
    const feld = child(rootField(schema), 'crisis_pattern');
    expect(feld.kind).toBe('text');
    expect(feld.catalog).toBe('patterns');
  });

  it('liest die Auszeichnung auch hinter einem `| None`', () => {
    // `quick_replies_mode: Annotated[str, Choices(...)] | None` — pydantic legt
    // sie in den anyOf-Zweig, nicht an die Eigenschaft selbst.
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        qr: { anyOf: [{ type: 'string', 'x-choices': ['exact'] }, { type: 'null' }] },
      },
    };
    expect(child(rootField(schema), 'qr').kind).toBe('select');
  });

  it('trägt die Auszeichnung am Listeneintrag, nicht an der Liste', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        rag_areas: { type: 'array', items: { type: 'string', 'x-catalog': 'rag_areas' } },
      },
    };
    const liste = child(rootField(schema), 'rag_areas');
    expect(liste.kind).toBe('list');
    expect(liste.catalog).toBeUndefined();
    expect(liste.item?.catalog).toBe('rag_areas');
  });

  it('macht auch aus einem `enum` ein Auswahlfeld', () => {
    // Befund 2026-08-13: `01-base/engine` deklariert `mode` seit A0–A6 als
    // `Literal["pattern","agent"]`. Der Mapper kannte `enum` nicht, also stand
    // der Umschalter Muster/Agent als Freitextfeld im Formular — obwohl der
    // Server jeden anderen Wert mit 422 abweist.
    const schema: JsonSchema = {
      type: 'object',
      properties: { mode: { type: 'string', enum: ['pattern', 'agent'] } },
    };
    const feld = child(rootField(schema), 'mode');
    expect(feld.kind).toBe('select');
    expect(feld.choices).toEqual(['pattern', 'agent']);
  });

  it('ignoriert eine leere Werteliste', () => {
    // Ein Auswahlfeld ohne Optionen wäre unbedienbar — dann lieber Freitext.
    const schema: JsonSchema = {
      type: 'object',
      properties: { v: { type: 'string', 'x-choices': [] } },
    };
    expect(child(rootField(schema), 'v').kind).toBe('text');
  });

  it('zeichnet in den ECHTEN Bereichsschemata die gemeldeten Felder aus', () => {
    // Gegen die generierte Fixture, nicht gegen erfundene Schemata: was das
    // Backend wirklich ausliefert, entscheidet.
    const treffer: string[] = [];
    for (const area of Object.keys(AREA_SCHEMAS)) {
      walk(rootField(AREA_SCHEMAS[area]), (f, path) => {
        if (f.catalog) treffer.push(`${area}:${path} → ${f.catalog}`);
        if (f.choices) treffer.push(`${area}:${path} → [${f.choices.join('|')}]`);
      });
    }
    expect(treffer).toContain('03-patterns:frontmatter.rag_areas[] → rag_areas');
    expect(treffer).toContain('03-patterns:frontmatter.tools[] → tools');
    expect(treffer).toContain('01-base/safety-config:crisis_pattern → patterns');
    expect(treffer).toContain('01-base/safety-config:escalation.mode → [off|smart|always]');
    // Der Umschalter Muster/Agent — über `enum`, nicht über `x-choices`.
    expect(treffer).toContain('01-base/engine:mode → [pattern|agent]');
  });
});
