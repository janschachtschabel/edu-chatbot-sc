/**
 * Anmelde-Chip (C5-c2) — der dritte und letzte Magic-Marker der Chip-Reihe,
 * Geschwister von `guide-qr.ts` und `action-qr.ts`.
 *
 * Konvention (Backend → Frontend):
 *
 *   __auth__
 *
 * **Ohne Beschriftung, anders als die beiden anderen.** Deren Text ist Inhalt
 * — vom Modell formuliert (`__guide__`) bzw. aus der Studio-Config
 * (`__action__`). Dieser hier benennt eine Handlung des Widgets, wird nirgends
 * hingeschickt und soll dem Sprachumschalter sofort folgen. Also gehört er in
 * den Katalog dieser Anwendung (`auth.signIn`) und nicht in den String.
 *
 * Das Gegenstück steht in `backend/src/boerdi/domain/auth_qr.py`; die beiden
 * Marker müssen zeichengleich bleiben.
 */

/** Der Marker, den das Backend setzt, wenn ein Zug ohne Anmeldung nicht
 *  kuratieren konnte. */
export const AUTH_QR_MARKER = '__auth__';

/**
 * True, wenn der Quick-Reply-String der Anmelde-Chip ist.
 *
 * Gleichheit statt `startsWith` wie bei den Geschwistern: der Marker trägt
 * nichts ausser sich selbst, also ist alles Längere etwas anderes — und ein
 * Präfix-Vergleich würde eine Nachricht, die zufällig so anfängt, zum Chip
 * erklären.
 */
export function isAuthQuickReply(qr: string): boolean {
  return qr === AUTH_QR_MARKER;
}
