/**
 * Action-Quick-Reply-Parser (Magic-Prefix ``__action__|``) — Gegenstück zu
 * ``guide-qr.ts`` für backend-definierte Direct-Action-Pills (§7 `ui/chips`).
 * Verbatim port of ALT `chat/action-qr.ts` (behaviour pinned by the ported
 * action-qr.spec.ts). No logic change.
 *
 * Konvention (Backend → Frontend):
 *
 *   __action__|<Anzeige-Label>|<action>|<params-json>
 *
 * Label und action dürfen kein ``|`` enthalten; der params-JSON-Teil ist der
 * Rest NACH dem 3. ``|`` und darf ``|`` enthalten. Klick sendet einen
 * Direct-Action-Turn (``action`` + ``action_params``) statt einer Textnachricht.
 * Bei kaputtem JSON fällt der Aufrufer auf „Label als normale Nachricht" zurück.
 */

export const ACTION_QR_PREFIX = '__action__|';

export interface ParsedActionQr {
  label: string;
  action: string;
  params: Record<string, unknown>;
}

/** True, wenn der Quick-Reply-String ein Action-Pill (Magic-Prefix) ist. */
export function isActionQuickReply(qr: string): boolean {
  return typeof qr === 'string' && qr.startsWith(ACTION_QR_PREFIX);
}

/**
 * Parse ``__action__|<label>|<action>|<params-json>``. Splittet nur auf die
 * ersten beiden ``|`` NACH dem Präfix — der params-JSON-Teil (Rest) bleibt
 * intakt, auch wenn er ``|`` enthält. Gibt ``null`` zurück, wenn Struktur oder
 * JSON ungültig sind (dann sendet der Aufrufer das Label als Textnachricht).
 */
export function parseActionQuickReply(qr: string): ParsedActionQr | null {
  if (!isActionQuickReply(qr)) return null;
  const rest = qr.slice(ACTION_QR_PREFIX.length);
  const i1 = rest.indexOf('|');
  if (i1 === -1) return null;
  const i2 = rest.indexOf('|', i1 + 1);
  if (i2 === -1) return null;
  const label = rest.slice(0, i1).trim();
  const action = rest.slice(i1 + 1, i2).trim();
  const paramsJson = rest.slice(i2 + 1);
  if (!label || !action) return null;
  try {
    const params = JSON.parse(paramsJson);
    if (params && typeof params === 'object' && !Array.isArray(params)) {
      return { label, action, params: params as Record<string, unknown> };
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Anzeige-Label für ein Action-Pill. Für Nicht-Action-Strings kommt der String
 * unverändert zurück; für strukturell-erkannte aber kaputte Pills wird das
 * Label-Segment extrahiert (nie der rohe Magic-String).
 */
export function actionQuickReplyLabel(qr: string): string {
  if (!isActionQuickReply(qr)) return qr;
  const rest = qr.slice(ACTION_QR_PREFIX.length);
  const i1 = rest.indexOf('|');
  const label = (i1 === -1 ? rest : rest.slice(0, i1)).trim();
  return label || qr;
}
