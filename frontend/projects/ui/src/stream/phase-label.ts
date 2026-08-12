/**
 * `formatPhaseLabel` (8-4S-d-α) — Verbatim-Port aus ALT `chat/chat-text-utils.ts`.
 * Übersetzt ein SSE-`phase`/`connected`-Event des Chat-Streams (8-3) in ein
 * kurzes Lade-Label für die laufende Bot-Bubble; `null` = kein Label
 * (die Bubble behält ihren Spinner). Konsumiert vom sendMessage-Orchestrator
 * (8-4S-c) über die `SendMessageContext.formatPhaseLabel`-Seam, die die Shell
 * (8-4S-d) an diese Funktion bindet.
 *
 * NEU (boerdi-chat): `ChatStreamEvent` aus `./stream-client` (8-3) statt ALT
 * services/api.service. Struktur verbatim; seit C1-b3 liefert die Map
 * Katalog-Schlüssel statt fertiger deutscher Texte.
 */
import type { TranslateFn } from '../i18n/i18n';
import { ChatStreamEvent } from './stream-client';

/** Bekannte SSE-Schritte → Katalog-Schlüssel. Bewusst eine ERLAUBNISLISTE und
 *  kein `'phase.' + step`: ein unbekannter Schritt muss `null` ergeben, sonst
 *  gäbe der Übersetzer den Schlüssel selbst zurück und in der Bubble stünde
 *  „phase.irgendwas". */
const SCHRITT_SCHLUESSEL: Record<string, string> = {
  // Muster-Engine (der Vorgabe-Weg).
  'safety_classify': 'phase.safety_classify',
  'context': 'phase.context',
  'policy': 'phase.policy',
  'pattern': 'phase.pattern',
  'wlo_search': 'phase.wlo_search',
  'topic_content': 'phase.topic_content',
  'response': 'phase.response',
  'query_meta': 'phase.query_meta',
  // Agent-Modus (A6). Ohne diese zwei fror das Etikett auf „Formuliere
  // Antwort …" ein — dem einen `progress.start`, das `respond_agent` beim
  // Eintritt setzt —, und zwar für den GANZEN Lauf: `send-message.ts` behält
  // bei `null` das vorige Label. Ausgerechnet die langsamste Phase des Agenten
  // (Werkzeugaufrufe, gemessen 1,2–23,3 s) meldete damit nichts.
  // Der Werkzeugname aus `data.tool` bleibt bewusst draußen (siehe Katalog).
  'agent_iteration': 'phase.agent_iteration',
  'agent_tool': 'phase.agent_tool',
};

/** SSE-`phase`/`connected`-Event → Lade-Label; `null` = kein Label. */
export function formatPhaseLabel(evt: ChatStreamEvent, t: TranslateFn): string | null {
  if (!evt) return null;
  if (evt.event === 'connected') return t('phase.connected');
  if (evt.event !== 'phase') return null;
  const data = evt.data || {};
  if (data.kind === 'end') return null; // ignore end to avoid flicker
  const key = SCHRITT_SCHLUESSEL[String(data.step || '')];
  return key ? t(key) : null;
}
