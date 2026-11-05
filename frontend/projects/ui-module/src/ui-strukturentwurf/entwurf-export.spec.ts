import { describe, expect, it } from 'vitest';

import { alsJson, alsMarkdown, dateiname, DOKUMENTTYP, type EntwurfDaten } from './entwurf-export';

/** Paket U2-e (T-12): Herunterladen als JSON (`wlo.sammlungsstruktur@1`) und Markdown. */
const DATEN: EntwurfDaten = {
  titel: 'Optik', quelle: 'ki', fach: 'Physik', bildungsstufe: 'Sekundarstufe I',
  knoten: [
    { id: 'k1', titel: 'Licht', beschreibung: 'Wie Licht sich ausbreitet.', keywords: ['Strahl', 'Schatten'],
      kinder: [{ id: 'k1-1', titel: 'Quellen' }] },
    { id: 'k2', titel: 'Farben' },
  ],
};

const BESCHRIFTUNG = { fach: 'Fach', stufe: 'Bildungsstufe', schlagworte: 'Schlagworte' };

describe('entwurf-export', () => {
  it('JSON trägt den Dokumenttyp und die Struktur', () => {
    const json = JSON.parse(alsJson(DATEN));
    expect(json.typ).toBe(DOKUMENTTYP);
    expect(json.knoten[0].kinder[0].titel).toBe('Quellen');
    expect(json.fach).toBe('Physik');
  });

  it('Markdown ist eine eingerückte Liste mit Beschreibung und Schlagworten', () => {
    expect(alsMarkdown(DATEN, BESCHRIFTUNG)).toBe([
      '# Optik', '', 'Fach: Physik · Bildungsstufe: Sekundarstufe I', '',
      '- **Licht** — Wie Licht sich ausbreitet.',
      '  Schlagworte: Strahl, Schatten',
      '  - **Quellen**',
      '- **Farben**', '',
    ].join('\n'));
  });

  it('Dateinamen ohne Sonderzeichen', () => {
    expect(dateiname('Optik in Klasse 8!', 'json')).toBe('optik-in-klasse-8.json');
    expect(dateiname('Größen & Maße', 'md')).toBe('groessen-masse.md');
    expect(dateiname('  ', 'md')).toBe('entwurf.md');
  });
});

describe('entwurf-export — Review U2 (Befund 7, 13)', () => {
  it('Markdown: ein Zeilenumbruch beginnt keine Zeile, Auszeichnungen und HTML sind maskiert', () => {
    const md = alsMarkdown({ titel: 'T', quelle: 'ki', knoten: [
      { id: 'a', titel: '**fett**\n# Kopf', beschreibung: '<script>x</script>', keywords: ['a_b'] }] }, BESCHRIFTUNG);
    const zeilen = md.split('\n');
    expect(zeilen).toContain('- **\\*\\*fett\\*\\* # Kopf** — \\<script\\>x\\</script\\>');
    expect(zeilen).toContain('  Schlagworte: a\\_b');
    expect(zeilen.some((z) => z.startsWith('# Kopf'))).toBe(false);
  });

  it('JSON trägt „gekuerzt“', () => {
    expect(JSON.parse(alsJson({ ...DATEN, gekuerzt: true })).gekuerzt).toBe(true);
  });
});
