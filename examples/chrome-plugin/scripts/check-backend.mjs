/**
 * Prüfung für `basisAusEingabe` — die Normalisierung der Backend-Adresse.
 *
 *     node scripts/check-backend.mjs
 */
import { basisAusEingabe } from '../backend.js';

let geprueft = 0;
const fehler = [];

function gleich(was, ist, soll) {
  geprueft++;
  if (JSON.stringify(ist) !== JSON.stringify(soll)) {
    fehler.push(`${was}\n    ist:  ${JSON.stringify(ist)}\n    soll: ${JSON.stringify(soll)}`);
  }
}

// Der eigentliche Anlass (live gemessen 2026-08-14): in „Backend" landete die
// BÜNDEL-Adresse. `ChatApiClient.setBaseUrl` hängt `/api` an, was drinsteht —
// daraus wurde `…/widget/boerdi-widget.js/api/chat/stream`, und jeder Zug
// endete mit „es ist ein Fehler aufgetreten". Gemessen: 404 gegen 200.
gleich('Bündel-Adresse wird auf die Herkunft gekürzt',
  basisAusEingabe('https://87.106.127.225.nip.io/widget/boerdi-widget.js'),
  { basis: 'https://87.106.127.225.nip.io', korrigiert: true });

gleich('auch die gehashte Fassung',
  basisAusEingabe('https://x.test/widget/boerdi-widget.745a62ee.js'),
  { basis: 'https://x.test', korrigiert: true });

gleich('eine saubere Herkunft bleibt, wie sie ist',
  basisAusEingabe('https://87.106.127.225.nip.io'),
  { basis: 'https://87.106.127.225.nip.io', korrigiert: false });

gleich('Schrägstrich am Ende fällt weg',
  basisAusEingabe('http://localhost:8000/'),
  { basis: 'http://localhost:8000', korrigiert: false });

// Ein Pfad-Präfix ist eine LEGITIME Aufstellung (Reverse-Proxy unter /boerdi).
// Er darf nicht gekürzt werden — nur `.js` ist eindeutig ein Versehen.
gleich('ein Pfad-Präfix bleibt erhalten',
  basisAusEingabe('https://x.test/boerdi'),
  { basis: 'https://x.test/boerdi', korrigiert: false });

gleich('leer bleibt leer', basisAusEingabe(''), { basis: '', korrigiert: false });
gleich('Unfug bleibt unverändert — das meldet der Gesundheits-Abruf',
  basisAusEingabe('nicht-mal-eine-url'),
  { basis: 'nicht-mal-eine-url', korrigiert: false });

if (fehler.length) {
  console.error(`\n  ${fehler.length} von ${geprueft} Prüfungen fehlgeschlagen:\n`);
  for (const f of fehler) console.error(`  ✗ ${f}\n`);
  process.exit(1);
}
console.log(`  ${geprueft} Prüfungen bestanden.`);
