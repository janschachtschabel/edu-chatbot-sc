/**
 * Drucken im Druckfenster, ohne Inline-Skript (Paket 8, P2).
 *
 * Ein leeres Pop-up erbt die Content-Security-Policy der Seite, die es öffnet. Unter
 * `script-src 'self'` — im Studio, auf jeder Gastseite mit strenger CSP — liefen ein
 * `<script>` und ein `onclick`-Attribut im geschriebenen HTML nicht: der Druck startete
 * nicht, der Knopf blieb tot. Beides hängt das Widget deshalb von außen an; ein per
 * `addEventListener` gesetzter Listener ist kein Inline-Code.
 *
 * Uhr und Druckfunktion sind die des Druckfensters (Paket 9, Review Paket 7 MINOR 22):
 * Timer und Funktionen der öffnenden Seite stehen still, sobald sie weiternavigiert —
 * der Knopf schwiege dann.
 */

/** Startet den Druck, sobald das Fenster geladen ist — wie früher das Inline-Skript
 *  mit 300 ms Abstand, damit Bilder und Stile stehen. Ist das Fenster bis dahin zu,
 *  laufen auch seine Timer nicht mehr. */
export function druckeNachDemLaden(w: Window): void {
  const drucken = w.setTimeout.bind(w, w.print.bind(w), 300);
  if (w.document.readyState === 'complete') drucken();
  else w.addEventListener('load', drucken, { once: true });
}

/** Der Knopf „Drucken / Als PDF speichern“ in der Leiste des Druckfensters. */
export function verdrahteDruckknopf(w: Window): void {
  w.document.querySelector('.print-bar button')?.addEventListener('click', w.print.bind(w));
}
