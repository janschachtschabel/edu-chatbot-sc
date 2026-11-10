import { describe, expect, it } from 'vitest';

import {
  artVon, eigenerSchritt, fehlerVon, mitWahl, regelFehlerOrte, regelFehlerVon, regelnAus, schritteAus, teileAus,
  wahlenAus, weiterAus,
} from './weiter-regeln';

/**
 * AS-2a (Plan 2026-11-09): `weiter` eines Ablaufschritts ohne JSON — die reinen Regeln des
 * Editors. `weiter` ist leer (der folgende Schritt), eine Schritt-Kennung oder eine Liste von Regeln
 * (`wenn_gewaehlt`/`wenn_teil` → `dann`, zuletzt `sonst`).
 */
const DOK = { id: 'a', schritte: [
  { id: 'frage', typ: 'modul', modul: 'ui_entscheidung',
    daten: { frage: '?', optionen: [{ id: 'ja', label: 'Ja' }, { id: 'nein', label: 'Nein' }] } },
  { id: 'entwurf', typ: 'werkzeug', schreibt: 'draft' },
  { id: 'ki', typ: 'agent', agent: { ausgabe: 'notiz' } },
  { id: 'wohin', typ: 'verzweigung' },
  { id: 'ende', typ: 'ende' },
] };

describe('weiter-regeln (AS-2a)', () => {
  it('erkennt die Art', () => {
    expect(artVon(undefined)).toBe('folge');
    expect(artVon(null)).toBe('folge');
    expect(artVon('')).toBe('folge');
    expect(artVon('ende')).toBe('schritt');
    expect(artVon([{ wenn_gewaehlt: 'ja', dann: 'ende' }, { sonst: 'frage' }])).toBe('regeln');
    // eine Regel mit zwei Bedingungen oder fremden Feldern kann der Editor nicht zeigen
    expect(artVon([{ wenn_gewaehlt: 'ja', wenn_teil: 'draft', dann: 'ende' }])).toBe('json');
    expect(artVon([{ dann: 'ende', mehr: 1 }])).toBe('json');
    expect(artVon(5)).toBe('json');
    // eine halbe Regel aus dem Editor bleibt eine Regel (sonst kippte die Ansicht beim Tippen)
    expect(artVon([{ wenn_gewaehlt: '', dann: '' }])).toBe('regeln');
    expect(regelnAus([{ wenn_teil: '', dann: '' }, { sonst: '' }])).toEqual([
      { bedingung: 'teil', wert: '', ziel: '' }, { bedingung: 'sonst', wert: '', ziel: '' }]);
  });

  it('Regeln hin und zurück', () => {
    const weiter = [{ wenn_gewaehlt: 'ja', dann: 'ende' }, { wenn_teil: 'draft', dann: 'ki' },
                    { sonst: 'frage' }];
    const zeilen = regelnAus(weiter);
    expect(zeilen).toEqual([
      { bedingung: 'gewaehlt', wert: 'ja', ziel: 'ende' },
      { bedingung: 'teil', wert: 'draft', ziel: 'ki' },
      { bedingung: 'sonst', wert: '', ziel: 'frage' },
    ]);
    expect(weiterAus(zeilen)).toEqual(weiter);
  });

  it('liest Schritte, Wahlen und Teile aus dem Dokument', () => {
    expect(schritteAus(DOK).map((s) => s.id)).toEqual(['frage', 'entwurf', 'ki', 'wohin', 'ende']);
    expect(wahlenAus(DOK)).toEqual([{ value: 'ja', label: 'Ja (frage)' }, { value: 'nein', label: 'Nein (frage)' }]);
    expect(teileAus(DOK)).toEqual(['draft', 'notiz']);
    expect(schritteAus({ schritte: 'kaputt' })).toEqual([]);
  });

  it('schreibt Werte ohne Leerzeichen am Rand — der Treiber vergleicht genau', () => {
    expect(weiterAus([{ bedingung: 'gewaehlt', wert: ' neu ', ziel: 'a' }, { bedingung: 'sonst', wert: '', ziel: 'b' }]))
      .toEqual([{ wenn_gewaehlt: 'neu', dann: 'a' }, { sonst: 'b' }]);
  });

  it('meldet halbe Regeln, damit das Speichern wartet', () => {
    expect(fehlerVon([{ bedingung: 'gewaehlt', wert: '', ziel: 'ende' }])).toEqual({ art: 'wert', zeile: 0 });
    expect(fehlerVon([{ bedingung: 'teil', wert: 'draft', ziel: '' }])).toEqual({ art: 'ziel', zeile: 0 });
    expect(fehlerVon([{ bedingung: 'sonst', wert: '', ziel: 'a' }, { bedingung: 'gewaehlt', wert: 'x', ziel: 'b' }]))
      .toEqual({ art: 'sonstZuletzt', zeile: 0 });
    expect(fehlerVon([])).toEqual({ art: 'leer', zeile: 0 });
    expect(fehlerVon([{ bedingung: 'gewaehlt', wert: 'x', ziel: 'b' }, { bedingung: 'sonst', wert: '', ziel: 'a' }]))
      .toBeNull();
    // Review AS-2, Befund 3: ohne „sonst“ am Ende lehnt die Prüfung ab
    expect(fehlerVon([{ bedingung: 'gewaehlt', wert: 'x', ziel: 'b' }])).toEqual({ art: 'sonstFehlt', zeile: 0 });
  });

  it('Regeln gelten genau an einer Verzweigung — wie die Prüfung (Review AS-2, Befund 1)', () => {
    const gut = [{ wenn_gewaehlt: 'x', dann: 'b' }, { sonst: 'a' }];
    expect(regelFehlerVon('verzweigung', gut)).toBeNull();
    expect(regelFehlerVon('verzweigung', null)).toEqual({ art: 'leer', zeile: 0 });
    expect(regelFehlerVon('verzweigung', 'a')).toEqual({ art: 'leer', zeile: 0 });
    expect(regelFehlerVon('modul', gut)).toEqual({ art: 'nurVerzweigung', zeile: 0 });
    expect(regelFehlerVon('modul', 'a')).toBeNull();
    // ohne Typ (frisch angelegt): Regeln gehen, halbe sperren
    expect(regelFehlerVon('', [{ wenn_gewaehlt: '', dann: 'b' }, { sonst: 'a' }])).toEqual({ art: 'wert', zeile: 0 });
    expect(regelFehlerOrte({ schritte: [
      { id: 'a', typ: 'verzweigung', weiter: gut }, { id: 'b', typ: 'verzweigung' }, { id: 'c', typ: 'nachricht', weiter: gut },
    ] })).toEqual(['schritte.1.weiter', 'schritte.2.weiter']);
  });

  it('der eigene Schritt kommt roh aus dem Dokument — auch ohne Kennung davor (Befund 4)', () => {
    const dok = { schritte: [{ typ: 'nachricht' }, { id: 'b', typ: 'verzweigung' }] };
    expect(eigenerSchritt(dok, ['schritte', 1, 'weiter'])).toEqual({ ablauf: dok, nr: 1, id: 'b', typ: 'verzweigung', mitWahl: false });
    expect(eigenerSchritt(dok, ['weiter'])).toBeNull();
  });
});

