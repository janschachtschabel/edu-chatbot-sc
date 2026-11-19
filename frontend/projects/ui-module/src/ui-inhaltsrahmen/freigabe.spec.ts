import { describe, expect, it } from 'vitest';

import { gruppen, freigabeAus, SEITE, sichtbar, TEXTE_FREIGABE } from './freigabe';

const eintrag = (titel: string, ordner = '') => ({ titel, ordner });

describe('freigabeAus (Paket N4)', () => {
  it('nimmt die Liste nur von einer Schreib-Vorschau mit gültigen Daten', () => {
    const f = { ablauf: 'a', id: 'x', anzahl: 1, eintraege: [eintrag('A')], probleme: [], flow: 'f', metadaten: false };
    expect(freigabeAus({ art: 'schreib_vorschau', freigabe: f })).toEqual(f);
    expect(freigabeAus({ art: 'dokument', freigabe: f })).toBeNull();      // nur das System
    expect(freigabeAus({ art: 'schreib_vorschau', freigabe: { id: 'x' } })).toBeNull();
    expect(freigabeAus({ art: 'schreib_vorschau' })).toBeNull();
  });
});

describe('sichtbar und gruppen', () => {
  const viele = Array.from({ length: 45 }, (_, i) => eintrag(`Titel ${i + 1}`, i < 30 ? 'Klasse 7' : ''));

  it('zeigt seitenweise höchstens SEITE Einträge je Schritt', () => {
    expect(sichtbar(viele, '', 1)).toHaveLength(SEITE);
    expect(sichtbar(viele, '', 3)).toHaveLength(45);
  });

  it('filtert nach Titel und Ordner, ohne Groß- und Kleinschreibung', () => {
    expect(sichtbar(viele, 'titel 4', 1).map((e) => e.titel)).toEqual(
      ['Titel 4', 'Titel 40', 'Titel 41', 'Titel 42', 'Titel 43', 'Titel 44', 'Titel 45']);
    expect(sichtbar(viele, 'klasse', 9)).toHaveLength(30);
  });

  it('gruppiert nach Ordner in der Reihenfolge des ersten Auftretens', () => {
    const g = gruppen([eintrag('A', 'X'), eintrag('B'), eintrag('C', 'X')]);
    expect(g.map((x) => [x.ordner, x.eintraege.map((e) => e.titel)])).toEqual([['X', ['A', 'C']], ['', ['B']]]);
  });
});

describe('TEXTE_FREIGABE', () => {
  it('nennt jedes Problem des MCP in beiden Sprachen', () => {
    for (const code of ['not_found', 'not_readable', 'not_a_record', 'is_reference', 'not_writable', 'unchecked']) {
      expect(TEXTE_FREIGABE.de.grund(code)).not.toBe(TEXTE_FREIGABE.de.grund('unbekannt'));
      expect(TEXTE_FREIGABE.en.grund(code)).not.toBe(TEXTE_FREIGABE.en.grund('unbekannt'));
    }
  });
});
