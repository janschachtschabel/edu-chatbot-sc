/**
 * WLO-Card-Datenvertrag (frontend-seitig) — die Card-JSON-Form, die das
 * Backend liefert. Verbatim-Port des ALT `WloCard`-Interface aus
 * `services/api.service.ts` (dort im Sammel-File; NEU trennt den Typ als
 * eigenständigen Card-Vertrag heraus, den `card-utils`, der Tile und die
 * Box-Renderer teilen). Keine Logik — nur Form.
 */
export interface WloCard {
  node_id: string;
  title: string;
  description: string;
  disciplines: string[];
  educational_contexts: string[];
  keywords: string[];
  learning_resource_types: string[];
  url: string;
  wlo_url: string;
  preview_url: string;
  license: string;
  publisher: string;
  node_type: string;
  /** Wie viele Skills die Redaktion an dieser Sammlung freigegeben hat; 0 oder
   *  fehlend = keine Registry. Kommt vom MCP an Sammlungstreffern ungefragt
   *  mit, kostet also keinen Zusatzabruf. Optional, weil ältere Antworten aus
   *  dem Sitzungs-Verlauf das Feld noch nicht tragen. */
  skill_count?: number;
  topic_pages: { url: string; target_group: string; label: string; variant_id: string }[];
  /** Set by the backend when guide-mode is on AND the card points to an
   *  allow-listed host. Empty string means "no guide target" — the
   *  frontend hides the "Bring mich hin"-button in that case.
   *  @deprecated Phase 10 — wird durch `link` ersetzt. */
  guide_url?: string;
  /** Card-Pipeline v2 — Single Source of Truth für den UI-Klick-Link.
   *  Vom Backend via `build_card_link` befüllt:
   *   - Themenseiten: `topic_page_url` (extern, kuratiert)
   *   - Sammlungen:  `{repo}/edu-sharing/components/collections?id=…&q=…`
   *   - Einzelinhalte: `url` (extern) im Normal-Modus, sonst Repo-Render.
   *
   *  Phase 4b: wenn vorhanden, bevorzugen wir es gegenüber der alten
   *  URL-Logik. Phase 10 macht es zum Pflichtfeld und entfernt die Alt-
   *  Auswahl-Logik (`guide_url`, `wlo_url`-Fallbacks). */
  link?: string;
  /** Ziel des Sammlungen-Kastens für Sammlungen MIT kuratierter Themenseite.
   *  Solche Karten tragen `node_type: 'topic_page'`, und `link` zeigt dann auf
   *  die Themenseite — die Sammlung selbst wäre unerreichbar. Das Backend
   *  liefert sie hier zusätzlich (`…/components/collections?id=…`).
   *
   *  Leer/fehlend bei allen anderen Karten: bei reinen Sammlungen IST `link`
   *  schon der Browse-Link. Optional, weil ältere Antworten aus dem
   *  Sitzungs-Verlauf das Feld noch nicht tragen. */
  collection_link?: string;
}
