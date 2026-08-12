/**
 * Wörterbuch-Kern (C1-a). Laufzeit-Kataloge statt `@angular/localize`: das
 * backt zur Bauzeit ein Bundle je Sprache und liesse sich nur per Neuladen
 * umschalten — mit dem Umschalter im Widget unvereinbar.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */

/** Ein Katalog ist eine flache Schlüssel→Text-Abbildung. Flach, weil
 *  verschachtelte Kataloge nur Zugriffs-Code kosten und nichts einbringen —
 *  die Schlüssel tragen ihre Gliederung im Namen (`widget.open`). */
export type Catalogue = Readonly<Record<string, string>>;

/** Werte für Platzhalter der Form `{name}`. */
export type TranslationParams = Readonly<Record<string, string | number>>;

export type Translator = (key: string, params?: TranslationParams) => string;

const PLATZHALTER = /\{(\w+)\}/g;

/**
 * Öffentlich seit C1-d4b2, weil `rich-text.ts` einen zweiten Aufrufer stellt:
 * dort wird der Katalog-Text erst geteilt und dann STÜCKWEISE eingesetzt. Eine
 * eigene Kopie des Platzhalter-Ausdrucks dort wäre zwei Regeln für eine Sache.
 *
 * Bibliotheks-intern — `public-api.ts` exportiert nur `splitRich`.
 */
export function einsetzen(text: string, params?: TranslationParams): string {
  if (!params) return text;
  return text.replace(PLATZHALTER, (ganz, name: string) =>
    // Ein Platzhalter ohne Wert bleibt STEHEN. Sichtbares `{count}` ist ein
    // Fehlerhinweis; „undefined" läse sich wie Inhalt.
    name in params ? String(params[name]) : ganz,
  );
}

/**
 * Baut die Übersetzungsfunktion für einen aktiven Katalog.
 *
 * Der Rückfall greift **je Schlüssel**: fehlt ein Text im aktiven Katalog,
 * erscheint der deutsche. Ein unvollständiger englischer Katalog kippt damit
 * nicht die ganze Oberfläche, und ein fehlender Text bleibt nie leer.
 *
 * Ist der Schlüssel in beiden unbekannt, kommt er selbst zurück — sichtbar
 * statt still leer, damit eine Lücke in der Oberfläche auffällt.
 */
export function createTranslator(active: Catalogue, fallback: Catalogue): Translator {
  return (key, params) => einsetzen(active[key] ?? fallback[key] ?? key, params);
}
