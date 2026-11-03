import { describe, expect, it } from 'vitest';

import type { UiModulManifest } from '@boerdi/ui-module';

import {
  type UiModulEintrag, feldUebersicht, mitSchalter, schalterAus, vorschauKontext, zustand,
} from './ui-module';

/** Paket U1-f: die reinen Regeln der Seite „UI-Module“ — Schalter im Bereichsdokument
 *  `01-base/display-rules` (`display_rules.ui_module`), Zustand je Modul, Feldübersicht. */

function eintrag(name: string, schaltbar = { aktiv: true, agent: true }): UiModulEintrag {
  const manifest = { name, version: 1, art: 'anzeigen', titel: { de: name }, beschreibung: '',
    eingabe: { type: 'object', properties: {} }, textfassung: { vorlage: 'markdown' },
    beispiele: [] } as unknown as UiModulManifest;
  return { name, manifest, schaltbar, abgeleitet: false };
}

describe('schalterAus', () => {
  it('liest die Ausschalt-Listen und nimmt fehlende als leer', () => {
    expect(schalterAus(null)).toEqual({ aus: [], agent_aus: [] });
    expect(schalterAus({ display_rules: {} })).toEqual({ aus: [], agent_aus: [] });
    expect(schalterAus({ display_rules: { ui_module: { aus: ['ui_linkbox'] } } }))
      .toEqual({ aus: ['ui_linkbox'], agent_aus: [] });
  });

  it('verträgt kaputten Bestand (nur Texte zählen)', () => {
    expect(schalterAus({ display_rules: { ui_module: { aus: 'ui_linkbox', agent_aus: [3, 'ui_x_y'] } } }))
      .toEqual({ aus: [], agent_aus: ['ui_x_y'] });
  });
});

describe('mitSchalter', () => {
  const doc = { display_rules: { groups: { webseiten_max: 3 } }, fremd: 1 };

  it('schaltet aus und wieder an, sortiert, und lässt den Rest des Dokuments stehen', () => {
    const aus = mitSchalter(doc, 'ui_trefferliste', 'aktiv', false);
    const beide = mitSchalter(aus, 'ui_linkbox', 'aktiv', false);
    expect(beide).toEqual({
      display_rules: { groups: { webseiten_max: 3 },
        ui_module: { aus: ['ui_linkbox', 'ui_trefferliste'], agent_aus: [] } },
      fremd: 1,
    });
    expect(schalterAus(mitSchalter(beide, 'ui_linkbox', 'aktiv', true)).aus).toEqual(['ui_trefferliste']);
    expect(doc).toEqual({ display_rules: { groups: { webseiten_max: 3 } }, fremd: 1 });   // unverändert
  });

  it('„für den Agenten“ schreibt agent_aus und lässt aus unberührt', () => {
    const neu = mitSchalter(doc, 'ui_entscheidung', 'agent', false);
    expect(schalterAus(neu)).toEqual({ aus: [], agent_aus: ['ui_entscheidung'] });
    expect(schalterAus(mitSchalter(neu, 'ui_entscheidung', 'agent', false)).agent_aus)
      .toEqual(['ui_entscheidung']);           // kein Doppel
  });
});

describe('zustand', () => {
  it('ohne Eintrag ist ein Modul an', () => {
    expect(zustand(eintrag('ui_entscheidung'), { aus: [], agent_aus: [] }))
      .toEqual({ aktiv: true, agent: true });
  });

  it('aus heißt auch nicht für den Agenten', () => {
    expect(zustand(eintrag('ui_entscheidung'), { aus: ['ui_entscheidung'], agent_aus: [] }))
      .toEqual({ aktiv: false, agent: false });
  });

  it('ohne Agent-Schalter steht dort null, ein festes Modul ist immer aktiv', () => {
    expect(zustand(eintrag('ui_linkbox', { aktiv: true, agent: false }), { aus: [], agent_aus: [] }))
      .toEqual({ aktiv: true, agent: null });
    expect(zustand(eintrag('ui_inhaltsrahmen', { aktiv: false, agent: false }),
      { aus: ['ui_inhaltsrahmen'], agent_aus: [] })).toEqual({ aktiv: true, agent: null });
  });
});

describe('feldUebersicht', () => {
  it('nennt Felder mit Typ, Pflicht, Beschreibung, Werten und Systemwerten', () => {
    const felder = feldUebersicht({
      type: 'object', required: ['titel'],
      properties: {
        titel: { type: 'string', description: 'Überschrift' },
        art: { enum: ['dokument', 'volltext'], 'x-nur-system': ['volltext'] },
        optionen: { type: 'array', items: { type: 'object' } },
        zahl: { type: ['integer', 'null'] },
      },
    });
    expect(felder).toEqual([
      { name: 'titel', typ: 'string', pflicht: true, beschreibung: 'Überschrift', werte: [], nurSystem: [] },
      { name: 'art', typ: 'enum', pflicht: false, beschreibung: '', werte: ['dokument', 'volltext'],
        nurSystem: ['volltext'] },
      { name: 'optionen', typ: 'array<object>', pflicht: false, beschreibung: '', werte: [], nurSystem: [] },
      { name: 'zahl', typ: 'integer | null', pflicht: false, beschreibung: '', werte: [], nurSystem: [] },
    ]);
  });

  it('ohne Schema keine Felder', () => {
    expect(feldUebersicht(undefined)).toEqual([]);
    expect(feldUebersicht({ type: 'object' })).toEqual([]);
  });
});

describe('vorschauKontext', () => {
  const beispiel = { titel: 'x', daten: {}, antwort: { gewaehlt: ['a'] } };

  it('ein beantwortet gezeigtes Beispiel steht nur lesend mit seiner Antwort', () => {
    expect(vorschauKontext('ui_entscheidung', 1, 'en', beispiel, true))
      .toEqual({ blockId: 'vorschau-ui-entscheidung-1', sprache: 'en', nurLesen: true,
        antwort: { gewaehlt: ['a'] }, schriftSkala: 0.85, anzeigeRegeln: null });
  });

  it('sonst ist es offen — auch ein Beispiel mit Antwort', () => {
    expect(vorschauKontext('ui_entscheidung', 1, 'de', beispiel, false))
      .toMatchObject({ nurLesen: false, antwort: null });
    expect(vorschauKontext('ui_linkbox', 0, 'de', { titel: 'x', daten: {} }, true).nurLesen).toBe(false);
  });
});
