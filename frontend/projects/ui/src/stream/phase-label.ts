/**
 * `formatPhaseLabel` (8-4S-d-α) — Verbatim-Port aus ALT `chat/chat-text-utils.ts`.
 * Übersetzt ein SSE-`phase`/`connected`-Event des Chat-Streams (8-3) in ein
 * kurzes deutsches Lade-Label für die laufende Bot-Bubble; `null` = kein Label
 * (die Bubble behält ihren Spinner). Konsumiert vom sendMessage-Orchestrator
 * (8-4S-c) über die `SendMessageContext.formatPhaseLabel`-Seam, die die Shell
 * (8-4S-d) an diese Funktion bindet.
 *
 * NEU (boerdi-chat): `ChatStreamEvent` aus `./stream-client` (8-3) statt ALT
 * services/api.service. Body + step→Label-Map verbatim — KEINE Logik-Änderung.
 */
import { ChatStreamEvent } from './stream-client';

/** SSE-`phase`/`connected`-Event → deutsches Lade-Label; `null` = kein Label. */
export function formatPhaseLabel(evt: ChatStreamEvent): string | null {
  if (!evt) return null;
  if (evt.event === 'connected') return 'Verbinde …';
  if (evt.event !== 'phase') return null;
  const data = evt.data || {};
  if (data.kind === 'end') return null; // ignore end to avoid flicker
  const step = String(data.step || '');
  const map: Record<string, string> = {
    'safety_classify': 'Verstehe deine Anfrage …',
    'context': 'Lade Sitzungs-Kontext …',
    'policy': 'Prüfe Datenschutz …',
    'pattern': 'Wähle die passende Antwort …',
    'wlo_search': 'Durchsuche WLO-Inhalte …',
    'topic_content': 'Lade Themenseiten-Inhalte …',
    'response': 'Formuliere Antwort …',
    'query_meta': 'Suchergebnisse zusammengestellt',
  };
  return map[step] || null;
}
