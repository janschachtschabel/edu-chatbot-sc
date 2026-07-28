/**
 * The evaluation endpoints as the studio reads them (9-5d).
 *
 * Twelve endpoints for two different kinds of run. A **generative** run has an
 * LLM invent scenarios, chat through them and judge the answers — it costs money
 * and time, so it is preceded by `/estimate`. A **golden** run replays checked
 * flows from `eval/gold-flows.yaml` and is deterministic; only its soft-quality
 * judging is optional.
 *
 * Both write into the same `eval_runs` table and both leave rows in
 * `quality_logs` under `session_id LIKE 'eval-%'`, which is why the log clean-up
 * lives here rather than with the quality analytics.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi, type QueryValue } from './studio-api.service';

/** ALT's list window; the endpoint allows 500. */
const RUN_LIMIT = 50;
/** ALT's trend window — enough runs for a sparkline, few enough to stay honest. */
const TREND_LIMIT = 20;

export type EvalMode = 'scenarios' | 'conversations' | 'both';

/** `''` while a run is queued; the backend fills it when the run finishes. */
export interface EvalRunSummary {
  readonly id: string;
  readonly created_at: string;
  readonly completed_at: string | null;
  readonly status: string;
  readonly mode: string;
  readonly config_slug: string;
  readonly total_turns: number;
  readonly avg_score: number | null;
  readonly personas: readonly string[];
  readonly intents: readonly string[];
  readonly error_message: string | null;
  /** How many judged turns the run set out to produce — the progress divisor. */
  readonly target_turns: number;
  readonly current_activity: string;
}

export interface EvalRunDetail extends Omit<EvalRunSummary,
  'target_turns' | 'current_activity'> {
  readonly turns_per_conv: number;
  readonly judge_model: string;
  readonly simulator_model: string;
  /** Free-form per-run metrics; `classification_metrics` is the interesting part. */
  readonly summary: Record<string, unknown>;
  readonly conversations: readonly Record<string, unknown>[];
}

/**
 * One entry of `eval/gold-flows.yaml`, handed through unparsed by
 * `GET /eval/gold-flows`. Field names checked against the file: `title`, not
 * `name`; `persona`/`intents`, no `description`.
 */
export interface GoldFlow {
  readonly id: string;
  readonly title?: string;
  readonly persona?: string;
  readonly intents?: readonly string[];
  readonly turns?: readonly unknown[];
}

export interface EvalEstimate {
  readonly scenarios: number;
  readonly conversations: number;
  readonly total_turns: number;
  readonly chat_calls: number;
  readonly judge_calls: number;
  readonly simulator_calls: number;
  readonly est_usd: number;
  readonly est_usd_min: number;
  readonly est_usd_max: number;
}

export interface EvalConfig {
  readonly personas: readonly Record<string, unknown>[];
  readonly intents: readonly Record<string, unknown>[];
}

/** One point of a cross-run series. `value` carries the rate for most series. */
export interface TrendPoint {
  readonly run_id: string;
  readonly created_at: string;
  readonly value?: number;
  readonly rate?: number;
  readonly ok?: number;
  readonly total?: number;
  readonly judged?: number;
  readonly prompt_tokens?: number;
  readonly cached_tokens?: number;
}

export interface EvalTrends {
  readonly runs: readonly {
    readonly id: string; readonly created_at: string; readonly mode: string;
    readonly config_slug: string; readonly total_turns: number;
    readonly avg_score: number | null;
  }[];
  readonly pattern_trend: Record<string, readonly TrendPoint[]>;
  readonly cache_hit_trend: readonly TrendPoint[];
  readonly llm_engine_match_trend: readonly TrendPoint[];
  readonly persona_correct_trend: readonly TrendPoint[];
  readonly intent_correct_trend: readonly TrendPoint[];
}

