import { describe, expect, it } from 'vitest';

import { antwortDaten, MAX_KNOTEN } from './upload-antwort';
import { erfasse, type Quelle } from './upload-erfassen';
import { alleIgnorieren, setzeRolle, vorschlagen } from './upload-rollen';

function q(relPfad: string, size = 10, type = 'application/pdf'): Quelle<null> {
  return { relPfad, name: relPfad.split('/').pop() ?? relPfad, size, type, handle: null };
}

describe('Rollen (U3-1a)', () => {
  it('schlägt einen einzelnen Lehrplan in der Wurzel als Strukturdokument vor', () => {
    const e = vorschlagen(erfasse([q('P/Kerncurriculum_Physik.pdf'), q('P/A/blatt.pdf')]));
    expect(e.dateien.find((d) => d.name.startsWith('Kern'))?.rolle).toBe('struktur');
    expect(e.dateien.find((d) => d.name === 'blatt.pdf')?.rolle).toBe('inhalt');
  });

  it('eine einzeln gewählte Datei wird Strukturdokument, wenn der Block es verlangt (Rückmeldung 11.11.)', () => {
    expect(vorschlagen(erfasse([q('Ausbildung_Augenoptik.pdf')]), true).dateien[0].rolle).toBe('struktur');
    // zwei Dateien, ein Bild oder ein Ordner bleiben ohne Vorschlag
    const zwei = vorschlagen(erfasse([q('a.pdf'), q('b.pdf')]), true);
    expect(zwei.dateien.every((d) => d.rolle === 'inhalt')).toBe(true);
    expect(vorschlagen(erfasse([q('foto.png', 10, 'image/png')]), true).dateien[0].rolle).toBe('inhalt');
    expect(vorschlagen(erfasse([q('P/A/notizen.pdf')]), true).dateien[0].rolle).toBe('inhalt');
  });

  it('ohne Wunsch des Blocks bleibt eine Einzeldatei Inhalt (Review 12.11., Befund 1)', () => {
    // sonst wäre sie beim Übertragen nach WLO still als Strukturdokument markiert
    expect(vorschlagen(erfasse([q('Ausbildung_Augenoptik.pdf')])).dateien[0].rolle).toBe('inhalt');
  });

  it('bei zwei Kandidaten, tief liegenden oder Bildern kein Vorschlag', () => {
    const zwei = vorschlagen(erfasse([q('P/Lehrplan_alt.pdf'), q('P/Lehrplan_neu.docx')]));
    expect(zwei.dateien.every((d) => d.rolle === 'inhalt')).toBe(true);
    const tief = vorschlagen(erfasse([q('P/A/Lehrplan.pdf')]));
    expect(tief.dateien[0].rolle).toBe('inhalt');
    const bild = vorschlagen(erfasse([q('P/Lehrplan.png', 10, 'image/png')]));
    expect(bild.dateien[0].rolle).toBe('inhalt');
  });

  it('höchstens ein Strukturdokument: das neue verdrängt das alte', () => {
    let e = erfasse([q('P/a.pdf'), q('P/b.pdf')]);
    e = setzeRolle(e, 0, 'struktur');
    e = setzeRolle(e, 1, 'struktur');
    expect(e.dateien.map((d) => d.rolle)).toEqual(['inhalt', 'struktur']);
  });

  it('ein Bild oder eine zu große Datei wird kein Strukturdokument', () => {
    const e = erfasse([q('P/x.png', 10, 'image/png'), q('P/gross.pdf', 999_999_999)]);
    const bild = e.dateien.findIndex((d) => d.name === 'x.png');
    const gross = e.dateien.findIndex((d) => d.name === 'gross.pdf');
    expect(setzeRolle(e, bild, 'struktur').dateien[bild].rolle).toBe('inhalt');
    expect(setzeRolle(e, gross, 'struktur').dateien[gross].rolle).toBe('ignorieren');
  });

  it('„alle in diesem Ordner ignorieren“ wirkt auf alles darunter und lässt sich zurücknehmen', () => {
    let e = erfasse([q('P/A/a.pdf'), q('P/A/B/b.pdf'), q('P/c.pdf')]);
    const ordnerA = e.wurzel.ordner[0];
    e = alleIgnorieren(e, ordnerA.pfad, true);
    expect(e.dateien.map((d) => d.rolle)).toEqual(['ignorieren', 'ignorieren', 'inhalt']);
    e = alleIgnorieren(e, ordnerA.pfad, false);
    expect(e.dateien.map((d) => d.rolle)).toEqual(['inhalt', 'inhalt', 'inhalt']);
  });

  it('Zurücknehmen lässt leere, zu große und Systemdateien ignoriert', () => {
    let e = erfasse([q('P/A/leer.pdf', 0), q('P/A/.DS_Store', 5), q('P/A/gross.pdf', 999_999_999)]);
    e = alleIgnorieren(e, 'P/A', true);
    e = alleIgnorieren(e, 'P/A', false);
    expect(e.dateien.map((d) => d.rolle)).toEqual(['ignorieren', 'ignorieren', 'ignorieren']);
  });
});

