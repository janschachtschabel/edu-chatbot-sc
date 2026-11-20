import { describe, expect, it } from 'vitest';

import { erfasse, type Quelle } from './upload-erfassen';
import { setzeRolle } from './upload-rollen';
import {
  ansageFaellig,
  ablageErlaubt, artVon, auswahl, codeAblage, type Ergebnis, letzteAus, maxBytesAblage, nochmalSenden, planAus, sha256Hex,
  stapelEnde, standAus, titelVon, uebertragenAntwort, zaehlung,
} from './upload-uebertragen';

/**
 * Paket U3-3b (T7): Regeln des Übertragens in den persönlichen Bereich — welche Dateien gehen
 * (Art, Größe, nicht ignoriert), was die Freigabe trägt (Titel, sha256, Größe, Art — kein Pfad),
 * wie die Antwort des Servers gelesen wird und was die Antwort an den Chat zählt (nur Zahlen).
 */
function q(relPfad: string, size = 10): Quelle<string> {
  return { relPfad, name: relPfad.split('/').pop() ?? relPfad, size, type: '', handle: relPfad };
}

const E = erfasse([
  q('Physik/01 Mechanik.pdf'), q('Physik/Bild.JPEG'), q('Physik/notiz.markdown'), q('Physik/Programm.exe'),
  q('Physik/gross.pdf', 50_000_000), q('Physik/.DS_Store'), q('Physik/leer.pdf', 0),
]);

