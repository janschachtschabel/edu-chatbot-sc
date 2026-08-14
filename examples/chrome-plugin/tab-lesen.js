/**
 * Was der Nachbar-Tab hergibt — Adresse, Titel, Seitentext.
 *
 * Eigene Datei, weil hier als einziges die Chrome-Berechtigungen wohnen und
 * das eine andere Änderungs-Ursache ist als „welches Formularfeld gilt".
 *
 * **Der Befund, der die Zweistufigkeit erzwingt** (live 2026-08-14 auf
 * `de.wikipedia.org`): `chrome.scripting.executeScript` verlangt eine
 * Host-Berechtigung für die Adresse des Tabs — `activeTab` genügt NICHT, wenn
 * die Erweiterung über die Seitenleiste bedient wird. Die Fehlermeldung lautet
 * dann „Extension manifest must request permission to access this host".
 *
 * Nachfragen lässt sich das nicht im selben Klick: `permissions.request`
 * verlangt eine Nutzergeste, und die ist nach `await chrome.tabs.query()`
 * verbraucht. Deshalb zwei Schritte und zwei Knöpfe — geraten hätte in der
 * Hälfte der Chrome-Fassungen funktioniert, und das ist keine Grundlage.
 *
 * **Beide Schritte meinen denselben Tab.** Schritt 1 gibt seine `tabId` heraus,
 * Schritt 2 verlangt sie. Wer erneut „den aktiven Tab" abfragte, läse nach
 * einem Tab-Wechsel zwischen den zwei Klicks den Text von Seite B unter der
 * Adresse von Seite A — bei gleicher Herkunft (zwei Wikipedia-Artikel) ohne
 * jede Fehlermeldung. Gepinnt in `scripts/check-tab.mjs`.
 *
 * Bleibt ein schmaleres Fenster: navigiert derselbe Tab zwischen den Klicks
 * weiter, gehört der Text zur neuen Seite. Das ließe sich nur mit einem
 * Navigations-Wächter schließen und ist für ein Beispiel nicht bezahlt.
 */

/** Zeichendeckel des Seitentexts — die Grenze, die der Agent-Endpunkt für
 *  ``instruction`` setzt. Ungekappt wäre der Text der häufigste Grund für 422. */
export const TEXT_DECKEL = 20000;

/**
 * Herkunft eines Tabs als Berechtigungs-Muster, oder `null`.
 *
 * `null` bei allem, was nicht `http(s)` ist: `chrome://`, der Web Store, eine
 * lokale Datei. Dort lässt Chrome grundsätzlich keinen Zugriff zu, und danach
 * zu fragen wäre eine Zumutung ohne Aussicht.
 */
export function tabHerkunft(url) {
  try {
    const u = new URL(String(url || ''));
    return (u.protocol === 'http:' || u.protocol === 'https:') ? `${u.origin}/*` : null;
  } catch {
    return null;
  }
}

/** Der aktive Tab des aktuellen Fensters. */
async function aktiverTab() {
  const [aktiv] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!aktiv) throw new Error('kein aktiver Tab');
  return aktiv;
}

/** Seitentext holen und kappen. */
async function seitentext(tabId) {
  const [treffer] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => document.body?.innerText || '',
  });
  return String(treffer?.result || '').slice(0, TEXT_DECKEL);
}

/**
 * Schritt 1: lesen, was ohne Nachfrage geht.
 *
 * @returns {Promise<{url,titel,text,tabId,zustand,herkunft}>} `zustand` ist
 *   `gelesen` | `ohne-text` | `braucht-erlaubnis` | `intern` — die Leiste
 *   entscheidet daran, was sie anzeigt. Ein Wort statt dreier Flaggen: die
 *   vier Fälle schließen einander aus. `tabId` geht an Schritt 2, damit beide
 *   denselben Tab meinen.
 */
export async function liesTab({ textGewuenscht }) {
  const aktiv = await aktiverTab();
  const basis = {
    url: aktiv.url || '', titel: aktiv.title || '', text: '', tabId: aktiv.id ?? null,
  };
  const herkunft = tabHerkunft(basis.url);

  if (!textGewuenscht || aktiv.id == null) {
    return { ...basis, zustand: 'ohne-text', herkunft };
  }
  if (!herkunft) return { ...basis, zustand: 'intern', herkunft };
  if (!await chrome.permissions.contains({ origins: [herkunft] })) {
    return { ...basis, zustand: 'braucht-erlaubnis', herkunft };
  }
  return { ...basis, text: await seitentext(aktiv.id), zustand: 'gelesen', herkunft };
}

/**
 * Schritt 2: erlauben und lesen. MUSS aus einer eigenen Nutzergeste laufen
 * (Klick auf den Erlauben-Knopf) — siehe Modulkopf.
 *
 * @param {string|null} herkunft — das Muster aus Schritt 1
 * @param {number|null} tabId — die Kennung aus Schritt 1. Pflicht: ohne sie
 *   gäbe es nur „der aktive Tab", und der kann inzwischen ein anderer sein.
 * @returns {Promise<{text: string, zustand: 'gelesen'|'abgelehnt'}>}
 */
export async function erlaubeUndLies(herkunft, tabId) {
  if (!herkunft || tabId == null) return { text: '', zustand: 'abgelehnt' };
  if (!await chrome.permissions.request({ origins: [herkunft] })) {
    return { text: '', zustand: 'abgelehnt' };
  }
  return { text: await seitentext(tabId), zustand: 'gelesen' };
}
