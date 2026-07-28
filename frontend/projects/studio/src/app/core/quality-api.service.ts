/**
 * Quality analytics as the studio reads them (9-5c).
 *
 * Nine endpoints that split into three groups with different reasons to reload:
 * the log window (follows the text filters), the aggregates (follow only the
 * scope), and the two drill-downs (matrix, flow) which carry their own knobs.
 * The view keeps one `AsyncData` per endpoint for exactly that reason — ALT
 * fetched five of them together on every keystroke, and four of those five
 * accept nothing but `scope`, so they could not have changed.
 *
 * `/quality/tight-races` is deliberately absent. `phase2_scores` has carried a
 * single entry (`{winner: 1.0}`) since Welle E v4, so `obs/quality_events.py`
 * never reaches its `len(...) >= 2` branch: `phase2_runner_up` is `''` and
 * `phase2_score_gap` is `0.0` on every row. The endpoint filters on
 * `runner_up != ''` and therefore returns nothing, for any data, forever. ALT
 * reached the same conclusion and stopped calling it (only a dead interface is
 * left in `QualityView.tsx`), but still renders a permanently-zero "Ø Score-Gap"
 * KPI next to the retired one; neither is ported. C2 has since made the endpoint
 * state that reason itself (`unavailable_reason`) instead of answering with a
 * bare `total_tight: 0`; that does not make it worth a view, so it stays absent.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi, type QueryValue } from './studio-api.service';

/** Production and eval turns share one table; `session_id LIKE 'eval-%'` splits them. */
export type QualityScope = 'all' | 'production' | 'eval';

/** Prefix matches on the server ("M04" finds M04a); the session id is exact. */
export interface LogFilters {
  readonly patternId?: string;
  readonly intentId?: string;
  readonly sessionId?: string;
}

/**
 * One logged turn, flattened by the backend from `columns + data` back into
 * ALT's single-row shape. Only the fields the studio actually shows are typed.
 */
export interface QualityLog {
  readonly id: number;
  readonly session_id: string;
  readonly pattern_id: string;
  readonly intent_id: string;
  readonly created_at: string;
  readonly persona_id: string;
  readonly state_id: string;
  readonly turn_type: string;
  readonly turn_count: number;
  readonly final_confidence: number;
  readonly pattern_label: string;
  readonly signals: readonly string[];
  readonly entities: Record<string, unknown>;
  readonly tools_called: readonly string[];
  /** 1/0, not a boolean — the endpoint restores ALT's sqlite int. */
  readonly degradation: number;
  readonly missing_slots: readonly string[];
  readonly response_length: number;
  readonly cards_count: number;
  readonly message: string;
}

export interface QualityStats {
  readonly scope: string;
  readonly total_turns: number;
  readonly pattern_distribution: Record<string, number>;
  readonly intent_distribution: Record<string, number>;
  readonly avg_confidence: number;
  readonly degradation_rate: number;
  readonly empty_entity_rate: number;
  readonly avg_response_length: number;
}

export interface MatrixCell {
  readonly persona_id: string;
  readonly intent_id: string;
  readonly top_pattern: string;
  readonly top_pattern_count: number;
  readonly total_count: number;
  readonly share: number;
  readonly alternatives: readonly { readonly pattern_id: string; readonly count: number }[];
}

export interface RoutingMatrix {
  readonly scope: string;
  readonly total_turns: number;
  readonly cells: readonly MatrixCell[];
}

export interface StateFlow {
  readonly scope: string;
  readonly days: number;
  readonly total_turns: number;
  readonly total_transitions: number;
  readonly state_distribution: Record<string, number>;
  readonly transitions: readonly { readonly prev: string; readonly next: string;
    readonly count: number }[];
}

/** The example fields are absent when the sample row vanished between queries. */
interface Example {
  readonly example_message?: string;
  readonly example_intent?: string;
  readonly example_persona?: string;
  readonly example_state?: string;
}