describe('weiter-regeln — Schnellantworten (AS-3a)', () => {
  it('mit Schnellantworten entscheidet die Wahl: weiter muss leer sein', () => {
    const mit = { typ: 'nachricht', optionen: [{ id: 'a', label: { de: 'A' }, ziel: 'e' }] };
    expect(mitWahl(mit)).toBe(true);
    expect(mitWahl({ typ: 'nachricht', optionen: [] })).toBe(false);
    expect(mitWahl({ typ: 'werkzeug', freitext: { ziel: 'e', schreibt: 'w' } })).toBe(false);
    expect(regelFehlerVon('nachricht', null, true)).toBeNull();
    expect(regelFehlerVon('nachricht', 'e', true)).toEqual({ art: 'wahlWeiter', zeile: 0 });
    expect(regelFehlerOrte({ schritte: [{ ...mit, weiter: 'e' }, { id: 'e', typ: 'ende' }] }))
      .toEqual(['schritte.0.weiter']);
  });
});

describe('weiter-regeln — Vorschläge aus Schnellantworten (Review AS-3a, Befund 5)', () => {
  it('Wahlen und Teile kennen Schnellantworten und Freitext', () => {
    const dok = { schritte: [{ id: 'f', typ: 'nachricht',
      optionen: [{ id: 'neu', label: { de: 'Neu' }, ziel: 'e' }], freitext: { ziel: 'e', schreibt: 'wunsch' } }] };
    expect(wahlenAus(dok)).toEqual([{ value: 'neu', label: 'Neu (f)' }]);
    expect(teileAus(dok)).toEqual(['wunsch']);
  });
});

