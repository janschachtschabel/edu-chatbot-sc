/**
 * Der Chat-Probelauf der Agent-Seite (ST-8e, AG-4 Teil A): ein Zug über
 * `POST /api/chat` mit `X-Boerdi-Engine: agent` — derselbe Weg wie im Widget,
 * also mit Master-Skill, Safety und Nutzungsbuchung. Der Auftrags-Tester daneben
 * fährt `/api/agent`, den Endpunkt der Gastanwendungen, mit eigenem Prompt.
 *
 * Die Sitzungen heißen `studio-<uuid>`: `services/session_origin.py` zählt sie
 * nicht als echte Gespräche (`STUDIO_PREFIX`).
 */
import { Injectable, inject } from '@angular/core';

import type { TraceDebug } from './sessions-api.service';
import { StudioApi } from './studio-api.service';

/** `STUDIO_PREFIX` in `backend/src/boerdi/services/session_origin.py`. */
export const PROBE_SESSION_PREFIX = 'studio-';

/** Was der Probelauf aus `ChatResponse` liest. */
export interface ChatProbeResponse {
  readonly content: string;
  /** `null` ohne Freigabe (Paket 18C/D, Phase 4). */
  readonly debug?: TraceDebug | null;
  readonly cards?: readonly unknown[];
  readonly inline_documents?: readonly { readonly title?: string }[];
}

/**
 * Eine neue Sitzungskennung. `randomUUID` gibt es nur in sicheren Kontexten
 * (https, localhost); sonst dieselben 128 Zufallsbits als Hex, wie im Widget
 * (`ui/src/session/session-id.ts`).
 */
export function newProbeSession(): string {
  if (typeof crypto.randomUUID === 'function') return PROBE_SESSION_PREFIX + crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return PROBE_SESSION_PREFIX + Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

@Injectable({ providedIn: 'root' })
export class ChatProbeApi {
  private readonly api = inject(StudioApi);

  turn(sessionId: string, message: string, locale: string): Promise<ChatProbeResponse> {
    return this.api.post<ChatProbeResponse>(
      '/chat',
      { session_id: sessionId, message, environment: { locale } },
      undefined,
      { 'X-Boerdi-Engine': 'agent' },
    );
  }
}
