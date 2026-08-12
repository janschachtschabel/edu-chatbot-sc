import { describe, expect, it } from 'vitest';

import { DE } from './de';
import { EN } from './en';
import { createTranslator } from './dictionary';

/**
 * Der englische Katalog (C1-c). Geprüft wird nicht der Wortlaut — den kann ein
 * Test nicht beurteilen — sondern das, was still schiefgehen kann:
 * **Vollständigkeit**, **keine deutschen Reste**, **gleiche Platzhalter** und
 * die beiden Formatwerte, die kein Text sind.
 *
 * Der Rückfall je Schlüssel (`dictionary.ts`) ist die Sicherung gegen Lücken,
 * kein Freibrief für welche: ein ausgelieferter Katalog ist vollständig, sonst
 * mischt die Oberfläche unbemerkt zwei Sprachen.
 */
describe('EN-Katalog', () => {
  it('hat genau die Schlüssel des deutschen Katalogs', () => {
    expect(Object.keys(EN).sort()).toEqual(Object.keys(DE).sort());
  });

  it('jeder Text trägt dieselben Platzhalter wie sein deutsches Gegenstück', () => {
    // Ein fehlendes `{title}` bliebe stumm: der Satz stünde ohne den Wert da,
    // der ihn erst konkret macht. Ein zusätzliches bliebe als `{foo}` stehen.
    const platzhalter = (s: string) => (s.match(/\{(\w+)\}/g) ?? []).sort();
    for (const key of Object.keys(DE)) {
      expect(platzhalter(EN[key]), `Platzhalter weichen ab: ${key}`)
        .toEqual(platzhalter(DE[key]));
    }
  });

  it('kein Text ist unübersetzt aus dem Deutschen stehengeblieben', () => {
    // Grober, aber wirksamer Fang: Umlaute und ß gibt es im Englischen nicht.
    for (const [key, text] of Object.entries(EN)) {
      expect(text, `deutscher Rest in ${key}: ${text}`).not.toMatch(/[äöüÄÖÜß]/);
    }
  });

  it('kein Text ist eine wörtliche Kopie des deutschen — ausser den benannten', () => {
    // Diese Werte lauten in beiden Sprachen gleich. Die Liste ist bewusst
    // vollständig aufgezählt: käme durch Nachlässigkeit ein deutscher Satz
    // unübersetzt herüber, schlägt der Test an, statt ihn durchzuwinken.
    const gleichErlaubt = new Set([
      'chat.speakStop',            // Stop
      'chat.print.canvasFallback', // Material
      'inlineDoc.kind.ki_material', 'inlineDoc.kind.remix',
      'contentType.video', 'contentType.audio', 'contentType.quiz', 'contentType.material',
      'print.docTitle', 'print.meta', // nur Produktname + Platzhalter
    ]);
    const kopien = Object.keys(DE).filter(k => !gleichErlaubt.has(k) && EN[k] === DE[k]);
    expect(kopien, 'unübersetzt aus DE kopiert').toEqual([]);
  });

  it('beide Formatwerte sind für Intl brauchbar — sonst wirft das Druckfenster', () => {
    // C1-b4 hat diesen Test für DE gebaut und für C1-c vorgemerkt: ein
    // Tippfehler im BCP-47-Tag wäre eine RangeError erst beim Klick auf
    // „Drucken". Der Katalog ist Code — das fängt hier ein Test, kein try/catch.
    for (const katalog of [DE, EN]) {
      expect(() => new Intl.DateTimeFormat(katalog['format.dateLocale'])).not.toThrow();
      expect(katalog['format.htmlLang']).toMatch(/^[a-z]{2}$/);
    }
    expect(EN['format.htmlLang']).toBe('en');
  });

  it('als aktiver Katalog braucht er den deutschen Rückfall nirgends', () => {
    const t = createTranslator(EN, DE);
    for (const key of Object.keys(DE)) {
      expect(t(key), `${key} fiel auf Deutsch zurück`).toBe(EN[key]);
    }
  });
});


describe('EU-AI-Act-Kennzeichnung (W12)', () => {
  it('steht in BEIDEN Katalogen', () => {
    // Art. 50 verlangt, dass Nutzer erkennen koennen, mit einer KI zu sprechen.
    // Faellt der Schluessel in einem Katalog weg, gibt `createTranslator` den
    // Schluesselnamen aus — das waere hier keine Schoenheitsfrage, sondern eine
    // fehlende Rechtspflicht. Deshalb woertlich gepinnt.
    expect(DE['chat.aiGenerated']).toBe('KI-generierte Antwort');
    expect(EN['chat.aiGenerated']).toBe('AI-generated answer');
  });
});