describe('weiter-regeln — wenn_wert (AS-3c)', () => {
  it('liest und schreibt einen Vergleich, ohne Wert bei vorhanden/leer', () => {
    const roh = [{ wenn_wert: { quelle: 'teil.zahlen.inhalte', vergleich: 'groesser', wert: '10' }, dann: 'ja' },
      { wenn_wert: { quelle: 'teil.zahlen', vergleich: 'vorhanden' }, dann: 'ja' }, { sonst: 'nein' }];
    expect(artVon(roh)).toBe('regeln');
    const zeilen = regelnAus(roh);
    expect(zeilen[0]).toEqual({ bedingung: 'wert', quelle: 'teil.zahlen.inhalte', vergleich: 'groesser',
                                wert: '10', ziel: 'ja' });
    expect(weiterAus(zeilen)).toEqual(roh);
    expect(fehlerVon(zeilen)).toBeNull();
    expect(fehlerVon([{ ...zeilen[0], quelle: ' ' }, zeilen[2]])).toEqual({ art: 'quelle', zeile: 0 });
    expect(fehlerVon([{ ...zeilen[0], wert: '' }, zeilen[2]])).toEqual({ art: 'wert', zeile: 0 });
    // zwei Bedingungen oder fremde Felder im Vergleich: JSON
    expect(artVon([{ wenn_wert: { quelle: 'teil.x', vergleich: 'leer' }, wenn_teil: 'x', dann: 'a' }])).toBe('json');
    expect(artVon([{ wenn_wert: { quelle: 'teil.x', vergleich: 'leer', extra: 1 }, dann: 'a' }])).toBe('json');
  });
});

describe('weiter-regeln — Review AS-3c', () => {
  const regel = (mehr: object) => ({ bedingung: 'wert' as const, quelle: 'teil.zahlen', vergleich: 'gleich',
                                      wert: '1', ziel: 'a', ...mehr });
  const sonst = { bedingung: 'sonst' as const, wert: '', ziel: 'b' };
  it('ein unbekannter Vergleich bleibt JSON (Befund 3)', () => {
    expect(artVon([{ wenn_wert: { quelle: 'teil.x', vergleich: 'ungefaehr', wert: '1' }, dann: 'a' }])).toBe('json');
  });
  it('Form der Quelle und Zahl sperren schon im Editor (Befund 4)', () => {
    expect(fehlerVon([regel({ quelle: 'zahlen' }), sonst])).toEqual({ art: 'quelleForm', zeile: 0 });
    expect(fehlerVon([regel({ quelle: 'teil.x' }), sonst])).toEqual({ art: 'quelleForm', zeile: 0 });
    expect(fehlerVon([regel({ vergleich: 'groesser', wert: 'viel' }), sonst])).toEqual({ art: 'zahl', zeile: 0 });
    expect(fehlerVon([regel({ vergleich: 'kleiner', wert: '1,5' }), sonst])).toBeNull();
  });
  it('die Teil-Vorschläge zählen schreibt nur an Werkzeug und Auftrag', () => {
    expect(teileAus({ schritte: [{ id: 'n', typ: 'nachricht', schreibt: 'geist' }] })).toEqual([]);
  });
});

describe('weiter-regeln: Bedingung „Seite“ (AS-7b, wenn_seite)', () => {
  const roh = [{ wenn_seite: ['/fach/*', '/mitmachen*'], dann: 'fach' }, { sonst: 'ende' }];

  it('liest und schreibt Muster als Liste, im Editor mit Komma getrennt', () => {
    expect(artVon(roh)).toBe('regeln');
    const zeilen = regelnAus(roh);
    expect(zeilen[0]).toEqual({ bedingung: 'seite', wert: '/fach/*, /mitmachen*', ziel: 'fach' });
    expect(weiterAus(zeilen)).toEqual(roh);
  });

  it('jedes Muster beginnt mit / — sonst ein Fehler an der Regel', () => {
    expect(fehlerVon([{ bedingung: 'seite', wert: '/a, fach', ziel: 'x' }, { bedingung: 'sonst', wert: '', ziel: 'y' }]))
      .toEqual({ art: 'muster', zeile: 0 });
    expect(fehlerVon([{ bedingung: 'seite', wert: '', ziel: 'x' }, { bedingung: 'sonst', wert: '', ziel: 'y' }]))
      .toEqual({ art: 'wert', zeile: 0 });
  });

  it('eine Liste, die keine Texte trägt, bleibt JSON', () => {
    expect(artVon([{ wenn_seite: [1], dann: 'x' }, { sonst: 'y' }])).toBe('json');
  });
});

describe('weiter-regeln: Seitenmuster ohne Inhalt (Review AS-7b, Befund 9)', () => {
  it('nur Kommas sind kein Muster', () => {
    expect(fehlerVon([{ bedingung: 'seite', wert: ' , ,', ziel: 'x' }, { bedingung: 'sonst', wert: '', ziel: 'y' }]))
      .toEqual({ art: 'wert', zeile: 0 });
  });
});
