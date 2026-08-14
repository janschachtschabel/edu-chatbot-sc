/**
 * Das Widget-Bündel in die Seitenleiste hängen.
 *
 * **Warum es aus `vendor/` kommt.** Manifest V3 verbietet nachgeladenen Code:
 * auf einer Erweiterungs-Seite gilt `script-src 'self'`, ein
 * `<script src="https://backend/widget/…">` wird gesperrt. Das Bündel muss
 * also im Ordner liegen — `node scripts/fetch-widget.mjs <backend>` holt es.
 */

/** Wie lange auf die Element-Definition gewartet wird, bevor es gemeldet wird.
 *  Ein Bündel, das lädt aber nichts definiert, hinge sonst ewig — und ewiges
 *  Warten sieht aus wie ein langsames Netz, nicht wie ein Fehler. */
const DEFINITIONS_FRIST_MS = 10000;

/**
 * @param {(grund: string) => void} beiFehler — die Leiste zeigt es an
 * @returns {Promise<boolean>}
 *
 * Ein gewöhnlicher `<script>`-Tag, **kein** `import()`: das Bündel ist ein
 * klassisches Skript (so binden es die Demo-Seiten und jede Gastseite ein).
 * `onerror` erkennt zugleich die fehlende Datei — ein Mechanismus statt zweier.
 */
export function ladeBuendel(beiFehler) {
  const scheitern = (grund) => { console.error('Widget-Bündel:', grund); beiFehler(grund); return false; };
  return new Promise((fertig) => {
    const s = document.createElement('script');
    s.src = chrome.runtime.getURL('vendor/boerdi-widget.js');
    s.onerror = () => fertig(scheitern('vendor/boerdi-widget.js nicht ladbar'));
    s.onload = () => {
      const frist = new Promise((_, ab) =>
        setTimeout(() => ab(new Error('kein <boerdi-chat> definiert')), DEFINITIONS_FRIST_MS));
      Promise.race([customElements.whenDefined('boerdi-chat'), frist])
        .then(() => fertig(true))
        .catch((err) => fertig(scheitern(err.message)));
    };
    document.head.append(s);
  });
}
