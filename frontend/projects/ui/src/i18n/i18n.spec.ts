import { computed } from '@angular/core';
import { describe, expect, it } from 'vitest';

import { DE } from './de';
import { I18n } from './i18n';

/**
 * Der Sprach-Seam (C1-b1). Vier Zusagen, auf denen alle weiteren Scheiben
 * stehen:
 *
 * 1. **Deutsch ohne Zutun.** Eine Instanz mit deutschem Basis-Katalog spricht
 *    Deutsch — das Widget muss ohne jede Konfiguration richtig rendern.
 * 2. **`t()` liest das Signal.** Nur deshalb genügt im Template ein
 *    `{{ t('…') }}`, damit der Umschalter (C1-c) wirkt; kein Aufrufer muss
 *    etwas von Signals wissen.
 * 3. **Eigene Instanz je Verbraucher.** Kein Modul-Global-State — zwei Widgets
 *    auf einer Seite dürfen verschiedene Sprachen sprechen.
 * 4. **Der Kern kennt keinen Katalog** (C1-d1). Erst mit dem Studio gibt es
 *    einen zweiten Verbraucher mit ganz anderen Schlüsseln; welcher Katalog
 *    Basis und Rückfall ist, entscheidet der Verbraucher.
 */

const EN = { 'widget.close': 'Close' };

describe('I18n', () => {
  it('spricht ohne Zutun die Sprache des Basis-Katalogs', () => {
    expect(new I18n(DE).t('widget.close')).toBe('Schließen');
  });

  it('übersetzt nach dem Umschalten', () => {
    const i18n = new I18n(DE, { en: EN });
    i18n.setLocale('en');
    expect(i18n.t('widget.close')).toBe('Close');
  });

  it('fällt je Schlüssel auf Deutsch zurück, wenn der Katalog lückenhaft ist', () => {
    const i18n = new I18n(DE, { en: EN });
    i18n.setLocale('en');
    // 'widget.restart' fehlt im englischen Katalog oben.
    expect(i18n.t('widget.restart')).toBe('Neuer Chat');
  });

  it('fällt auf Deutsch zurück, wenn zur Sprache gar kein Katalog da ist', () => {
    const i18n = new I18n(DE);
    i18n.setLocale('en');
    expect(i18n.t('widget.close')).toBe('Schließen');
  });

  it('liest das Sprach-Signal IN t() — sonst würde kein Template neu rendern', () => {
    const i18n = new I18n(DE, { en: EN });
    // `computed` verfolgt nur, was während der Auswertung gelesen wird. Bleibt
    // der Wert nach setLocale stehen, hat t() die Sprache nicht als Signal
    // gelesen und jedes Template im Widget bliebe beim Umschalten deutsch.
    const abgeleitet = computed(() => i18n.t('widget.close'));
    expect(abgeleitet()).toBe('Schließen');
    i18n.setLocale('en');
    expect(abgeleitet()).toBe('Close');
  });

  it('meldet die aktive Sprache nach außen', () => {
    const i18n = new I18n(DE);
    expect(i18n.locale()).toBe('de');
    i18n.setLocale('en');
    expect(i18n.locale()).toBe('en');
  });

  it('reicht Platzhalter durch', () => {
    const i18n = new I18n(DE, { en: { 'x.y': 'Sources used ({count})' } });
    i18n.setLocale('en');
    expect(i18n.t('x.y', { count: 3 })).toBe('Sources used (3)');
  });

  it('hält zwei Instanzen auseinander (kein Modul-Global-State)', () => {
    const a = new I18n(DE, { en: EN });
    const b = new I18n(DE, { en: EN });
    a.setLocale('en');
    expect(a.t('widget.close')).toBe('Close');
    expect(b.t('widget.close')).toBe('Schließen');
  });

  it('kennt von sich aus KEINEN Katalog — sonst schleppte das Studio die '
    + 'Widget-Texte als toten Rückfall mit', () => {
    // Der Kern darf `de.ts` nicht importieren: die Studio-Schlüssel sind
    // andere, und ein eingebauter Vorgabe-Katalog wäre im Studio-Bundle
    // unentfernbar (Default-Werte lassen sich nicht wegtreeshaken).
    const i18n = new I18n({ 'studio.nav': 'Navigation' });
    expect(i18n.t('studio.nav')).toBe('Navigation');
    expect(i18n.t('widget.close')).toBe('widget.close');
  });
});
