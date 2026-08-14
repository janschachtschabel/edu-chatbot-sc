/**
 * Prüfung für `tab-lesen.js` — Herkunft und der Zwei-Schritt-Ablauf.
 *
 * `chrome` ist hier ein Doppel: die echten APIs gibt es nur im Browser, aber
 * die Frage, die schiefgehen kann, ist keine Browser-Frage — sie lautet
 * **„welchen Tab liest Schritt 2?"**. Der Befund (Review 2026-08-14): Schritt 2
 * fragte erneut den aktiven Tab ab. Wer zwischen den zwei nötigen Klicks den
 * Tab wechselte, bekam den Text von Seite B unter der Adresse von Seite A —
 * still, weil die Anzeige weiter Seite A zeigte.
 *
 *     node scripts/check-tab.mjs
 */
import { erlaubeUndLies, liesTab, tabHerkunft } from '../tab-lesen.js';

let geprueft = 0;
const fehler = [];

function gleich(was, ist, soll) {
  geprueft++;
  const a = JSON.stringify(ist);
  const b = JSON.stringify(soll);
  if (a !== b) fehler.push(`${was}\n    ist:  ${a}\n    soll: ${b}`);
}

/**
 * Ein `chrome`-Doppel. `gelesen` sammelt, welche Tab-Kennungen `executeScript`
 * tatsächlich angefasst hat — daran hängt der eigentliche Regressionstest.
 */
function stelleChrome({ tabs = [], erlaubt = false, gewaehrt = true } = {}) {
  const gelesen = [];
  globalThis.chrome = {
    tabs: { query: async () => tabs },
    permissions: {
      contains: async () => erlaubt,
      request: async () => gewaehrt,
    },
    scripting: {
      executeScript: async ({ target }) => {
        gelesen.push(target.tabId);
        return [{ result: `Text von Tab ${target.tabId}` }];
      },
    },
  };
  return gelesen;
}

const SEITE_A = { id: 1, url: 'https://de.wikipedia.org/wiki/Optik', title: 'Optik' };
const SEITE_B = { id: 2, url: 'https://de.wikipedia.org/wiki/Akustik', title: 'Akustik' };

// ── tabHerkunft: reine Funktion, entscheidet über die Nachfrage ────

gleich('https ergibt ein Herkunfts-Muster',
  tabHerkunft('https://de.wikipedia.org/wiki/Optik'), 'https://de.wikipedia.org/*');
gleich('http ebenso', tabHerkunft('http://localhost:8000/x'), 'http://localhost:8000/*');
gleich('chrome:// gibt nichts her', tabHerkunft('chrome://extensions'), null);
// Der Web Store ist https und sieht hier deshalb aus wie jede Seite — die
// Erlaubnis verweigert erst Chrome selbst, nicht diese Funktion. Bewusst so
// gepinnt, damit niemand später eine Sonderregel einbaut, die es nicht braucht.
gleich('der Web Store ist für DIESE Funktion eine gewöhnliche https-Seite',
  tabHerkunft('https://chromewebstore.google.com/'), 'https://chromewebstore.google.com/*');
gleich('file:// gibt nichts her', tabHerkunft('file:///C:/tmp/x.html'), null);
gleich('die eigene Leiste gibt nichts her',
  tabHerkunft('chrome-extension://abc/panel.html'), null);
gleich('leer gibt nichts her', tabHerkunft(''), null);
gleich('Unfug wirft nicht', tabHerkunft('http://['), null);

// ── liesTab: die vier Zustände ─────────────────────────────────────

stelleChrome({ tabs: [SEITE_A] });
gleich('ohne Textwunsch: nur Adresse und Titel',
  await liesTab({ textGewuenscht: false }),
  { url: SEITE_A.url, titel: 'Optik', text: '', tabId: 1,
    zustand: 'ohne-text', herkunft: 'https://de.wikipedia.org/*' });

stelleChrome({ tabs: [{ id: 3, url: 'chrome://extensions', title: 'Erweiterungen' }] });
gleich('interne Seite: Chrome lässt nichts zu',
  (await liesTab({ textGewuenscht: true })).zustand, 'intern');

stelleChrome({ tabs: [SEITE_A], erlaubt: false });
gleich('ohne Erlaubnis: braucht-erlaubnis, kein Text',
  (await liesTab({ textGewuenscht: true })).zustand, 'braucht-erlaubnis');

const mitErlaubnis = stelleChrome({ tabs: [SEITE_A], erlaubt: true });
gleich('mit Erlaubnis: gelesen',
  (await liesTab({ textGewuenscht: true })).text, 'Text von Tab 1');
gleich('und zwar aus dem aktiven Tab', mitErlaubnis, [1]);

// ── erlaubeUndLies: DER Regressionstest ────────────────────────────

const nachWechsel = stelleChrome({ tabs: [SEITE_B], gewaehrt: true });
const ergebnis = await erlaubeUndLies('https://de.wikipedia.org/*', SEITE_A.id);
gleich('Schritt 2 liest die übergebene Kennung, NICHT den inzwischen aktiven Tab',
  nachWechsel, [1]);
gleich('und liefert deren Text', ergebnis.text, 'Text von Tab 1');
gleich('Zustand gelesen', ergebnis.zustand, 'gelesen');

stelleChrome({ tabs: [SEITE_A], gewaehrt: false });
gleich('abgelehnte Erlaubnis: kein Text',
  await erlaubeUndLies('https://de.wikipedia.org/*', 1),
  { text: '', zustand: 'abgelehnt' });

stelleChrome({ tabs: [SEITE_A] });
gleich('ohne Herkunft gar nicht erst fragen',
  await erlaubeUndLies(null, 1), { text: '', zustand: 'abgelehnt' });
gleich('ohne Tab-Kennung ebenso',
  await erlaubeUndLies('https://de.wikipedia.org/*', null),
  { text: '', zustand: 'abgelehnt' });

// ── Ausgabe ────────────────────────────────────────────────────────

if (fehler.length) {
  console.error(`\n  ${fehler.length} von ${geprueft} Prüfungen fehlgeschlagen:\n`);
  for (const f of fehler) console.error(`  ✗ ${f}\n`);
  process.exit(1);
}
console.log(`  ${geprueft} Prüfungen bestanden.`);
