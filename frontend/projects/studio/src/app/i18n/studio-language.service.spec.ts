// @vitest-environment jsdom
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from './studio-language.service';

/**
 * Die Spracheinstellung des Studios (C1-d1).
 *
 * Sie ist bewusst **unabhängig vom Widget**: dieselbe Rangfolge, aber ein
 * eigener Speicher-Schlüssel und ein eigener Katalog. Wer im Studio auf
 * Englisch stellt, stellt damit nicht die Chat-Oberfläche einer Vorschau um —
 * und umgekehrt. Der Entwurf hält genau das fest („eigene, vom Widget
 * unabhängige Spracheinstellung").
 *
 * Anders als das Widget ist das Studio eine ganze Seite. Darum trägt es hier
 * zusätzlich `<html lang>` nach — ohne das liest ein Screenreader englische
 * Oberfläche mit deutscher Aussprache vor (WCAG 3.1.1).
 */

function service(): StudioLanguageService {
  TestBed.configureTestingModule({});
  return TestBed.inject(StudioLanguageService);
}

beforeEach(() => {
  TestBed.resetTestingModule();
  sessionStorage.clear();
  document.documentElement.setAttribute('lang', 'de');
  // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund). Da der Browser
  // beim Studio die zweitstärkste Quelle ist, muss jeder Test, der Deutsch
  // erwartet, das selbst herstellen — hier über `navigator`, denn genau diese
  // Quelle ist der Gegenstand.
  vi.stubGlobal('navigator', { language: 'de-DE' });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('StudioLanguageService', () => {
  it('spricht ohne Zutun Deutsch', () => {
    expect(service().i18n.t('studio.nav.label')).toBe('Navigation');
  });

  it('übersetzt nach dem Umschalten', () => {
    const lang = service();
    lang.toggle();
    expect(lang.i18n.locale()).toBe('en');
    expect(lang.i18n.t('studio.nav.label')).toBe('Navigation');
    expect(lang.i18n.t('studio.logout')).toBe('Sign out');
  });

  it('merkt die Wahl unter dem EIGENEN Schlüssel — nicht unter dem des Widgets', () => {
    // Widget und Studio laufen auf demselben Origin. Teilten sie den Schlüssel,
    // schaltete die Wahl hier still die Vorschau mit um.
    service().toggle();
    expect(sessionStorage.getItem(STUDIO_LOCALE_STORAGE_KEY)).toBe('en');
    expect(sessionStorage.getItem('boerdi_locale')).toBeNull();
  });

  it('nimmt die gemerkte Wahl beim nächsten Start wieder auf', () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'en');
    expect(service().i18n.locale()).toBe('en');
  });

  it('die Nutzerwahl schlägt den Browser', () => {
    // Sonst spränge die Sprache beim nächsten Laden auf das Browser-Profil
    // zurück und der Umschalter wäre für eine Sitzung wirkungslos.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    vi.stubGlobal('navigator', { language: 'en-GB' });
    expect(service().i18n.locale()).toBe('de');
  });

  it('ohne Wahl entscheidet der Browser', () => {
    vi.stubGlobal('navigator', { language: 'en-GB' });
    expect(service().i18n.locale()).toBe('en');
  });

  it('nimmt <html lang> NICHT als Quelle — das ist die eigene Ausgabe', () => {
    // `index.html` liefert fest `lang="de"`. Würde die Auflösung das lesen,
    // käme `navigator.language` nie zum Zug und die Quelle wäre still tot.
    // Beim Widget ist die Quelle richtig: dort gehört die Seite jemand anderem.
    document.documentElement.setAttribute('lang', 'de');
    vi.stubGlobal('navigator', { language: 'en-GB' });
    expect(service().i18n.locale()).toBe('en');
  });

  it('ohne jede Angabe Deutsch', () => {
    vi.stubGlobal('navigator', { language: 'fr-FR' });
    expect(service().i18n.locale()).toBe('de');
  });

  it('trägt <html lang> nach — sonst spricht der Screenreader Englisch deutsch aus', () => {
    const lang = service();
    expect(document.documentElement.lang).toBe('de');
    lang.toggle();
    expect(document.documentElement.lang).toBe('en');
  });

  it('benennt am Umschalter das ZIEL, nicht den Zustand', () => {
    const lang = service();
    expect(lang.switchCode()).toBe('EN');
    expect(lang.switchLabel()).toBe('Auf Englisch umschalten');
    lang.toggle();
    expect(lang.switchCode()).toBe('DE');
    expect(lang.switchLabel()).toBe('Switch to German');
  });

  // ── Mehrzahl (C1-d3a) ───────────────────────────────────────────────
  //
  // Bis C1-d2 stand die Mehrzahl handgeschrieben in den Ansichten
  // (`total === 1 ? 'Bereich' : 'Bereiche'`). Das ging, solange es eine Sprache
  // gab: die Grenze zwischen Einzahl und Mehrzahl ist je Sprache verschieden,
  // und ein `=== 1` im Template ist die deutsche Regel, fest verdrahtet.
  describe('plural', () => {
    it('wählt die Form nach der Regel der aktiven Sprache', () => {
      const lang = service();
      expect(lang.plural('areas.count', 1)).toBe('1 Bereich');
      expect(lang.plural('areas.count', 3)).toBe('3 Bereiche');
      expect(lang.plural('areas.count', 0)).toBe('0 Bereiche');
      lang.toggle();
      expect(lang.plural('areas.count', 1)).toBe('1 area');
      expect(lang.plural('areas.count', 3)).toBe('3 areas');
    });

    it('reicht die Anzahl als {count} durch und nimmt weitere Platzhalter an', () => {
      const lang = service();
      expect(lang.plural('schemaForm.unmapped', 2, { keys: 'a, b' }))
        .toContain('2 Schlüssel');
    });
  });

  // ── Aufzählung (C1-d3c) ─────────────────────────────────────────────
  //
  // Dieselbe Klasse wie die Mehrzahl: `gaps.join(' und ')` in
  // `rag-ingest.component.ts` ist die deutsche Aufzählungsregel, fest
  // verdrahtet. Ein übersetzter Binder ` und ` wäre kein Ausweg, sondern
  // genau die Satzbildung aus Bruchstücken, die C1-d3a abgeschafft hat — wo
  // ein Komma steht und ob vor dem letzten Glied eines steht, ist Sache der
  // Sprache. `Intl.ListFormat` ist die Plattform-Antwort und braucht dafür
  // keinen einzigen Katalog-Eintrag.
  describe('list', () => {
    it('verbindet nach der Aufzählungsregel der aktiven Sprache', () => {
      const lang = service();
      expect(lang.list(['ein Wissensbereich', 'eine Datei']))
        .toBe('ein Wissensbereich und eine Datei');

      lang.toggle();
      expect(lang.list(['a knowledge area', 'a file'])).toBe('a knowledge area and a file');
    });

    it('ein einzelnes Glied steht für sich, ohne Binder', () => {
      expect(service().list(['eine Datei'])).toBe('eine Datei');
    });
  });

  // ── Mehrzahl MIT Auszeichnung (C1-d4b3) ─────────────────────────────
  //
  // Der Satz der Pattern-Nutzung braucht beides zugleich: die Mehrzahlform
  // hängt an der Anzahl, und die Anzahl selbst steht hervorgehoben im Satz.
  // `splitRich(lang.plural(…))` wäre der naheliegende Weg und genau falsch —
  // `plural()` setzt die Werte ein, und danach zu teilen hiesse, einen
  // eingesetzten Wert über die Auszeichnung entscheiden zu lassen.
  describe('richPlural', () => {
    it('wählt die Form nach der Anzahl und zerlegt die Auszeichnung', () => {
      const lang = service();
      expect(lang.richPlural('evalPattern.total', 1, { combos: '1 Kombination' })).toEqual([
        { kind: 'strong', text: '1 Turn' },
        { kind: 'plain', text: ' in 1 Kombination.' },
      ]);
      expect(lang.richPlural('evalPattern.total', 19, { combos: '5 Kombinationen' })).toEqual([
        { kind: 'strong', text: '19 Turns' },
        { kind: 'plain', text: ' in 5 Kombinationen.' },
      ]);

      lang.toggle();
      expect(lang.richPlural('evalPattern.total', 1, { combos: '1 combination' })).toEqual([
        { kind: 'strong', text: '1 turn' },
        { kind: 'plain', text: ' in 1 combination.' },
      ]);
    });

    it('teilt VOR dem Einsetzen — ein Stern im Wert zeichnet nichts aus', () => {
      // Dieselbe Eigenschaft wie bei `rich()`, hier eigens geprüft: sie geht
      // verloren, sobald jemand die Reihenfolge der beiden Schritte tauscht.
      expect(service().richPlural('evalPattern.total', 2, { combos: '*keine*' })).toEqual([
        { kind: 'strong', text: '2 Turns' },
        { kind: 'plain', text: ' in *keine*.' },
      ]);
    });
  });
});
