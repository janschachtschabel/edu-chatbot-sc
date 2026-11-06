import { describe, expect, it } from 'vitest';

import { erfasse, type Quelle } from './upload-erfassen';
import {
  ansageFaellig,
  ablageErlaubt, artVon, auswahl, codeAblage, type Ergebnis, maxBytesAblage, nochmalSenden, planAus, sha256Hex,
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

  it('die Antwort trägt nur Zahlen — keine Kennungen, keine Dateinamen', () => {
    const plan = planAus({ batch_token: 'tok-1234567890', layout: 'flach', ordner: 'Physik', gesamt: 1,
      eintraege: [{ index: 0, titel: 'A', art: 'pdf', groesse: 1, name: 'A.pdf' },
        { index: 1, titel: 'B', art: 'pdf', groesse: 1, name: 'B.pdf' }] }, 2)!;
    const a = uebertragenAntwort(E, plan, [{ stand: 'stored', link: 'https://repo/n-1' }, { stand: 'abgebrochen' }],
      { ordnerVerweigert: true, vorgangAbgelegt: false });
    expect(a.aktion).toBe('uebertragen');
    expect(a.ablage).toEqual({ layout: 'flach', gesamt: 2, abgelegt: 1, unklar: 0, fehler: 0, abgebrochen: 1,
      ordner_verweigert: true, vorgang_abgelegt: false });
    expect(JSON.stringify(a)).not.toContain('n-1');
    expect(JSON.stringify(a)).not.toContain('Mechanik');
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
