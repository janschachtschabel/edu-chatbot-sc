/**
 * Prüfung für `ergebnisse.js` — die Ergebnis-Liste unter dem Chat.
 *
 * Der Fall, der die Datei überhaupt entstehen ließ (Review 2026-08-14): Liste
 * und Zähler lagen getrennt, die Liste überlebte den Neuaufbau des Chats, der
 * Zähler zählte weiter — über der ersten Antwort des neuen Laufs stand „Zug 5".
 * Genau das prüft der letzte Block: nach `leereErgebnisse` heißt der nächste
 * Eintrag wieder „Zug 1".
 *
 * `document` ist ein Doppel. Das Modul nutzt fünf Dinge davon (createElement,
 * className, textContent, append, prepend/replaceChildren/hidden) — ein
 * vollständiges DOM nachzubauen wäre teurer als der Nutzen, ein Doppel dieser
 * Größe ist in zwanzig Zeilen ehrlich.
 *
 *     node scripts/check-ergebnisse.mjs
 */

/** Ein Element-Doppel: nur was `ergebnisse.js` wirklich anfasst. */
function element(tag) {
  return {
    tag,
    className: '',
    textContent: '',
    hidden: false,
    kinder: [],
    append(...teile) { this.kinder.push(...teile); },
    prepend(...teile) { this.kinder.unshift(...teile); },
    replaceChildren() { this.kinder = []; },
  };
}

globalThis.document = { createElement: element };

// Erst nach dem Doppel importieren — der Modulrumpf fasst `document` zwar nicht
// an, aber die Reihenfolge soll niemand später erraten müssen.
const { leereErgebnisse, zeigeErgebnis } = await import('../ergebnisse.js');

let geprueft = 0;
const fehler = [];

function gleich(was, ist, soll) {
  geprueft++;
  const a = JSON.stringify(ist);
  const b = JSON.stringify(soll);
  if (a !== b) fehler.push(`${was}\n    ist:  ${a}\n    soll: ${b}`);
}

/** Frische Leiste; `$` gibt die zwei Kennungen heraus, die das Modul kennt. */
function leiste() {
  const knoten = { ergebnisListe: element('ol'), ergebnisLeer: element('p') };
  return { $: (id) => knoten[id], knoten };
}

/** Die Kopfzeile eines Eintrags als Text — „Zug 3" steht dort als Textstück. */
function kopfText(li) {
  const kopf = li.kinder[0];
  return kopf.kinder.map((k) => (typeof k === 'string' ? k : k.textContent)).join(' ');
}

// ── Ein Eintrag je Zug ─────────────────────────────────────────────

const a = leiste();
leereErgebnisse(a.$);   // Modulzustand aus früheren Blöcken zurücksetzen

zeigeErgebnis(a.$, { result: { taxon_id: '460' }, stop_reason: 'submit_result' });
gleich('ein Zug ergibt einen Eintrag', a.knoten.ergebnisListe.kinder.length, 1);
gleich('der Leer-Hinweis verschwindet', a.knoten.ergebnisLeer.hidden, true);
gleich('die Marke trägt den Grund',
  kopfText(a.knoten.ergebnisListe.kinder[0]), 'submit_result Zug 1');
gleich('mit Ergebnis: Marke "gut"',
  a.knoten.ergebnisListe.kinder[0].kinder[0].kinder[0].className, 'marke gut');
gleich('das Ergebnis steht eingerückt darunter',
  a.knoten.ergebnisListe.kinder[0].kinder[1].textContent,
  JSON.stringify({ taxon_id: '460' }, null, 2));

zeigeErgebnis(a.$, { result: null, stop_reason: 'text' });
gleich('der neueste Eintrag steht OBEN',
  kopfText(a.knoten.ergebnisListe.kinder[0]), 'text Zug 2');
gleich('ohne Ergebnis: Marke "leer"',
  a.knoten.ergebnisListe.kinder[0].kinder[0].kinder[0].className, 'marke leer');
gleich('und ein Satz statt JSON',
  a.knoten.ergebnisListe.kinder[0].kinder[1].textContent,
  'kein Ergebnis in diesem Zug — der Grund steht links');

zeigeErgebnis(a.$, { result: null, stop_reason: '' });
gleich('ohne Grund steht ein Strich', kopfText(a.knoten.ergebnisListe.kinder[0]), '— Zug 3');

// ── Der Neuaufbau: Liste UND Zählung gehen zusammen ────────────────

const b = leiste();
zeigeErgebnis(b.$, { result: { a: 1 }, stop_reason: 'submit_result' });
gleich('vor dem Leeren zählt es weiter (Modulzustand)',
  kopfText(b.knoten.ergebnisListe.kinder[0]), 'submit_result Zug 4');

leereErgebnisse(b.$);
gleich('Leeren räumt die Liste', b.knoten.ergebnisListe.kinder.length, 0);
gleich('und holt den Leer-Hinweis zurück', b.knoten.ergebnisLeer.hidden, false);

zeigeErgebnis(b.$, { result: { a: 1 }, stop_reason: 'submit_result' });
gleich('DER Fall: nach dem Leeren beginnt die Zählung wieder bei 1',
  kopfText(b.knoten.ergebnisListe.kinder[0]), 'submit_result Zug 1');

// ── Ausgabe ────────────────────────────────────────────────────────

if (fehler.length) {
  console.error(`\n  ${fehler.length} von ${geprueft} Prüfungen fehlgeschlagen:\n`);
  for (const f of fehler) console.error(`  ✗ ${f}\n`);
  process.exit(1);
}
console.log(`  ${geprueft} Prüfungen bestanden.`);
