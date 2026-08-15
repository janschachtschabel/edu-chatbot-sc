/**
 * Jedes Host-Attribut von `<boerdi-chat>` muss in der Laufzeit-Tabelle der
 * Einbindungs-Doku eingeordnet sein.
 *
 * **Warum es das gibt.** Die Tabelle „Was zur Laufzeit noch wirkt"
 * (`docs/browser-plugin-einbindung.md` §3) beantwortet die Frage, an der eine
 * Erweiterung scheitert: wirkt ein `setAttribute` nach dem Einhängen noch? Ein
 * neues Attribut, das dort fehlt, ist schlimmer als eines, das gar nicht
 * dokumentiert ist — die Tabelle sieht vollständig aus und ist es nicht.
 *
 * Am 14.08.2026 stand in derselben Tabelle noch eine Zeilenangabe, die zwei
 * Umbauten alt war (`widget.component.ts:279-315`, tatsächlich 317-370). Genau
 * diese Klasse von Verfall fängt der Wächter: Namen prüft er, Zeilennummern
 * nennt die Doku deshalb bewusst keine mehr.
 *
 * Quelle der Wahrheit ist die Input-Liste im Wächter-Spec der Hülle — dieselbe,
 * die auch die Studio-Referenz bindet. Diese Prüfung liest sie, statt eine
 * zweite Liste zu pflegen, die auseinanderlaufen könnte.
 *
 *     node scripts/check-docs-attributes.mjs
 */
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const SPEC = join(HIER, '..', 'projects/widget/src/app/widget/widget.component.spec.ts');
const DOKU = join(HIER, '..', '..', 'docs/browser-plugin-einbindung.md');
const ABSCHNITT = '### Was zur Laufzeit noch wirkt';

/** camelCase → kebab-case, wie Angular Elements die Attribute ableitet. */
const zuAttribut = (name) => name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);

const spec = await readFile(SPEC, 'utf8');
const liste = spec.match(/expect\(inputs\)\.toEqual\(\[([\s\S]*?)\]\)/);
if (!liste) {
  console.error('\n  Die Input-Liste im Wächter-Spec ist nicht auffindbar.');
  console.error(`  Erwartet: expect(inputs).toEqual([...]) in ${SPEC}\n`);
  process.exit(1);
}
const attribute = [...liste[1].matchAll(/'([a-zA-Z]+)'/g)].map((m) => zuAttribut(m[1]));

const doku = await readFile(DOKU, 'utf8');
const nach = doku.split(ABSCHNITT)[1];
if (!nach) {
  console.error(`\n  Der Abschnitt „${ABSCHNITT}" fehlt in der Doku.`);
  console.error('  Wurde er umbenannt? Dann hier mitziehen.\n');
  process.exit(1);
}
// Bis zur nächsten Hauptüberschrift. NICHT an `---` schneiden: der Trennstrich
// einer Markdown-Tabelle (`|---|---|`) sähe genauso aus, und der Abschnitt wäre
// nach der ersten Tabellenzeile zu Ende (beim Schreiben dieser Prüfung genau
// einmal passiert).
const tabelle = nach.split(/\n## /)[0];

const fehlend = attribute.filter((a) => !tabelle.includes(`\`${a}\``));

if (fehlend.length) {
  console.error(`\n  ${fehlend.length} Host-Attribut(e) ohne Zeile in der Laufzeit-Tabelle:`);
  for (const a of fehlend) console.error(`  ✗ ${a}`);
  console.error(`\n  Einordnen in ${ABSCHNITT} (docs/browser-plugin-einbindung.md):`);
  console.error('  A = wirkt sofort · B = erst beim nächsten Neustart · C = nur beim Start\n');
  process.exit(1);
}

console.log(`  ${attribute.length} Host-Attribute, alle in der Laufzeit-Tabelle eingeordnet.`);
