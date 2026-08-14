/**
 * Das Widget-Bündel vom Backend nach `vendor/` holen.
 *
 * **Warum das nötig ist.** Manifest V3 verbietet nachgeladenen Code: auf einer
 * Erweiterungs-Seite gilt `script-src 'self'`, und ein
 * `<script src="https://backend/widget/boerdi-widget.js">` wird gesperrt. Das
 * Bündel muss also im Ordner liegen. Das ist kein Umweg des Beispiels, sondern
 * die Regel — jede echte Erweiterung muss es genauso machen.
 *
 *     node scripts/fetch-widget.mjs http://localhost:8000
 *
 * Danach in `chrome://extensions` auf „Neu laden" — ein getauschtes Bündel
 * sieht Chrome nicht von selbst.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const ZIEL = join(HIER, '..', 'vendor', 'boerdi-widget.js');

const basis = (process.argv[2] || 'http://localhost:8000').replace(/\/+$/, '');
const quelle = `${basis}/widget/boerdi-widget.js`;

console.log(`Hole ${quelle}`);

let antwort;
try {
  antwort = await fetch(quelle);
} catch (err) {
  console.error(`\n  Backend nicht erreichbar: ${err.message}`);
  console.error('  Läuft es? Und ist die Adresse richtig?\n');
  process.exit(1);
}

if (!antwort.ok) {
  console.error(`\n  ${antwort.status} ${antwort.statusText}`);
  if (antwort.status === 503) {
    console.error('  503 heißt: das Bündel ist im Backend nicht gebaut.');
    console.error('  Im Repositorium: cd frontend && npm run build:widget\n');
  }
  process.exit(1);
}

const code = await antwort.text();
// Ein 200 mit einer HTML-Fehlerseite wäre schlimmer als ein 404: die Datei
// läge da, und die Erweiterung scheiterte erst beim Laden mit einem
// Syntaxfehler, den niemand hierher zurückverfolgt.
if (/^\s*</.test(code)) {
  console.error('\n  Die Antwort ist kein JavaScript, sondern HTML.');
  console.error('  Zeigt die Adresse wirklich auf das Backend?\n');
  process.exit(1);
}

await mkdir(dirname(ZIEL), { recursive: true });
await writeFile(ZIEL, code, 'utf8');

const kb = Math.round(code.length / 1024);
console.log(`  vendor/boerdi-widget.js geschrieben (${kb} kB).`);
console.log('  Jetzt in chrome://extensions auf „Neu laden".');
