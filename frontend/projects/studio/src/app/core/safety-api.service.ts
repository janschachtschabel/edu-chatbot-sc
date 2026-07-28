/**
 * Safety decisions as the studio reads them (9-5b).
 *
 * Two endpoints that deliberately do NOT move together: `/logs` answers the
 * filtered window the editor is looking at, `/stats` aggregates the whole
 * window server-side and ignores the filter entirely. The view therefore reads
 * them as two independent things — one can fail without blanking the other.
 *
 * `/logs` wraps its rows in `{count, logs}`; unwrapping here is what lets
 * `AsyncData.isEmpty` tell "loaded, nothing there" from "not loaded yet".
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

/** `''` = every event; the others are the endpoint's own risk floors. */
export type RiskFilter = '' | 'medium' | 'high';

export interface SafetyLog {
  readonly id: number;
  readonly session_id: string;
  /**
   * Sent by the endpoint and deliberately never rendered: an IP is personal
   * data, and the session id already identifies the conversation. Kept in the
   * type so the omission reads as a decision rather than an oversight.
   */
  readonly ip: string;
  readonly risk_level: string;
  readonly stages_run: readonly string[];
  readonly reasons: readonly string[];
  readonly legal_flags: readonly string[];
  readonly flagged_categories: readonly string[];
  readonly blocked_tools: readonly string[];
  readonly enforced_pattern: string;
  /** 0/1, not booleans — ALT's sqlite ints, preserved by the NEU endpoint. */
  readonly escalated: number;
  readonly rate_limited: number;
  readonly message: string;
  /** Moderation category scores, under ALT's leaked sqlite column name. */
  readonly categories_json: Record<string, number>;
  readonly created_at: string;
}

export interface SafetyStats {
  readonly total: number;
  readonly by_risk: Record<string, number>;
  readonly by_legal: Record<string, number>;
  readonly rate_limited: number;
  readonly escalated: number;
}

interface LogsResponse {
  readonly count: number;
  readonly logs: readonly SafetyLog[];
}

/** ALT's window (`limit: '200'`), twice the endpoint's default of 100. */
const LOG_LIMIT = 200;

@Injectable({ providedIn: 'root' })
export class SafetyApi {
  private readonly api = inject(StudioApi);

  async logs(riskMin: RiskFilter = ''): Promise<readonly SafetyLog[]> {
    const body = await this.api.get<LogsResponse>('/safety/logs', {
      limit: LOG_LIMIT,
      // `undefined` is dropped by StudioApi rather than sent as an empty value.
      risk_min: riskMin || undefined,
    });
    return body.logs ?? [];
  }

  stats(): Promise<SafetyStats> {
    return this.api.get<SafetyStats>('/safety/stats');
  }
}
