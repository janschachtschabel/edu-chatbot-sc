/**
 * The chat sessions as the studio reads them (9-5a).
 *
 * `list()` hits `/sessions/` WITH the trailing slash: that route exists only
 * with one, and without it FastAPI answers a 307 whose Location would leave the
 * BFF (studio-api.service.ts documents why the slash is preserved).
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

export interface SessionRow {
  readonly session_id: string;
  readonly persona_id: string;
  readonly state_id: string;
  readonly turn_count: number;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface SessionMessageDebug {
  readonly pattern?: string;
  readonly persona?: string;
  readonly intent?: string;
  readonly state?: string;
  readonly signals?: readonly string[];
  readonly tools_called?: readonly string[];
}

export interface SessionMessage {
  readonly id?: number;
  readonly role: string;
  readonly content: string;
  readonly debug?: SessionMessageDebug;
  readonly created_at?: string;
}

/** The endpoint's own cap (`_MAX_MESSAGES_LIMIT`), asked for explicitly: the
 *  studio reads a whole conversation, not the widget's 50-message restore. */
const TRANSCRIPT_LIMIT = 200;

@Injectable({ providedIn: 'root' })
export class SessionsApi {
  private readonly api = inject(StudioApi);

  list(): Promise<SessionRow[]> {
    return this.api.get<SessionRow[]>('/sessions/');
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
}
