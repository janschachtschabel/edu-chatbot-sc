/**
 * Die Spracheinstellung des Studios (C1-d1) — unabhängig vom Widget.
 *
 * Rangfolge **Nutzerwahl › Browser › Deutsch** — zwei der vier Widget-Quellen
 * fallen weg, und beide aus einem sachlichen Grund:
 *
 *  - **Element-Attribut**: das Studio ist eine Anwendung, kein eingebettetes
 *    Element. Es gibt keine einbettende Seite, die es konfigurieren könnte.
 *  - **`<html lang>`**: das ist beim Studio kein fremder Hinweis, sondern die
 *    **eigene Ausgabe** — `apply()` schreibt den Wert dorthin. Läse die
 *    Auflösung ihn wieder ein, stünde dort dauerhaft das `lang="de"` aus
 *    `index.html` und der Browser-Wunsch käme nie zum Zug. Beim Widget ist die
 *    Quelle richtig, weil die Seite dort wirklich jemand anderem gehört.
 *
 * **Eigener Speicher-Schlüssel und eigener Katalog**: beide Oberflächen laufen
 * auf demselben Origin; teilten sie den Schlüssel, stellte eine Wahl im Studio
 * still die Chat-Vorschau mit um.
 *
 * `@Injectable({ providedIn: 'root' })` und damit bewusst ANDERS als
 * `WidgetLanguage`: dort verbietet sich ein Singleton, weil zwei Widgets auf
 * einer Seite verschiedene Sprachen sprechen dürfen. Das Studio ist eine SPA —
 * es gibt genau eine Instanz je Seite, und alle 13 Studio-Dienste sind aus
 * demselben Grund root-provided. Kein Modul-Global-State: der Zustand hängt am
 * Injector, nicht am Modul.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import { Injectable, computed } from '@angular/core';
import {
  I18n, Locale, nextLocale, readBrowserLocale, readStoredLocale, resolveLocale, splitRich,
  writeStoredLocale,
} from '@boerdi/ui';
import type { RichSegment } from '@boerdi/ui';

import { STUDIO_DE } from './de';
import { STUDIO_EN } from './en';

/** Eigener Schlüssel — siehe Klassen-Kommentar. */
export const STUDIO_LOCALE_STORAGE_KEY = 'boerdi_studio_locale';

/**
 * Die Form von `StudioLanguageService.t`, damit reine Funktionen und
 * nicht-injizierbare Klassen sie als Parameter annehmen können, statt sich
 * einen Dienst zu holen (`describeAreaError`, `describeRagError`,
 * `AreaDocEditor`).
 *
 * Wohnt hier und nicht bei einem der Verbraucher: der Übersetzer gehört dem
 * i18n-Modul. Stünde der Typ im `schema-form`, müsste `core` von dort
 * importieren — nach aussen statt nach innen.
 */
export type Translate = (key: string, params?: Record<string, string | number>) => string;

/** Zielsprache → Schlüssel des zugänglichen Namens. Erlaubnisliste statt
 *  `'studio.language.to' + ziel`: ein dynamischer Schlüssel gäbe bei einer
 *  unbekannten Sprache den Schlüssel selbst als Beschriftung aus. */
const SWITCH_LABEL_KEY: Record<Locale, string> = {
  de: 'studio.language.toDe',
  en: 'studio.language.toEn',
};

