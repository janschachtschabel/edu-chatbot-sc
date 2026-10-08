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

/** Paths of every text area in a real area's form. */
function multilinePaths(area: string): string[] {
  const paths: string[] = [];
  walk(rootField(AREA_SCHEMAS[area]), (f, path) => {
    if (f.kind === 'multiline') paths.push(path);
  });
  return paths;
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

  it('gibt Fließtext eine Textfläche, wenn das Modell es sagt — nicht nach dem Namen (ST-2f)', () => {
    // Bis ST-2f entschied eine Namensliste: `description` war überall eine
    // Fläche, auch ein kurzes; eine Muster-Kennung namens `pattern` ebenso.
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        structure: { type: 'string', 'x-widget': 'textarea' },
        description: { type: 'string' }, // der Name allein entscheidet nichts mehr
        rolle: { anyOf: [{ type: 'string' }, { type: 'null' }], 'x-widget': 'textarea' },
      },
    };
    const root = rootField(schema);
    expect(child(root, 'structure').kind).toBe('multiline');
    expect(child(root, 'description').kind).toBe('text');
    expect(child(root, 'rolle').kind).toBe('multiline'); // Hinweis an der Eigenschaft
  });

  it('nimmt den Hinweis eines Listen-Elements vom Element selbst', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        rules: { type: 'array', items: { type: 'string', 'x-widget': 'textarea' } },
        tags: { type: 'array', items: { type: 'string' } },
      },
    };
    const root = rootField(schema);
    expect(child(root, 'rules').item?.kind).toBe('multiline');
    expect(child(root, 'tags').item?.kind).toBe('text');
  });

  it('trifft an den echten Bereichen die Fließtexte des Seeds', () => {
    // Der Backend-Wächter `test_config_textarea_hints.py` hält die Hinweise
    // aktuell; hier nur die Stichprobe, dass sie im Studio ankommen.
    expect(multilinePaths('01-base/base-persona')).toContain('body');
    expect(multilinePaths('03-patterns')).toEqual(
      expect.arrayContaining(['frontmatter.core_rule', 'frontmatter.when_to_use[]', 'body']),
    );
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
    // S1: `mode` ist seit dem 18.08.2026 eine Auswahl, kein Textfeld — zwei
    // Werte, und ein Tippfehler nahm den Bereich still aus der Nutzung.
    expect(child(root.item!, 'mode').kind).toBe('select');
    expect(child(root.item!, 'agent').kind).toBe('boolean');
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
      'eval/gold-flows:flows[].environment', // dict[str, Any] — AG-5, geprüft serverseitig
      'eval/gold-flows:flows[].turns[].expect', // dict[str, Any]
    ]);
  });

  it('gibt den mehrzeiligen Musterfeldern eine Textfläche (SF-2)', () => {
    // 15 von 20 Kernregeln im Seed sind mehrzeilig, M18 hat 1 072 Zeichen in
    // 20 Zeilen. Die Messung von 2026-08-13 las nur `*.yaml` und sah die
    // Frontmatter der Muster (`*.md`) nie.
    expect(multilinePaths('03-patterns')).toEqual(
      expect.arrayContaining([
        'frontmatter.core_rule',
        'frontmatter.short_purpose',
        'frontmatter.when_to_use[]',
        'frontmatter.when_not_to_use[]',
        'frontmatter.discriminators[].example',
      ]),
    );
  });

  it('gibt der Rolle des Agenten eine Textfläche (AG-3)', () => {
    // Ihr Vorgabetext hat drei Absätze und steht im Modell, nicht im Seed —
    // die Messung über den Seed-Baum sieht ihn deshalb nicht.
    expect(multilinePaths('01-base/engine')).toContain('agent_rolle.rolle');
  });

  it('gibt dem Krisentext eine Textfläche (D-14)', () => {
    // Frei im Studio gepflegt, Vorgabe im Modell — wie die Rolle des Agenten.
    expect(multilinePaths('01-base/safety-config')).toEqual(
      expect.arrayContaining(['crisis_message', 'crisis_message_en']),
    );
  });

  it('gibt jedem Feld eine Textfläche, dessen Seed-Wert Zeilenumbrüche trägt', () => {
    // Umbrüche gehen nicht nur in langen Texten verloren: die Rate-Limit-Meldung
    // und zwei Tour-Texte sind kurz, im Seed aber als `|`-Block mehrzeilig.
    expect(multilinePaths('01-base/safety-config')).toEqual(
      expect.arrayContaining(['rate_limits.blocked_message', 'rate_limits.blocked_message_en']),
    );
    expect(multilinePaths('01-base/website-tour')).toEqual(
      expect.arrayContaining([
        'website_tour.nudge',
        'website_tour.nudge_en',
        'website_tour.explore',
        'website_tour.explore_en',
      ]),
    );
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
    // Der Maschinen-Umschalter — über `enum`, nicht über `x-choices`. Seit
    // K1-1 (2026-09-27) wieder ZWEI Werte: der Hybrid ist entfernt, ein
    // gespeichertes `hybrid` liest das Backend als `agent`. Die Fixture hält
    // `test_area_schema_fixture.py` aktuell.
    expect(treffer).toContain('01-base/engine:mode → [pattern|agent]');
    // S1: der RAG-Modus war ein leeres Textfeld — ein Tippfehler nahm den
    // Bereich still aus der Nutzung.
    expect(treffer).toContain('05-knowledge/rag-config:[].mode → [always|on-demand]');
    // Die Kontext-Aktion: `preflight` verzweigt auf genau diese vier Namen,
    // alles andere faellt still durch. `str | None` — der Mapper holt die
    // Auszeichnung aus dem anyOf-Zweig (siehe `resolveNode`).
    expect(treffer).toContain(
      '01-base/context-actions:context_actions.pills[][].action → [browse_collection|curate_collection|generate_learning_path|show_content_text]',
    );
  });
});

