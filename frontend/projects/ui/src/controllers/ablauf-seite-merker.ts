/**
 * Merker „ein Ablauf wartet auf eine Seite“ (Plan 2026-11-15, Webseitenführung als Ablauf, WF-5).
 *
 * Ein Schritt `seite` führt per Chip auf eine andere Seite. Die lädt neu, und das Widget startet
 * dort zugeklappt — die Chat-Oberfläche hängt sich erst beim Öffnen ein, und erst dann meldet der
 * Seiten-Ping die Ankunft. Die eingebaute Web-Tour löst das mit `boerdi_tour_active`; ein Ablauf
 * bekommt denselben Weg: der Merker im `localStorage` überlebt den Seitenwechsel, und
 * `computeInitialExpanded` öffnet das Widget, solange er steht.
 */
import type { AblaufStand } from '../grouping/message-types';

/** Schlüssel im `localStorage` (gelesen von `widget/widget-init.ts`). */
export const ABLAUF_SEITE_MERKER = 'boerdi_ablauf_seite';

/** Soll der Merker stehen? `true` bei `wartet_seite`; `false` bei einem anderen Stand oder einem
 *  beendeten Lauf — aber erst, wenn eine Serverantwort da ist (`antwortDa`): nach dem Neuladen ist
 *  der Stand bis zum Verlauf leer, und das Widget klappte sonst zu. `null`: nichts ändern. */
export function merkerNachStand(stand: AblaufStand | null, antwortDa: boolean): boolean | null {
  if (stand?.status === 'wartet_seite') return true;
  return antwortDa ? false : null;
}

export function setzeAblaufSeiteMerker(an: boolean): void {
  try {
    if (an) localStorage.setItem(ABLAUF_SEITE_MERKER, '1');
    else localStorage.removeItem(ABLAUF_SEITE_MERKER);
  } catch { /* ohne localStorage (privates Fenster) bleibt es beim Öffnen von Hand */ }
}

export function ablaufSeiteMerkerGesetzt(): boolean {
  try { return localStorage.getItem(ABLAUF_SEITE_MERKER) === '1'; }
  catch { return false; }
}
