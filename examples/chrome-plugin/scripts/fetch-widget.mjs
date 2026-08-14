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
 *
 * **Nur gegen ein Backend, dem ihr vertraut.** Was hier ankommt, läuft danach
 * mit den Rechten der Erweiterung — samt der Erlaubnis für die Seiten, die ihr
 * ihr gebt. Eine Prüfsumme gibt es nicht (es wird keine veröffentlicht), also
 * ist die Quelle die ganze Sicherheit. Über `http://` auf einem fremden Host
 * kann jeder dazwischen den Code austauschen; das Skript sagt es, verweigert
 * aber nichts — beim Entwickeln gegen `localhost` ist `http` der Normalfall.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const ZIEL = join(HIER, '..', 'vendor', 'boerdi-widget.js');

const basis = (process.argv[2] || 'http://localhost:8000').replace(/\/+$/, '');
const quelle = `${basis}/widget/boerdi-widget.js`;

console.log(`Hole ${quelle}`);

// Unverschlüsselt von einem fremden Host: dann bestimmt jeder auf dem Weg, was
// gleich mit den Rechten der Erweiterung läuft. Kein Abbruch — gegen
// `localhost` ist genau das der Entwicklungsalltag.
try {
  const u = new URL(quelle);
  const lokal = ['localhost', '127.0.0.1', '::1'].includes(u.hostname);
  if (u.protocol === 'http:' && !lokal) {
    console.warn(`\n  ACHTUNG: ${u.hostname} liefert über http, also ungeschützt.`);
    console.warn('  Was hier ankommt, läuft danach mit den Rechten der Erweiterung.\n');
  }
} catch {
  // Unbrauchbare Adresse — das meldet der Abruf gleich mit einer klareren Zeile.
}

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
