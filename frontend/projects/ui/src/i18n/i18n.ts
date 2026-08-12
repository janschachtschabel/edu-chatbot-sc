/**
 * Der Sprach-Seam (C1-b1): hält die aktive Sprache und übersetzt.
 *
 * Bewusst KEIN ``@Injectable``-Singleton, sondern eine schlichte Klasse mit
 * eigener Instanz je Widget — dieselbe Entscheidung wie bei `TourController`,
 * `SpeechService` und `MarkdownRenderer`. Grund: Modul-Global-State ist in
 * diesem Projekt ausgeschlossen, und zwei Widgets auf einer Seite dürfen
 * verschiedene Sprachen sprechen.
 *
 * Der Weg zur Oberfläche ist der schon vorhandene (seit C1-b2 gebaut): als
 * `[translate]`-Input an die Hülle bzw. die Shell, von dort in die
 * `GroupingContext`/`ResultGroupsContext`-Objekte, die die drei Grouping-
 * Renderer ohnehin bekommen. i18n erfindet keinen zweiten Verdrahtungsweg.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import { computed, signal } from '@angular/core';

import { Catalogue, TranslationParams, createTranslator } from './dictionary';
import { DEFAULT_LOCALE, Locale } from './locale';

export class I18n {
  private readonly _catalogues: Partial<Record<Locale, Catalogue>>;
  private readonly _locale = signal<Locale>(DEFAULT_LOCALE);

  /** Neu gebaut nur bei Sprachwechsel — nicht bei jedem `t()`-Aufruf. */
  private readonly _translate = computed(() =>
    createTranslator(this._catalogues[this._locale()] ?? this._base, this._base),
  );

  /**
   * @param _base Deutscher Katalog des Verbrauchers — zugleich Vorgabe und
   *   Rückfall. Als Argument und nicht eingebaut (C1-d1): mit dem Studio gibt
   *   es einen zweiten Verbraucher mit ganz anderen Schlüsseln, und ein
   *   eingebauter Vorgabe-Katalog läge in dessen Bundle unentfernbar herum —
   *   Default-Argumente lassen sich nicht wegtreeshaken.
   * @param catalogues Kataloge außer Deutsch. Fehlt die aktive Sprache hier,
   *   erscheint durchgehend Deutsch — sichtbar, aber nie leer.
   */
  constructor(
    private readonly _base: Catalogue,
    catalogues: Partial<Record<Locale, Catalogue>> = {},
  ) {
    this._catalogues = { de: _base, ...catalogues };
  }

  /** Aktive Sprache, lesbar für Anzeige und Umschalter. */
  readonly locale = this._locale.asReadonly();

  setLocale(locale: Locale): void {
    this._locale.set(locale);
  }

  /**
   * Übersetzt einen Schlüssel. Liest das Sprach-Signal **innerhalb** des
   * Aufrufs — dadurch registriert jede Template-Auswertung ihre Abhängigkeit
   * selbst und rendert beim Umschalten neu, ohne dass ein Aufrufer etwas von
   * Signals wissen muss.
   */
  t(key: string, params?: TranslationParams): string {
    return this._translate()(key, params);
  }
}

/** Signatur, die Komponenten und Kontext-Objekte durchreichen. Absichtlich nur
 *  die Funktion statt der ganzen Instanz: wer übersetzt, soll nicht umschalten
 *  können. */
export type TranslateFn = (key: string, params?: TranslationParams) => string;
