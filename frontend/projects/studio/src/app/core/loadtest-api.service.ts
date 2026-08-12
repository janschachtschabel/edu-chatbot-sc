/**
 * The load-test endpoints as the studio uses them (9-5e).
 *
 * `POST /runs` fires the REAL chat pipeline (LLM + MCP), so it is the one call
 * in the studio that costs money and staging capacity. The endpoint allows a
 * single run at a time and answers 409 otherwise; the view keeps the button
 * shut when any run is in flight rather than letting someone find out that way.
 *
 * The list and mix endpoints wrap their arrays (`{runs}`, `{options}`);
 * unwrapping here is what lets `AsyncData.isEmpty` distinguish "no runs yet"
 * from "not loaded yet".
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

export interface MixOption {
  readonly key: string;
  readonly label: string;
  readonly prompt: string;
}

export interface RunProfile {
  readonly stages: readonly number[];
  readonly requests_per_stage: number;
  readonly mix: Readonly<Record<string, number>>;
  readonly p95_threshold_s: number;
  readonly total_requests: number;
}

export interface StageResult {
  readonly concurrency: number;
  readonly requests: number;
  readonly ok: number;
  readonly errors: number;
  readonly error_kinds: readonly string[];
  readonly p50_s: number;
  readonly p95_s: number;
  readonly max_s: number;
  readonly mean_s: number;
  readonly duration_s: number;
  readonly rps: number;
  readonly by_kind: Readonly<Record<string, { n: number; ok: number; p50_s: number; p95_s: number }>>;
}

/**
 * The six keys `_summary` in `services/loadtest.py` actually returns.
 *
 * The two peaks were removed in B5 and **restored in C5 (2026-07-31)**, this
 * time with a producer behind them: psutil is a backend dependency now and the
 * runner samples CPU/RSS every 0.5 s. B5's lesson is why the wording above is
 * "actually returns" — a type that promised fields nobody wrote was the reason
 * "Spitze NaN MB" shipped unnoticed. Check the backend before extending this.
 */
export interface RunSummary {
  /** `null` = even the first stage missed the threshold. */
  readonly stable_concurrency: number | null;
  readonly p95_threshold_s: number;
  /** Highest sampled RSS in MB; `0` when a run recorded no sample at all. */
  readonly peak_rss_mb: number;
  /** Highest sampled process CPU in percent; `0` as above. */
  readonly peak_proc_cpu_pct: number;
  readonly total_requests: number;
  readonly total_errors: number;
}

export interface LoadTestRun {
  readonly id: string;
  readonly status: 'running' | 'completed' | 'failed';
  readonly created_at: string;
  readonly finished_at: string | null;
  readonly profile: RunProfile;
  readonly stages: readonly StageResult[];
  /** Seit C5 gefüllt: ein Punkt je 0,5 s Laufzeit (`t` = Sekunden seit Start). */
  readonly resource_samples: readonly { t: number; proc_cpu: number; rss_mb: number }[];
  readonly summary: RunSummary | null;
  readonly error: string | null;
}

export interface RunListItem {
  readonly id: string;
  readonly status: string;
  readonly created_at: string;
  readonly summary: RunSummary | null;
  readonly profile: RunProfile;
  readonly error: string | null;
}

/** The body `POST /runs` expects; the response echoes the NORMALISED profile. */
export interface StartProfile {
  readonly stages: readonly number[];
  readonly requests_per_stage: number;
  readonly mix: Record<string, number>;
  readonly p95_threshold_s: number;
}

@Injectable({ providedIn: 'root' })
export class LoadtestApi {
  private readonly api = inject(StudioApi);

  async mixOptions(): Promise<readonly MixOption[]> {
    const body = await this.api.get<{ options: readonly MixOption[] }>('/loadtest/mix-options');
    return body.options ?? [];
  }

  async runs(): Promise<readonly RunListItem[]> {
    const body = await this.api.get<{ runs: readonly RunListItem[] }>('/loadtest/runs');
    return body.runs ?? [];
  }

  run(id: string): Promise<LoadTestRun> {
    return this.api.get<LoadTestRun>(`/loadtest/runs/${encodeURIComponent(id)}`);
  }

  start(profile: StartProfile): Promise<{ id: string }> {
    return this.api.post<{ id: string }>('/loadtest/runs', profile);
  }

  remove(id: string): Promise<unknown> {
    return this.api.delete(`/loadtest/runs/${encodeURIComponent(id)}`);
  }
}
