import { describe, expect, it } from 'vitest';

import manifest from './manifest.json';
import { groesse, texte } from './upload-texte';
import { uebertragenTexte } from './upload-uebertragen-texte';

/** Alle Texte eines Katalogs: Zeichenketten direkt, Funktionen über ihren Quelltext (Vorlagen). */
function alleTexte(wert: unknown): string[] {
  if (typeof wert === 'string') return [wert];
  if (typeof wert === 'function') return [String(wert)];
  if (wert && typeof wert === 'object') return Object.values(wert).flatMap(alleTexte);
  return [];
}

describe('Texte ui_upload (U3-1a)', () => {
  it('jede Warnung und jede Rolle gibt es auf Deutsch und Englisch, nicht gleich', () => {
    const de = texte('de');
    const en = texte('en');
    expect(Object.keys(en.warnung).sort()).toEqual(Object.keys(de.warnung).sort());
    for (const k of Object.keys(de.warnung) as (keyof typeof de.warnung)[]) {
      expect(de.warnung[k](3)).not.toBe(en.warnung[k](3));
    }
    expect(Object.keys(en.rolle).sort()).toEqual(Object.keys(de.rolle).sort());
  });

  it('Einzahl und Mehrzahl, Zahlen je Sprache formatiert', () => {
    expect(texte('de').dateien(1)).toBe('1 Datei');
    expect(texte('de').dateien(1234)).toBe('1.234 Dateien');
    expect(texte('en').dateien(1234)).toBe('1,234 files');
    expect(texte('en').ordner(1)).toBe('1 folder');
  });

  it('Größen in kB und MB mit einer Nachkommastelle', () => {
    expect(groesse('de', 1_500_000)).toBe('1,5 MB');
    expect(groesse('en', 1_500_000)).toBe('1.5 MB');
    expect(groesse('de', 12_300)).toBe('12 kB');
    expect(groesse('de', 10)).toBe('1 kB');
  });

  // Plan 2026-11-16, TG-1 (G-E4): das Upload-Feld stellt nur bereit — kein Knopf und kein Text nennt
  // ein Ziel wie den Themenbaum; was mit den Daten geschieht, klären Ablauf oder KI danach.
  it('TG-1: kein Text des Moduls nennt einen Themenbaum (de/en)', () => {
    for (const sprache of ['de', 'en'] as const) {
      const saetze = [...alleTexte(texte(sprache)), ...alleTexte(uebertragenTexte(sprache))];
      expect(saetze.length).toBeGreaterThan(50);
      expect(saetze.filter((s) => /themenbaum|topic.?tree/i.test(s))).toEqual([]);
    }
  });

  it('TG-1: neutraler Knopf „Lesen lassen“ und „Weiter“ nach dem Lesen', () => {
    expect(texte('de').lesenLassen).toBe('Lesen lassen');
    expect(texte('en').lesenLassen).toBe('Read document');
    expect(texte('de').weiterNachLesen).toBe('Weiter');
    expect(texte('en').weiterNachLesen).toBe('Continue');
    expect(texte('de').blaseDokument('Lehr.pdf')).toBe('Dokument „Lehr.pdf“ lesen lassen');
    expect(texte('en').blaseDokument('Lehr.pdf')).toBe('Read “Lehr.pdf”');
    // Review TG-1, m4: der Name trägt die Beschriftung und sagt, was gesendet wird
    expect(texte('de').weiterNachLesenName).toBe('Weiter: gelesenes Dokument an den Chat');
  });

  // Plan 2026-11-16, TG-3a (G-E1): seit dem Teil `struktur` gehen auch die Dateinamen an den Chat
  it('TG-3a: der Datenschutzsatz nennt Ordner- und Dateinamen', () => {
    expect(texte('de').datenschutzBeides).toBe('Ordner- und Dateinamen gehen an den Chat. Das Strukturdokument '
      + 'wird erst hochgeladen, wenn du es lesen lässt, und Dateien gehen erst an WLO, wenn du sie überträgst – '
      + 'bis dahin bleibt alles auf deinem Gerät.');
    for (const t of [texte('de'), texte('en')]) {
      for (const satz of [t.datenschutz, t.datenschutzDokument, t.datenschutzAblage, t.datenschutzBeides]) {
        expect(satz).toMatch(/^(Ordner- und Dateinamen gehen an den Chat|Folder and file names go to the chat)/);
      }
    }
  });
});

