/**
 * Sprache eines Widgets (C1-c): Auflösung aus den vier Quellen, Umschalten,
 * Merken — und die `I18n`-Instanz, die daraus spricht.
 *
 * Eigene Klasse statt weiterer Zeilen in `widget.component.ts`, nach demselben
 * Muster wie `PanelState`, `GuideBoot`, `GuideNav` und `HostBridges`: die Hülle
 * bleibt Element-Kontrakt und Verdrahtung, hier steht die eine Änderungs-
 * Ursache „welche Sprache spricht dieses Widget".
 *
 * Bewusst KEIN Singleton — die `I18n`-Instanz gehört diesem Widget. Zwei
 * Widgets auf einer Seite dürfen verschiedene Sprachen sprechen; ein Test hält
 * das fest.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import { computed } from '@angular/core';

import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
import { I18n } from '../i18n/i18n';
import { Locale, nextLocale, resolveLocale } from '../i18n/locale';
import {
  readBrowserLocale, readHostLocale, readStoredLocale, writeStoredLocale,
} from '../i18n/locale-sources';

/**
 * Schlüssel der Nutzerwahl im `sessionStorage` — der des **Widgets**.
 *
 * Steht hier und nicht bei den Lesern (C1-d1): das Studio merkt sich seine
 * Sprache getrennt, also gehört der Name dem Verbraucher. Fester Name, anders
 * als der konfigurierbare `sessionKey` der Session-ID: die Sprache ist kein
 * Sitzungsdatum und wird nicht über Subdomains geteilt.
 */
export const WIDGET_LOCALE_STORAGE_KEY = 'boerdi_locale';

/** Live-Zustand, den die Sprachauflösung liest — deferred Arrows wie bei den
 *  übrigen Widget-Bausteinen, damit jeder Zugriff frisch ist. */
export interface WidgetLanguageContext {
  /** `<boerdi-chat language="en">` — die einbettende Seite konfiguriert. */
  attribute: () => string;
  /** Host-Element des Widgets; Startpunkt der `[lang]`-Suche nach oben. */
  hostElement: () => Element | null;
}

/** Zielsprache → Schlüssel des zugänglichen Namens. Erlaubnisliste statt
 *  `'widget.language.to' + ziel`: ein dynamischer Schlüssel gäbe bei einer
 *  unbekannten Sprache den Schlüssel selbst als Beschriftung aus. Dieselbe
 *  Entscheidung wie bei `formatPhaseLabel`. */
const SWITCH_LABEL_KEY: Record<Locale, string> = {
  de: 'widget.language.toDe',
  en: 'widget.language.toEn',
};

export class WidgetLanguage {
  /** Beide Kataloge liegen im Bundle — kein Nachladen, also kein Ladezustand
   *  und kein Fehlerpfad (siehe Entwurf, „Korrektur 2026-08-02"). */
  readonly i18n = new I18n(DE, { en: EN });

  constructor(private readonly ctx: WidgetLanguageContext) {}

  /** Sprache aus allen vier Quellen bestimmen und setzen. Idempotent, also
   *  auch aufrufbar, wenn der Host das `language`-Attribut zur Laufzeit
   *  ändert. */
  resolve(): void {
    this.i18n.setLocale(resolveLocale({
      chosen: readStoredLocale(WIDGET_LOCALE_STORAGE_KEY),
      attribute: this.ctx.attribute(),
      host: readHostLocale(this.ctx.hostElement()),
      browser: readBrowserLocale(),
    }));
  }

  /** Nächste Sprache im Rundlauf, gemerkt. Das Merken ist nicht Komfort,
   *  sondern Voraussetzung: ohne die oberste Quelle spränge die Sprache beim
   *  nächsten `resolve()` auf die Host-Vorgabe zurück. */
  toggle(): void {
    const ziel = nextLocale(this.i18n.locale());
    writeStoredLocale(WIDGET_LOCALE_STORAGE_KEY, ziel);
    this.i18n.setLocale(ziel);
  }

  /** Sprache, in die der Knopf umschaltet. */
  readonly target = computed(() => nextLocale(this.i18n.locale()));

  /** Sichtbares Kürzel des Knopfs („EN"/„DE"). Der ISO-Code ist in jeder
   *  Sprache derselbe und braucht daher keinen Katalog-Eintrag. */
  readonly switchCode = computed(() => this.target().toUpperCase());

  /** Zugänglicher Name des Knopfs — benennt die Zielsprache, in der aktiven
   *  Sprache formuliert. */
  readonly switchLabel = computed(() => this.i18n.t(SWITCH_LABEL_KEY[this.target()]));
}
