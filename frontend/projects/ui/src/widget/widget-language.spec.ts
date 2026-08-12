// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WIDGET_LOCALE_STORAGE_KEY as LOCALE_STORAGE_KEY, WidgetLanguage } from './widget-language';

/**
 * Die Sprache eines Widgets (C1-c) — Rangfolge, Umschalten, Merken.
 *
 * `locale.spec.ts` beweist die Rangfolge auf Werten, `locale-sources.spec.ts`
 * das Lesen der Quellen. Hier ist geprüft, dass beides zusammen an EINEM Widget
 * das Richtige ergibt: dass wirklich alle vier Quellen angeschlossen sind. Ein
 * vergessener Anschluss wäre sonst genau die Klasse „gebaut, aber ohne
 * Verbraucher", die dieses Projekt schon mehrfach getroffen hat.
 */
function bauen(attribut = ''): { sprache: WidgetLanguage; wirt: HTMLElement } {
  const wirt = document.createElement('div');
  document.body.appendChild(wirt);
  return {
    sprache: new WidgetLanguage({ attribute: () => attribut, hostElement: () => wirt }),
    wirt,
  };
}

beforeEach(() => {
  document.documentElement.removeAttribute('lang');
  document.body.innerHTML = '';
  sessionStorage.clear();
  vi.stubGlobal('navigator', { language: 'de-DE' });
});

describe('WidgetLanguage — Rangfolge am echten Widget', () => {
  it('ohne jede Quelle Deutsch', () => {
    const { sprache } = bauen();
    sprache.resolve();
    expect(sprache.i18n.locale()).toBe('de');
  });

  it('der Browser greift, wenn sonst nichts gesetzt ist', () => {
    vi.stubGlobal('navigator', { language: 'en-US' });
    const { sprache } = bauen();
    sprache.resolve();
    expect(sprache.i18n.locale()).toBe('en');
  });

  it('die Host-Seite schlägt den Browser', () => {
    document.documentElement.setAttribute('lang', 'en');
    const { sprache } = bauen();
    sprache.resolve();
    expect(sprache.i18n.locale()).toBe('en');
  });

  it('das Element-Attribut schlägt die Host-Seite', () => {
    document.documentElement.setAttribute('lang', 'de');
    const { sprache } = bauen('en');
    sprache.resolve();
    expect(sprache.i18n.locale()).toBe('en');
  });

  it('die gemerkte Nutzerwahl schlägt alles', () => {
    sessionStorage.setItem(LOCALE_STORAGE_KEY, 'de');
    document.documentElement.setAttribute('lang', 'en');
    vi.stubGlobal('navigator', { language: 'en-US' });
    const { sprache } = bauen('en');
    sprache.resolve();
    expect(sprache.i18n.locale()).toBe('de');
  });
});

describe('WidgetLanguage — Umschalten', () => {
  it('schaltet um und merkt die Wahl', () => {
    const { sprache } = bauen();
    sprache.resolve();
    sprache.toggle();
    expect(sprache.i18n.locale()).toBe('en');
    expect(sessionStorage.getItem(LOCALE_STORAGE_KEY)).toBe('en');
  });

  it('die Wahl überlebt ein erneutes Auflösen — sonst spränge sie zurück', () => {
    document.documentElement.setAttribute('lang', 'de');
    const { sprache } = bauen('de');
    sprache.resolve();
    sprache.toggle();
    sprache.resolve(); // z.B. weil der Host das `language`-Attribut neu setzt
    expect(sprache.i18n.locale()).toBe('en');
  });

  it('übersetzt nach dem Umschalten wirklich englisch', () => {
    const { sprache } = bauen();
    sprache.resolve();
    expect(sprache.i18n.t('widget.close')).toBe('Schließen');
    sprache.toggle();
    expect(sprache.i18n.t('widget.close')).toBe('Close');
  });

  it('zwei Widgets auf einer Seite schalten unabhängig um', () => {
    // Der Grund, warum `I18n` kein Root-Singleton ist.
    const a = bauen().sprache;
    const b = bauen().sprache;
    a.resolve();
    b.resolve();
    a.toggle();
    expect(a.i18n.locale()).toBe('en');
    expect(b.i18n.locale()).toBe('de');
  });
});

describe('WidgetLanguage — Beschriftung des Knopfs', () => {
  it('Kürzel und Name benennen das ZIEL, nicht die aktive Sprache', () => {
    const { sprache } = bauen();
    sprache.resolve();
    expect(sprache.switchCode()).toBe('EN');
    expect(sprache.switchLabel()).toBe('Auf Englisch umschalten');
  });

  it('nach dem Umschalten zeigt der Knopf den Rückweg — in der neuen Sprache', () => {
    const { sprache } = bauen();
    sprache.resolve();
    sprache.toggle();
    expect(sprache.switchCode()).toBe('DE');
    expect(sprache.switchLabel()).toBe('Switch to German');
  });
});