describe('rootField — Grenzen aus dem Schema (ST-2c)', () => {
  it('übernimmt minimum und maximum an Zahlfeldern', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { n: { type: 'integer', minimum: 70, maximum: 100 } },
    };
    const n = child(rootField(schema), 'n');
    expect([n.minimum, n.maximum]).toEqual([70, 100]);
  });

  it('liest die Grenze auch hinter „| None" aus dem Nicht-null-Zweig', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: {
        n: { anyOf: [{ type: 'number', minimum: -0.3, maximum: 0.3 }, { type: 'null' }] },
      },
    };
    const n = child(rootField(schema), 'n');
    expect([n.minimum, n.maximum]).toEqual([-0.3, 0.3]);
  });

  it('trägt am echten Bereich die Grenzen der Lader-Kappung', () => {
    const regeln = rootField(AREA_SCHEMAS['01-base/display-rules']);
    const schrift = child(child(child(regeln, 'display_rules'), 'inline_documents'), 'font_size_percent');
    expect([schrift.minimum, schrift.maximum]).toEqual([70, 100]);
  });
});

describe('rootField — Schieberegler (ST-2h)', () => {
  it('macht ein begrenztes Zahlfeld mit Hinweis zum Regler, samt Schritt und Schwellen', () => {
    const ton = rootField(AREA_SCHEMAS['01-base/tone-modifiers']);
    const bias = child(child(ton, 'default_modifier'), 'length_bias');
    expect(bias.widget).toBe('slider');
    expect([bias.minimum, bias.maximum, bias.step]).toEqual([-0.3, 0.3, 0.05]);
    expect(bias.thresholds).toEqual([-0.15, 0.15]);
  });

  it('liest den Hinweis auch an einem Feld mit „| None"', () => {
    // pydantic legt `json_schema_extra` an die Eigenschaft, die Grenzen in
    // den Nicht-null-Zweig — beides muss ankommen
    const persona = rootField(AREA_SCHEMAS['04-personas']);
    const bias = child(child(persona, 'frontmatter'), 'length_bias');
    expect([bias.widget, bias.minimum, bias.maximum]).toEqual(['slider', -0.3, 0.3]);
  });

  it('bleibt ohne Grenzen ein Zahlfeld — ein Regler braucht beide Enden', () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { n: { type: 'number', 'x-widget': 'slider', minimum: 0 } },
    };
    expect(child(rootField(schema), 'n').widget).toBeUndefined();
  });
});

