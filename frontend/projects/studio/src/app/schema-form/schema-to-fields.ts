/**
 * JSON Schema -> renderable field tree (9-3b).
 *
 * Pure and data-free: it describes *what* a document may contain, never what
 * one does. The renderer walks the tree and binds each field to a path in the
 * document it was handed, which is what keeps unpinned config (357 paths in
 * the ALT tree) alive across a save — the form edits a document, it does not
 * rebuild one.
 *
 * Anything the measured schema subset (see json-schema.ts) does not cover maps
 * to `raw` rather than to a guess. That is not a dead end: 13 real fields land
 * there because their model declares `dict[str, Any]` / `Any` (policy rules,
 * classify overrides, tour steps …), so `raw` is rendered as a JSON text area.
 * Free-form config stays editable; it just gets no typed controls.
 */
import type { JsonSchema } from './json-schema';

export type FieldKind =
  | 'text'
  | 'select'
  | 'multiline'
  | 'number'
  | 'integer'
  | 'boolean'
  | 'group'
  | 'list'
  | 'map'
  | 'raw';

export interface SchemaField {
  /** Config key. Empty for the element template of a list or map. */
  readonly key: string;
  /** Shown to the editor — the raw key, so form and YAML tab name the same thing. */
  readonly label: string;
  readonly kind: FieldKind;
  readonly required: boolean;
  /** The schema allowed `null` (a pydantic `X | None`). */
  readonly nullable: boolean;
  readonly description?: string;
  /** `group` only. */
  readonly children?: readonly SchemaField[];
  /** `list` and `map` only: the template for one element. */
  readonly item?: SchemaField;
  /** `select` only: the whole allowed vocabulary, in schema order. */
  readonly choices?: readonly string[];
  /** `text` with a live suggestion list — the catalog name to look up. */
  readonly catalog?: string;
  /** Value for a fresh entry — used when adding a list/map element. */
  readonly blank: unknown;
}

/** Stops a `$ref` cycle; the deepest real chain in the registry is 2 hops. */
const MAX_REF_HOPS = 10;

/**
 * Schlüssel, die Fließtext tragen und deshalb eine Textfläche bekommen.
 *
 * **Gemessen, nicht geraten** (Nutzer-Befund 2026-08-13: `structure` in den
 * Material-Formaten stand in einer fortlaufenden Zeile). Aufgenommen ist jeder
 * Schlüssel, unter dem im ausgelieferten Seed-Baum ein String über 120 Zeichen
 * steht — `structure` bis 729, `description` bis 671, `pattern` bis 1013.
 * Neu messen:
 *
 * ```
 * cd backend && python -c "import pathlib,yaml,collections; ..."   # siehe §9 im Plan
 * ```
 *
 * Nach dem SCHLÜSSELNAMEN und nicht nach dem Wert: sonst wechselte ein Feld
 * beim Tippen die Bauart und verlöre den Fokus. Ein zu großzügiger Treffer
 * kostet nur Höhe — ein verpasster kostet die Bearbeitbarkeit.
 */
const MULTILINE_KEYS = new Set([
  'body', 'bot_directive', 'brand_pattern', 'curate_prompt', 'description',
  'greeting', 'greeting_en', 'intent_conflict_rule', 'intro', 'intro_en',
  'message', 'pattern', 'phrase', 'rationale', 'rule', 'rules', 'solutions',
  'solutions_en', 'structure', 'text', 'text_en', 'unsure_text',
  'unsure_text_en',
]);

/** Describe a whole area document. The root is a `group` for every area but
 * `05-knowledge/rag-config`, whose model is a `RootModel[dict[str, …]]`. */
export function rootField(schema: JsonSchema): SchemaField {
  return fieldFor('', schema, schema, false);
}

function fieldFor(
  key: string,
  raw: JsonSchema,
  root: JsonSchema,
  required: boolean,
): SchemaField {
  const node = resolveNode(raw, root);
  const nullable = isNullable(raw, root);
  const base = {
    key,
    label: key,
    required,
    nullable,
    description: raw.description ?? node?.description,
  };
  const blank = (fallback: unknown): unknown => {
    if (raw.default !== undefined) return raw.default;
    if (node?.default !== undefined) return node.default;
    return nullable ? null : fallback;
  };

  if (!node) return { ...base, kind: 'raw', blank: blank(null) };

  switch (node.type) {
    case 'string':
      return { ...base, ...stringKind(key, node), blank: blank('') };
    case 'integer':
      return { ...base, kind: 'integer', blank: blank(0) };
    case 'number':
      return { ...base, kind: 'number', blank: blank(0) };
    case 'boolean':
      return { ...base, kind: 'boolean', blank: blank(false) };
    case 'array': {
      if (!node.items) return { ...base, kind: 'raw', blank: blank(null) };
      return {
        ...base,
        kind: 'list',
        item: inheritMultiline(fieldFor('', node.items, root, false), key),
        blank: blank([]),
      };
    }
    case 'object':
      return objectField(base, node, root, blank);
    default:
      return { ...base, kind: 'raw', blank: blank(null) };
  }
}

