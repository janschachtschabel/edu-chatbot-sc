import { describe, expect, it } from 'vitest';

import { erfasse, type Quelle } from './upload-erfassen';
import { gewaehlt, lokaleAuswahl, lokaleGrenzen, orteAus, orteFuer } from './upload-orte';
import { setzeRolle } from './upload-rollen';

/**
 * Plan 2026-11-17, Paket U4 (Teil b): „Wo sollen sie verarbeitet werden?“ — die Orte aus dem Vertrag
 * (`orte`, `grenzen.lokal_*`), gegen die Auswahl geprüft (E13).
 */
function q(relPfad: string, size = 10, type = 'application/pdf'): Quelle<null> {
  return { relPfad, name: relPfad.split('/').pop() ?? relPfad, size, type, handle: null };
}

const ORTE_WLO = {
  vorauswahl: 'wlo', chat: { geht: true, ueber_grenze: 'ueber_grenze' }, wlo: { geht: true }, namen: { geht: true },
};
const ORTE_ANONYM = {
  vorauswahl: 'chat', chat: { geht: true, ueber_grenze: 'ueber_grenze_anmelden' },
  wlo: { geht: false, grund: 'nur_angemeldet' }, namen: { geht: true },
};
const MB = 1024 * 1024;

describe('Orte aus dem Vertrag (Paket U4)', () => {
  it('nimmt Vorauswahl, Sperrgründe und Hinweis aus `orte`', () => {
    const o = orteAus({ orte: { ...ORTE_WLO, wlo: { geht: true, hinweis: 'ohne_erschliessung' } } });
    expect(o.vorauswahl).toBe('wlo');
    expect(o.chat).toEqual({ geht: true, ueber_grenze: 'ueber_grenze' });
    expect(o.wlo).toEqual({ geht: true, hinweis: 'ohne_erschliessung' });
    expect(orteAus({ orte: ORTE_ANONYM }).wlo).toEqual({ geht: false, grund: 'nur_angemeldet' });
  });

  it('ohne `orte` (älteres Backend, Vorschau) aus den Schaltern abgeleitet', () => {
    const wlo = orteAus({ schalter: { dokument_im_chat: true, ablage_in_wlo: true } });
    expect(wlo.vorauswahl).toBe('wlo');
    expect(wlo.chat.geht && wlo.wlo.geht).toBe(true);
    const chat = orteAus({ schalter: { dokument_im_chat: true, ablage_nach_anmeldung: true } });
    expect(chat.vorauswahl).toBe('chat');
    expect(chat.wlo).toEqual({ geht: false, grund: 'nur_angemeldet' });
    const keins = orteAus({ schalter: { lesen_nach_anmeldung: true } });
    expect(keins.vorauswahl).toBe('namen');
    expect(keins.chat).toEqual({ geht: false, grund: 'nur_angemeldet' });
    expect(keins.wlo).toEqual({ geht: false, grund: 'aus' });
    expect(orteAus({}).vorauswahl).toBe('namen');
  });

  it('ein kaputtes `orte` gilt nicht — dann die Schalter', () => {
    expect(orteAus({ orte: { vorauswahl: 'mond' }, schalter: { ablage_in_wlo: true } }).vorauswahl).toBe('wlo');
    expect(orteAus({ orte: { ...ORTE_WLO, chat: { geht: 'ja' } } }).chat.geht).toBe(false);
  });

  it('Grenzen „Hier im Chat“ mit den Vorgaben des Studios', () => {
    // ohne `lokal_max_mb_datei` und ohne Rest der Sitzung (älteres Backend) prüft das Modul nur die Auswahl
    expect(lokaleGrenzen({})).toEqual({
      maxDateien: 10, maxBytes: 50 * MB, aufbewahrungH: 24, maxBytesDatei: Infinity, freiDateien: null, freiBytes: null });
    expect(lokaleGrenzen({ grenzen: { lokal_max_dateien: 3, lokal_max_mb_gesamt: 2, lokal_aufbewahrung_h: 6 } }))
      .toMatchObject({ maxDateien: 3, maxBytes: 2 * MB, aufbewahrungH: 6 });
  });

  it('Review Oberfläche 5 + Sitzungsrest: Grenze je Datei und `lokal_frei_*` (0 heißt voll)', () => {
    expect(lokaleGrenzen({ grenzen: { lokal_max_mb_datei: 4, lokal_frei_dateien: 0, lokal_frei_mb: 2.5 } }))
      .toMatchObject({ maxBytesDatei: 4 * MB, freiDateien: 0, freiBytes: 2.5 * MB });
    expect(lokaleGrenzen({ grenzen: { lokal_frei_dateien: -1, lokal_frei_mb: 'viel' } }))
      .toMatchObject({ freiDateien: null, freiBytes: null });
  });

  it('Review Oberfläche: Sperrgrund `grenze_sitzung` aus dem Vertrag bleibt erhalten', () => {
    expect(orteAus({ orte: { ...ORTE_ANONYM, chat: { geht: false, grund: 'grenze_sitzung' } } }).chat)
      .toEqual({ geht: false, grund: 'grenze_sitzung' });
  });
});

