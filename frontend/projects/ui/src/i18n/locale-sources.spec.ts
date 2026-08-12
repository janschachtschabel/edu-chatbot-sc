// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  readBrowserLocale, readHostLocale, readStoredLocale, writeStoredLocale,
} from './locale-sources';

/** Frei erfundene Schlüssel: die echten gehören den Anwendungen, nicht dem
 *  Leser — genau das hält der letzte Test dieser Datei fest. */
const KEY = 'test_locale';

/**
 * Die drei **unreinen** Sprachquellen (C1-c). `locale.ts` bleibt rein und
 * entscheidet nur über Werte; hier steht das Lesen aus DOM, `navigator` und
 * Speicher — und nur das ist gegen eine echte Browser-Umgebung prüfbar.
 *
 * Muster wie `session/session-id.spec.ts`: jsdom statt Attrappen, damit die
 * `try`-Zweige (blockierter Speicher) wirklich durchlaufen werden.
 */

beforeEach(() => {
  document.documentElement.removeAttribute('lang');
  document.body.innerHTML = '';
  sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('readHostLocale', () => {
  it('liest das nächste [lang] über dem Element', () => {
    document.body.innerHTML = '<div lang="en"><span id="w"></span></div>';
    expect(readHostLocale(document.getElementById('w'))).toBe('en');
  });

  it('das nähere [lang] gewinnt gegen <html lang>', () => {
    document.documentElement.setAttribute('lang', 'de');
    document.body.innerHTML = '<article lang="en"><span id="w"></span></article>';
    expect(readHostLocale(document.getElementById('w'))).toBe('en');
  });

  it('findet <html lang> auch durch eine Shadow-Grenze hindurch', () => {
    // Der Regelfall auf komponentenbasierten Seiten: das Widget steckt im
    // Shadow-Baum eines fremden Elements. `closest` hielte dort an — und
    // <html lang> ist IMMER ausserhalb jedes Shadow-Roots, also wäre genau die
    // häufigste Quelle still unerreichbar.
    document.documentElement.setAttribute('lang', 'en');
    const wirt = document.createElement('div');
    document.body.appendChild(wirt);
    const schatten = wirt.attachShadow({ mode: 'open' });
    const drin = document.createElement('span');
    schatten.appendChild(drin);
    expect(readHostLocale(drin)).toBe('en');
  });

  it('ohne jedes [lang] null — nicht eine erfundene Sprache', () => {
    document.body.innerHTML = '<span id="w"></span>';
    expect(readHostLocale(document.getElementById('w'))).toBeNull();
    expect(readHostLocale(null)).toBeNull();
  });
});

describe('readBrowserLocale', () => {
  it('gibt navigator.language weiter — roh, nicht normalisiert', () => {
    // Normalisiert wird an einer Stelle (`resolveLocale`); ein Leser, der auch
    // normalisiert, wäre die zweite und könnte davon abweichen.
    vi.stubGlobal('navigator', { language: 'en-GB' });
    expect(readBrowserLocale()).toBe('en-GB');
  });

  it('null, wenn der Browser nichts angibt', () => {
    vi.stubGlobal('navigator', {});
    expect(readBrowserLocale()).toBeNull();
  });
});

describe('Speicher der Nutzerwahl', () => {
  it('schreibt und liest die gewählte Sprache', () => {
    writeStoredLocale(KEY, 'en');
    expect(sessionStorage.getItem(KEY)).toBe('en');
    expect(readStoredLocale(KEY)).toBe('en');
  });

  it('sessionStorage, nicht localStorage: die Wahl gilt für die Sitzung', () => {
    // Entscheid im Entwurf („persistiert je Sitzung"). Zugleich die sparsamere
    // Variante: kein langlebiger Origin-Speicher für eine Anzeigeeinstellung.
    writeStoredLocale(KEY, 'en');
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it('ohne vorherige Wahl null', () => {
    expect(readStoredLocale(KEY)).toBeNull();
  });

  it('blockierter Speicher bricht nicht — die Sprache fällt auf die anderen Quellen', () => {
    const kaputt = {
      getItem() { throw new Error('blocked'); },
      setItem() { throw new Error('blocked'); },
    };
    vi.stubGlobal('sessionStorage', kaputt);
    expect(() => writeStoredLocale(KEY, 'en')).not.toThrow();
    expect(readStoredLocale(KEY)).toBeNull();
  });

  it('zwei Schlüssel stören einander nicht — Widget und Studio wählen getrennt', () => {
    // Der Grund für den Parameter (C1-d1): Widget und Studio laufen auf
    // demselben Origin. Mit einem festen Schlüssel überschriebe die Wahl im
    // Studio still die Wahl im Widget und umgekehrt.
    writeStoredLocale('boerdi_locale', 'en');
    writeStoredLocale('boerdi_studio_locale', 'de');
    expect(readStoredLocale('boerdi_locale')).toBe('en');
    expect(readStoredLocale('boerdi_studio_locale')).toBe('de');
  });
});
