#!/usr/bin/env node
/**
 * CI-Gate gegen zwei Struktur-Fehler in den Studio-Templates, die kein Test
 * und kein Linter bemerkt — sie sehen im Bild völlig normal aus und schaden
 * nur denen, die die Seite nicht sehen.
 *
 * **Regel 1 — genau ein `<h1>` je Seite.** Die Shell trägt `<h1>BOERDi
 * Studio</h1>`; eine View, die selbst ein `<h1>` setzt, erzeugt zwei
 * Dokument-Titel. Screenreader bieten eine Überschriften-Liste zum Springen an
 * — mit zwei h1 ist unklar, was die Seite überhaupt ist (WCAG 1.3.1).
 * Die Norm der Seiten-Views ist `<h2>` (9 von 11 hielten sie; 2 nicht).
 *
 * **Regel 2 — jedes `<th>` braucht `scope`.** Ohne `scope` kann ein
 * Screenreader eine Zelle ihrer Kopfzeile nicht zuordnen und liest bei einer
 * 6-spaltigen Tabelle nackte Werte ohne Bedeutung vor (WCAG 1.3.1). Auch hier
 * war die Norm etabliert (49 von 69) und nur nicht durchgehalten — genau die
 * Art Lücke, die von allein zurückkehrt, wenn niemand sie prüft.
 *
 * Warum ein Skript und kein Komponententest: der Defekt ist eine EIGENSCHAFT
 * ALLER Templates, auch der noch nicht geschriebenen. Ein Test je bekanntem
 * Fall schließt die zwei gefundenen Stellen, nicht die Klasse. Gebaut im
 * Muster von `check-tokens.mjs` (gleiche Wurzel-Übergabe für Fixtures).
 *
 * Aufruf: node scripts/check-a11y-structure.mjs [wurzel]
 * Ohne Argument: `projects/studio/src/app/views`.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const STANDARD_WURZEL = 'projects/studio/src/app/views';

/** `<h1` mit Wortgrenze — `<h1>` und `<h1 class=…>` treffen, `<h10` nicht. */
const H1 = /<h1\b/gi;
/** Ein vollständiges `<th …>`-Start-Tag, damit die Attribute lesbar sind. */
const TH = /<th\b[^>]*>/gi;

const wurzel = resolve(process.argv[2] ?? STANDARD_WURZEL);

/**
 * HTML-Kommentare ausblenden, ZEILENTREU (jedes Zeichen außer `\n` wird ein
 * Leerzeichen), damit die gemeldeten Zeilennummern stimmen.
 *
 * Nötig, weil dieses Gate beim ersten Lauf den ERKLÄRENDEN KOMMENTAR anschlug,
 * der die Regel begründet — er nennt `<h1>` im Fließtext. Ein Prüfer, der eine
 * Begründung als Verstoß meldet, erzieht dazu, keine Begründung zu schreiben.
 */
function ohneKommentare(quelle) {
  return quelle.replace(/<!--[\s\S]*?-->/g, (block) => block.replace(/[^\n]/g, ' '));
}

function* wandern(verzeichnis) {
  for (const eintrag of readdirSync(verzeichnis)) {
    const pfad = join(verzeichnis, eintrag);
    if (statSync(pfad).isDirectory()) yield* wandern(pfad);
    else if (eintrag.endsWith('.html')) yield pfad;
  }
}

/** `{ regel, ort, ausschnitt }` je Verstoß, in Scan-Reihenfolge. */
const verstoesse = [];
let dateien = 0;
let thGesamt = 0;

for (const pfad of wandern(wurzel)) {
  dateien += 1;
  const zeilen = ohneKommentare(readFileSync(pfad, 'utf8')).split('\n');
  zeilen.forEach((zeile, index) => {
    const ort = `${relative(wurzel, pfad).replace(/\\/g, '/')}:${index + 1}`;
    for (const [treffer] of zeile.matchAll(H1)) {
      verstoesse.push({ regel: 'h1', ort, ausschnitt: treffer });
    }
    for (const [treffer] of zeile.matchAll(TH)) {
      thGesamt += 1;
      if (!/\bscope\s*=/.test(treffer)) {
        verstoesse.push({ regel: 'th-scope', ort, ausschnitt: treffer.trim() });
      }
    }
  });
}

console.log(`Wurzel:     ${wurzel}`);
console.log(`Templates:  ${dateien}`);
console.log(`<th>:       ${thGesamt}`);

if (verstoesse.length) {
  const texte = {
    h1: 'View-Templates dürfen kein <h1> setzen — die Shell trägt es bereits.'
      + ' Seiten-Titel sind <h2> (Norm der übrigen Seiten-Views).',
    'th-scope': 'Jedes <th> braucht scope="col" oder scope="row", sonst kann'
      + ' ein Screenreader Zelle und Kopfzeile nicht verbinden.',
  };
  for (const regel of ['h1', 'th-scope']) {
    const treffer = verstoesse.filter((v) => v.regel === regel);
    if (!treffer.length) continue;
    console.error(`\n${treffer.length}× ${regel}: ${texte[regel]}`);
    for (const { ort, ausschnitt } of treffer) console.error(`  ${ort}  ${ausschnitt}`);
  }
  process.exit(1);
}
console.log('\nÜberschriften-Hierarchie und Tabellen-Köpfe sind in Ordnung.');
