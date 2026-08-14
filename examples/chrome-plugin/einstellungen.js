/**
 * Die Eingaben der Leiste über ein Neuladen retten (`chrome.storage.local`).
 *
 * Eigene Datei, weil es eine eigene Änderungs-Ursache ist: „welche Felder
 * werden gemerkt" hat nichts damit zu tun, wie der Chat gestartet wird. In
 * `panel.js` war es der Block, den man beim Lesen überspringt.
 *
 * Absichtlich `local` und nicht `sync`: die Felder enthalten Sammlungs-IDs und
 * Seitentexte einer Arbeitssitzung. Über alle Geräte einer Anmeldung zu
 * verteilen, was hier nur ein Versuchsaufbau ist, wäre mehr Streuung als Nutzen.
 */
const SCHLUESSEL = 'boerdi.plugin.einstellungen';

/** Die Felder, deren `.value` gemerkt wird — Kennung = Element-Kennung. */
export const GEMERKTE_FELDER = [
  'apiUrl', 'art', 'collectionId', 'topicSlug', 'nodeId', 'suche',
  'auftrag', 'schema',
];

/**
 * Gemerkte Werte in die Felder zurückschreiben.
 *
 * `$` wird hereingereicht statt importiert: so bleibt dieses Modul ohne
 * Wissen über das Dokument und ist von Hand nachvollziehbar.
 */
export async function ladeEinstellungen($) {
  let gespeichert;
  try {
    ({ [SCHLUESSEL]: gespeichert } = await chrome.storage.local.get(SCHLUESSEL));
  } catch (err) {
    // Kein Grund, die Leiste nicht zu starten — sie ist dann nur leer.
    console.warn('Einstellungen nicht gelesen:', err);
    return;
  }
  if (!gespeichert) return;

  for (const id of GEMERKTE_FELDER) {
    if (gespeichert[id] != null) $(id).value = gespeichert[id];
  }
  if (gespeichert.modus) {
    const knopf = document.querySelector(
      `input[name="modus"][value="${CSS.escape(gespeichert.modus)}"]`);
    if (knopf) knopf.checked = true;
  }
  $('textMit').checked = !!gespeichert.textMit;
}

/** Den aktuellen Stand sichern. Fehler werden gemeldet, nicht geworfen: ein
 *  voller Speicher darf das Tippen nicht unterbrechen. */
export function merkeEinstellungen($, modus) {
  const stand = { modus, textMit: $('textMit').checked };
  for (const id of GEMERKTE_FELDER) stand[id] = $(id).value;
  chrome.storage.local.set({ [SCHLUESSEL]: stand })
    .catch((err) => console.warn('Einstellungen nicht gespeichert:', err));
}
