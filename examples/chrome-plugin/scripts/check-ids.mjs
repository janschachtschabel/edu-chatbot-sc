/**
 * Jede `$('…')`-Kennung aus `panel.js`/`einstellungen.js`/`ergebnisse.js` muss
 * es in `panel.html` geben.
 *
 * Ein Tippfehler dort ist ein `null` und damit ein Fehler erst beim Klick — in
 * einer Seitenleiste, deren Konsole man erst aufmachen muss. Diese Prüfung
 * ersetzt keinen Browser, aber sie fängt genau diese Klasse ab, ohne einen.
 *
 *     node scripts/check-ids.mjs
 */
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
// ALLE Dateien, die `$` hereingereicht bekommen: sie greifen genauso auf
// Kennungen zu. Nur `panel.js` zu prüfen ließe eine ganze Datei durchrutschen —
// wer hier ein neues Modul vergisst, hat den Wächter für dieses Modul
// abgeschaltet, ohne dass etwas rot wird.
const quellen = ['panel.js', 'einstellungen.js', 'ergebnisse.js'];
const js = (await Promise.all(
  quellen.map((d) => readFile(join(HIER, '..', d), 'utf8')))).join('\n');
const html = await readFile(join(HIER, '..', 'panel.html'), 'utf8');

const vorhanden = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));

// `$('x')` plus die Kennungen, die als Zeichenketten in `GEMERKTE_FELDER`
// stehen — beide Wege enden bei `document.getElementById`.
const benutzt = new Set([...js.matchAll(/\$\('([^']+)'\)/g)].map((m) => m[1]));
const gemerkt = js.match(/GEMERKTE_FELDER = \[([\s\S]*?)\];/);
if (gemerkt) {
  for (const m of gemerkt[1].matchAll(/'([^']+)'/g)) benutzt.add(m[1]);
}

const fehlend = [...benutzt].filter((id) => !vorhanden.has(id)).sort();
const unbenutzt = [...vorhanden].filter((id) => !benutzt.has(id)).sort();

if (fehlend.length) {
  console.error(`\n  ${fehlend.length} Kennung(en) in panel.js ohne Gegenstück in panel.html:`);
  for (const id of fehlend) console.error(`  ✗ #${id}`);
  console.error('');
  process.exit(1);
}

console.log(`  ${benutzt.size} Kennungen geprüft, alle vorhanden.`);
if (unbenutzt.length) {
  // Kein Fehler: manche Kennungen stehen nur für `aria`-Bezüge oder CSS da.
  console.log(`  (nur im HTML, von panel.js nicht angefasst: ${unbenutzt.join(', ')})`);
}
