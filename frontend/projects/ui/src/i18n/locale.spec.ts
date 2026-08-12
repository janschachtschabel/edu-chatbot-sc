import { describe, expect, it } from 'vitest';

import { DEFAULT_LOCALE, SUPPORTED_LOCALES, nextLocale, normalizeLocale, resolveLocale } from './locale';

/**
 * Rangfolge der Sprachquellen (C1-a, Entscheid 2026-08-02 —
 * `docs/plans/2026-08-02-c1-i18n.md`):
 *
 *     Umschalter > Element-Attribut > Host-[lang] > Browser > 'de'
 *
 * `resolveLocale` ist bewusst **rein**: die unreinen Quellen (sessionStorage,
 * navigator, DOM) liest der Aufrufer und reicht sie als Werte herein. Sonst
 * wäre die Rangfolge nur über eine gemockte Browser-Umgebung prüfbar — und
 * genau sie ist der Teil, der stimmen muss.
 */

describe('normalizeLocale', () => {
  it('nimmt die unterstützten Sprachen unverändert', () => {
    expect(normalizeLocale('de')).toBe('de');
    expect(normalizeLocale('en')).toBe('en');
  });

  it('kürzt einen Regions-Tag auf die Sprache', () => {
    expect(normalizeLocale('en-GB')).toBe('en');
    expect(normalizeLocale('de-AT')).toBe('de');
  });

  it('ist gross-/kleinschreibungs- und leerzeichentolerant', () => {
    // Host-Attribute kommen so, wie die einbettende Seite sie schreibt.
    expect(normalizeLocale('  EN ')).toBe('en');
    expect(normalizeLocale('De-CH')).toBe('de');
  });

  it('gibt null für nicht unterstützte oder leere Werte', () => {
    for (const raw of ['fr', '', '   ', null, undefined, 'english']) {
      expect(normalizeLocale(raw)).toBeNull();
    }
  });
});

describe('resolveLocale', () => {
  it('ohne jede Quelle die Vorgabe Deutsch', () => {
    expect(DEFAULT_LOCALE).toBe('de');
    expect(resolveLocale({})).toBe('de');
  });

  it('der Umschalter schlägt alles andere', () => {
    // Sonst spränge die Sprache beim nächsten Rendern auf die Host-Vorgabe zurück.
    expect(resolveLocale({ chosen: 'de', attribute: 'en', host: 'en', browser: 'en' }))
      .toBe('de');
  });

  it('das Element-Attribut schlägt Host-Seite und Browser', () => {
    expect(resolveLocale({ attribute: 'en', host: 'de', browser: 'de' })).toBe('en');
  });

  it('die Host-Seite schlägt den Browser', () => {
    // Ein deutscher Nutzer auf einer englischen Seite soll die Seite lesen können.
    expect(resolveLocale({ host: 'en', browser: 'de-DE' })).toBe('en');
  });

  it('der Browser greift, wenn sonst nichts gesetzt ist', () => {
    expect(resolveLocale({ browser: 'en-US' })).toBe('en');
  });

  it('überspringt unbrauchbare Werte, statt auf die Vorgabe zu fallen', () => {
    // Eine Host-Seite mit lang="fr" darf den Browser-Wunsch nicht verschlucken.
    expect(resolveLocale({ attribute: '', host: 'fr', browser: 'en' })).toBe('en');
  });
});

describe('nextLocale', () => {
  it('schaltet zwischen den beiden unterstützten Sprachen hin und her', () => {
    expect(nextLocale('de')).toBe('en');
    expect(nextLocale('en')).toBe('de');
  });

  it('kommt aus jeder Sprache in höchstens so vielen Schritten zurück, wie es Sprachen gibt', () => {
    // Bindet den Umschalter an SUPPORTED_LOCALES statt an ein „de↔en"-Paar:
    // käme eine dritte Sprache dazu, schlüge dieser Test an, wenn sie im
    // Rundlauf fehlte — statt sie still unerreichbar zu lassen.
    for (const start of SUPPORTED_LOCALES) {
      const gesehen = new Set([start]);
      let aktuell = start;
      for (let i = 0; i < SUPPORTED_LOCALES.length; i++) {
        aktuell = nextLocale(aktuell);
        gesehen.add(aktuell);
      }
      expect(aktuell).toBe(start);
      expect(gesehen.size).toBe(SUPPORTED_LOCALES.length);
    }
  });
});
