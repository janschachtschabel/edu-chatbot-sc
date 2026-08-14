/**
 * Die zwei Reiter der Seitenleiste: „Einstellungen" und „Chat".
 *
 * **Warum getrennt und warum verstecken statt neu bauen.** Auf 360 px Breite
 * steht die Steuerung dem Gespräch im Weg; wer chattet, will nur den Chat
 * sehen (Nutzer-Vorgabe 2026-08-14). Der Chat-Bereich wird deshalb per
 * `hidden` weggeblendet und NICHT aus dem Dokument genommen: `<boerdi-chat>`
 * hält Sitzung und Verlauf in seiner Instanz — ein Neuaufbau beim Reiterwechsel
 * verlöre beides.
 *
 * Tastatur nach der ARIA-Praxis: Pfeile wandern, Home/End springen. Ohne das
 * wären die Reiter nur mit der Maus bedienbar.
 */

/**
 * @param {Array<{knopf: HTMLElement, feld: HTMLElement}>} reiter
 * @returns {{zeige: (index: number) => void}} — `zeige` wechselt von außen,
 *   was „Starten" braucht, damit der Zug nicht unsichtbar läuft.
 */
export function verdrahteReiter(reiter) {
  function zeige(index) {
    reiter.forEach(({ knopf, feld }, i) => {
      const aktiv = i === index;
      knopf.setAttribute('aria-selected', String(aktiv));
      // Roving tabindex: nur der aktive Reiter liegt in der Tab-Reihenfolge,
      // sonst müsste man sich durch alle Knöpfe hindurchtabben.
      knopf.tabIndex = aktiv ? 0 : -1;
      feld.hidden = !aktiv;
    });
  }

  reiter.forEach(({ knopf }, i) => {
    knopf.addEventListener('click', () => zeige(i));
    knopf.addEventListener('keydown', (e) => {
      const schritt = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      let ziel = null;
      if (schritt) ziel = (i + schritt + reiter.length) % reiter.length;
      else if (e.key === 'Home') ziel = 0;
      else if (e.key === 'End') ziel = reiter.length - 1;
      if (ziel === null) return;
      e.preventDefault();
      zeige(ziel);
      reiter[ziel].knopf.focus();
    });
  });

  zeige(0);
  return { zeige };
}
