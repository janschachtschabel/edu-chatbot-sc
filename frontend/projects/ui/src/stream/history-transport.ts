/**
 * Der Verlauf einer Sitzung — `GET /sessions/:id/messages`, render-fertig
 * aufbereitet.
 *
 * Aus `chat-api.ts` gelöst (Review Paket 7, C-3), als die Nachfrage nach einem
 * Stream-Abbruch einen zweiten Zugang brauchte: der Wiederaufbau beim Start
 * schluckt jeden Fehler (er darf den Boot nie brechen), die Nachfrage muss ein
 * Ratenlimit von „noch nichts da“ unterscheiden.
 */
import { httpFehler } from './http-fehler';
import type { HistoryMessage } from './chat-api';

/** Ein Verlaufseintrag, wie die Shell ihn braucht: `web_links`/`query_metas`
 *  aus `ui` auf die Top-Level; ein Typ-Fokus überstimmt stale `web_links` mit
 *  `[]` (Material-Typ-Antwort → keine Webseiten-Inhalte-Box). Nach ALT
 *  api.service.ts:556-602; seit Paket 18C/D aus `ui` statt `debug` — einen
 *  Debug-Block bekommt das Widget ohne Freigabe nicht mehr. */
export function verlaufseintrag(m: any): HistoryMessage {
  const ui = m && typeof m === 'object' && m.ui && typeof m.ui === 'object' ? m.ui : {};
  const wl = ui.type_focus
    ? []
    : (Array.isArray(ui.web_links) ? ui.web_links : undefined);
  const qm = Array.isArray(ui.query_metas) ? ui.query_metas : undefined;
  return { ...m, webLinks: wl, queryMetas: qm };
}

/** Den Verlauf holen. Wirft bei Netz- und HTTP-Fehlern; eine Antwort, die keine
 *  Liste ist, gilt als leerer Verlauf. */
export async function verlaufAbrufen(
  doFetch: typeof fetch, baseUrl: string, sessionId: string, limit: number,
  signal?: AbortSignal, sprache?: string, kopfzeilen: Record<string, string> = {},
): Promise<HistoryMessage[]> {
  const url = `${baseUrl}/sessions/${encodeURIComponent(sessionId)}/messages?limit=${limit}`;
  // Paket AS-Ub (zweites Review, Befund 6): die Sprache des Widgets — der Stand der Ablauf-Leiste
  // trägt den Titel in ihr, wie live. `Accept-Language` löst keinen CORS-Preflight aus.
  // Querschnitts-Review Q-1: dazu der Zugangsblock der Person (`kopfzeilen`) — ihr Verweis gehört
  // ihr, ohne ihn fehlte die Leiste nach dem Neuladen. Wie bei den Zügen nur, wenn angemeldet.
  const kopf = { ...(sprache ? { 'Accept-Language': sprache } : {}), ...kopfzeilen };
  const optionen: RequestInit = {
    ...(signal ? { signal } : {}),
    ...(Object.keys(kopf).length ? { headers: kopf } : {}),
  };
  const resp = await (Object.keys(optionen).length ? doFetch(url, optionen) : doFetch(url));
  if (!resp.ok) throw httpFehler(resp, 'History error');
  const data = await resp.json();
  return Array.isArray(data) ? data.map(verlaufseintrag) : [];
}
