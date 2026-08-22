/**
 * Pure shaping for the golden scorecard (9-5d / A1).
 *
 * Kept out of the component for the same reason as `loadtest-profile.ts`: the
 * grouping and the hard-rate arithmetic are testable without a DOM, and they are
 * the part that would silently lie if it drifted.
 *
 * The hard rate is derived from `golden_metrics.per_flow`, which the backend
 * already aggregates. ALT recomputed the same numbers client-side from
 * `per_turn` (`flowAgg`) — two implementations of one sum, and the client copy
 * had no test.
 */
import type { Translate } from '../i18n/studio-language.service';

/** A category `aggregate_golden` reports; `host` is soft (see below). */
export type GoldCategory = string;

export interface GoldChecks {
  readonly [category: string]: boolean | null | undefined;
}

export interface GoldPerTurn {
  readonly flow: string;
  readonly title: string;
  readonly turn: number;
  readonly message: string;
  readonly expected: Readonly<Record<string, unknown>>;
  readonly observed: Readonly<Record<string, unknown>>;
  readonly checks: GoldChecks;
}

/**
 * One `golden_metrics.per_flow` entry: `title` and `zielgruppe` plus one
 * `{ok, total}` cell per category.
 *
 * `zielgruppe` exists since GV1. Its v1 predecessor was a field named
 * `persona` that the backend's dict spread immediately overwrote with the
 * same-named CATEGORY cell (in ALT too) — v1 entries therefore carry the
 * persona only as a `{ok, total}` cell, never as an id.
 */
export interface GoldPerFlow {
  readonly title?: string;
  readonly zielgruppe?: string;
  readonly [category: string]: unknown;
}

export interface GoldMetrics {
  readonly categories: readonly string[];
  readonly totals: Readonly<Record<string, number>>;
  readonly passed: Readonly<Record<string, number>>;
  readonly rates: Readonly<Record<string, number | null>>;
  readonly overall_pass_rate: number;
  readonly hard_passed: number;
  readonly hard_total: number;
  readonly flows: number;
  readonly turns: number;
  readonly per_turn: readonly GoldPerTurn[];
  readonly per_flow: Readonly<Record<string, GoldPerFlow>>;
  /** Only present when the run was started with the judge (C3). */
  readonly judge_avg?: number;
  readonly judged_turns?: number;
}

/**
 * The hard categories of a stored run, derived from the report's own
 * `categories` list: everything except the soft `host` (`check_golden_turn`
 * marks it soft because a wrong `REPO_BASE_URL` fails it for every turn
 * without saying anything about the bot).
 *
 * Derived rather than hardcoded (GV5): the same scorecard then renders
 * stored v1 runs (persona/intent/register/structure/qr) and v2 runs
 * (register/structure/tools_any/qr) without a version switch — the report
 * says what it asserted. Mirrors `GOLDEN_HARD` in `evals/run_golden.py`.
 */
export function hardCats(
  metrics: Pick<GoldMetrics, 'categories'> | null | undefined,
): readonly string[] {
  return (metrics?.categories ?? []).filter((c) => c !== 'host');
}

/**
 * Kategorie → Katalog-Schlüssel (C1-d4b2). Bis dahin standen hier die fertigen
 * Namen und froren damit die Sprache ein, die beim Laden des Moduls gerade
 * galt — derselbe Fall wie `overview-cards.ts` und `TABS`.
 *
 * Erlaubnisliste statt `'evalDetail.cat.' + category`: eine neue Kategorie des
 * Backends gäbe sonst den Schlüssel selbst als Beschriftung aus, statt den
 * rohen Wert zu zeigen.
 */
const CAT_KEYS: Readonly<Record<string, string>> = {
  persona: 'evalDetail.cat.persona',
  intent: 'evalDetail.cat.intent',
  register: 'evalDetail.cat.register',
  structure: 'evalDetail.cat.structure',
  tools_any: 'evalDetail.cat.tools_any',
  qr: 'evalDetail.cat.qr',
  host: 'evalDetail.cat.host',
};

/** Beschriftung in der aktiven Sprache, oder der rohe Schlüssel — eine
 *  unbekannte Kategorie muss sichtbar bleiben. */
export function catLabel(category: string, t: Translate): string {
  const key = CAT_KEYS[category];
  return key ? t(key) : category;
}

export interface FlowGroup {
  readonly flow: string;
  readonly title: string;
  readonly turns: readonly GoldPerTurn[];
}

/** Turns grouped by flow, first-appearance order preserved. */
export function flowGroups(perTurn: readonly GoldPerTurn[]): readonly FlowGroup[] {
  const byFlow = new Map<string, GoldPerTurn[]>();
  const titles = new Map<string, string>();
  for (const turn of perTurn) {
    let bucket = byFlow.get(turn.flow);
    if (!bucket) {
      bucket = [];
      byFlow.set(turn.flow, bucket);
      titles.set(turn.flow, turn.title);
    }
    bucket.push(turn);
  }
  return [...byFlow].map(([flow, turns]) => ({
    flow, title: titles.get(flow) ?? '', turns,
  }));
}

export interface HardRate {
  readonly ok: number;
  readonly total: number;
  /** `null` when nothing was asserted — 0 % would claim everything failed. */
  readonly rate: number | null;
}

/** Hard pass rate of one flow, from the server-side `per_flow` entry.
 *  `cats` comes from `hardCats(metrics)` — the run's own hard set. */
export function hardRate(
  entry: GoldPerFlow | undefined, cats: readonly string[],
): HardRate {
  let ok = 0;
  let total = 0;
  for (const category of cats) {
    const cell = entry?.[category] as { ok?: number; total?: number } | undefined;
    ok += cell?.ok ?? 0;
    total += cell?.total ?? 0;
  }
  return { ok, total, rate: total ? Math.round((ok / total) * 1000) / 1000 : null };
}
