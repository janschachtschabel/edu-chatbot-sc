import { describe, expect, it } from 'vitest';

import manifest from './manifest.json';
import { ARTEN, artBezeichnung, artSymbol, dateiname, markdownDatei } from './inhaltsrahmen';

describe('Inhaltsrahmen — Hilfen', () => {
  it('kennt jede Art aus dem Manifest, mit Bezeichnung in beiden Sprachen', () => {
    const imManifest = manifest.eingabe.properties.art.enum;
    expect([...Object.keys(ARTEN)].sort()).toEqual([...imManifest].sort());
    for (const art of imManifest) {
      expect(artBezeichnung(art, 'de')).not.toBe('');
      expect(artBezeichnung(art, 'en')).not.toBe('');
      expect(artSymbol(art)).toContain('<svg');
    }
  });

  it('fällt bei unbekannter Art auf „Inhalt“ und das Dokument-Symbol zurück', () => {
    expect(artBezeichnung('gibt_es_nicht', 'de')).toBe('Inhalt');
    expect(artBezeichnung('gibt_es_nicht', 'en')).toBe('Content');
    expect(artSymbol('gibt_es_nicht')).toBe(artSymbol('dokument'));
  });

  it('Namen aus Object.prototype und Nicht-Texte fallen sauber zurück', () => {
    for (const art of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) {
      expect(artBezeichnung(art, 'de')).toBe('Inhalt');
      expect(artSymbol(art)).toBe(artSymbol('dokument'));
    }
    expect(artBezeichnung(42 as unknown as string, 'de')).toBe('Inhalt');
  });

  it('bildet einen lesbaren Dateinamen aus dem Titel', () => {
    expect(dateiname('Unterrichtsverlaufsplan: Optik & Licht!')).toBe('unterrichtsverlaufsplan-optik-licht.md');
    expect(dateiname('Übung für Größe')).toBe('uebung-fuer-groesse.md');
    expect(dateiname('Résumé der Stunde')).toBe('resume-der-stunde.md');
    expect(dateiname('  ')).toBe('inhalt.md');
    expect(dateiname('x'.repeat(200)).length).toBeLessThanOrEqual(63);
  });

  it('setzt den Titel als Überschrift vor das Markdown, außer er steht schon da', () => {
    expect(markdownDatei('Plan', 'Text')).toBe('# Plan\n\nText\n');
    expect(markdownDatei('Plan', '# Plan\n\nText')).toBe('# Plan\n\nText\n');
    expect(markdownDatei('Plan', undefined as unknown as string)).toBe('# Plan\n');
  });
});
