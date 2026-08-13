/**
 * The JSON-Schema subset the config areas actually emit.
 *
 * Measured 2026-07-25 over all 32 distinct area models: only `$defs`/`$ref`
 * (26 models), `anyOf` (11, always a `X | None` union), arrays, objects and
 * `additionalProperties` occur. `oneOf`, `allOf`, `const`, `discriminator`,
 * `patternProperties`, `prefixItems` and `if/then` still do not — which is why
 * this project renders schemas itself instead of pulling in a general
 * JSON-Schema form library (9-3).
 *
 * Re-measured 2026-08-11 with `01-base/pricing` (K3): `minimum` joins the set,
 * emitted by that area's `ge=0` price fields.
 *
 * Nachgemessen 2026-08-13 (S3), nachdem die Fixture neu erzeugt wurde: die
 * Aussage „kein `enum`" stimmte nicht mehr. `01-base/engine` deklariert
 * `mode` und `agent.write_mode` als `Literal` (A0–A6, 2026-08-12) und
 * `01-base/pricing` die Währung mit einem `pattern`; beides kam nach der
 * letzten Messung dazu und blieb unbemerkt, weil die Fixture seither nicht
 * neu erzeugt worden war. Der Umschalter Muster/Agent stand deshalb als
 * FREITEXTFELD im Formular. `enum` rendert seit S3 als Auswahlfeld.
 *
 * `maximum` und `pattern` liest der Mapper NICHT: der Server weist eine
 * Verletzung auf PUT zurück, und dort gehört die Prüfung hin. Sie stehen hier
 * nur, damit der Typ ehrlich beschreibt, was wirklich ausgeliefert wird.
 *
 * Dazu kommen mit S2 `x-choices` und `x-catalog`. Sie sind KEIN
 * JSON-Schema-Vokabular, sondern eine Erweiterung dieses Projekts — daher der
 * `x-`-Präfix. Unterschied zu `enum`: ein `enum` entsteht aus einem `Literal`
 * und ist damit zugleich eine Speichersperre; `x-choices` zeichnet einen
 * Vorrat aus, ohne einen Bestandswert außerhalb davon unspeicherbar zu machen
 * (Begründung in `config_models/_shared.py`). Für die Bedienung sind beide
 * dasselbe: ein Auswahlfeld.
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
  readonly maximum?: number;
  readonly pattern?: string;
  /** Aus einem `Literal` im Modell — geschlossen UND vom Server erzwungen. */
  readonly enum?: readonly string[];
  /** Geschlossener Wertevorrat ohne Speichersperre -> ebenfalls Auswahlfeld. */
  readonly 'x-choices'?: readonly string[];
  /** Name eines Katalogs aus `GET /api/config/choices` -> Vorschlagsliste. */
  readonly 'x-catalog'?: string;
}
