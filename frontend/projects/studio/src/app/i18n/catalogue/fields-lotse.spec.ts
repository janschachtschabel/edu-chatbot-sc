import { describe, expect, it } from 'vitest';

import { FIELDS_LOTSE } from './fields-lotse';

/**
 * Rundgang 3: „Vertraute Domains“ und „Freigegebene Hosts“ sind zwei Listen mit zwei Aufgaben.
 * Wohin Lotsen-Knöpfe führen, regeln die freigegebenen Hosts (`guide_markers.py`); die
 * vertrauten Domains nehmen nur die Sitzung mit und schalten die Warnung „Externe URL“ ab
 * (`ui/src/session/trusted-host.ts`). Der Hilfetext verwechselte beides.
 */
describe('Hilfetexte Lotse', () => {
  const de = FIELDS_LOTSE.de as Record<string, string>;
  const en = FIELDS_LOTSE.en as Record<string, string>;

  it('schreibt das Führen den freigegebenen Hosts zu, nicht den vertrauten Domains', () => {
    expect(de['feld.GuideModeBlock.trusted_domains.hint']).not.toContain('führen dürfen');
    expect(de['feld.GuideModeBlock.trusted_domains.hint']).toContain('Externe URL');
    expect(en['feld.GuideModeBlock.trusted_domains.hint']).not.toContain('may lead to');
    expect(de['feld.GuideModeBlock.allowed_hosts.hint']).toContain('führt');
  });
});
