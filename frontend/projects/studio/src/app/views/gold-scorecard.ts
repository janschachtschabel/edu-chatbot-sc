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

/** The 6 categories `aggregate_golden` reports; `host` is soft (see below). */
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
 * One `golden_metrics.per_flow` entry: `title` plus one `{ok, total}` cell per
 * category.
 *
 * There is deliberately no `persona` id here even though the backend looks like
 * it sets one: `aggregate_golden` builds the entry as
 * `{"title": …, "persona": conv["persona_id"], **{c: {ok, total} for c in
 * GOLDEN_CATS}}`, and `GOLDEN_CATS` contains `"persona"` — so the spread
 * overwrites the id with the category cell, on every entry, in ALT too. The
 * flow's persona therefore comes from `conversations[].persona_id`.
 */
export interface GoldPerFlow {
  readonly title?: string;
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
 * `host` is deliberately absent: `check_golden_turn` marks it soft because a
 * wrong `REPO_BASE_URL` fails it for every turn without saying anything about
 * the bot. Mirrors `GOLDEN_HARD` in `evals/run_golden.py`.
 */
export const GOLD_HARD_CATS: readonly string[] = [
  'persona', 'intent', 'register', 'structure', 'qr',
];

const CAT_LABELS: Readonly<Record<string, string>> = {
  persona: 'Persona',
  intent: 'Intent',
  register: 'Tonalität',
  structure: 'Struktur',
  qr: 'Quick-Replies',
  host: 'Link-Host',
};

/** German label, or the raw key — an unknown category must stay visible. */
export function catLabel(category: string): string {
  return CAT_LABELS[category] ?? category;
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

/** Hard pass rate of one flow, from the server-side `per_flow` entry. */
export function hardRate(entry: GoldPerFlow | undefined): HardRate {
  let ok = 0;
  let total = 0;
  for (const category of GOLD_HARD_CATS) {
    const cell = entry?.[category] as { ok?: number; total?: number } | undefined;
    ok += cell?.ok ?? 0;
    total += cell?.total ?? 0;
  }
  return { ok, total, rate: total ? Math.round((ok / total) * 1000) / 1000 : null };
}