type FieldBase = Pick<SchemaField, 'key' | 'label' | 'required' | 'nullable' | 'description'>;

/**
 * Which control a string gets (S3). Read from the RESOLVED node, not from the
 * raw property: for a `str | None` field pydantic puts the annotation into the
 * non-null `anyOf` branch, not onto the property itself.
 *
 * `enum` and `x-choices` both mean "closed vocabulary" and both become a
 * select. They differ only in what a save does: `enum` comes from a `Literal`
 * and the server rejects anything else, `x-choices` does not (see
 * `config_models/_shared.py`). `enum` first — where the model really enforces
 * a list, that list is the authority.
 *
 * An empty list stays a text field: a select without options could not be
 * operated, and free text is the better fallback.
 */
function stringKind(
  key: string,
  node: JsonSchema,
): Pick<SchemaField, 'kind' | 'choices' | 'catalog'> {
  const choices = node.enum?.length ? node.enum : node['x-choices'];
  if (choices?.length) return { kind: 'select', choices };
  const kind = MULTILINE_KEYS.has(key) ? 'multiline' : 'text';
  const catalog = node['x-catalog'];
  return catalog ? { kind, catalog } : { kind };
}

/**
 * Ein Listen-Element erbt die Textflächen-Entscheidung vom Listen-Schlüssel.
 *
 * Das Element selbst hat keinen Schlüssel (`key: ''`) — bei `rules:`, einer
 * Liste langer Sätze, könnte es die Entscheidung sonst gar nicht treffen.
 */
function inheritMultiline(item: SchemaField, listKey: string): SchemaField {
  return item.kind === 'text' && MULTILINE_KEYS.has(listKey)
    ? { ...item, kind: 'multiline' }
    : item;
}

function objectField(
  base: FieldBase,
  node: JsonSchema,
  root: JsonSchema,
  blank: (fallback: unknown) => unknown,
): SchemaField {
  if (node.properties) {
    const required = new Set(node.required ?? []);
    const children = Object.entries(node.properties).map(([childKey, childSchema]) =>
      fieldFor(childKey, childSchema, root, required.has(childKey)),
    );
    const fromChildren = Object.fromEntries(children.map((c) => [c.key, c.blank]));
    return { ...base, kind: 'group', children, blank: blank(fromChildren) };
  }
  // `additionalProperties` as a *schema* is a typed map (RootModel[dict[str, X]]);
  // as `true` it is a free-form bag with nothing to render.
  const extra = node.additionalProperties;
  if (extra && typeof extra === 'object') {
    return { ...base, kind: 'map', item: fieldFor('', extra, root, false), blank: blank({}) };
  }
  return { ...base, kind: 'raw', blank: blank(null) };
}

/** Follow `$ref`s and strip a `| None` union. `null` = nothing renderable. */
function resolveNode(node: JsonSchema, root: JsonSchema): JsonSchema | null {
  const direct = followRefs(node, root);
  if (!direct?.anyOf) return direct;
  const options = direct.anyOf.filter((option) => option.type !== 'null');
  // more than one non-null option (real case: `str | float | None`) has no
  // single widget — better raw than a control that silently retypes the value
  return options.length === 1 ? followRefs(options[0], root) : null;
}

function isNullable(node: JsonSchema, root: JsonSchema): boolean {
  const direct = followRefs(node, root);
  return (direct?.anyOf ?? []).some((option) => option.type === 'null');
}

function followRefs(node: JsonSchema, root: JsonSchema): JsonSchema | null {
  let current: JsonSchema = node;
  for (let hop = 0; current.$ref !== undefined; hop += 1) {
    if (hop >= MAX_REF_HOPS) return null;
    const target = dereference(current.$ref, root);
    if (!target) return null;
    current = target;
  }
  return current;
}

function dereference(ref: string, root: JsonSchema): JsonSchema | null {
  const [uri, pointer] = ref.split('#/');
  if (uri || !pointer) return null; // remote refs do not occur and are not fetched
  let node: unknown = root;
  for (const raw of pointer.split('/')) {
    const segment = raw.replace(/~1/g, '/').replace(/~0/g, '~');
    if (typeof node !== 'object' || node === null) return null;
    node = (node as Record<string, unknown>)[segment];
  }
  return typeof node === 'object' && node !== null ? (node as JsonSchema) : null;
}
