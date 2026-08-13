/**
 * Der Agent-Endpunkt, wie das Studio ihn ruft (2026-08-13).
 *
 * `POST /api/agent` startet die **echte** Agent-Schleife: bis zu einem Dutzend
 * LLM-Runden plus MCP-Werkzeuge. Er kostet also Geld und Staging-Kapazität —
 * derselbe Rang wie der Lasttest, und die Ansicht sagt das vor dem Knopf.
 *
 * Der Schlüssel bleibt serverseitig: `StudioApi` schickt an `/studio/api/agent`,
 * die Proxy-Middleware schreibt auf `/api/agent` um und spritzt `X-Studio-Key`
 * ein. Genau deshalb ist das Studio der richtige Ort für dieses Werkzeug — eine
 * öffentliche Demo-Seite müsste den Admin-Schlüssel im Browser halten.
 *
 * Kein Streaming: `/api/agent/stream` sendet nur `phase`-Ereignisse, keine
 * Token (`run_agent_loop` hat keinen `on_token`-Haken). Für ein Formular, das
 * am Ende ein Ergebnis zeigt, wäre der Strom Aufwand ohne Gewinn.
 */
import { Injectable, inject } from '@angular/core';

import type { Translate } from '../i18n/studio-language.service';
import type { AgentRequestBody } from '../views/agent-request';
import { StudioApiError } from './studio-api-error';
import { StudioApi } from './studio-api.service';

/** Was `AgentResponse` (`schemas_agent.py`) zurückgibt. */
export interface AgentResult {
  readonly text: string;
  /** Frei geformt — was `result_schema` verlangt hat, oder `null`. */
  readonly result: unknown;
  /**
   * Warum der Lauf endete. Gehört zur Antwort und nicht ins Protokoll: ein an
   * der Frist abgeschnittener Lauf sähe von aussen sonst aus wie einer, der
   * fertig wurde.
   */
  readonly stop_reason: string;
  readonly iterations: number;
  readonly tools_called: readonly string[];
}

@Injectable({ providedIn: 'root' })
export class AgentApi {
  private readonly api = inject(StudioApi);

  run(request: AgentRequestBody): Promise<AgentResult> {
    return this.api.post<AgentResult>('/agent', request);
  }
}

/**
 * Ein gescheiterter Lauf, in einem Satz — Muster `describeRagError`.
 *
 * Die drei benannten Fälle sind die, bei denen der Text des Servers dem Nutzer
 * NICHT sagt, was zu tun ist: 403 nennt keine Ursache, 429 keine Wartezeit,
 * und 0 kommt gar nicht vom Server. Alles andere kommt durch, wie es ankommt —
 * eine 422 benennt das Feld, und das ist besser als jeder eigene Satz.
 */
export function describeAgentError(err: unknown, t: Translate): string {
  if (!(err instanceof StudioApiError)) return t('error.unexpected');
  switch (err.status) {
    case 0:
      return t('error.offline');
    case 401:
    case 403:
      return t('agent.error.forbidden');
    case 429:
      return t('agent.error.rateLimit');
    default:
      return err.detail || t('error.unknown');
  }
}