export interface DegradationGroup extends Example {
  readonly pattern_id: string;
  readonly missing_slots: readonly string[];
  readonly count: number;
}

export interface EmptyEntityGroup extends Example {
  readonly intent_id: string;
  readonly pattern_id: string;
  readonly count: number;
}

export interface LowConfidenceTurn {
  readonly id: number;
  readonly message: string;
  readonly intent_id: string;
  readonly pattern_id: string;
  readonly persona_id: string;
  readonly state_id: string;
  readonly final_confidence: number;
  readonly created_at: string;
}

export interface Breakdown<T> {
  readonly groups: readonly T[];
  readonly total: number;
  readonly scope: string;
}

export interface LowConfidence {
  readonly turns: readonly LowConfidenceTurn[];
  readonly total: number;
  readonly scope: string;
  readonly max_confidence: number;
}

/** ALT's window; the endpoint allows 500 but 200 rows is already a long page. */
const LOG_LIMIT = 200;
/** ALT's `&limit=30` on all three diagnosis breakdowns. */
const BREAKDOWN_LIMIT = 30;

/** Empty strings are dropped, not sent: `pattern_id=` is a filter that matches nothing. */
function filterParams(filters: LogFilters): Record<string, QueryValue> {
  return {
    pattern_id: filters.patternId || undefined,
    intent_id: filters.intentId || undefined,
    session_id: filters.sessionId || undefined,
  };
}

@Injectable({ providedIn: 'root' })
export class QualityApi {
  private readonly api = inject(StudioApi);

  async logs(scope: QualityScope, filters: LogFilters): Promise<readonly QualityLog[]> {
    const body = await this.api.get<{ count: number; logs: readonly QualityLog[] }>(
      '/quality/logs', { limit: LOG_LIMIT, scope, ...filterParams(filters) },
    );
    return body.logs ?? [];
  }

  deleteLog(id: number): Promise<unknown> {
    return this.api.delete(`/quality/logs/${id}`);
  }

  /**
   * Bulk delete. The endpoint refuses an unfiltered wipe of every scope unless
   * `confirm=true`, and counts a narrowed scope as a filter — mirrored here so
   * the flag is sent exactly when it is required.
   */
  clearLogs(scope: QualityScope, filters: LogFilters): Promise<{ deleted: number }> {
    const params = filterParams(filters);
    const filtered = scope !== 'all' || Object.values(params).some(Boolean);
    return this.api.post<{ deleted: number }>('/quality/logs/clear', null, {
      scope, ...params, confirm: filtered ? undefined : true,
    });
  }

  stats(scope: QualityScope): Promise<QualityStats> {
    return this.api.get<QualityStats>('/quality/stats', { scope });
  }

  matrix(scope: QualityScope, minCount: number): Promise<RoutingMatrix> {
    return this.api.get<RoutingMatrix>('/quality/matrix', { scope, min_count: minCount });
  }

  stateTransitions(scope: QualityScope, days: number, minCount: number): Promise<StateFlow> {
    return this.api.get<StateFlow>('/quality/state-transitions', {
      scope, days, min_count: minCount,
    });
  }

  degradations(scope: QualityScope): Promise<Breakdown<DegradationGroup>> {
    return this.api.get<Breakdown<DegradationGroup>>('/quality/degradations', {
      scope, limit: BREAKDOWN_LIMIT,
    });
  }

  emptyEntities(scope: QualityScope): Promise<Breakdown<EmptyEntityGroup>> {
    return this.api.get<Breakdown<EmptyEntityGroup>>('/quality/empty-entities', {
      scope, limit: BREAKDOWN_LIMIT,
    });
  }

  lowConfidence(scope: QualityScope): Promise<LowConfidence> {
    return this.api.get<LowConfidence>('/quality/low-confidence', {
      scope, limit: BREAKDOWN_LIMIT,
    });
  }
}
