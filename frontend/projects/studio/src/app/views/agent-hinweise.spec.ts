import { describe, expect, it } from 'vitest';

import { policyHinweise, regelWirktImAgentModus } from './agent-hinweise';

/**
 * Rundgang 3: Im Agent-Modus gibt es keinen Klassifikator — die Persona bleibt P-AND, das
 * Anliegen I01, das Muster heißt AGENT (`assess.py`, `domain/agent_pattern.py`). Regeln mit
 * einer anderen Bedingung greifen dort nie; die Presse-Regel (P-RED) fiel genau darunter.
 */
describe('regelWirktImAgentModus', () => {
  it('lässt Regeln ohne Bedingung oder nur mit Nachrichten-Muster gelten', () => {
    expect(regelWirktImAgentModus({ match: { message_regex: 'passwort' } })).toBe(true);
    expect(regelWirktImAgentModus({ match: {} })).toBe(true);
    expect(regelWirktImAgentModus({})).toBe(true);
  });

  it('erkennt Persona- und Anliegen-Bedingungen, die der Agent nie erfüllt', () => {
    expect(regelWirktImAgentModus({ match: { persona: 'P-RED' } })).toBe(false);
    expect(regelWirktImAgentModus({ match: { intent: 'I05' } })).toBe(false);
  });

  it('liest die Bedingung wie das Backend (Review A-1): vorhanden heißt Bedingung', () => {
    // `assess_policy` prüft `"persona" in match` — ein leerer Wert trifft nie.
    expect(regelWirktImAgentModus({ match: { persona: '' } })).toBe(false);
    expect(regelWirktImAgentModus({ match: { intent: null } })).toBe(false);
    // `pattern` kennt `assess_policy` nicht — die Regel greift in beiden Modi.
    expect(regelWirktImAgentModus({ match: { pattern: 'M09' } })).toBe(true);
  });

  it('lässt die Werte gelten, die der Agent immer trägt', () => {
    expect(regelWirktImAgentModus({ match: { persona: 'P-AND' } })).toBe(true);
    expect(regelWirktImAgentModus({ match: { intent: 'I01' } })).toBe(true);
  });
});

describe('policyHinweise', () => {
  it('nennt die Regeln, die im Agent-Modus nicht greifen', () => {
    const doc = { rules: [
      { id: 'pol-presse-only-public', match: { persona: 'P-RED' } },
      { id: 'pol-no-personal-data-search', match: { message_regex: 'x' } },
    ] };
    expect(policyHinweise(doc)).toEqual([{
      key: 'curated.agentRolle.policy.hinweis.ohneWirkung',
      params: { regeln: 'pol-presse-only-public' },
    }]);
  });

  it('schweigt, wenn alle Regeln greifen oder es keine gibt', () => {
    expect(policyHinweise({ rules: [{ id: 'a', match: { message_regex: 'x' } }] })).toEqual([]);
    expect(policyHinweise({})).toEqual([]);
  });
});
