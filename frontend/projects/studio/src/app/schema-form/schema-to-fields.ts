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
import {
  bounds, fixed, primary, slider, stringKind, vorgabe, withTextKey,
} from './field-hints';
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
  /**
   * Katalog-Schlüssel der Feldtexte (ST-1): `feld.<Modell>.<feld>`, darunter
   * `.label` und `.hint`. Nach dem MODELL und nicht nach Bereich und Pfad:
   * vier Bereiche teilen sich `LayerDocFrontmatter`, alle Muster ein Modell —
   * so steht jede Bedeutung einmal im Katalog. Fehlt, wo es keinen Namen gibt:
   * an der Wurzel und an den Elementen einer Liste oder Map.
   */
  readonly textKey?: string;
  /**
   * `select` only (ST-2d): Präfix der Klartexte seiner Werte,
   * `<choiceKey>.wahl.<wert>`. Der eigene `textKey` — bei einem Element einer
   * Liste (`sources`) der der Liste, denn das Element hat keinen eigenen.
   */
  readonly choiceKey?: string;
  /**
   * `list` only (ST-2i): the sibling field that marks ONE of this list's
   * entries (`tour_reply` for the start chips) — rendered as a radio per row.
   * `markerTextKey` names that sibling in the catalogue, for the radio's label.
   */
  readonly marker?: string;
  readonly markerTextKey?: string;
  /** `boolean` only (ST-6): the code fixes the value (the safety log is always
   *  written) — shown locked as "fest aktiv", never editable. */
  readonly fixed?: boolean;
  /** The area's content (ST-4, `x-primary`) — its section comes first and open. */
  readonly primary?: boolean;
  /** A nullable list whose `null` means "the default applies", not "empty"
   *  (Paket 4c, B2, `x-vorgabe`) — the form shows which case holds. */
  readonly vorgabe?: boolean;
  /** `number` only (ST-2h): drawn as a slider — only with both bounds. `step`
   *  is its step; `thresholds` are where the value changes what it does (the
   *  slider names the zone the value is in). */
  readonly widget?: 'slider';
  readonly step?: number;
  readonly thresholds?: readonly number[];
  /** `integer`/`number` only (ST-2c): the schema's bounds, shown at the field and
   *  set as `min`/`max`. The server stays the authority — a PUT out of range is
   *  refused there. */
  readonly minimum?: number;
  readonly maximum?: number;
  /** Value for a fresh entry — used when adding a list/map element. */
  readonly blank: unknown;
  /** Paket 15 (A3): the schema's explicit default — what the runtime applies when the key is
   *  missing. The form shows it (marked „Vorgabe“) instead of an empty or switched-off field. */
  readonly defaultValue?: unknown;
  /** Paket 15: a sibling list's marker writes this field — it is not rendered on its own. */
  readonly markerZiel?: boolean;
  /** `group` only (Paket 15): the section heading already names it — no second legend. */
  readonly ohneLegende?: boolean;
  /** `group` only (Paket 15, Review-Runde 2): the defaults of ALL its children, by key —
   *  computed before any section or tab prunes `children`. A missing group whose shown value
   *  equals these needs no materialising: the server fills the gaps the same way. */
  readonly kinderVorgaben?: Readonly<Record<string, unknown>>;
}

/** Stops a `$ref` cycle; the deepest real chain in the registry is 2 hops. */
const MAX_REF_HOPS = 10;

/** Describe a whole area document. The root is a `group` for every area but
 * `05-knowledge/rag-config`, whose model is a `RootModel[dict[str, …]]`. */
export function rootField(schema: JsonSchema): SchemaField {
  return fieldFor('', schema, schema, false);
}

/** The default the schema states — on the property or on its resolved type. */
function explicitDefault(
  raw: JsonSchema, node: JsonSchema | null,
): { readonly defaultValue?: unknown } {
  if (raw.default !== undefined) return { defaultValue: raw.default };
  if (node?.default !== undefined) return { defaultValue: node.default };
  return {};
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
    ...primary(raw, node),
    ...vorgabe(raw),
    ...explicitDefault(raw, node),
  };
  const blank = (fallback: unknown): unknown => {
    if (raw.default !== undefined) return raw.default;
    if (node?.default !== undefined) return node.default;
    return nullable ? null : fallback;
  };

  if (!node) return { ...base, kind: 'raw', blank: blank(null) };

  switch (node.type) {
    case 'string':
      return { ...base, ...stringKind(raw, node), blank: blank('') };
    case 'integer':
      return { ...base, kind: 'integer', ...bounds(node), blank: blank(0) };
    case 'number':
      return { ...base, kind: 'number', ...bounds(node), ...slider(raw, node), blank: blank(0) };
    case 'boolean':
      return { ...base, kind: 'boolean', ...fixed(raw, node), blank: blank(false) };
    case 'array': {
      if (!node.items) return { ...base, kind: 'raw', blank: blank(null) };
      return {
        ...base,
        kind: 'list',
        item: fieldFor('', node.items, root, false),
        ...(node['x-marker'] ? { marker: node['x-marker'] } : {}),
        blank: blank([]),
      };
    }
    case 'object':
      return objectField(base, node, root, blank);
    default:
      return { ...base, kind: 'raw', blank: blank(null) };
  }
}

type FieldBase = Pick<
  SchemaField, 'key' | 'label' | 'required' | 'nullable' | 'description' | 'primary' | 'vorgabe'
>;

function objectField(
  base: FieldBase,
  node: JsonSchema,
  root: JsonSchema,
  blank: (fallback: unknown) => unknown,
): SchemaField {
  if (node.properties) {
    const required = new Set(node.required ?? []);
    // `node.title` ist der Modellname (pydantic setzt ihn an jedes Modell).
    // Das `title` einer EIGENSCHAFT („Core Rule") ist nur ihre Überschrift und
    // kommt hier nicht an: `node` ist bereits das aufgelöste Objekt.
    const roh = Object.entries(node.properties).map(([childKey, childSchema]) => {
      const child = fieldFor(childKey, childSchema, root, required.has(childKey));
      return node.title ? withTextKey(child, `feld.${node.title}.${childKey}`) : child;
    });
    // Paket 15: das Ziel eines Markers (`tour_reply`) bedienen die Radios der Liste —
    // als eigenes Feld stand derselbe Wert ein zweites Mal da.
    const ziele = new Set(roh.map((c) => c.marker).filter(Boolean));
    const children = roh.map((c) => (ziele.has(c.key) ? { ...c, markerZiel: true } : c));
    const fromChildren = Object.fromEntries(children.map((c) => [c.key, c.blank]));
    const kinderVorgaben = Object.fromEntries(
      children.filter((c) => c.defaultValue !== undefined).map((c) => [c.key, c.defaultValue]));
    return { ...base, kind: 'group', children, kinderVorgaben, blank: blank(fromChildren) };
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
