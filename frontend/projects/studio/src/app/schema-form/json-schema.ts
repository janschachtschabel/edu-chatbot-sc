/**
 * The JSON-Schema subset the config areas actually emit.
 *
 * Measured 2026-07-25 over all 32 distinct area models: only `$defs`/`$ref`
 * (26 models), `anyOf` (11, always a `X | None` union), arrays, objects and
 * `additionalProperties` occur. No `enum`, `oneOf`, `allOf`, `const`,
 * `discriminator`, `patternProperties`, `prefixItems` or `if/then` — which is
 * why this project renders schemas itself instead of pulling in a general
 * JSON-Schema form library (9-3).
 *
 * Re-measured 2026-08-11 with `01-base/pricing` (K3): `minimum` joins the set,
 * emitted by that area's `ge=0` price fields. The mapper does not read it — the
 * server rejects a negative price on PUT, which is where that check belongs —
 * so it is listed here only to keep the type honest about what is served.
 *
 * Fields outside this set are simply absent from the type; the mapper falls
 * back to a `raw` field rather than guessing, so an unforeseen shape degrades
 * to "edit it in the YAML tab" instead of silently dropping data.
 */
export interface JsonSchema {
  readonly $ref?: string;
  readonly $defs?: Readonly<Record<string, JsonSchema>>;
  readonly type?: string;
  readonly title?: string;
  readonly description?: string;
  readonly default?: unknown;
  readonly properties?: Readonly<Record<string, JsonSchema>>;
  readonly required?: readonly string[];
  readonly items?: JsonSchema;
  readonly additionalProperties?: JsonSchema | boolean;
  readonly anyOf?: readonly JsonSchema[];
  readonly minimum?: number;
}
