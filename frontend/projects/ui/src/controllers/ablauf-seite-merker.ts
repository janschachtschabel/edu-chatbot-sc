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

/** Wartet eine Führung auf die Person — auf eine Seite oder (Plan 2026-11-20, G2d) an ihrer Frage?
 *  Dann gehört ihr ein Seitenaufruf wie der Tour: Ping, und das Widget öffnet sich
 *  (der Merker hier). Der Ping an der Frage zeigt sie samt Chips erneut — nach dem Neuladen
 *  sind die Chips der alten Blase weg. */
export function wartendeFuehrung(stand: AblaufStand | null): boolean {
  return stand?.status === 'wartet_seite' || (stand?.status === 'wartet_wahl' && !!stand.fuehrung);
}

/** Soll der Merker stehen? `true`, solange eine Führung wartet (`wartet_seite`, seit G2d auch an
 *  ihrer Frage); `false` bei einem anderen Stand oder einem beendeten Lauf — aber erst, wenn eine
 *  Serverantwort da ist (`antwortDa`): nach dem Neuladen ist der Stand bis zum Verlauf leer, und das
 *  Widget klappte sonst zu. `null`: nichts ändern. */
export function merkerNachStand(stand: AblaufStand | null, antwortDa: boolean): boolean | null {
  if (wartendeFuehrung(stand)) return true;
  return antwortDa ? false : null;
}

/** WF-5 (Review M1): fällt der Merker, wenn der Verlauf geladen ist? Nur bei bestimmtem Stand
 *  (`unbestimmt`: die Anmeldung kam zu spät) und wenn keine Führung wartet — seit Review G2
 *  (MINOR 5) auch nicht an ihrer Frage, sonst klappte das Widget dort nach dem Neuladen zu. */
export function merkerFaelltNachVerlauf(stand: AblaufStand | null, unbestimmt: boolean): boolean {
  return !unbestimmt && !wartendeFuehrung(stand);
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