describe('antwortDaten (U3-1a)', () => {
  it('nur der Ordnerbaum mit Zahlen — keine Dateinamen, außer dem Strukturdokument', () => {
    let e = erfasse([q('P/Lehrplan.pdf', 300), q('P/A/geheim-Mueller.pdf', 100), q('P/A/.DS_Store', 5)]);
    e = setzeRolle(e, e.dateien.findIndex((d) => d.name === 'Lehrplan.pdf'), 'struktur');
    const a = antwortDaten(e, 'erfasst');
    expect(a.aktion).toBe('erfasst');
    expect(a.struktur).toEqual({ name: 'P', dateien: 1, alle_dateien: 2,
      kinder: [{ name: 'A', dateien: 1, alle_dateien: 1, kinder: [] }] });
    expect(a.zahlen).toEqual({ ordner: 2, dateien: 3, inhalte: 1, ignoriert: 1, strukturdokumente: 1, bytes: 400 });
    expect(a.strukturdokument).toEqual({ name: 'Lehrplan.pdf', groesse: 300, endung: 'pdf' });
    expect(JSON.stringify(a)).not.toContain('geheim');
  });

  it('Review U3-1, Befund 13: Kürzen auf 120 Zeichen zerbricht kein Emoji', () => {
    const name = 'x'.repeat(119) + '😀' + 'y';
    const a = antwortDaten(erfasse([q(`${name}/a.pdf`), q('b.pdf')]), 'erfasst');
    const gekuerzt = a.struktur.kinder[0].name;
    expect(Array.from(gekuerzt)).toHaveLength(120);
    expect(gekuerzt.endsWith('😀')).toBe(true);
  });

  it('ohne Strukturdokument null; Warnungen werden durchgereicht', () => {
    const a = antwortDaten(erfasse([q('P/x.pdf', 0)]), 'ordner_als_entwurf');
    expect(a.strukturdokument).toBeNull();
    expect(a.warnungen).toEqual(['leer']);
    expect(a.aktion).toBe('ordner_als_entwurf');
  });

  it('Ordnernamen eine Zeile, höchstens 120 Zeichen; die künstliche Wurzel heißt leer', () => {
    const lang = 'x'.repeat(200);
    const a = antwortDaten(erfasse([q(`${lang}/a.pdf`), q('b.pdf')]), 'erfasst');
    expect(a.struktur.name).toBe('');
    expect(a.struktur.kinder[0].name).toHaveLength(120);
  });

  it(`höchstens ${MAX_KNOTEN} Ordnerknoten, dann Warnung zu_viele_ordner`, () => {
    const quellen = Array.from({ length: MAX_KNOTEN + 20 }, (_, i) => q(`P/o${String(i).padStart(4, '0')}/a.pdf`));
    const a = antwortDaten(erfasse(quellen, { maxDateien: 1000, maxTiefe: 8, maxBytesDatei: 1e9 }), 'erfasst');
    let n = 0;
    const zaehle = (k: { kinder: readonly unknown[] }): void => { n++; (k.kinder as { kinder: readonly unknown[] }[]).forEach(zaehle); };
    zaehle(a.struktur);
    expect(n).toBeLessThanOrEqual(MAX_KNOTEN);
    expect(a.warnungen).toContain('zu_viele_ordner');
  });
});
