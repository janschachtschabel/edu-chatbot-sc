import { describe, expect, it } from 'vitest';

import { antwortDaten, MAX_KNOTEN } from './upload-antwort';
import { erfasse, type Quelle } from './upload-erfassen';
import {
  alleIgnorieren, alsAblageRolle, istGliederung, istMaterial, MAX_STRUKTUR, rollenVorgabe, setzeRolle,
  strukturWaehlbar, strukturZahl, vorschlagen,
} from './upload-rollen';

function q(relPfad: string, size = 10, type = 'application/pdf'): Quelle<null> {
  return { relPfad, name: relPfad.split('/').pop() ?? relPfad, size, type, handle: null };
}

describe('Rollen (U3-1a)', () => {
  it('schlägt einen einzelnen Lehrplan in der Wurzel als Strukturdokument vor', () => {
    const e = vorschlagen(erfasse([q('P/Kerncurriculum_Physik.pdf'), q('P/A/blatt.pdf')]));
    expect(e.dateien.find((d) => d.name.startsWith('Kern'))?.rolle).toBe('struktur');
    expect(e.dateien.find((d) => d.name === 'blatt.pdf')?.rolle).toBe('inhalt');
  });

  // Plan 2026-11-20, P2: die Rollen-Vorgabe des Schritts ersetzt „einzeldatei_als_struktur“ (Rückmeldung
  // 11.11.: eine einzeln gewählte Datei wurde nur dann Strukturdokument) — jetzt jede lesbare Datei
  it('P2: Vorgabe gliederung — jede lesbare Datei beginnt als Gliederung, höchstens fünf, der Rest Material', () => {
    expect(vorschlagen(erfasse([q('Ausbildung_Augenoptik.pdf')]), 'gliederung').dateien[0].rolle).toBe('struktur');
    const zwei = vorschlagen(erfasse([q('a.pdf'), q('b.pdf')]), 'gliederung');
    expect(zwei.dateien.map((d) => d.rolle)).toEqual(['struktur', 'struktur']);
    expect(vorschlagen(erfasse([q('foto.png', 10, 'image/png')]), 'gliederung').dateien[0].rolle).toBe('inhalt');
    expect(vorschlagen(erfasse([q('P/A/notizen.pdf')]), 'gliederung').dateien[0].rolle).toBe('struktur');
    const sieben = vorschlagen(erfasse(['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((n) => q(`P/${n}.pdf`))), 'gliederung');
    expect(strukturZahl(sieben)).toBe(MAX_STRUKTUR);
    expect(sieben.dateien.filter((d) => d.rolle === 'inhalt')).toHaveLength(2);
  });

  it('P2: Vorgabe beides wie gliederung, Vorgabe material lässt auch einen Lehrplan Material', () => {
    const beides = vorschlagen(erfasse([q('P/a.pdf'), q('P/folien.pptx', 10, 'application/vnd.ms-powerpoint')]), 'beides');
    expect(beides.dateien.map((d) => d.rolle)).toEqual(['beides', 'inhalt']);
    expect(vorschlagen(erfasse([q('P/Lehrplan.pdf')]), 'material').dateien[0].rolle).toBe('inhalt');
    // auto: die bisherige Regel — eine Einzeldatei ohne Lehrplan-Namen bleibt Material
    expect(vorschlagen(erfasse([q('Ausbildung_Augenoptik.pdf')]), 'auto').dateien[0].rolle).toBe('inhalt');
    expect(vorschlagen(erfasse([q('P/Lehrplan.pdf')]), 'auto').dateien[0].rolle).toBe('struktur');
  });

  it('P2: rollenVorgabe liest den Block — der alte Schlüssel heißt gliederung, ein ausdrücklicher Wert zählt', () => {
    expect(rollenVorgabe({})).toBe('auto');
    expect(rollenVorgabe({ einzeldatei_als_struktur: true })).toBe('gliederung');
    expect(rollenVorgabe({ rolle_vorgabe: 'material', einzeldatei_als_struktur: true })).toBe('material');
    expect(rollenVorgabe({ rolle_vorgabe: 'beides' })).toBe('beides');
    expect(rollenVorgabe({ rolle_vorgabe: 'quatsch' })).toBe('auto');
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

  it('TG-3e: bis zu fünf Strukturdokumente — ein weiteres verdrängt keins, ein sechstes geht nicht', () => {
    let e = erfasse(['a', 'b', 'c', 'd', 'e', 'f'].map((n) => q(`P/${n}.pdf`)));
    e = setzeRolle(e, 0, 'struktur');
    e = setzeRolle(e, 1, 'struktur');
    expect(e.dateien.map((d) => d.rolle).slice(0, 2)).toEqual(['struktur', 'struktur']);
    for (const i of [2, 3, 4]) e = setzeRolle(e, i, 'struktur');
    expect(strukturZahl(e)).toBe(MAX_STRUKTUR);
    expect(strukturWaehlbar(e, 5)).toBe(false);
    expect(strukturWaehlbar(e, 4)).toBe(true);           // ein markiertes bleibt wählbar
    expect(setzeRolle(e, 5, 'struktur')).toBe(e);        // unverändert, keine stille Verdrängung
    e = setzeRolle(e, 0, 'inhalt');
    expect(setzeRolle(e, 5, 'struktur').dateien[5].rolle).toBe('struktur');
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

// Plan 2026-11-20, P1 (UO-4): „Gliederung und Material“ ist Strukturdokument und Inhalt zugleich
describe('Rolle beides (P1)', () => {
  it('istGliederung / istMaterial / alsAblageRolle', () => {
    expect((['struktur', 'inhalt', 'beides', 'ignorieren'] as const).map((r) => [istGliederung(r), istMaterial(r)]))
      .toEqual([[true, false], [false, true], [true, true], [false, false]]);
    expect(['struktur', 'beides', 'inhalt', 'ignorieren', 'structure', undefined].map(alsAblageRolle))
      .toEqual(['struktur', 'beides', 'inhalt', 'inhalt', 'inhalt', 'inhalt']);
  });

  it('beides zählt zur Höchstzahl der Strukturdokumente', () => {
    let e = erfasse(['a', 'b', 'c', 'd', 'e', 'f'].map((n) => q(`P/${n}.pdf`)));
    for (const i of [0, 1, 2, 3]) e = setzeRolle(e, i, 'struktur');
    e = setzeRolle(e, 4, 'beides');
    expect(e.dateien[4].rolle).toBe('beides');
    expect(strukturZahl(e)).toBe(MAX_STRUKTUR);
    expect(strukturWaehlbar(e, 5)).toBe(false);
    expect(setzeRolle(e, 5, 'beides')).toBe(e);
    expect(strukturWaehlbar(e, 4)).toBe(true);           // ein markiertes bleibt wählbar
  });

  it('beides nur für lesbare Formate', () => {
    const e = erfasse([q('P/x.png', 10, 'image/png')]);
    expect(setzeRolle(e, 0, 'beides').dateien[0].rolle).toBe('inhalt');
  });

  it('antwortDaten: beides zählt als Strukturdokument (nicht doppelt bei den Inhalten)', () => {
    let e = erfasse([q('P/Lehrplan.pdf'), q('P/blatt.pdf')]);
    e = setzeRolle(e, e.dateien.findIndex((d) => d.name === 'Lehrplan.pdf'), 'beides');
    const a = antwortDaten(e, 'erfasst');
    expect(a.zahlen).toMatchObject({ strukturdokumente: 1, inhalte: 1 });
    expect(a.strukturdokument).toMatchObject({ name: 'Lehrplan.pdf' });
    expect(a.struktur.dateiliste.map((d) => d.rolle).sort()).toEqual(['beides', 'inhalt']);
  });
});

describe('antwortDaten (U3-1a)', () => {
  // Plan 2026-11-16, TG-3a: der Baum trägt je Ordner seine Dateien mit fester Nummer `i`
  it('der Ordnerbaum mit Zahlen und den Dateien je Ordner (TG-3a), ohne Systemdateien', () => {
    let e = erfasse([q('P/Lehrplan.pdf', 300), q('P/A/blatt.pdf', 100), q('P/A/.DS_Store', 5), q('P/A/leer.txt', 0)]);
    e = setzeRolle(e, e.dateien.findIndex((d) => d.name === 'Lehrplan.pdf'), 'struktur');
    const a = antwortDaten(e, 'erfasst');
    expect(a.aktion).toBe('erfasst');
    // sortiert nach Pfad: 0 P/A/.DS_Store, 1 P/A/blatt.pdf, 2 P/A/leer.txt, 3 P/Lehrplan.pdf
    expect(a.struktur).toEqual({ name: 'P', dateien: 1, alle_dateien: 2,
      dateiliste: [{ i: 3, name: 'Lehrplan.pdf', endung: 'pdf', groesse: 300, rolle: 'struktur' }],
      kinder: [{ name: 'A', dateien: 1, alle_dateien: 1, kinder: [], dateiliste: [
        { i: 1, name: 'blatt.pdf', endung: 'pdf', groesse: 100, rolle: 'inhalt' },
        // Review TG-3a–c, R3-4: ausgeschlossen heißt ohne Namen
        { i: 2, endung: 'txt', groesse: 0, rolle: 'ignorieren' }] }] });
    expect(a.zahlen).toEqual({ ordner: 2, dateien: 4, inhalte: 1, ignoriert: 2, strukturdokumente: 1, bytes: 400 });
    expect(a.strukturdokument).toEqual({ name: 'Lehrplan.pdf', groesse: 300, endung: 'pdf' });
    expect(JSON.stringify(a)).not.toContain('DS_Store');
  });

  it('TG-3a: `i` bleibt dieselbe Nummer, wenn sich Rollen ändern', () => {
    let e = erfasse([q('P/a.pdf'), q('P/b.pdf'), q('P/c.pdf')]);
    const vorher = antwortDaten(e, 'erfasst').struktur.dateiliste.map((d) => d.i);
    e = alleIgnorieren(e, 'P', true);
    e = setzeRolle(e, 2, 'struktur');
    const nachher = antwortDaten(e, 'erfasst').struktur.dateiliste;
    expect(nachher.map((d) => d.i)).toEqual(vorher);
    expect(nachher.map((d) => d.name)).toEqual([undefined, undefined, 'c.pdf']);   // R3-4
    expect(nachher.map((d) => d.rolle)).toEqual(['ignorieren', 'ignorieren', 'struktur']);
  });

  it('TG-3a: Endung kleingeschrieben, ohne Endung leer, eine Datei mit Punkt vorn hat keine', () => {
    const a = antwortDaten(erfasse([q('P/Bild.JPEG'), q('P/LIESMICH'), q('P/x.tar.gz')]), 'erfasst');
    expect(a.struktur.dateiliste.map((d) => [d.name, d.endung])).toEqual([
      ['Bild.JPEG', 'jpeg'], ['LIESMICH', ''], ['x.tar.gz', 'gz']]);
  });

  it('TG-3a: ein Dateiname über 120 Zeichen wird gekürzt und gemeldet — keine stille Kürzung', () => {
    const lang = 'n'.repeat(130) + '.pdf';
    const a = antwortDaten(erfasse([q(`P/${lang}`), q('P/kurz.pdf')]), 'erfasst');
    const erste = a.struktur.dateiliste.find((d) => d.name?.startsWith('n'))!;
    expect(Array.from(erste.name ?? '')).toHaveLength(120);
    expect(erste.endung).toBe('pdf');
    expect(a.warnungen).toEqual(['namen_gekuerzt']);
    expect(antwortDaten(erfasse([q('P/kurz.pdf')]), 'erfasst').warnungen).toEqual([]);
  });

  it('TG-3a: über 500 Dateien meldet „zu_viele“ — höchstens 500 in den Listen', () => {
    const quellen = Array.from({ length: 503 }, (_, n) => q(`P/d${String(n).padStart(4, '0')}.pdf`));
    const a = antwortDaten(erfasse(quellen), 'erfasst');
    expect(a.struktur.dateiliste).toHaveLength(500);
    expect(a.struktur.dateiliste.at(-1)?.i).toBe(499);
    expect(a.warnungen).toContain('zu_viele');
  });

  it('Review TG-3a–c, R3-4: eine ausgeschlossene Datei geht ohne Namen mit — nur Nummer, Endung, Größe', () => {
    let e = erfasse([q('P/Zeugnis_Mueller.pdf', 50), q('P/blatt.pdf')]);
    e = setzeRolle(e, e.dateien.findIndex((d) => d.name.startsWith('Zeugnis')), 'ignorieren');
    const a = antwortDaten(e, 'erfasst');
    // nach Pfad sortiert: 0 Zeugnis_Mueller.pdf, 1 blatt.pdf
    expect(a.struktur.dateiliste).toEqual([
      { i: 0, endung: 'pdf', groesse: 50, rolle: 'ignorieren' },
      { i: 1, name: 'blatt.pdf', endung: 'pdf', groesse: 10, rolle: 'inhalt' }]);
    expect(JSON.stringify(a)).not.toContain('Zeugnis');
  });

  it('Review TG-3a–c, NIT: ein Name nur aus Leerzeichen wird „(ohne Namen)“ — die Antwort kippt nicht', () => {
    const e = erfasse([q('P/   ', 10, 'text/plain'), q('P/b.pdf')]);
    const de = antwortDaten(e, 'erfasst');
    expect(de.struktur.dateiliste.map((d) => d.name)).toEqual(['(ohne Namen)', 'b.pdf']);
    expect(antwortDaten(e, 'erfasst', '(no name)').struktur.dateiliste[0].name).toBe('(no name)');
    // als Strukturdokument ebenso
    const sd = antwortDaten(setzeRolle(erfasse([q('P/  .md', 10, 'text/markdown')]), 0, 'struktur'), 'erfasst');
    expect(sd.strukturdokument?.name).toBe('.md');
  });

  it('Review U3-1, Befund 13: Kürzen auf 120 Zeichen zerbricht kein Emoji', () => {
    const name = 'x'.repeat(119) + '😀' + 'y';
    const a = antwortDaten(erfasse([q(`${name}/a.pdf`), q('b.pdf')]), 'erfasst');
    const gekuerzt = a.struktur.kinder[0].name;
    expect(Array.from(gekuerzt)).toHaveLength(120);
    expect(gekuerzt.endsWith('😀')).toBe(true);
  });

  it('ohne Strukturdokument null; Warnungen werden durchgereicht', () => {
    const a = antwortDaten(erfasse([q('P/x.pdf', 0)]), 'uebertragen');
    expect(a.strukturdokument).toBeNull();
    expect(a.warnungen).toEqual(['leer']);
    expect(a.aktion).toBe('uebertragen');
  });

  it('Ordnernamen eine Zeile, höchstens 120 Zeichen; die künstliche Wurzel heißt leer', () => {
    const lang = 'x'.repeat(200);
    const a = antwortDaten(erfasse([q(`${lang}/a.pdf`), q('b.pdf')]), 'erfasst');
    expect(a.struktur.name).toBe('');
    expect(a.struktur.kinder[0].name).toHaveLength(120);
    // TG-3a: auch ein gekürzter Ordnername wird gemeldet
    expect(a.warnungen).toEqual(['namen_gekuerzt']);
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
