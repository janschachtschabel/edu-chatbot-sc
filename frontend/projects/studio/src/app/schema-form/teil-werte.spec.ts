import { describe, expect, it } from 'vitest';

import { alsTabelleLesbar, type TeilZeile, vorigeTeile, wertAus, zeilenAus } from './teil-werte';

/** Paket K2c-3: Regeln der Tabelle „Argumente“ — Lesen, Schreiben, Fehler, Teile der vorigen Schritte. */
describe('teil-werte (K2c-3)', () => {
  it('liest Text, Teil und alles andere als JSON — nichts geht verloren', () => {
    expect(zeilenAus({ titel: 'fest', dokument: { $teil: 'document' }, n: 3, liste: [1], tief: { $teil: 'a', x: 1 } }))
      .toEqual([
        { name: 'titel', art: 'text', wert: 'fest' },
        { name: 'dokument', art: 'teil', wert: 'document' },
        { name: 'n', art: 'json', wert: '3' },
        { name: 'liste', art: 'json', wert: '[1]' },
        { name: 'tief', art: 'json', wert: '{"$teil":"a","x":1}' },
      ]);
    expect(zeilenAus(null)).toEqual([]);
  });

  it('schreibt die Zeilen zurück — derselbe Wert, in derselben Reihenfolge', () => {
    const wert = {
      titel: 'fest', dokument: { $teil: 'document' }, n: 3, liste: [1], leer: '', nichts: null,
      tief: { a: { b: [true, 1.5] } }, mitPfad: { $teil: 'volltext', pfad: 'outputs.markdown' },
      zeilen: 'eins\nzwei',
    };
    const zurueck = wertAus(zeilenAus(wert));
    // Review K2c-3 (2), Befund 6: `toEqual` prüft die Reihenfolge der Schlüssel nicht
    expect(JSON.stringify(zurueck)).toBe(JSON.stringify({ wert }));
  });

  it('Review 2, Befund 2: ein Text mit Zeilenumbruch steht als JSON-Zeile — der Umbruch bleibt', () => {
    expect(zeilenAus({ a: 'eins\nzwei', b: 'x\ry' })).toEqual([
      { name: 'a', art: 'json', wert: '"eins\\nzwei"' },
      { name: 'b', art: 'json', wert: '"x\\ry"' },
    ]);
  });

  it('K2d-1: ein Verweis mit Pfad ist eine Teil-Zeile „name.pfad“ — und zurück', () => {
    const wert = { text: { $teil: 'volltext', pfad: 'outputs.markdown' }, ganz: { $teil: 'draft' } };
    const zeilen = zeilenAus(wert);
    expect(zeilen).toEqual([
      { name: 'text', art: 'teil', wert: 'volltext.outputs.markdown' },
      { name: 'ganz', art: 'teil', wert: 'draft' },
    ]);
    expect(JSON.stringify(wertAus(zeilen))).toBe(JSON.stringify({ wert }));
    // mehr als `$teil` und `pfad` bleibt JSON, ein ganzer Verweis mit Pfad steht nur in der Box
    expect(zeilenAus({ a: { $teil: 'x', pfad: 'y', mehr: 1 } })[0].art).toBe('json');
    expect(zeilenAus({ a: { $teil: 'x', pfad: 3 } })[0].art).toBe('json');
    // Review K2d-1, Befund 4: ein Name mit Punkt bleibt, wie er ist
    const mitPunkt = { a: { $teil: 'volltext.outputs' }, b: { $teil: 'a.b', pfad: 'c' } };
    expect(zeilenAus(mitPunkt).map((z) => z.art)).toEqual(['json', 'json']);
    expect(JSON.stringify(wertAus(zeilenAus(mitPunkt)))).toBe(JSON.stringify({ wert: mitPunkt }));
    expect(alsTabelleLesbar({ $teil: 'draft', pfad: 'knoten' })).toBe(false);
    // Review K2d-1 (2), Befund 3: ein Umbruch in Pfad oder Name bleibt verlustfrei als JSON
    const umbruch = { a: { $teil: 'volltext', pfad: 'markdown\n' }, b: { $teil: 'x\r' } };
    expect(zeilenAus(umbruch).map((z) => z.art)).toEqual(['json', 'json']);
    expect(JSON.stringify(wertAus(zeilenAus(umbruch)))).toBe(JSON.stringify({ wert: umbruch }));
    // `volltext.` wird ein leerer Pfad — gespeichert, wie geschrieben (die Prüfung meldet ihn)
    const leer = wertAus([{ name: 'a', art: 'teil', wert: 'volltext.' }]);
    expect(JSON.stringify(leer)).toBe(JSON.stringify({ wert: { a: { $teil: 'volltext', pfad: '' } } }));
  });

  it('Review 2, Befund 5: der Name __proto__ ist ein Eintrag wie jeder andere', () => {
    const roh = JSON.parse('{"__proto__": "x", "a": "y"}') as Record<string, unknown>;
    const zurueck = wertAus(zeilenAus(roh));
    expect('wert' in zurueck && Object.keys(zurueck.wert!)).toEqual(['__proto__', 'a']);
    expect(JSON.stringify(zurueck)).toBe('{"wert":{"__proto__":"x","a":"y"}}');
    const z = (name: string): TeilZeile => ({ name, art: 'text', wert: '' });
    expect(wertAus([z('__proto__'), z('__proto__')]))
      .toEqual({ fehler: { art: 'name_doppelt', zeile: 1, name: '__proto__' } });
  });

  it('ein halber Stand schreibt nichts: leerer Name, doppelter Name, Teil ohne Namen, kaputtes JSON', () => {
    const z = (name: string, art: TeilZeile['art'], wert: string): TeilZeile => ({ name, art, wert });
    expect(wertAus([z(' ', 'text', 'x')])).toEqual({ fehler: { art: 'name_leer', zeile: 0 } });
    expect(wertAus([z('a', 'text', ''), z('a', 'text', '')]))
      .toEqual({ fehler: { art: 'name_doppelt', zeile: 1, name: 'a' } });
    expect(wertAus([z('a', 'teil', ' ')])).toEqual({ fehler: { art: 'teil_leer', zeile: 0 } });
    const kaputt = wertAus([z('a', 'json', '{')]);
    expect('fehler' in kaputt && kaputt.fehler.art).toBe('json');
  });

  it('nur ein Objekt oder nichts lässt sich als Tabelle zeigen — ein ganzer Verweis nicht', () => {
    expect(alsTabelleLesbar(undefined)).toBe(true);
    expect(alsTabelleLesbar({})).toBe(true);
    expect(alsTabelleLesbar([])).toBe(false);
    expect(alsTabelleLesbar('x')).toBe(false);
    // Review K2c-3, Befund 1: `daten: {$teil: draft}` ist ein Verweis, keine Zeile „$teil“.
    expect(alsTabelleLesbar({ $teil: 'draft' })).toBe(false);
    // K2d-1: mit `pfad` ist es seither auch ein (ganzer) Verweis — wie im Treiber
    expect(alsTabelleLesbar({ $teil: 'draft', pfad: 'a' })).toBe(false);
  });

  it('Namen und Teile bleiben, wie sie getippt sind; ohne Zeilen null', () => {
    const z = (name: string, art: TeilZeile['art'], wert: string): TeilZeile => ({ name, art, wert });
    // Review K2c-3, Befund 6/7: kein stilles Umbenennen, und `{}` änderte die Fassung.
    expect(wertAus([z(' a', 'teil', ' x ')])).toEqual({ wert: { ' a': { $teil: ' x ' } } });
    expect(wertAus([])).toEqual({ wert: null });
  });

  it('die Teile der Schritte davor — schreibt und agent.ausgabe, je einmal, in Reihenfolge', () => {
    const dok = { ablaeufe: [{ schritte: [
      { id: 'a', schreibt: 'volltext' },
      { id: 'b', agent: { ausgabe: 'gliederung' } },
      { id: 'c', schreibt: 'volltext' },
      { id: 'f', freitext: { ziel: 'd', schreibt: 'wunsch' } },
      { id: 'd', schreibt: 'spaeter' },
    ] }] };
    expect(vorigeTeile(dok, ['ablaeufe', 0, 'schritte', 4, 'argumente'])).toEqual(['volltext', 'gliederung', 'wunsch']);
    expect(vorigeTeile(dok, ['ablaeufe', 0, 'schritte', 0, 'argumente'])).toEqual([]);
    expect(vorigeTeile(dok, ['etwas', 'anderes'])).toEqual([]);
  });
});

describe('alsTabelleLesbar — Auswahl (Review AS-Da, Befund 1)', () => {
  it('eine Auswahl als ganze Daten ist keine Tabelle mit Zeilen „$teil“, „liste“, „feld“', () => {
    expect(alsTabelleLesbar({ $teil: 'ablage', liste: 'inhalte', feld: 'node_id' })).toBe(false);
    expect(alsTabelleLesbar({ frage: 'x' })).toBe(true);
  });
});