describe('Übertragen — Regeln (U3-3b)', () => {
  it('die Art kommt aus der Endung, auf die Arten des MCP abgebildet', () => {
    expect(artVon('a.PDF')).toBe('pdf');
    expect(artVon('a.jpeg')).toBe('jpg');
    expect(artVon('a.markdown')).toBe('md');
    expect(artVon('a.exe')).toBeNull();
    expect(artVon('ohne_endung')).toBeNull();
  });

  it('der Titel ist der Name ohne Endung, eine Zeile, höchstens 200 Zeichen', () => {
    expect(titelVon('01 Mechanik.pdf')).toBe('01 Mechanik');
    expect(titelVon('  zwei\nZeilen .txt')).toBe('zwei Zeilen');
    expect(titelVon('.pdf')).toBe('.pdf');
    expect(Array.from(titelVon(`${'ä'.repeat(300)}.pdf`))).toHaveLength(200);
  });

  it('übertragen werden nicht ignorierte Dateien bekannter Art bis zur Größe der Ablage', () => {
    const a = auswahl(E, 10_000_000);
    expect(a.kandidaten.map((k) => k.titel)).toEqual(['01 Mechanik', 'Bild', 'notiz']);
    expect(a.kandidaten.map((k) => k.art)).toEqual(['pdf', 'jpg', 'md']);
    expect(a.ohneArt).toBe(1);
    expect(a.zuGross).toBe(1);           // 50 MB: erfasst, aber über der Grenze der Ablage
    expect(auswahl(E, 5).zuGross).toBe(4);
  });

  it('erlaubt nur, wenn das System es im Block sagt; die Größe aus den Grenzen', () => {
    expect(ablageErlaubt({ schalter: { ablage_in_wlo: true } })).toBe(true);
    expect(ablageErlaubt({ schalter: { ablage_in_wlo: 'ja' } })).toBe(false);
    expect(ablageErlaubt({})).toBe(false);
    expect(maxBytesAblage({ grenzen: { max_mb_ablage: 7 } })).toBe(7 * 1024 * 1024);
    expect(maxBytesAblage({})).toBe(10 * 1024 * 1024);
  });

  it('sha256 als Hex (bekannter Prüfwert von „abc“)', async () => {
    const abc = await sha256Hex(new Blob([]), async () => new TextEncoder().encode('abc').buffer as ArrayBuffer);
    expect(abc).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  });

  it('ohne sichere Seite (kein crypto.subtle) der Code „unsicher“', async () => {
    const echt = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: {} });
    try {
      await expect(sha256Hex(new Blob([]))).rejects.toMatchObject({ code: 'unsicher' });
    } finally {
      if (echt) Object.defineProperty(globalThis, 'crypto', echt);
    }
  });

  it('der Plan des Servers wird nur angenommen, wenn er zur Freigabe passt', () => {
    const roh = {
      batch_token: 'tok-1234567890', layout: 'folder', ordner: 'Physik', gesamt: 30,
      eintraege: [{ index: 0, titel: 'A', art: 'pdf', groesse: 10, name: 'A.pdf' },
        { index: 1, titel: 'B', art: 'jpg', groesse: 20, name: 'B.jpg' }],
    };
    expect(planAus(roh, 2)).toMatchObject({ token: 'tok-1234567890', layout: 'ordner', ordner: 'Physik' });
    expect(planAus(roh, 3)).toBeNull();
    // Review U3-3b, Befund 1: das Backend reicht das Layout des MCP durch (`folder` | `flat`).
    expect(planAus({ ...roh, layout: 'flat' }, 2)?.layout).toBe('flach');
    expect(planAus({ ...roh, layout: 'irgendwas' }, 2)?.layout).toBe('flach');
    expect(planAus({ ...roh, batch_token: '' }, 2)).toBeNull();
    expect(planAus({ ...roh, eintraege: [roh.eintraege[1], roh.eintraege[0]] }, 2)).toBeNull();
  });

  it('der Stand einer Datei; ein Link nur als https', () => {
    expect(standAus({ stand: 'stored', link: 'https://repo/x' })).toEqual({ stand: 'stored', link: 'https://repo/x' });
    expect(standAus({ stand: 'dropped', link: 'javascript:alert(1)' })).toEqual({ stand: 'dropped', link: null });
    expect(standAus({ stand: 'offen' })).toBeNull();
    expect(standAus({})).toBeNull();
  });

  it('ein Fehler einer Datei geht weiter, einer des Stapels hält an', () => {
    expect(stapelEnde('passt_nicht')).toBe(false);
    expect(stapelEnde('zu_langsam')).toBe(false);
    expect(stapelEnde('nur_angemeldet')).toBe(true);
    expect(stapelEnde('neu_vorbereiten')).toBe(true);
    expect(stapelEnde('netz')).toBe(true);
    expect(stapelEnde('abgebrochen')).toBe(true);
  });

  it('Review U3-3b, Befund 2/7: Codes der Ablage — Abbruch, eigener Code vor 429, sonst wie beim Dokument', () => {
    expect(codeAblage(new DOMException('weg', 'AbortError'))).toBe('abgebrochen');
    expect(codeAblage({ status: 429, code: 'voll' })).toBe('voll');
    expect(codeAblage({ status: 429, code: 'fehler' })).toBe('gedrosselt');
    expect(codeAblage({ status: 413, code: 'fehler' })).toBe('zu_gross');
    expect(codeAblage({ status: 503, code: 'nicht_erreichbar' })).toBe('nicht_erreichbar');
    expect(codeAblage(new TypeError('x'))).toBe('fehler');
  });

  it('Zählung und was noch einmal gehen kann', () => {
    const e: Ergebnis[] = [
      { stand: 'stored' }, { stand: 'dropped' }, { stand: 'unverified' },
      { stand: 'failed', code: 'passt_nicht' }, { stand: 'failed', code: 'erneut' }, { stand: 'abgebrochen' },
      { stand: 'failed' }, { stand: 'unverified', code: 'zu_langsam' },
    ];
    expect(zaehlung(e)).toEqual({ abgelegt: 2, unklar: 2, fehler: 3, abgebrochen: 1 });
    // „unklar“ ohne Code meldete das Backend selbst; mit Code blieb die Antwort aus — nachfragen hilft.
    expect(nochmalSenden(e)).toEqual([4, 5, 7]);
  });

  // Plan 2026-11-16, TG-3a: die Auswahl trägt die Dateinamen je Ordner (`struktur`) — die Ablage
  // selbst nur Zahlen, keine Kennungen und keine Links
  it('die Ablage in der Antwort trägt nur Zahlen — keine Kennungen', () => {
    const plan = planAus({ batch_token: 'tok-1234567890', layout: 'flach', ordner: 'Physik', gesamt: 1,
      eintraege: [{ index: 0, titel: 'A', art: 'pdf', groesse: 1, name: 'A.pdf' },
        { index: 1, titel: 'B', art: 'pdf', groesse: 1, name: 'B.pdf' }] }, 2)!;
    const a = uebertragenAntwort(E, plan, [{ stand: 'stored', link: 'https://repo/n-1' }, { stand: 'abgebrochen' }],
      { ordnerVerweigert: true, vorgangAbgelegt: false, nummern: [1, 3] });
    // Plan 2026-11-17, Paket U4: `bereitgestellt` mit Ort wlo — je abgelegter Datei die Nummer i der
    // Auswahl und die Rolle (nicht gesendete fehlen)
    expect(a).toMatchObject({ aktion: 'bereitgestellt', ort: 'wlo', dateien: [{ i: 1, rolle: 'inhalt' }] });
    // Review P2, Befund 1: die Antwort nennt, was der Server zum Häkchen festhielt (hier nichts → nein)
    expect(a.ablage).toEqual({ layout: 'flach', gesamt: 2, abgelegt: 1, unklar: 0, fehler: 0, abgebrochen: 1,
      ordner_verweigert: true, vorgang_abgelegt: false, erschliessen: false });
    const mit = uebertragenAntwort(E, { ...plan, erschliessen: true }, [{ stand: 'stored' }, { stand: 'abgebrochen' }],
      { ordnerVerweigert: false, vorgangAbgelegt: true, nummern: [1, 3] });
    expect(mit.ablage?.erschliessen).toBe(true);
    expect(JSON.stringify(a)).not.toContain('n-1');
    expect(JSON.stringify(a.ablage)).not.toContain('Mechanik');
    expect(a.struktur.dateiliste.map((d) => d.name)).toContain('01 Mechanik.pdf');
  });
});

