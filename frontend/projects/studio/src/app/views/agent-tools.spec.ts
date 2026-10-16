import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import type { AgentTool } from '../core/agent-center-api.service';
import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import { type LockWords, firstSentence, groupTools, lockLink, lockText } from './agent-tools';

function wörter(locale: 'de' | 'en'): LockWords {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  const t = (key: string, params?: Record<string, string | number>): string => i18n.t(key, params);
  return {
    t,
    plural: (key, count, params) => t(`${key}.${count === 1 ? 'one' : 'other'}`, { count, ...params }),
    listOr: (parts) => new Intl.ListFormat(locale, { type: 'disjunction' }).format(parts),
  };
}

function werkzeug(name: string, kind: string): AgentTool {
  return { name, kind, description: '', offered: true, locks: [] };
}

describe('groupTools (ST-8b)', () => {
  it('ordnet lesend, kuratierend, virtuell und behält die Reihenfolge je Gruppe', () => {
    const gruppen = groupTools([
      werkzeug('zeige_dokument', 'virtual'),
      werkzeug('wlo_create_content', 'curation'),
      werkzeug('search_wlo_content', 'read'),
      werkzeug('get_skill', 'read'),
    ]);
    expect(gruppen.map((g) => [g.kind, g.tools.map((t) => t.name)])).toEqual([
      ['read', ['search_wlo_content', 'get_skill']],
      ['curation', ['wlo_create_content']],
      ['virtual', ['zeige_dokument']],
    ]);
  });

  it('stellt eine unbekannte Art als eigene Gruppe ans Ende und lässt leere weg', () => {
    const gruppen = groupTools([werkzeug('neu', 'plugin'), werkzeug('get_skill', 'read')]);
    expect(gruppen.map((g) => g.kind)).toEqual(['read', 'plugin']);
  });
});

describe('firstSentence (ST-8b)', () => {
  it('nimmt den ersten Satz', () => {
    expect(firstSentence('Holt den Volltext. Nutze das nur, wenn …')).toBe('Holt den Volltext.');
  });

  // Die Werkzeug-Beschreibungen sind deutsch und voller Abkürzungen.
  it('trennt nicht an Abkürzungen oder Zahlen', () => {
    expect(firstSentence("Filtert eine Sammlung — z.B. 'welche Videos'. Danach mehr."))
      .toBe("Filtert eine Sammlung — z.B. 'welche Videos'.");
    expect(firstSentence('Bulk-Abfrage (max. 50). Spart Round-Trips.')).toBe('Bulk-Abfrage (max. 50).');
  });

  it('endet am ersten Absatz und nimmt einen Text ohne Satzende ganz', () => {
    expect(firstSentence('Erste Zeile\n\nZweiter Absatz. Mehr.')).toBe('Erste Zeile');
    expect(firstSentence('Ohne Punkt am Ende')).toBe('Ohne Punkt am Ende');
    expect(firstSentence('')).toBe('');
  });
});

describe('lockText (ST-8b)', () => {
  it('sagt je Sperre, wann das Werkzeug fehlt', () => {
    const de = wörter('de');
    // Paket 7 (S5): im Studio je MCP-Server ein- und abschaltbar.
    expect(lockText({ code: 'hidden' }, de))
      .toBe('Abgeschaltet unter „MCP-Server“ (search_skill von Haus aus) — dort einschaltbar.');
    // Paket 7 (S4): schreiben nur mit persönlicher Anmeldung oder Gastkonto-Erlaubnis.
    expect(lockText({ code: 'needs_access' }, de))
      .toBe('Nur mit persönlicher WLO-Anmeldung — oder mit dem Gastkonto, wenn es unter '
        + '„Betrieb“ schreiben darf.');
    expect(lockText({ code: 'tool_mode', modes: ['read-only'] }, de))
      .toBe('Fehlt in Einbettungen mit tool-mode read-only.');
    expect(lockText({ code: 'safety_fixed', signals: ['pii'] }, de))
      .toBe('Fällt weg, wenn das Regex-Gate persönliche Daten in der Nachricht erkennt '
        + '(fest im Code).');
    expect(lockText({ code: 'knowledge_areas' }, de))
      .toBe('Nur mit mindestens einem Wissensbereich für den Agenten.');
    expect(lockText({ code: 'host_schema' }, de))
      .toBe('Nur wenn die Einbettung ein Ergebnis-Schema erklärt.');
  });

  it('nennt Policy-Regeln mit ihrer Kennung, in Einzahl und Mehrzahl', () => {
    const de = wörter('de');
    expect(lockText({ code: 'policy', rules: ['keine-wikipedia'] }, de))
      .toBe('Fällt weg, wenn die Policy-Regel keine-wikipedia greift.');
    expect(lockText({ code: 'policy', rules: ['keine-wikipedia', 'policy-rule'] }, de))
      .toBe('Fällt weg, wenn eine der Policy-Regeln keine-wikipedia oder policy-rule greift.');
  });

  it('zeigt einen unbekannten Code und einen unbekannten Anlass roh', () => {
    const de = wörter('de');
    expect(lockText({ code: 'warp' }, de)).toBe('warp');
    expect(lockText({ code: 'safety_fixed', signals: ['nebel'] }, de))
      .toBe('Fällt weg, wenn das Regex-Gate nebel erkennt (fest im Code).');
  });

  it('spricht Englisch', () => {
    const en = wörter('en');
    expect(lockText({ code: 'tool_mode', modes: ['read-only', 'curate'] }, en))
      .toBe('Missing in embeddings with tool-mode read-only or curate.');
    expect(lockText({ code: 'safety_fixed', signals: ['pii'] }, en))
      .toBe('Dropped when the regex gate detects personal data in the message (fixed in code).');
  });
});

describe('lockLink (ST-8b)', () => {
  it('führt zur Seite, auf der die Sperre gepflegt wird', () => {
    expect(lockLink({ code: 'policy', rules: ['x'] })).toBe('identitaet');
    expect(lockLink({ code: 'knowledge_areas' })).toBe('wissen');
    expect(lockLink({ code: 'safety_fixed', signals: ['pii'] })).toBeNull();
    expect(lockLink({ code: 'tool_mode', modes: ['curate'] })).toBeNull();
  });
});
