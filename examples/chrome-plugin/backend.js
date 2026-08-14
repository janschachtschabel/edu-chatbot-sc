/**
 * Welche Backend-Adresse gilt — und lebt sie?
 *
 * **Warum es das gibt.** Am 2026-08-14 landete beim Ausprobieren die
 * BÜNDEL-Adresse im Feld „Backend". `ChatApiClient.setBaseUrl` hängt `/api` an,
 * was drinsteht; daraus wurde `…/widget/boerdi-widget.js/api/chat/stream`, und
 * jeder Zug endete mit „Entschuldigung, es ist ein Fehler aufgetreten" — die
 * Antwort des Bots auf einen 404, dreißig Sekunden nach dem Klick. Gemessen:
 * 404 gegen 200 auf der richtigen Adresse.
 *
 * Zwei Lehren, beide hier umgesetzt: den einen eindeutigen Tippfehler
 * korrigieren und es SAGEN, und vor dem ersten Zug nachsehen, statt raten zu
 * lassen.
 */

/**
 * Die API-Basis aus dem, was jemand eingetippt hat.
 *
 * Gekürzt wird **nur** ein Pfad, der auf `.js` endet — das ist eindeutig die
 * Bündel-Adresse und niemals eine API-Basis. Ein gewöhnliches Pfad-Präfix
 * (`https://host/boerdi`, Reverse-Proxy) bleibt stehen: es zu kürzen wäre
 * geraten, und ein falsch geratener Wert ist schlimmer als ein falsch
 * getippter, weil ihn niemand mehr sieht.
 *
 * @returns {{basis: string, korrigiert: boolean}} `korrigiert` steuert den
 *   Hinweis in der Leiste — eine stille Korrektur wäre eine Falle.
 */
export function basisAusEingabe(wert) {
  const roh = String(wert ?? '').trim();
  if (!roh) return { basis: '', korrigiert: false };

  let url;
  try {
    url = new URL(roh);
  } catch {
    return { basis: roh, korrigiert: false };   // meldet der Gesundheits-Abruf
  }

  if (url.pathname.toLowerCase().endsWith('.js')) {
    return { basis: url.origin, korrigiert: true };
  }
  return { basis: roh.replace(/\/+$/, ''), korrigiert: false };
}

/**
 * `GET {basis}/api/health` — die eine Frage, die alles andere entscheidet.
 *
 * Wirft nie: der Rückgabewert beschreibt jeden Ausgang, damit die Leiste
 * denselben Weg für „läuft", „falscher Pfad" und „nicht erreichbar" hat.
 */
export async function pruefeGesundheit(basis) {
  if (!basis) return { ok: false, text: 'Keine Adresse eingetragen.' };
  const ziel = `${basis}/api/health`;
  let antwort;
  try {
    antwort = await fetch(ziel, { cache: 'no-store' });
  } catch (err) {
    return { ok: false, text: `Nicht erreichbar: ${err.message}` };
  }
  if (!antwort.ok) {
    const zusatz = antwort.status === 404
      ? ' — zeigt die Adresse wirklich auf das Backend und nicht auf eine Datei?'
      : '';
    return { ok: false, text: `${ziel} → HTTP ${antwort.status}${zusatz}` };
  }
  let daten;
  try {
    daten = await antwort.json();
  } catch {
    return { ok: false, text: 'Antwort ist kein JSON — vermutlich eine Fehlerseite.' };
  }
  // Das Repositorium MIT anzeigen: ob der Bot gegen Staging oder Produktion
  // läuft, ist die Frage, die man sonst erst am Ziel eines Karten-Links merkt.
  return {
    ok: true,
    text: `${daten.status || 'ok'} · Repo: ${daten.repo || '—'} · Modell: ${daten.chat_model || '—'}`,
  };
}