describe('Antwort mit Ort wlo (Paket U4)', () => {
  it('`dateien` nennt abgelegte (auch „angelegt, Inhalt verworfen“), nie unklare oder gescheiterte', () => {
    const eintrag = (index: number, rolle = 'inhalt') => ({ index, titel: `T${index}`, art: 'pdf', groesse: 1, name: `T${index}.pdf`, rolle });
    const plan = planAus({ batch_token: 'tok-1234567890', layout: 'ordner', ordner: 'P', gesamt: 4,
      eintraege: [eintrag(0, 'struktur'), eintrag(1), eintrag(2), eintrag(3)] }, 4)!;
    const a = uebertragenAntwort(E, plan,
      [{ stand: 'stored' }, { stand: 'dropped' }, { stand: 'unverified' }, { stand: 'failed', code: 'art' }],
      { ordnerVerweigert: false, vorgangAbgelegt: true, nummern: [4, 0, 2, 5] });
    expect(a.dateien).toEqual([{ i: 4, rolle: 'struktur' }, { i: 0, rolle: 'inhalt' }]);
    expect(a.ablage).toMatchObject({ gesamt: 4, abgelegt: 2, unklar: 1, fehler: 1 });
  });
});

describe('ansageFaellig (Querschnitts-Review FE-5)', () => {
  it('sagt die erste, jede zehnte und die letzte Datei an — nicht jede', () => {
    expect([1, 2, 3].map((n) => ansageFaellig(n, 3))).toEqual([true, false, true]);
    expect([1, 2, 9, 10, 11, 20, 30].map((n) => ansageFaellig(n, 30)))
      .toEqual([true, false, false, true, false, true, true]);
  });
});

describe('fehlerSatz (Review Q1, Befund 10)', () => {
  it('ein Code wie `constructor` liefert den allgemeinen Satz, keinen Wert des Prototyps', async () => {
    const { fehlerSatz, uebertragenTexte } = await import('./upload-uebertragen-texte');
    const t = uebertragenTexte('de');
    expect(fehlerSatz(t, 'constructor')).toBe(t.fehler.fehler);
    expect(fehlerSatz(t, '__proto__')).toBe(t.fehler.fehler);
    expect(fehlerSatz(t, 'voll')).toBe(t.fehler.voll);
  });
});

describe('Letzte Ablagen (Paket M6)', () => {
  it('liest die Liste aus der Antwort von vorbereiten — ohne Kennungen, unlesbarer Stand ohne Zahlen', () => {
    const l = letzteAus({ letzte: { gekappt: true, ablagen: [
      { titel: 'Physik 7', datum: '2026-11-06T10:15:00Z', lesbar: true, stored: 30, dropped: 1, failed: 2, open: 1, unverified: 2 },
      { titel: 'Chemie', datum: 'x', lesbar: false },
      { titel: '', lesbar: true },
    ] } });
    // Wie `zaehlung`: `dropped` ist abgelegt, „unklar“ (kann abgelegt sein) steht für sich (Review M6, Befund 2).
    expect(l).toEqual({ gekappt: true, ablagen: [
      { titel: 'Physik 7', datum: '2026-11-06T10:15:00Z', zahlen: { abgelegt: 31, unklar: 2, gescheitert: 2, offen: 1 } },
      { titel: 'Chemie', datum: 'x', zahlen: null },
    ] });
    expect(letzteAus({})).toEqual({ ablagen: [], gekappt: false });
    expect(letzteAus({ letzte: { ablagen: 'kaputt' } })).toEqual({ ablagen: [], gekappt: false });
  });
});