// Plan 2026-11-16, TG-1: das Manifest kennt kein Ziel mehr — `zweck` neutral, der alte Wert bleibt gültig.
describe('Manifest ui_upload (TG-1)', () => {
  const antwort = manifest.antwort as unknown as {
    properties: { aktion: { enum: string[] }; dokument: { required: string[]; properties: Record<string, unknown> } };
  };
  const zweck = (s: unknown) => (s as { properties: { zweck: { enum: string[] } } }).properties.zweck.enum;

  it('kein ziel am Dokument, keine Aktion ordner_als_entwurf', () => {
    expect(antwort.properties.aktion.enum).toEqual(['erfasst', 'dokument', 'uebertragen']);
    expect(antwort.properties.dokument.required).not.toContain('ziel');
    expect(Object.keys(antwort.properties.dokument.properties)).not.toContain('ziel');
  });

  it('zweck bereitstellen, sammlungsstruktur bleibt gültig (Rückwärts)', () => {
    expect(zweck(manifest.eingabe)).toEqual(['bereitstellen', 'sammlungsstruktur']);
    expect(zweck(manifest.dienst.parameter)).toEqual(['bereitstellen', 'sammlungsstruktur']);
    expect(manifest.beispiele.every((b) => b.daten.zweck === 'bereitstellen')).toBe(true);
  });

  it('Beschreibung und wann ohne Themenbaum-Anweisung', () => {
    const text = [manifest.beschreibung, ...manifest.wann].join(' ');
    expect(text).not.toMatch(/themenbaum|entwurf/i);
  });
});

// Plan 2026-11-16, TG-3a: das Antwortschema kennt die Dateien je Ordner, das Manifest den Teil `struktur`.
describe('Manifest ui_upload (TG-3a)', () => {
  const antwort = manifest.antwort as unknown as {
    $defs: Record<string, { required?: string[]; properties: Record<string, { items?: { $ref?: string } }> }>;
    properties: { warnungen: { items: { enum: string[] } } };
  };

  it('jede Ordnerebene trägt `dateiliste` (nicht Pflicht — alte Antworten bleiben gültig)', () => {
    const ebenen = Object.entries(antwort.$defs).filter(([name]) => name.startsWith('ordner'));
    expect(ebenen).toHaveLength(9);
    for (const [, ebene] of ebenen) {
      expect(ebene.properties['dateiliste'].items?.$ref).toBe('#/$defs/datei');
      expect(ebene.required).not.toContain('dateiliste');
    }
    // Review TG-3a–c, R3-4: der Name ist Pflicht — außer bei Rolle „ignorieren“, dort verboten
    expect(antwort.$defs['datei'].required).toEqual(['i', 'endung', 'groesse', 'rolle']);
    const datei = antwort.$defs['datei'] as unknown as {
      if: { properties: { rolle: { const: string } } }; then: unknown; else: { required: string[] } };
    expect(datei.if.properties.rolle.const).toBe('ignorieren');
    expect(datei.then).toEqual({ not: { required: ['name'] } });
    expect(datei.else.required).toEqual(['name']);
  });

  it('die Warnung namen_gekuerzt und der Teil struktur', () => {
    expect(antwort.properties.warnungen.items.enum).toContain('namen_gekuerzt');
    expect((manifest as unknown as { vorgang: { schreibt: string[] } }).vorgang.schreibt)
      // Plan 2026-11-16, TG-3d: dazu die Verweise auf alle gelesenen Strukturdokumente
      .toEqual(['structure', 'struktur', 'document', 'strukturdokument']);
  });
});
