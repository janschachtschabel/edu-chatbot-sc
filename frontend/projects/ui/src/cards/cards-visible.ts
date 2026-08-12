import type { PanelSizeStep } from '../element/attr';

/**
 * U2b — Kachel-Regel: welche der beiden Trefferdarstellungen greift.
 *
 * **Beide gibt es schon** (gemessen 2026-08-09, vor dem Bauen):
 * `result-groups` rendert Icon + Titel als Textlink in Gruppen-Boxen — null
 * `<img>` —, `card-list` den flachen Grid aus `wlo-card-tile` MIT Vorschaubild,
 * Sammlungs-Aktionen und Pagination. Diese Datei erfindet keine dritte
 * Darstellung, sie entscheidet nur zwischen den zweien.
 *
 * Bis U2b hing die Wahl allein am Attribut `inline-result-grouping`. Das ist
 * der Grund für die Rangfolge unten: `show-cards` ist der neue, an die Größe
 * gekoppelte Schalter, aber ein Host, der heute `inline-result-grouping="false"`
 * setzt, hat damit „ich will Kacheln" gesagt und muss sie weiter bekommen.
 *
 * `show-cards` ist zugleich der Nachfolger von ALTs `cards-enabled`, das die
 * Welle E auf `true` eingefroren hatte (siehe `cardsEnabledBool` in der
 * Chat-Shell) — der Schalter kommt damit zurück, nur mit drei statt zwei
 * Stellungen.
 */
export const SHOW_CARDS_MODES = ['auto', 'always', 'never'] as const;

/** Stellungen des `show-cards`-Attributs. */
export type ShowCardsMode = (typeof SHOW_CARDS_MODES)[number];

/**
 * @param size            Aktuelle Größenstufe des Panels.
 * @param showCards       Host-Wunsch; `auto` (Vorgabe) überlässt es der Größe.
 * @param inlineGrouping  Aufgelöstes `inline-result-grouping` (Vorgabe `true`).
 * @returns `true` = Kacheln mit Vorschaubild, `false` = Textlinks in Boxen.
 */
export function resolveCardsVisible(
  size: PanelSizeStep,
  showCards: ShowCardsMode,
  inlineGrouping: boolean,
): boolean {
  if (showCards === 'always') return true;
  if (showCards === 'never') return false;
  // `auto`: erst das Bestands-Attribut ehren, dann die Größe entscheiden lassen.
  if (!inlineGrouping) return true;
  return size === 'large';
}
