/**
 * Card-URL + Typ-Helpers.
 *
 * Alle URLs kommen fertig vom Backend — das Frontend konstruiert keine
 * Repo-URLs mehr. ``card.link`` ist die Single Source of Truth (gesetzt
 * via ``build_card_link`` im Backend, berücksichtigt REPO_BASE_URL,
 * Lotsen-Modus, Search-Query-Params usw.). Fallback-Kette für ältere
 * Backends: ``guide_url → wlo_url → url``.
 *
 * Verbatim-Port des ALT `services/card-utils.ts` (Verhalten gepinnt durch
 * die mitportierte card-utils.spec.ts). Imports umgehängt: `WloCard` aus dem
 * herausgetrennten `./card-types`, `ICONS` aus `../icons/icons`.
 */
import { WloCard } from './card-types';
import { ICONS } from '../icons/icons';
import type { TranslateFn } from '../i18n/i18n';

/**
 * Primary URL for a card — alle Varianten kommen vom Backend.
 *
 * Fallback-Kette (alle Felder werden serverseitig befüllt):
 *   0. ``topic_pages[0].url`` — wenn die Card eine Themenseiten-Card
 *      ist (variants-Array non-empty), zeigt der Primary-Link
 *      direkt auf die kuratierte Themenseite — NICHT auf die
 *      zugrundeliegende Sammlung. Eine TP-Card ist semantisch eine
 *      Themenseite, kein Sammlungs-Wrapper; entsprechend muss die
 *      ``Box: Themenseiten`` im Chat-Widget zur Themenseite linken.
 *   1. ``link``      — Card-Pipeline v2 Single Source of Truth
 *   2. ``guide_url`` — Lotsen-Modus Repo-Render-Link
 *   3. ``wlo_url``   — Stabiler Repo-Permalink
 *   4. ``url``       — Externe Provider-URL (wwwurl)
 */
export function getCardPrimaryUrl(c: WloCard | null | undefined): string {
  if (!c) return '#';
  if (Array.isArray(c.topic_pages) && c.topic_pages.length > 0) {
    const tpUrl = c.topic_pages[0]?.url;
    if (tpUrl) return tpUrl;
  }
  return c.link || c.guide_url || c.wlo_url || c.url || '#';
}

/**
 * Ziel im Sammlungen-Kasten. {@link getCardPrimaryUrl} taugt hier NICHT: es
 * zieht `topic_pages[0].url` allem anderen vor, und dann zeigte der
 * Sammlungen-Kasten auf die Themenseite statt auf die Sammlung.
 *
 * Kette, in dieser Reihenfolge:
 *   1. `collection_link` — vom Backend gesetzt, wenn `link` woanders
 *      hinzeigt (Karte mit `node_type: 'topic_page'`).
 *   2. `link` — für die ZWEITE Darstellung einer Themenseite
 *      (`node_type: 'collection'` MIT Varianten, entsteht beim
 *      Zusammenführen zweier Treffer derselben node_id) und für reine
 *      Sammlungen ist `link` bereits der Browse-Link. Beides liefert
 *      `build_card_link` über denselben Zweig — kein Zufall.
 *   3. `getCardPrimaryUrl` — letzte Rückfalllinie für alte gespeicherte
 *      Antworten ohne `link`.
 */
export function getCardCollectionUrl(c: WloCard): string {
  return c.collection_link || c.link || getCardPrimaryUrl(c);
}

/**
 * Drei-Wege-Klassifikation einer Card für die visuelle Unterscheidung
 * (Themenseite / Sammlung / Inhalt) — Single Source of Truth.
 *
 * Die drei Prädikate sind über alle `node_type`-Fälle **paarweise
 * disjunkt und vollständig**: für jede Card ist genau eines wahr.
 * ``chat.component`` bindet sie im Template und delegiert hierher.
 */

