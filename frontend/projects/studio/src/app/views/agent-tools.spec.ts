import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import type { AgentTool } from '../core/agent-center-api.service';
import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { McpServer } from '../core/mcp-registry-store';
import {
  type LockWords, firstSentence, groupTools, herkunftVon, lockLink, lockText, schalterFuer,
} from './agent-tools';

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
      .toBe('Abgeschaltet (search_skill von Haus aus) — hier in der Spalte „Anbieten“ einschaltbar.');
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


describe('schalterFuer (Paket 15)', () => {
  const server = (id: string, katalog: string[]): McpServer => ({
    id, name: id.toUpperCase(), url: '', description: '', enabled: true,
    werkzeuge_im_katalog: katalog,
  });
  const SERVERS = [server('wlo-mcp', ['get_skill', 'search_skill']), server('fremd', ['suche'])];

  it('findet den Server, dessen Katalog das Werkzeug führt', () => {
    expect(schalterFuer(werkzeug('get_skill', 'read'), SERVERS))
      .toEqual({ index: 0, name: 'get_skill', server: 'WLO-MCP' });
  });

  it('nimmt bei fremden Werkzeugen Server und Originalnamen aus der Zeile (Review-Runde 2)', () => {
    // Der Modellname ist bereinigt und gekürzt — zurückrechnen ging bei langen Namen schief.
    const lang = 'ein_sehr_langes_werkzeug_mit_vielen_zeichen.v2';
    const servers = [...SERVERS, server('fremd.dienst', [lang])];
    const zeile = { ...werkzeug('fremd_dienst__ein_sehr_langes_werkzeug_mit', 'external'),
      server_id: 'fremd.dienst', tool: lang };
    expect(schalterFuer(zeile, servers)).toEqual({ index: 2, name: lang, server: 'FREMD.DIENST' });
    expect(schalterFuer({ ...werkzeug('fremd__suche', 'external'), server_id: 'fremd', tool: 'suche' },
      SERVERS)).toEqual({ index: 1, name: 'suche', server: 'FREMD' });
  });

  it('schaltet WLO-Werkzeuge nur am WLO-Server, nie an einem gleichnamigen fremden', () => {
    const vorn = [server('fremd', ['get_skill']), server('wlo-mcp', ['get_skill'])];
    expect(schalterFuer(werkzeug('get_skill', 'read'), vorn))
      .toEqual({ index: 1, name: 'get_skill', server: 'WLO-MCP' });
  });

  it('hat keinen Schalter für eingebaute und nicht schaltbare Werkzeuge', () => {
    expect(schalterFuer(werkzeug('zeige_dokument', 'virtual'), SERVERS)).toBeNull();
    expect(schalterFuer(werkzeug('wlo_create_content', 'curation'), SERVERS)).toBeNull();
    expect(schalterFuer(werkzeug('fremd__schreibe', 'external'), SERVERS)).toBeNull();
  });
});

describe('herkunftVon (Paket 16, C7)', () => {
  const servers = [
    { id: 'wlo-mcp', name: 'WLO', url: 'https://wlo.example/mcp', description: '', enabled: true },
    { id: 'wikidata', name: 'Wikidata', url: 'https://wd.example:8443/mcp', description: '',
      enabled: true },
  ] as McpServer[];
  const tool = (t: Partial<AgentTool>): AgentTool =>
    ({ name: 'x', kind: 'read', offered: true, description: '', locks: [], ...t }) as AgentTool;

  it('nennt die Art unabhängig vom Schalter, dazu Server und Host', () => {
    expect(herkunftVon(tool({ kind: 'read' }), servers))
      .toEqual({ art: 'wlo', server: 'WLO', host: 'wlo.example' });
    expect(herkunftVon(tool({ kind: 'curation' }), servers).art).toBe('wlo');
    expect(herkunftVon(tool({ kind: 'external', server_id: 'wikidata' }), servers))
      .toEqual({ art: 'fremd', server: 'Wikidata', host: 'wd.example:8443' });
    expect(herkunftVon(tool({ kind: 'virtual' }), servers))
      .toEqual({ art: 'eingebaut', server: '', host: '' });
  });

  it('nennt die Server-Kennung, solange die Liste fehlt, und verträgt eine kaputte URL', () => {
    expect(herkunftVon(tool({ kind: 'external', server_id: 'wikidata' }), []))
      .toEqual({ art: 'fremd', server: 'wikidata', host: '' });
    const kaputt = [{ ...servers[0], url: 'kein url' }] as McpServer[];
    expect(herkunftVon(tool({ kind: 'read' }), kaputt))
      .toEqual({ art: 'wlo', server: 'WLO', host: '' });
  });
});
