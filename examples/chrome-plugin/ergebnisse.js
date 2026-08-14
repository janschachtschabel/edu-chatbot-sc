/**
 * Die Ergebnis-Liste unter dem Chat: je Zug ein Eintrag.
 *
 * Eigene Datei, weil „wie ein Ergebnis aussieht" sich aus einem anderen Grund
 * ändert als „welches Formularfeld gerade gilt".
 *
 * Der Zähler wohnt HIER, nicht in `panel.js`: er gehört zur Liste, und beide
 * müssen beim Neuaufbau des Chats gemeinsam zurückgesetzt werden. Dass sie
 * getrennt lagen, war genau der Fehler (Review 2026-08-14) — die Liste
 * überlebte den Neuaufbau, der Zähler zählte weiter, und über der ersten
 * Antwort des neuen Laufs stand „Zug 5".
 *
 * `$` wird hereingereicht statt importiert, wie in `einstellungen.js`: so
 * bleibt das Modul ohne eigenes Wissen über das Dokument.
 */
let zaehler = 0;

/** Liste und Zählung zurücksetzen. Gehört zu jedem Neuaufbau des Chats. */
export function leereErgebnisse($) {
  zaehler = 0;
  $('ergebnisListe').replaceChildren();
  $('ergebnisLeer').hidden = false;
}

/**
 * Einen Zug anzeigen — neuester oben, damit man nicht scrollen muss.
 *
 * Ein Eintrag entsteht AUCH ohne `result`: der Unterschied zwischen „in diesem
 * Zug war nichts dabei" und „abgeschnitten" (`deadline`) ist das, was man hier
 * sehen will, und er steckt allein im `stop_reason`.
 */
export function zeigeErgebnis($, { result, stop_reason: grund }) {
  $('ergebnisLeer').hidden = true;
  const li = document.createElement('li');

  const kopf = document.createElement('div');
  kopf.className = 'kopf';
  const marke = document.createElement('span');
  marke.className = `marke ${result ? 'gut' : 'leer'}`;
  marke.textContent = grund || '—';
  kopf.append(marke, `Zug ${++zaehler}`);

  const pre = document.createElement('pre');
  pre.textContent = result
    ? JSON.stringify(result, null, 2)
    : 'kein Ergebnis in diesem Zug — der Grund steht links';

  li.append(kopf, pre);
  $('ergebnisListe').prepend(li);
}
