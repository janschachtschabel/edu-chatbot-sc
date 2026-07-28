/**
 * The two reference catalogues, shaped from LIVE config (A5-Rest).
 *
 * Written as a transform rather than a checked-in table because ALT's
 * hand-copied versions of exactly these two lists had drifted:
 *
 *  - the 17 signals: four rows were simply wrong against
 *    `04-signals/signal-modulations.yaml` (`effizient` was listed as "mittel"
 *    but is `kurz`; `vertrauend` as "keine Overrides" but sets tone
 *    `empfehlend` + length `mittel`; `vergleichend` as "sachlich" but is
 *    `analytisch`; `delegierend` as "kurz" but is `mittel`/`proaktiv`), and
 *    five more silently dropped a flag the config sets (`skip_intro` on
 *    ungeduldig/gestresst/erfahren/entscheidungsbereit, `show_more` on
 *    neugierig, `show_overview` on orientierungssuchend).
 *  - the 18 material types: the "Didaktisch (13)" box listed thirteen chips of
 *    which one was `auto`, so twelve real types stood under a heading claiming
 *    thirteen — `Vokabelliste` was missing entirely.
 *
 * `GET /config/elements` carries every signal's modulation dict and
 * `GET /config/data/05-canvas/material-types` the whole type list, so both
 * tables are read, not remembered.
 */

/** One entry of `/config/elements` → `signals`. */
export interface SignalElement {
  readonly id: string;
  readonly modulations?: Record<string, unknown>;
}

export interface SignalRow {
  readonly id: string;
  /** '' when the signal does not set it — an invented value would be a claim. */
  readonly tone: string;
  readonly length: string;
  readonly flags: readonly string[];
}

export interface SignalDimension {
  /** The config's own value, e.g. `D1-Zeit`. */
  readonly key: string;
  /** `D1-Zeit` → `D1 — Zeit`. */
  readonly heading: string;
  readonly signals: readonly SignalRow[];
}

/** Keys of a modulation dict that are not flags. */
const NON_FLAG_KEYS = new Set(['dimension', 'label', 'tone', 'length']);

/**
 * German wording for the flags the engine knows today. Unknown keys fall
 * through as-is rather than disappearing — a flag added to the config must show
 * up here without a code change, which is the whole point of reading live.
 */
const FLAG_LABELS: Record<string, string> = {
  skip_intro: 'ohne Einleitung',
  one_option: 'nur ein Vorschlag',
  add_sources: 'mit Quellen',
  show_more: 'ohne Rückfrage-Vorschlag',
  show_overview: 'mit Überblick',
};

function textOf(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function flagsOf(mods: Record<string, unknown>): readonly string[] {
  return Object.entries(mods)
    .filter(([key, value]) => !NON_FLAG_KEYS.has(key) && value === true)
    .map(([key]) => FLAG_LABELS[key] ?? key);
}

/** Signals grouped by their configured dimension, dimensions in key order. */
export function groupSignals(elements: readonly SignalElement[]): readonly SignalDimension[] {
  const byKey = new Map<string, SignalRow[]>();
  for (const element of elements) {
    const mods = element.modulations;
    if (!mods) continue;
    const key = textOf(mods['dimension']);
    if (!key) continue;
    const rows = byKey.get(key) ?? [];
    rows.push({
      id: element.id,
      tone: textOf(mods['tone']),
      length: textOf(mods['length']),
      flags: flagsOf(mods),
    });
    byKey.set(key, rows);
  }
  return [...byKey.entries()]
    .sort(([a], [b]) => a.localeCompare(b, 'de'))
    .map(([key, signals]) => ({ key, heading: headingOf(key), signals }));
}

function headingOf(key: string): string {
  const cut = key.indexOf('-');
  return cut < 0 ? key : `${key.slice(0, cut)} — ${key.slice(cut + 1)}`;
}

export interface MaterialType {
  readonly id: string;
  readonly label: string;
  readonly emoji: string;
  readonly category: string;
}

export interface MaterialSplit {
  readonly didaktisch: readonly MaterialType[];
  readonly analytisch: readonly MaterialType[];
  /** Anything with another category — shown, never dropped. */
  readonly weitere: readonly MaterialType[];
  /** Rows in the file. */
  readonly entries: number;
  /** Rows minus `auto`, which selects a type rather than being one. */
  readonly types: number;
}

const AUTO_ID = 'auto';

/** `/config/data/05-canvas/material-types` → the two boxes plus the counts. */
export function splitMaterialTypes(data: Record<string, unknown>): MaterialSplit {
  const raw = Array.isArray(data['material_types']) ? data['material_types'] : [];
  const rows = raw.map((entry): MaterialType => {
    const row = (entry ?? {}) as Record<string, unknown>;
    return {
      id: textOf(row['id']),
      label: textOf(row['label']),
      emoji: textOf(row['emoji']),
      category: textOf(row['category']),
    };
  });
  return {
    didaktisch: rows.filter((r) => r.category === 'didaktisch'),
    analytisch: rows.filter((r) => r.category === 'analytisch'),
    weitere: rows.filter((r) => r.category !== 'didaktisch' && r.category !== 'analytisch'),
    entries: rows.length,
    types: rows.filter((r) => r.id !== AUTO_ID).length,
  };
}