// W4-Anbindung (MCP-Stand 2026-11-08): die Rolle je Datei reist mit — Teil der Freigabe.
describe('Rolle im Stapel (W4)', () => {
  it('ein Strukturdokument geht als „struktur“, alles andere als „inhalt“', () => {
    const i = E.dateien.findIndex((d) => d.name === '01 Mechanik.pdf');
    const a = auswahl(setzeRolle(E, i, 'struktur'), 10_000_000);
    expect(a.kandidaten.map((k) => k.rolle)).toEqual(['struktur', 'inhalt', 'inhalt']);
    expect(auswahl(E, 10_000_000).kandidaten.every((k) => k.rolle === 'inhalt')).toBe(true);
  });

  it('der Plan trägt die Rolle zurück; eine unbekannte gilt als Inhalt', () => {
    const roh = {
      batch_token: 'tok-1234567890', layout: 'folder', ordner: 'Physik', gesamt: 30,
      eintraege: [{ index: 0, titel: 'A', art: 'pdf', groesse: 10, name: 'A.pdf', rolle: 'struktur' },
        { index: 1, titel: 'B', art: 'jpg', groesse: 20, name: 'B.jpg', rolle: 'quatsch' }],
    };
    expect(planAus(roh, 2)?.eintraege.map((e) => e.rolle)).toEqual(['struktur', 'inhalt']);
  });

  // Review P1, MINOR 5: `beides` bleibt im Plan und in der Antwort `bereitgestellt` (Ort wlo)
  it('P1: beides bleibt im Plan und steht mit `i` in der Antwort', () => {
    const roh = {
      batch_token: 'tok-1234567890', layout: 'folder', ordner: 'Physik', gesamt: 20,
      eintraege: [{ index: 0, titel: 'A', art: 'pdf', groesse: 10, name: 'A.pdf', rolle: 'beides' },
        { index: 1, titel: 'B', art: 'pdf', groesse: 10, name: 'B.pdf', rolle: 'inhalt' }],
    };
    const plan = planAus(roh, 2)!;
    expect(plan.eintraege.map((e) => e.rolle)).toEqual(['beides', 'inhalt']);
    const antwort = uebertragenAntwort(E, plan, [{ stand: 'stored' }, { stand: 'failed' }],
      { ordnerVerweigert: false, vorgangAbgelegt: true, nummern: [4, 0] });
    expect(antwort.dateien).toEqual([{ i: 4, rolle: 'beides' }]);
  });

  // Plan 2026-11-20, P2: der Plan sagt, ob der Server das Häkchen festhielt — ein älteres Backend nichts
  it('P2: `erschliessen` nur, wenn der Server es ausdrücklich bestätigt', () => {
    const roh = { batch_token: 'tok-1234567890', layout: 'folder', ordner: 'P', gesamt: 10,
      eintraege: [{ index: 0, titel: 'A', art: 'pdf', groesse: 10, name: 'A.pdf' }] };
    expect(planAus({ ...roh, erschliessen: true }, 1)?.erschliessen).toBe(true);
    expect(planAus({ ...roh, erschliessen: 'ja' }, 1)?.erschliessen).toBe(false);
    expect(planAus(roh, 1)?.erschliessen).toBe(false);
  });
});


describe('fehlerSatz — Probe der Studio-Vorschau (AS-8b)', () => {
  it('nennt den Trockenlauf in beiden Sprachen', async () => {
    const { fehlerSatz, uebertragenTexte } = await import('./upload-uebertragen-texte');
    for (const sprache of ['de', 'en'] as const) {
      const t = uebertragenTexte(sprache);
      expect(fehlerSatz(t, 'trockenlauf')).not.toBe(t.fehler.fehler);
    }
  });
});
