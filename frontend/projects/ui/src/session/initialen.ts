/**
 * Das Kürzel der angemeldeten Person im Kreis neben dem Abmelde-Knopf (Plan 2026-11-19, E8).
 *
 * Rein, ohne DOM: aus dem Anzeigenamen der erste Buchstabe des ersten und des letzten Worts,
 * groß geschrieben („Jan Schachtschabel“ → „JS“). Ein Wort gibt einen Buchstaben. Wörter ohne
 * Buchstaben (Gedankenstriche, Klammern allein) zählen nicht, Satzzeichen davor auch nicht. Leer
 * heißt: kein Name bekannt — dann zeigt der Kreis das Personen-Symbol.
 */

const BUCHSTABE = /\p{L}/u;

function ersterBuchstabe(wort: string): string {
  // Großschreiben kann mehr Zeichen ergeben („ß“ → „SS“) — im Kreis bleibt eins je Wort.
  return Array.from((wort.match(BUCHSTABE)?.[0] ?? '').toLocaleUpperCase('de'))[0] ?? '';
}

export function initialen(name: string): string {
  const woerter = (name || '').split(/\s+/).filter((wort) => BUCHSTABE.test(wort));
  if (woerter.length === 0) return '';
  const erstes = ersterBuchstabe(woerter[0]);
  return woerter.length === 1 ? erstes : erstes + ersterBuchstabe(woerter[woerter.length - 1]);
}
