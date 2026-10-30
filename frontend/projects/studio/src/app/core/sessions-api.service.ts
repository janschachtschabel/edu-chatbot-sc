/**
 * The chat sessions as the studio reads them (9-5a).
 *
 * `list()` hits `/sessions/` WITH the trailing slash: that route exists only
 * with one, and without it FastAPI answers a 307 whose Location would leave the
 * BFF (studio-api.service.ts documents why the slash is preserved).
 */
import { Injectable, inject } from '@angular/core';

import { type OriginScope, scopeParams } from './origin-scope';
import { StudioApi } from './studio-api.service';

export interface SessionRow {
  readonly session_id: string;
  readonly persona_id: string;
  readonly state_id: string;
  readonly turn_count: number;
  readonly created_at: string;
  readonly updated_at: string;
}

/**
 * What a turn records about the engine that answered it (AG-1, shown since
 * ST-8a). `token_usage` and `trace` stay `unknown`: they are stored JSON from
 * every backend version since P7, and `views/agent-trace.ts` checks each field
 * instead of trusting a shape.
 */
export interface TraceDebug {
  /** `pattern` | `agent`; empty for turns answered before any engine. */
  readonly engine?: string;
  readonly token_usage?: unknown;
  readonly trace?: unknown;
}

export interface SessionMessageDebug extends TraceDebug {
  readonly pattern?: string;
  readonly persona?: string;
  readonly intent?: string;
  readonly state?: string;
  readonly signals?: readonly string[];
  readonly tools_called?: readonly string[];
  /** The turn record (Paket 18C/D): tool calls with arguments, rewrites,
   *  shortcuts. Stored JSON — `views/zugakte.ts` checks every field. */
  readonly _zugakte?: unknown;
}

export interface SessionMessage {
  readonly id?: number;
  readonly role: string;
  readonly content: string;
  readonly debug?: SessionMessageDebug;
  /** Only for the studio (Paket 18C/D) — its start is the error number. */
  readonly trace_id?: string;
  readonly created_at?: string;
}

/** What a purge across ALL sessions takes (ST-6) — one flag per table, named
 *  as `POST /sessions/purge` reads them. `sessions` cascades in the database
 *  to messages, memory AND `usage_events` (the cost figures). */
export interface PurgeScope {
  readonly messages: boolean;
  readonly memory: boolean;
  readonly quality_logs: boolean;
  readonly safety_logs: boolean;
  readonly sessions: boolean;
}

/** Rows deleted per table — only for the tables the purge was asked to clear. */
export type PurgeCounts = Partial<Record<keyof PurgeScope, number>>;

/** `GET /sessions/db-stats`. `reclaimable_bytes` is an ESTIMATE: the dead-row
 *  share of the whole database size. */
export interface DbStats {
  readonly size_bytes: number;
  readonly live_tuples: number;
  readonly dead_tuples: number;
  readonly reclaimable_bytes: number;
}

/** `POST /sessions/optimize` (a plain `VACUUM (ANALYZE)`, which rarely makes
 *  the file smaller — `reclaimed_bytes` is usually 0). */
export interface OptimizeResult {
  readonly before_bytes: number;
  readonly after_bytes: number;
  readonly reclaimed_bytes: number;
}

/** What has a retention period (Paket 8, A): the conversations — messages and
 *  session memory — and the two logs. Since Paket 9 (V7) also the state of idle
 *  sessions (entities, signals, tour), which is cleared rather than deleted. */
export type RetentionLog =
  'messages' | 'memory' | 'session_state' | 'safety_logs' | 'quality_logs'
  // Paket 16, D1: der Text im Qualitätsprotokoll, mit der Frist der Gesprächsverläufe.
  | 'quality_text';

/** `GET /sessions/retention`, one row per log: period in days (0 = unlimited),
 *  entries due now, oldest entry as ISO time (`null` = the log is empty). */
export interface RetentionRow {
  readonly bereich: RetentionLog;
  readonly tage: number;
  readonly faellig: number;
  readonly aeltester: string | null;
}

/** Rows deleted per log by one retention run. */
export type RetentionCounts = Partial<Record<RetentionLog, number>>;

/** The endpoint's own cap (`_MAX_MESSAGES_LIMIT`), asked for explicitly: the
 *  studio reads a whole conversation, not the widget's 50-message restore. */
const TRANSCRIPT_LIMIT = 200;

@Injectable({ providedIn: 'root' })
export class SessionsApi {
  private readonly api = inject(StudioApi);

  /** `scope` (ST-9) filters by origin on the server — the list is capped at 100,
   *  so filtering here would lose real sessions behind a load test's burst. */
  list(scope: OriginScope = 'all'): Promise<SessionRow[]> {
    return this.api.get<SessionRow[]>('/sessions/', scopeParams(scope));
  }

  messages(sessionId: string): Promise<SessionMessage[]> {
    return this.api.get<SessionMessage[]>(
      `/sessions/${encodeURIComponent(sessionId)}/messages`,
      { limit: TRANSCRIPT_LIMIT },
    );
  }

  deleteSession(sessionId: string): Promise<unknown> {
    return this.api.delete(`/sessions/${encodeURIComponent(sessionId)}`);
  }

  clearMessages(sessionId: string): Promise<unknown> {
    return this.api.delete(`/sessions/${encodeURIComponent(sessionId)}/messages`);
  }

  /**
   * Deletes across ALL sessions. Every flag is sent, the `false` ones too: the
   * endpoint defaults three of them to true, so an omitted flag would delete.
   * `confirm=true` is the endpoint's guard against stray calls — the studio's
   * own confirmation happens before this is called.
   */
  async purge(scope: PurgeScope): Promise<PurgeCounts> {
    const answer = await this.api.post<{ deleted: PurgeCounts }>(
      '/sessions/purge', null, { ...scope, confirm: true },
    );
    return answer.deleted;
  }

  dbStats(): Promise<DbStats> {
    return this.api.get<DbStats>('/sessions/db-stats');
  }

  optimize(): Promise<OptimizeResult> {
    return this.api.post<OptimizeResult>('/sessions/optimize', null);
  }

  async retention(): Promise<RetentionRow[]> {
    const answer = await this.api.get<{ fristen: RetentionRow[] }>('/sessions/retention');
    return answer.fristen;
  }

  /** Brings forward the run the backend makes every six hours; 409 while one
   *  is already running. */
  async runRetention(): Promise<RetentionCounts> {
    const answer = await this.api.post<{ deleted: RetentionCounts }>('/sessions/retention', null);
    return answer.deleted;
  }
}
