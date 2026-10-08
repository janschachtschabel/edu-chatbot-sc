/**
 * Was das Modell über die DARSTELLUNG eines Feldes sagt (ST-2, Plan 2026-09-26
 * §9.3): Textfläche, Auswahl, Katalog, Grenzen, Regler, Katalog-Schlüssel der
 * Feldtexte und das Nachbarfeld eines Markers.
 *
 * Aus `schema-to-fields.ts` gezogen, als der Konverter die 300 Zeilen
 * überschritt: dort steht, wie der Schema-Baum durchlaufen wird, hier, wie ein
 * einzelner Knoten gelesen wird. Rein und ohne Zustand, wie der Konverter.
 */
import type { JsonSchema } from './json-schema';
import type { SchemaField } from './schema-to-fields';

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
export function stringKind(
  raw: JsonSchema,
  node: JsonSchema,
): Pick<SchemaField, 'kind' | 'choices' | 'catalog'> {
  const choices = node.enum?.length ? node.enum : node['x-choices'];
  if (choices?.length) return { kind: 'select', choices };
  const kind = textarea(raw, node) ? 'multiline' : 'text';
  const catalog = node['x-catalog'];
  return catalog ? { kind, catalog } : { kind };
}

/**
 * Fließtext bekommt eine Textfläche — wenn das MODELL es sagt (`Textarea()`,
 * ST-2f), nicht mehr nach dem Schlüsselnamen. Bis ST-2f stand hier eine
 * handgemessene Namensliste; wo die Messung fehlte, plättete ein einzeiliges
 * Feld mehrzeilige Kernregeln (SF-2), und gleichnamige kurze Felder
 * (`FewShotExample.pattern`, eine Muster-Kennung) bekamen eine Fläche. Die
 * Messung ist jetzt ein Backend-Wächter: `tests/test_config_textarea_hints.py`
 * verlangt den Hinweis an jedem langen Seed-Text und jeder langen Vorgabe.
 * Der Hinweis steht an der Eigenschaft (`raw`) oder bei `| None` im Zweig.
 */
function textarea(raw: JsonSchema, node: JsonSchema): boolean {
  return (raw['x-widget'] ?? node['x-widget']) === 'textarea';
}

/**
 * Den Katalog-Schlüssel eines Objektfelds setzen (ST-1) — und bei einer
 * Auswahl, auch der eines Listen-Elements, das Präfix ihrer Klartexte (ST-2d).
 */
export function withTextKey(field: SchemaField, textKey: string): SchemaField {
  const item = field.item?.choices ? { ...field.item, choiceKey: textKey } : field.item;
  return {
    ...field,
    textKey,
    ...(field.choices ? { choiceKey: textKey } : {}),
    // the marker is a SIBLING: same model, other field
    ...(field.marker ? { markerTextKey: textKey.replace(/[^.]+$/, field.marker) } : {}),
    ...(item !== field.item ? { item } : {}),
  };
}

/**
 * A slider (ST-2h) — only with both bounds, a slider needs two ends. pydantic
 * puts `json_schema_extra` on the PROPERTY (`raw`) but the bounds of a
 * `float | None` into the non-null branch (`node`), so both are read.
 */
export function slider(raw: JsonSchema, node: JsonSchema): Pick<SchemaField, 'widget' | 'step' | 'thresholds'> {
  const widget = raw['x-widget'] ?? node['x-widget'];
  if (widget !== 'slider' || node.minimum === undefined || node.maximum === undefined) return {};
  const step = raw['x-step'] ?? node['x-step'];
  const thresholds = raw['x-thresholds'] ?? node['x-thresholds'];
  return {
    widget: 'slider',
    ...(step !== undefined ? { step } : {}),
    ...(thresholds?.length ? { thresholds } : {}),
  };
}

/**
 * Ein Schalter, den der Code festsetzt (ST-6, `x-fixed`): das Formular zeigt,
 * was WIRKT, gesperrt — statt eines Schalters, der sich wirkungslos umlegen
 * und speichern ließe. Hinweis an der Eigenschaft oder bei `| None` im Zweig.
 */
export function fixed(raw: JsonSchema, node: JsonSchema): Pick<SchemaField, 'fixed'> {
  return (raw['x-fixed'] ?? node['x-fixed']) ? { fixed: true } : {};
}

/** Der Inhalt eines Bereichs (ST-4, `x-primary`): sein Abschnitt kommt zuerst. */
export function primary(raw: JsonSchema, node: JsonSchema | null): Pick<SchemaField, 'primary'> {
  return (raw['x-primary'] ?? node?.['x-primary']) ? { primary: true } : {};
}

/** „Nicht gesetzt“ heißt hier: es gilt die Vorgabe (Paket 4c, B2, `x-vorgabe`).
 *  Der Hinweis steht neben `anyOf` an der Eigenschaft, nicht im aufgelösten Zweig. */
export function vorgabe(raw: JsonSchema): Pick<SchemaField, 'vorgabe'> {
  return raw['x-vorgabe'] ? { vorgabe: true } : {};
}

/** The bounds of a number, read from the RESOLVED node like `stringKind`. */
export function bounds(node: JsonSchema): Pick<SchemaField, 'minimum' | 'maximum'> {
  return {
    ...(node.minimum !== undefined ? { minimum: node.minimum } : {}),
    ...(node.maximum !== undefined ? { maximum: node.maximum } : {}),
  };
}