describe('rootField — Katalog-Schlüssel der Feldtexte (ST-1)', () => {
  it('gibt jedem Objektfeld den Schlüssel seines Modells', () => {
    const schema: JsonSchema = {
      title: 'WelcomeArea',
      type: 'object',
      properties: { greeting: { type: 'string' }, inner: { $ref: '#/$defs/Inner' } },
      $defs: { Inner: { title: 'Inner', type: 'object', properties: { x: { type: 'integer' } } } },
    };
    const root = rootField(schema);
    expect(root.textKey).toBeUndefined();
    expect(child(root, 'greeting').textKey).toBe('feld.WelcomeArea.greeting');
    expect(child(root, 'inner').textKey).toBe('feld.WelcomeArea.inner');
    expect(child(child(root, 'inner'), 'x').textKey).toBe('feld.Inner.x');
  });

  it('lässt Listen- und Map-Elemente ohne Schlüssel — sie heißen nach ihrer Liste', () => {
    const schema: JsonSchema = {
      title: 'A',
      type: 'object',
      properties: {
        rows: { type: 'array', items: { $ref: '#/$defs/Row' } },
        byId: { type: 'object', additionalProperties: { $ref: '#/$defs/Row' } },
      },
      $defs: { Row: { title: 'Row', type: 'object', properties: { id: { type: 'string' } } } },
    };
    const root = rootField(schema);
    const rows = child(root, 'rows');
    expect(rows.item?.textKey).toBeUndefined();
    expect(child(rows.item!, 'id').textKey).toBe('feld.Row.id');
    expect(child(root, 'byId').item?.textKey).toBeUndefined();
  });

  it('vergibt keinen Schlüssel, wenn das Objekt kein Modell nennt', () => {
    const schema: JsonSchema = { type: 'object', properties: { v: { type: 'string' } } };
    expect(child(rootField(schema), 'v').textKey).toBeUndefined();
  });

  it('nennt ein Feld hinter „| None" nach dem Modell des Objekts, nicht nach dem Feld', () => {
    // pydantic setzt auch an Eigenschaften ein `title` („Core Rule") — das ist
    // die Feldüberschrift, kein Modellname, und darf nie in den Schlüssel.
    const schema: JsonSchema = {
      title: 'Doc',
      type: 'object',
      properties: {
        meta: { anyOf: [{ $ref: '#/$defs/Meta' }, { type: 'null' }], title: 'Meta Field' },
      },
      $defs: { Meta: { title: 'Meta', type: 'object', properties: { core_rule: { type: 'string', title: 'Core Rule' } } } },
    };
    const meta = child(rootField(schema), 'meta');
    expect(meta.textKey).toBe('feld.Doc.meta');
    expect(child(meta, 'core_rule').textKey).toBe('feld.Meta.core_rule');
  });

  it('trifft die echten Muster: alle 20 teilen sich die Texte ihres Modells', () => {
    const muster = rootField(AREA_SCHEMAS['03-patterns']);
    const kernregel = child(child(muster, 'frontmatter'), 'core_rule');
    expect(kernregel.textKey).toMatch(/^feld\.[A-Za-z]+\.core_rule$/);
  });
});

describe('rootField — Vorgabe oder leer (Paket 4c, B2)', () => {
  it('trägt den Vorgabe-Hinweis an `sources` und `rag_areas`, nicht an `tools`', () => {
    // Nur dort heißt „nicht gesetzt“ etwas anderes als „leer“ (der Wächter
    // `test_config_vorgabe_hint.py` hält die Liste im Backend).
    const kopf = child(rootField(AREA_SCHEMAS['03-patterns']), 'frontmatter');
    expect(child(kopf, 'sources').vorgabe).toBe(true);
    expect(child(kopf, 'rag_areas').vorgabe).toBe(true);
    expect(child(kopf, 'tools').vorgabe).toBeUndefined();
  });
});
