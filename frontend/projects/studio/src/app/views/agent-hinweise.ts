/**
 * Hinweise der Agent-Seiten (Rundgang 3). Im Agent-Modus klassifiziert niemand: die Persona
 * bleibt `P-AND`, das Anliegen `I01` (`graph/nodes/assess.py`). Eine Regel mit anderer
 * Bedingung greift dort nie. Gelesen wie `domain/policy.assess_policy`: ein vorhandener
 * Schlüssel ist eine Bedingung (auch leer); `pattern` prüft das Backend nicht (Review A-1).
 */
import type { Hinweis } from './curated-views';

const AGENT_TRAEGT: Readonly<Record<string, string>> = {
  persona: 'P-AND',
  intent: 'I01',
};

/** Greift die Regel im Agent-Modus? Nachrichten-Muster und fehlende Bedingungen: ja. */
export function regelWirktImAgentModus(regel: Readonly<Record<string, unknown>>): boolean {
  const match = (regel['match'] ?? {}) as Readonly<Record<string, unknown>>;
  return Object.entries(AGENT_TRAEGT).every(([feld, wert]) =>
    !Object.hasOwn(match, feld) || match[feld] === wert);
}

/** Werkzeug-Regelwerk auf „Rolle & Schutz“: welche Regeln dort nicht greifen. */
export function policyHinweise(doc: Readonly<Record<string, unknown>>): readonly Hinweis[] {
  const regeln = Array.isArray(doc['rules'])
    ? (doc['rules'] as readonly Readonly<Record<string, unknown>>[]) : [];
  const ohne = regeln.filter((r) => !regelWirktImAgentModus(r)).map((r) => String(r['id'] ?? '?'));
  return ohne.length
    ? [{ key: 'curated.agentRolle.policy.hinweis.ohneWirkung', params: { regeln: ohne.join(', ') } }]
    : [];
}
