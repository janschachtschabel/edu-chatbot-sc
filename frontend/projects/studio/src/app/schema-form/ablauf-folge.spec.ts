import { describe, expect, it } from 'vitest';

import { schrittFolge } from './ablauf-folge';

describe('schrittFolge (K2c-4)', () => {
  it('folgt ohne weiter dem nächsten Schritt; der letzte läuft aus', () => {
    const folge = schrittFolge({ schritte: [
      { id: 'a', typ: 'nachricht' },
      { id: 'b', typ: 'modul', weiter: 'd', bei_fehler: 'c' },
      { id: 'c', typ: 'nachricht', weiter: '' },
      { id: 'd', typ: 'nachricht' },
    ] });
    expect(folge.map((z) => z.pfeile.map((p) => [p.art, p.ziel]))).toEqual([
      [['weiter', 'b']],
      [['weiter', 'd'], ['fehler', 'c']],
      [['weiter', 'd']],
      [['weiter', '']],
    ]);
    expect(folge.every((z) => z.pfeile.every((p) => p.bekannt))).toBe(true);
    expect(folge.map((z) => [z.nr, z.id, z.typ])[1]).toEqual([1, 'b', 'modul']);
    // AS-2c: das Modul nur am Modul-Schritt (für den Verweis auf seine Seite)
    expect(folge.map((z) => z.modul)).toEqual(folge.map((z) => (z.typ === 'modul' ? z.modul : '')));
  });

  it('ende hat keinen Nachfolger, auch kein bei_fehler', () => {
    const [z] = schrittFolge({ schritte: [{ id: 'x', typ: 'ende', weiter: 'y', bei_fehler: 'y' }] });
    expect(z.pfeile).toEqual([]);
  });

  it('Regeln der Verzweigung: Bedingungen und sonst wie der Treiber', () => {
    const [z] = schrittFolge({ schritte: [
      { id: 'w', typ: 'verzweigung', weiter: [
        { wenn_teil: 'draft', dann: 'a' },
        { wenn_gewaehlt: 'ja', dann: 'b' },
        { sonst: 'c', dann: 'falsch' },
      ] },
      { id: 'a', typ: 'ende' }, { id: 'b', typ: 'ende' }, { id: 'c', typ: 'ende' },
    ] });
    expect(z.pfeile).toEqual([
      { ziel: 'a', art: 'regel', wennTeil: 'draft', bekannt: true },
      { ziel: 'b', art: 'regel', wennGewaehlt: 'ja', bekannt: true },
      { ziel: 'c', art: 'regel', sonst: true, bekannt: true },
    ]);
  });

  it('Review K2c-4, Befund 2: eine Verzweigung läuft aus, wenn keine Regel greift oder sie keine hat', () => {
    const [ohne, mit] = schrittFolge({ schritte: [
      { id: 'w', typ: 'verzweigung', weiter: 'x' },
      { id: 'v', typ: 'verzweigung', weiter: [{ wenn_gewaehlt: 'ja', dann: 'w' }] },
    ] });
    expect(ohne.pfeile).toEqual([{ ziel: '', art: 'regel', keineGreift: true, bekannt: true }]);
    expect(mit.pfeile.map((p) => [p.ziel, p.keineGreift ?? false])).toEqual([['w', false], ['', true]]);
  });

  it('markiert unbekannte Ziele', () => {
    const [z] = schrittFolge({ schritte: [{ id: 'a', typ: 'werkzeug', weiter: 'zz', bei_fehler: 'yy' }] });
    expect(z.pfeile.map((p) => p.bekannt)).toEqual([false, false]);
  });

  it('eine falsche Form gibt keine oder leere Zeilen statt eines Fehlers', () => {
    expect(schrittFolge(null)).toEqual([]);
    expect(schrittFolge({ schritte: 'kaputt' })).toEqual([]);
    const folge = schrittFolge({ schritte: [7, { id: 3, typ: null, weiter: [null] }] });
    expect(folge).toHaveLength(2);
    expect(folge[0]).toEqual({ nr: 0, id: '', typ: '', modul: '', pfeile: [{ ziel: '', art: 'weiter', bekannt: true }] });
    // eine Liste in `weiter` außerhalb einer Verzweigung nimmt der Treiber wie kein `weiter`
    expect(folge[1].pfeile).toEqual([{ ziel: '', art: 'weiter', bekannt: true }]);
  });

  it('bei_fehler nur, wo der Treiber ihn nimmt; weiter: [] geht zum folgenden Schritt', () => {
    const folge = schrittFolge({ schritte: [
      { id: 'n', typ: 'nachricht', bei_fehler: 'e' },
      { id: 'w', typ: 'werkzeug', weiter: [], bei_fehler: 'e' },
      { id: 'e', typ: 'ende' },
    ] });
    expect(folge[0].pfeile).toEqual([{ ziel: 'w', art: 'weiter', bekannt: true }]);
    expect(folge[1].pfeile).toEqual([
      { ziel: 'e', art: 'weiter', bekannt: true },
      { ziel: 'e', art: 'fehler', bekannt: true },
    ]);
  });
});

describe('schrittFolge — Schnellantworten (AS-3a)', () => {
  it('an nachricht und modul entscheidet die Wahl: je Option ein Pfeil, dazu der Freitext', () => {
    const [z] = schrittFolge({ schritte: [
      { id: 'f', typ: 'nachricht', weiter: 'e',
        optionen: [{ id: 'a', label: { de: 'Neu' }, ziel: 'e' }, { id: 'b', label: {}, ziel: 'x' }],
        freitext: { ziel: 'e', schreibt: 'w' } },
      { id: 'e', typ: 'ende' }] });
    expect(z.pfeile).toEqual([
      { ziel: 'e', art: 'wahl', label: 'Neu', bekannt: true },
      { ziel: 'x', art: 'wahl', label: 'b', bekannt: false },
      { ziel: 'e', art: 'freitext', bekannt: true },
    ]);
  });
});