describe('Orte gegen die Auswahl (E13)', () => {
  it('zählt nur lesbare Dateien (Inhalt und Strukturdokument), nennt die übrigen', () => {
    let e = erfasse([q('P/a.pdf', 100), q('P/b.docx', 50), q('P/c.pptx', 70), q('P/d.png', 30, 'image/png'), q('P/e.txt', 5)]);
    e = setzeRolle(e, e.dateien.findIndex((d) => d.name === 'b.docx'), 'struktur');
    e = setzeRolle(e, e.dateien.findIndex((d) => d.name === 'e.txt'), 'ignorieren');
    const a = lokaleAuswahl(e);
    expect(a.lesbar.map((d) => [d.i, d.rolle])).toEqual([[0, 'inhalt'], [1, 'struktur']]);
    expect(a.nichtLesbar).toBe(2);
    expect(a.bytes).toBe(150);
  });

  it('über der Zahl: „Hier im Chat“ gesperrt mit dem Code des Vertrags, die Vorauswahl wechselt', () => {
    const daten = { orte: ORTE_ANONYM, grenzen: { lokal_max_dateien: 2 } };
    const o = orteFuer(daten, erfasse([q('a.pdf'), q('b.pdf'), q('c.pdf')]));
    expect(o.chat).toMatchObject({ geht: false, grund: 'ueber_grenze_anmelden', grenze: 'anzahl' });
    // WLO geht ohne Anmeldung nicht → nur die Namen
    expect(o.vorauswahl).toBe('namen');
    const angemeldet = orteFuer({ orte: { ...ORTE_WLO, vorauswahl: 'chat' }, grenzen: { lokal_max_dateien: 2 } },
      erfasse([q('a.pdf'), q('b.pdf'), q('c.pdf')]));
    expect(angemeldet.chat).toMatchObject({ geht: false, grund: 'ueber_grenze' });
    expect(angemeldet.vorauswahl).toBe('wlo');
  });

  it('über der Menge: gesperrt mit `grenze: gesamt`; genau an der Grenze geht es', () => {
    const daten = { orte: ORTE_ANONYM, grenzen: { lokal_max_dateien: 2, lokal_max_mb_gesamt: 1 } };
    expect(orteFuer(daten, erfasse([q('a.pdf', MB), q('b.pdf', 1)])).chat).toMatchObject({ geht: false, grenze: 'gesamt' });
    const passt = orteFuer(daten, erfasse([q('a.pdf', MB / 2), q('b.pdf', MB / 2)]));
    expect(passt.chat.geht).toBe(true);
    expect(passt.vorauswahl).toBe('chat');
  });

  it('Review Oberfläche 5: eine Datei über `lokal_max_mb_datei` zählt wie nicht lesbar — nur ihr Name', () => {
    const e = erfasse([q('a.pdf', 3 * MB), q('b.pdf', MB), q('c.pptx', 10)]);
    const a = lokaleAuswahl(e, lokaleGrenzen({ grenzen: { lokal_max_mb_datei: 2 } }));
    expect(a.lesbar.map((d) => d.name)).toEqual(['b.pdf']);
    expect([a.nichtLesbar, a.zuGross, a.bytes]).toEqual([1, 1, MB]);
    // ohne Grenze je Datei (älteres Backend) geht jede lesbare hoch
    expect(lokaleAuswahl(e).lesbar).toHaveLength(2);
  });

  it('Review Oberfläche 3: ohne lesbare Datei ist „Hier im Chat“ gesperrt (`keine`), sind alle zu groß `grenze: datei`', () => {
    const nur = orteFuer({ orte: ORTE_ANONYM }, erfasse([q('a.pptx'), q('b.mp4', 10, 'video/mp4')]));
    expect(nur.chat).toEqual({ geht: false, grund: 'keine' });
    expect(nur.vorauswahl).toBe('namen');
    const gross = orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_max_mb_datei: 1 } }, erfasse([q('a.pdf', 2 * MB)]));
    expect(gross.chat).toEqual({ geht: false, grund: 'keine', grenze: 'datei' });
    // ein Sperrgrund des Backends geht vor
    expect(orteFuer({ orte: { ...ORTE_ANONYM, chat: { geht: false, grund: 'aus' } } }, erfasse([q('a.pptx')])).chat)
      .toEqual({ geht: false, grund: 'aus' });
  });

  it('Sitzungsrest: die Auswahl gegen `lokal_frei_*` — Rest der Sitzung statt der ganzen Grenze', () => {
    const e = erfasse([q('a.pdf', MB), q('b.pdf', MB)]);
    const anzahl = orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_frei_dateien: 1 } }, e);
    expect(anzahl.chat).toMatchObject({ geht: false, grund: 'ueber_grenze_anmelden', grenze: 'frei_anzahl' });
    const menge = orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_frei_dateien: 5, lokal_frei_mb: 1.5 } }, e);
    expect(menge.chat).toMatchObject({ geht: false, grenze: 'frei_gesamt' });
    expect(orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_frei_dateien: 2, lokal_frei_mb: 2 } }, e).chat.geht).toBe(true);
    // die Grenze je Auswahl geht vor (sie sagt mehr)
    expect(orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_max_dateien: 1, lokal_frei_dateien: 0 } }, e).chat)
      .toMatchObject({ grenze: 'anzahl' });
  });

  it('zweites Review, 4: Dubletten (Rolle, Größe, Name) zählen einmal gegen die Grenzen', () => {
    const e = erfasse([q('P/a/x.pdf', MB), q('P/b/x.pdf', MB), q('P/c.pdf', MB)]);
    const a = lokaleAuswahl(e);
    expect(a.lesbar).toHaveLength(3);              // hochgeladen und beantwortet werden alle i
    expect([a.anzahl, a.bytes]).toEqual([2, 2 * MB]);
    expect(orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_max_dateien: 2, lokal_max_mb_gesamt: 2 } }, e).chat.geht).toBe(true);
    expect(orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_frei_dateien: 2, lokal_frei_mb: 2 } }, e).chat.geht).toBe(true);
    // eine andere Rolle ist eine eigene Datei (wie der Server prüft)
    const zwei = setzeRolle(e, 0, 'struktur');
    expect(lokaleAuswahl(zwei).anzahl).toBe(3);
  });

  it('nicht lesbare Dateien zählen nicht gegen die Grenze', () => {
    const o = orteFuer({ orte: ORTE_ANONYM, grenzen: { lokal_max_dateien: 1 } },
      erfasse([q('a.pdf'), q('b.pptx'), q('c.mp4', 10, 'video/mp4')]));
    expect(o.chat.geht).toBe(true);
  });

  it('WLO: mehr als 200 übertragbare Dateien → gesperrt (`stapel`), keine übertragbare → `keine`', () => {
    const viele = erfasse(Array.from({ length: 201 }, (_, i) => q(`P/d${String(i).padStart(3, '0')}.pdf`)));
    const o = orteFuer({ orte: ORTE_WLO, grenzen: { lokal_max_dateien: 30 } }, viele);
    expect(o.wlo).toMatchObject({ geht: false, grund: 'stapel' });
    expect(o.vorauswahl).toBe('namen');          // chat liegt ebenso über der Grenze
    expect(orteFuer({ orte: ORTE_WLO }, erfasse([q('x.exe', 10, '')])).wlo).toMatchObject({ geht: false, grund: 'keine' });
  });

  it('die Wahl der Person gilt, solange der Ort geht; sonst die Vorauswahl; nur Namen → null', () => {
    const e = erfasse([q('a.pdf')]);
    const o = orteFuer({ orte: ORTE_WLO }, e);
    expect(gewaehlt(o, null)).toBe('wlo');
    expect(gewaehlt(o, 'chat')).toBe('chat');
    const anonym = orteFuer({ orte: ORTE_ANONYM }, e);
    expect(gewaehlt(anonym, 'wlo')).toBe('chat');
    expect(gewaehlt(orteFuer({}, e), null)).toBeNull();
  });
});
