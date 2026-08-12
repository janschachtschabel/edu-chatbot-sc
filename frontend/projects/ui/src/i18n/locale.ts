/**
 * Sprachauflösung (C1-a). Rein und ohne Browser-Zugriff — die unreinen Quellen
 * liest der Aufrufer und reicht sie als Werte herein. Der Entwurf steht in
 * `docs/plans/2026-08-02-c1-i18n.md`.
 */

export const SUPPORTED_LOCALES = ['de', 'en'] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

/** Deutsch ist die Standardsprache: eingebaut, ohne Nachladen. */
export const DEFAULT_LOCALE: Locale = 'de';

/**
 * Bildet einen BCP-47-artigen Wert auf eine unterstützte Sprache ab.
 * `'en-GB'` → `'en'`, `'  DE-CH '` → `'de'`, alles andere → `null`.
 *
 * Tolerant bei Schreibweise und Leerzeichen, weil die Werte aus fremder Hand
 * kommen: aus einem Host-Attribut, aus `navigator.language`, aus dem Speicher
 * einer älteren Sitzung.
 */
export function normalizeLocale(raw: string | null | undefined): Locale | null {
  const tag = (raw ?? '').trim().toLowerCase().split('-')[0];
  return (SUPPORTED_LOCALES as readonly string[]).includes(tag) ? (tag as Locale) : null;
}

/** Die vier Sprachquellen, in der Reihenfolge ihrer Stärke. */
export interface LocaleSources {
  /** Umschalter im Widget, für die Sitzung gemerkt. */
  chosen?: string | null;
  /** `<boerdi-chat language="en">` — die einbettende Seite konfiguriert. */
  attribute?: string | null;
  /** Nächstes `[lang]` im DOM, meist `<html lang>`. */
  host?: string | null;
  /** `navigator.language`. */
  browser?: string | null;
}

/**
 * Wählt die Sprache nach der Rangfolge
 * `Umschalter > Attribut > Host-Seite > Browser > 'de'`.
 *
 * Der Umschalter steht oben, weil eine bewusste Nutzeraktion die Host-Vorgabe
 * schlagen muss — sonst spränge die Sprache beim nächsten Rendern zurück. Die
 * Host-Seite steht vor dem Browser, weil ein deutscher Nutzer auf einer
 * englischen Seite diese Seite lesen können soll.
 *
 * Nicht unterstützte Werte werden **übersprungen**, nicht als Abbruch gewertet:
 * eine Seite mit `lang="fr"` darf den Browser-Wunsch nicht verschlucken.
 */
export function resolveLocale(sources: LocaleSources): Locale {
  const kette = [sources.chosen, sources.attribute, sources.host, sources.browser];
  for (const roh of kette) {
    const treffer = normalizeLocale(roh);
    if (treffer) return treffer;
  }
  return DEFAULT_LOCALE;
}

/**
 * Ziel des Umschalters (C1-c): die nächste Sprache im Rundlauf.
 *
 * Über `SUPPORTED_LOCALES` statt als `'de' ↔ 'en'`, damit eine dritte Sprache
 * nicht still unerreichbar wäre — sie stünde im Katalog, aber kein Knopf käme
 * je hin.
 */
export function nextLocale(current: Locale): Locale {
  const i = SUPPORTED_LOCALES.indexOf(current);
  return SUPPORTED_LOCALES[(i + 1) % SUPPORTED_LOCALES.length];
}
