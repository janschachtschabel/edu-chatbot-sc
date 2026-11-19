import { describe, expect, it } from 'vitest';

import { FIELDS_ABLAEUFE } from './fields-ablaeufe';

/**
 * Paket K9 (Plan 2026-11-17): Das Studio hat keine Person — seine Flow-Liste kommt über den Schlüssel
 * der Anlage. Welche Flows der WLO-MCP mit einer Anmeldung wirklich startet, legt dort
 * `WLO_BAPI_FLOWS` fest; das sagt der Hinweis am Flow-Feld in beiden Sprachen. Paket K7: „Gesperrt“
 * nennt den dritten Knopf „Später weitermachen“.
 */
describe('fields-ablaeufe (K7, K9)', () => {
  it('der Flow-Hinweis nennt WLO_BAPI_FLOWS des MCP', () => {
    for (const sprache of ['de', 'en'] as const) {
      expect(FIELDS_ABLAEUFE[sprache]['feld.Schritt.flow.hint']).toContain('WLO_BAPI_FLOWS');
    }
  });

  it('der Hinweis zu „warten“ nennt „Später weitermachen“', () => {
    expect(FIELDS_ABLAEUFE.de['feld.Schritt.warten.hint']).toContain('„Später weitermachen“');
    expect(FIELDS_ABLAEUFE.en['feld.Schritt.warten.hint']).toContain('“Continue later”');
  });

  // Review B8: „Später weitermachen“ hebt die Sperre für die Sitzung auf
  it('der Hinweis zu „warten“ sagt, dass „Später“ die Sperre für die Sitzung aufhebt', () => {
    expect(FIELDS_ABLAEUFE.de['feld.Schritt.warten.hint']).toContain('hebt die Sperre für diese Sitzung auf');
    expect(FIELDS_ABLAEUFE.en['feld.Schritt.warten.hint']).toContain('lifts the lock for this session');
  });

  // Review A4/A7: nur ein Schritt mit dem Vermerk geht über den MCP — dort muss der Flow freigegeben sein
  it('der Hinweis zu repo_schreibt nennt den MCP-Weg und WLO_BAPI_FLOWS', () => {
    for (const sprache of ['de', 'en'] as const) {
      const hinweis = FIELDS_ABLAEUFE[sprache]['feld.Schritt.repo_schreibt.hint'];
      expect(hinweis).toContain('WLO_BAPI_FLOWS');
      expect(hinweis).toContain('node-metadata-write');
    }
  });
});