/**
 * Themenseite? — erkennt BEIDE Repräsentationen, passend zum Backend
 * (`_is_themenseite_card`): neu ``node_type='topic_page'`` (topic-pages-
 * Renderer-Link), alt ``node_type='collection'`` mit topic_pages-Varianten.
 * Sonst landet die Themenseite in der falschen Box (Regression 2026-06-02:
 * topic_page → Material-Box).
 */
export function isThemenseite(card: WloCard): boolean {
  if (card.node_type === 'topic_page') return true;
  return card.node_type === 'collection'
    && Array.isArray(card.topic_pages) && card.topic_pages.length > 0;
}

/** Sammlung? — ``node_type='collection'`` ohne topic_pages-Varianten. */
export function isSammlung(card: WloCard): boolean {
  return card.node_type === 'collection'
    && !(Array.isArray(card.topic_pages) && card.topic_pages.length > 0);
}

/** Einzelinhalt? — weder Sammlung noch Themenseite. */
export function isInhalt(card: WloCard): boolean {
  return card.node_type !== 'collection' && card.node_type !== 'topic_page';
}

/**
 * Liefert das passende Material-Symbol-Inline-SVG für den Inhaltstyp einer
 * Kachel. Template-Verwendung (via ``chat.component``-Delegate):
 *   <span class="card-content-icon" [innerHTML]="getCardIcon(card) | safeSvg"></span>
 */
export function getCardIcon(card: WloCard): string {
  // Themenseiten bekommen ihr eigenes Icon — sie sind kuratierte
  // Webseiten, keine reinen Sammlungen, und unterscheiden sich
  // visuell vom "Stapel"-Symbol der klassischen Sammlung.
  if (isThemenseite(card)) return ICONS.topic;
  if (card.node_type === 'collection') return ICONS.auto_stories;
  const types = card.learning_resource_types || [];
  if (types.some(t => t.toLowerCase().includes('video'))) return ICONS.play_circle;
  if (types.some(t => t.toLowerCase().includes('arbeitsblatt'))) return ICONS.article;
  if (types.some(t => t.toLowerCase().includes('interaktiv'))) return ICONS.videogame_asset;
  if (types.some(t => t.toLowerCase().includes('audio'))) return ICONS.headphones;
  if (types.some(t => t.toLowerCase().includes('quiz') || t.toLowerCase().includes('test'))) return ICONS.quiz;
  if (types.some(t => t.toLowerCase().includes('präsent') || t.toLowerCase().includes('praesent'))) return ICONS.image;
  if (types.some(t => t.toLowerCase().includes('übung') || t.toLowerCase().includes('uebung'))) return ICONS.edit_note;
  if (types.some(t => t.toLowerCase().includes('kurs'))) return ICONS.school;
  if (types.some(t => t.toLowerCase().includes('webseite') || t.toLowerCase().includes('website'))) return ICONS.language;
  return ICONS.menu_book;
}

/**
 * Lesbares Label für den Inhaltstyp (über dem Bild). Nutzt den ersten
 * `learning_resource_types`-Eintrag wenn vorhanden, sonst Fallback.
 *
 * @param t Übersetzer (C1-b3) — als Parameter statt Import, weil diese Datei
 *   rein bleibt und der Aufrufer die Sprache seiner Instanz kennt.
 *   Der `learning_resource_type` selbst wird NICHT übersetzt: er ist
 *   Backend-Inhalt, kein Oberflächentext.
 */
export function getContentTypeLabel(card: WloCard, t: TranslateFn): string {
  if (isThemenseite(card)) return t('contentType.topicPage');
  if (card.node_type === 'collection') {
    // Sammlungen unterscheiden wir über das Kind-Badge rechts.
    return t('contentType.collection');
  }
  const types = (card.learning_resource_types || []).filter(
    typ => typ && typ.toLowerCase() !== 'sammlung' && typ.toLowerCase() !== 'collection',
  );
  if (types.length) return types[0];
  return t('contentType.fallback');
}