@Injectable({ providedIn: 'root' })
export class StudioLanguageService {
  /** Beide Kataloge liegen im Bundle — kein Nachladen, also kein Ladezustand
   *  und kein Fehlerpfad. */
  readonly i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });

  constructor() {
    this.apply(resolveLocale({
      chosen: readStoredLocale(STUDIO_LOCALE_STORAGE_KEY),
      browser: readBrowserLocale(),
    }));
  }

  /** Nächste Sprache im Rundlauf, gemerkt. Das Merken ist nicht Komfort:
   *  ohne die oberste Quelle spränge die Sprache beim nächsten Laden auf
   *  `<html lang>` zurück. */
  toggle(): void {
    const ziel = nextLocale(this.i18n.locale());
    writeStoredLocale(STUDIO_LOCALE_STORAGE_KEY, ziel);
    this.apply(ziel);
  }

  /** Übersetzen für Komponenten. Als gebundener Pfeil, damit Templates ihn
   *  direkt als `t(…)` aufrufen können. */
  readonly t = (key: string, params?: Record<string, string | number>): string =>
    this.i18n.t(key, params);

  /**
   * Mehrzahl (C1-d3a): wählt `<key>.one` oder `<key>.other` nach der Regel der
   * aktiven Sprache und reicht die Anzahl als `{count}` durch.
   *
   * Bis hierher stand die Mehrzahl handgeschrieben in den Ansichten
   * (`total === 1 ? 'Bereich' : 'Bereiche'`). Das ist die **deutsche** Regel,
   * fest verdrahtet — mit zwei Sprachen ist es die Frage der Sprache, wo die
   * Grenze liegt. `Intl.PluralRules` ist die Plattform-Antwort darauf und
   * kostet nicht mehr als das `=== 1`, das es ersetzt.
   *
   * Deutsch und Englisch kennen beide nur `one`/`other`; eine Sprache mit
   * weiteren Formen müsste die zugehörigen Schlüssel mitbringen, sonst zeigte
   * sie den Schlüssel selbst — sichtbar, nicht still falsch.
   */
  readonly plural = (
    key: string, count: number, params?: Record<string, string | number>,
  ): string => this.i18n.t(this.pluralKey(key, count), { count, ...params });

  /**
   * Aufzählung (C1-d3c): verbindet fertige Glieder nach der Regel der aktiven
   * Sprache — „A und B" auf Deutsch, „A and B" auf Englisch, mit dem Komma
   * dort, wo die Sprache es setzt.
   *
   * Dieselbe Begründung wie bei `plural()`: `gaps.join(' und ')` war die
   * deutsche Regel, fest verdrahtet. Ein übersetzter Binder wäre kein Ausweg,
   * sondern ein Satz aus Bruchstücken — `Intl.ListFormat` ist die
   * Plattform-Antwort und kostet keinen Katalog-Eintrag.
   *
   * Die Glieder kommen bereits übersetzt herein; das Verbinden ist Grammatik,
   * nicht Inhalt.
   */
  readonly list = (parts: readonly string[]): string =>
    new Intl.ListFormat(this.i18n.locale(), { style: 'long', type: 'conjunction' })
      .format(parts);

  /**
   * Auszeichnung mitten im Satz (C1-d4b2): übersetzt UND zerlegt in Stücke,
   * die `<studio-rich>` als `<strong>`/`<code>` rendert.
   *
   * Dieselbe Gattung wie `plural()` und `list()` — die Ansicht bekommt fertige
   * Grammatik, nicht die Bausteine dafür. Der Katalog-Text wird bewusst ZUERST
   * geteilt und danach eingesetzt: ein Wert wie eine Backend-Fehlermeldung kann
   * so keine Auszeichnung erzeugen.
   *
   * Liest `this.i18n.t` und damit das Sprach-Signal — ein Aufruf im Template
   * rendert beim Umschalten neu, wie jeder andere auch.
   */
  readonly rich = (
    key: string, params?: Record<string, string | number>,
  ): readonly RichSegment[] => splitRich(this.i18n.t(key), params);

  /**
   * Mehrzahl UND Auszeichnung in einem Satz (C1-d4b3).
   *
   * Existiert, weil `splitRich(this.plural(…))` die Reihenfolge umdrehte:
   * `plural()` setzt die Werte ein, und erst danach zu teilen hiesse, einen
   * eingesetzten Wert über die Auszeichnung entscheiden zu lassen. Hier wählt
   * die Anzahl nur die FORM; geteilt wird der rohe Katalog-Text, eingesetzt
   * wird danach — dieselbe Zusage wie bei `rich()`.
   */
  readonly richPlural = (
    key: string, count: number, params?: Record<string, string | number>,
  ): readonly RichSegment[] =>
    splitRich(this.i18n.t(this.pluralKey(key, count)), { count, ...params });

  /** Sprache, in die der Knopf umschaltet. */
  readonly target = computed(() => nextLocale(this.i18n.locale()));

  /** Sichtbares Kürzel („EN"/„DE"). Der ISO-Code ist in jeder Sprache
   *  derselbe und braucht daher keinen Katalog-Eintrag. */
  readonly switchCode = computed(() => this.target().toUpperCase());

  /** Zugänglicher Name des Knopfs — benennt die Zielsprache, in der aktiven
   *  Sprache formuliert. */
  readonly switchLabel = computed(() => this.i18n.t(SWITCH_LABEL_KEY[this.target()]));

  /**
   * Sprache setzen UND `<html lang>` nachziehen.
   *
   * Anders als das Widget besitzt das Studio die ganze Seite. Bliebe `lang`
   * auf „de" stehen, spräche ein Screenreader die englische Oberfläche mit
   * deutscher Aussprache — ein Fehler, den man am Bildschirm nicht sieht.
   */
  /** Die Mehrzahlform der aktiven Sprache als Schlüssel-Endung. Geteilt von
   *  `plural()` und `richPlural()` — eine Regel, eine Stelle. */
  private pluralKey(key: string, count: number): string {
    return `${key}.${new Intl.PluralRules(this.i18n.locale()).select(count)}`;
  }

  private apply(locale: Locale): void {
    this.i18n.setLocale(locale);
    document.documentElement.lang = this.i18n.t('format.htmlLang');
  }
}