export interface PatternUsage {
  readonly triples: readonly {
    readonly pattern_id: string; readonly intent_id: string;
    readonly persona_id: string; readonly count: number;
    /** `null` when no turn of the triple carried a confidence — not 0. */
    readonly avg_conf?: number | null;
  }[];
  readonly by_pattern: readonly { readonly pattern_id: string; readonly count: number }[];
  readonly by_intent: readonly { readonly intent_id: string; readonly count: number }[];
  readonly total: number;
  readonly scope: string;
}

export interface StartRunRequest {
  readonly mode: EvalMode;
  readonly persona_ids: readonly string[];
  readonly intent_ids: readonly string[];
  readonly scenarios_per_combo: number;
  readonly turns_per_conv: number;
  readonly config_slug: string;
}

/**
 * `warnings` carries the persona/intent ids the backend dropped as unknown — it
 * filters instead of rejecting, so a run can legitimately cover less than was
 * asked for and the caller has to say so.
 */
export interface StartRunResult {
  readonly run_id: string;
  readonly status?: string;
  readonly warnings?: readonly string[];
}

export interface GoldenRunRequest {
  readonly flow_ids: readonly string[];
  readonly judge: boolean;
  readonly config_slug: string;
}

/** Restrict a bulk delete; both empty means "every run". */
export interface RunDeleteFilters {
  readonly status?: string;
  readonly mode?: string;
}

@Injectable({ providedIn: 'root' })
export class EvalApi {
  private readonly api = inject(StudioApi);

  config(): Promise<EvalConfig> {
    return this.api.get<EvalConfig>('/eval/config');
  }

  estimate(request: Omit<StartRunRequest, 'config_slug'>): Promise<EvalEstimate> {
    return this.api.post<EvalEstimate>('/eval/estimate', request);
  }

  async runs(): Promise<readonly EvalRunSummary[]> {
    const body = await this.api.get<{ runs?: readonly EvalRunSummary[] }>(
      '/eval/runs', { limit: RUN_LIMIT },
    );
    return body.runs ?? [];
  }

  run(id: string): Promise<EvalRunDetail> {
    return this.api.get<EvalRunDetail>(`/eval/runs/${id}`);
  }

  startRun(request: StartRunRequest): Promise<StartRunResult> {
    return this.api.post<StartRunResult>('/eval/runs', request);
  }

  async goldFlows(): Promise<readonly GoldFlow[]> {
    const body = await this.api.get<{ flows?: readonly GoldFlow[] }>('/eval/gold-flows');
    return body.flows ?? [];
  }

  /** `warnings` lists flow ids the backend did not know and dropped. */
  startGoldenRun(request: GoldenRunRequest): Promise<StartRunResult> {
    return this.api.post<StartRunResult>('/eval/runs/golden', request);
  }

  deleteRun(id: string): Promise<{ deleted: string }> {
    return this.api.delete<{ deleted: string }>(`/eval/runs/${id}`);
  }

  /**
   * Bulk delete. `confirm=true` is required for an unrestricted wipe and is sent
   * only then — a status or mode filter already restricts the delete.
   */
  deleteRuns(filters: RunDeleteFilters): Promise<{ deleted: number }> {
    const params: Record<string, QueryValue> = {
      status: filters.status || undefined,
      mode: filters.mode || undefined,
    };
    const restricted = Object.values(params).some(Boolean);
    return this.api.delete<{ deleted: number }>('/eval/runs', {
      ...params, confirm: restricted ? undefined : true,
    });
  }

  /** Removes only the `quality_logs` rows an eval run wrote, not real turns. */
  clearEvalQualityLogs(): Promise<{ deleted: number }> {
    return this.api.delete<{ deleted: number }>('/eval/quality-logs');
  }

  trends(): Promise<EvalTrends> {
    return this.api.get<EvalTrends>('/eval/trends', { limit: TREND_LIMIT });
  }

  patternUsage(scope: string, since: string): Promise<PatternUsage> {
    return this.api.get<PatternUsage>('/eval/analytics/pattern-usage', {
      scope, since: since || undefined,
    });
  }
}
