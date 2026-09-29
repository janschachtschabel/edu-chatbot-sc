/**
 * What the backend says about one run (ST-7b) — the shapes of K0-1's arithmetic
 * (`services/eval/engine_metrics.py`), as `GET /eval/runs/{id}` delivers them
 * under `profile`. The comparison (ST-7c) carries the same four parts per engine.
 *
 * `null` always means "not measured", never zero: a run without a judge has no
 * axis values, a generative run no turn duration, a model without a price no
 * cost. The views say so instead of printing 0.
 */

/** The judge axes in the order the Studio shows them: the task first (plan
 *  §5.1: "vor allem `auftrag_erfuellt`"), the pattern axis last — agent turns
 *  never have it. */
export const JUDGE_AXES = [
  'auftrag_erfuellt', 'intent_fit', 'persona_tone', 'info_quality', 'safety', 'pattern_match',
] as const;

export type JudgeAxis = typeof JUDGE_AXES[number];

/** Below this a judge axis counts as weak — the threshold ALT's quality
 *  profile used for its warning sign. */
export const WEAK_AXIS = 1.2;

export interface ProfileQuality {
  readonly hard_rate: number | null;
  readonly hard_passed: number;
  readonly hard_total: number;
  readonly axes: Readonly<Record<string, number | null>>;
}

export interface ProfileSpeed {
  readonly p50_ms: number | null;
  readonly p95_ms: number | null;
  /** Share of turns above 30 s, 0…1. */
  readonly over_30s: number | null;
  /** Number of turns above the widget's 90 s silence limit. */
  readonly over_90s: number;
}

export interface ProfileCost {
  readonly turns_with_usage: number;
  /** Mean tokens per turn. */
  readonly prompt: number | null;
  readonly cached: number | null;
  readonly completion: number | null;
  /** In the price table's currency; `null` as soon as one model has no price. */
  readonly cost_per_turn: number | null;
  readonly cost_total: number | null;
  readonly price_unavailable: readonly string[];
}

export interface ProfileRobustness {
  readonly turns: number;
  readonly chat_errors: number;
  readonly judge_failed: number;
  readonly empty: number;
  /** The app's fallback sentences, delivered with HTTP 200. */
  readonly fallback: number;
}

export interface RunProfile {
  readonly quality: ProfileQuality;
  readonly speed: ProfileSpeed;
  readonly cost: ProfileCost;
  readonly robustness: ProfileRobustness;
  /** `null` when the price table is unreadable. */
  readonly currency: string | null;
}

// ── ST-7c: the engine comparison (`GET /eval/compare`) ────────────────

/** How alike the repeats of one engine are — `null` below two runs. */
export interface EngineDeterminism {
  readonly turns_compared: number;
  /** Share of turns with the same check outcome in every repeat, 0…1. */
  readonly check_agreement: number | null;
  /** Mean Jaccard similarity of the tool sets, 1 = the same tools. */
  readonly tool_jaccard: number | null;
  /** Mean text similarity of the answers, 1 = the same text. */
  readonly text_similarity: number | null;
  /** Mean standard deviation of `auftrag_erfuellt` per turn. */
  readonly judge_spread: number | null;
}

/** One engine's column: the run profile over all its turns, plus what only
 *  repeats can say. */
export interface EngineSummary extends Omit<RunProfile, 'currency'> {
  readonly runs: number;
  readonly hard_rate_runs: readonly (number | null)[];
  readonly determinism: EngineDeterminism;
  readonly safe: ProfileQuality;
  readonly frei: ProfileQuality;
}

/** Rule R2(a) of plan §5.4: does the pattern engine show a measurable edge?
 *  `gruende` are fixed words from the backend (`stabiler`, `billiger`,
 *  `schneller`) — codes, translated by the Studio. */
export interface RuleR2a {
  readonly erfuellt: boolean;
  readonly gruende: readonly string[];
  readonly d_agreement: number | null;
  readonly kosten_faktor: number | null;
  readonly p50_faktor: number | null;
}

/** One set of runs that measured under the same conditions. */
export interface CompareCondition {
  readonly provider: string | null;
  readonly chat_model: string | null;
  readonly judge_model: string | null;
  readonly master_skill: { readonly enabled: boolean | null; readonly sha256: string | null };
  readonly agent_limits: Readonly<Record<string, unknown>> | null;
  readonly runs: readonly string[];
}

export interface CompareRun {
  readonly id: string;
  readonly engine: string;
  readonly status: string;
  readonly label: string;
  readonly counted: boolean;
}

export type CompareWarning =
  | { readonly code: 'not_found' | 'engine_unknown'; readonly run: string }
  | { readonly code: 'not_done'; readonly run: string; readonly status: string }
  | { readonly code: 'price_missing'; readonly models: readonly string[] }
  | { readonly code: 'master_skill_off'; readonly runs: readonly string[] }
  | { readonly code: 'pricing_unreadable' | 'conditions_differ' };

export interface EngineComparison {
  readonly engines: Readonly<Record<string, EngineSummary>>;
  readonly rules: { readonly R2a?: RuleR2a };
  readonly currency: string | null;
  readonly conditions: readonly CompareCondition[];
  readonly runs: readonly CompareRun[];
  readonly warnings: readonly CompareWarning[];
}
