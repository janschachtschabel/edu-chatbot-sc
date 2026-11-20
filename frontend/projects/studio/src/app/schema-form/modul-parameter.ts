/**
 * Plan 2026-11-20, P6: die Parameter eines UI-Moduls als Hilfe unter „Daten“ eines Modul-Schritts —
 * ohne DOM. Quelle ist das Manifest (`dienst.parameter`, ein JSON Schema): dieselben Parameter, die
 * der Treiber dem Dienst gibt und die Prüfung (`pruefung._dienst_daten`) mit Namen und Wert prüft.
 */

/** Ein Parameter, so wie die Hilfe ihn zeigt. */
export interface ModulParameter {
  readonly name: string;
  /** Aus dem Manifest — deutsch. */
  readonly beschreibung: string;
  /** Erlaubte Werte (`enum`, bei einer Liste die der Einträge); leer = frei im Rahmen des Typs. */
  readonly werte: readonly string[];
  /** Die Werte gelten je Eintrag einer Liste. */
  readonly liste: boolean;
  /** Der Typ, wenn das Schema einen nennt (`boolean`, `string` …). */
  readonly typ: string | null;
  /** Die Vorgabe des Schemas (`default`) als JSON-Text, sonst `null`. */
  readonly vorgabe: string | null;
  readonly pflicht: boolean;
}

const objekt = (w: unknown): w is Record<string, unknown> =>
  typeof w === 'object' && w !== null && !Array.isArray(w);

/** Das Modul eines Modul-Schritts, wenn `pfad` auf dessen `daten` zeigt — sonst `null`. */
export function modulAmPfad(dokument: unknown, pfad: readonly (string | number)[]): string | null {
  if (pfad.length < 3 || pfad.at(-1) !== 'daten' || pfad.at(-3) !== 'schritte') return null;
  let knoten: unknown = dokument;
  for (const teil of pfad.slice(0, -1)) {
    if (!objekt(knoten) && !Array.isArray(knoten)) return null;
    knoten = (knoten as Record<string | number, unknown>)[teil];
  }
  if (!objekt(knoten) || knoten['typ'] !== 'modul') return null;
  const modul = knoten['modul'];
  return typeof modul === 'string' && modul.trim() ? modul.trim() : null;
}

/** Die Parameter aus `dienst.parameter` eines Manifests, in ihrer Reihenfolge. */
export function parameterAus(manifest: unknown): ModulParameter[] {
  const dienst = objekt(manifest) ? manifest['dienst'] : null;
  const schema = objekt(dienst) ? dienst['parameter'] : null;
  const felder = objekt(schema) ? schema['properties'] : null;
  if (!objekt(schema) || !objekt(felder)) return [];
  const pflicht = Array.isArray(schema['required']) ? schema['required'] : [];
  return Object.entries(felder).filter(([, f]) => objekt(f)).map(([name, f]) => {
    const feld = f as Record<string, unknown>;
    const items = objekt(feld['items']) ? feld['items'] : null;
    const eigene = Array.isArray(feld['enum']) ? feld['enum'] : null;
    const jeEintrag = !eigene && items && Array.isArray(items['enum']) ? items['enum'] : null;
    return {
      name,
      beschreibung: typeof feld['description'] === 'string' ? feld['description'] : '',
      werte: (eigene ?? jeEintrag ?? []).map((w) => String(w)),
      liste: jeEintrag !== null,
      typ: typeof feld['type'] === 'string' ? feld['type'] : null,
      vorgabe: 'default' in feld ? JSON.stringify(feld['default']) : null,
      pflicht: pflicht.includes(name),
    };
  });
}
