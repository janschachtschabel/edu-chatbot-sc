/**
 * Der Verlauf einer Sitzung — `GET /sessions/:id/messages`, render-fertig
 * aufbereitet.
 *
 * Aus `chat-api.ts` gelöst (Review Paket 7, C-3), als die Nachfrage nach einem
 * Stream-Abbruch einen zweiten Zugang brauchte: der Wiederaufbau beim Start
 * schluckt jeden Fehler (er darf den Boot nie brechen), die Nachfrage muss ein
 * Ratenlimit von „noch nichts da“ unterscheiden.
 */
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

/** Ein nicht-ok-Abruf als Fehler: mit `status` und — wenn der Server sagt, wann
 *  es wieder geht — `retryAfterMs`. */
function abrufFehler(resp: Response): Error {
  // ``0`` heißt „sofort“ und nicht „fehlt“ (Paket 9); ein fehlender Kopf ergäbe
  // über ``Number(null)`` ebenfalls 0 und wird deshalb vorher ausgeschieden.
  const roh = resp.headers?.get?.('Retry-After');
  const sekunden = roh == null || !roh.trim() ? NaN : Number(roh);
  return Object.assign(new Error(`History error: ${resp.status}`), {
    status: resp.status,
    ...(Number.isFinite(sekunden) && sekunden >= 0 ? { retryAfterMs: sekunden * 1000 } : {}),
  });
}

/** Den Verlauf holen. Wirft bei Netz- und HTTP-Fehlern; eine Antwort, die keine
 *  Liste ist, gilt als leerer Verlauf. */
export async function verlaufAbrufen(
  doFetch: typeof fetch, baseUrl: string, sessionId: string, limit: number,
  signal?: AbortSignal,
): Promise<HistoryMessage[]> {
  const url = `${baseUrl}/sessions/${encodeURIComponent(sessionId)}/messages?limit=${limit}`;
  const resp = await (signal ? doFetch(url, { signal }) : doFetch(url));
  if (!resp.ok) throw abrufFehler(resp);
  const data = await resp.json();
  return Array.isArray(data) ? data.map(verlaufseintrag) : [];
}
