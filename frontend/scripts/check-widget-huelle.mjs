#!/usr/bin/env node
/**
 * Bau-Test „keine Deklaration auf oberster Ebene“ für alles, was das Widget als klassisches Skript
 * auf eine Gastseite bringt: das Bündel `main.js` und die nachgeladenen Module.
 *
 * Warum: In einem klassischen `<script>` gehört die oberste Ebene der Gastseite. `var` und
 * Funktionsdeklarationen werden dort zu Eigenschaften von `window`, `let`/`const`/`class` zu Namen,
 * die jedes andere Skript der Seite lesen kann. Der Angular-Builder schreibt das Bündel als
 * ES-Modul (ohne Hülle), ausgeliefert wird es aber klassisch — bis zum 2026-11-15 hingen deshalb
 * rund 2 000 Namen des Bündels am Fenster der Gastseite, darunter die Funktion, die den
 * Zugangsblock liest. `build-widget-huelle.mjs` setzt das Bündel in eine Hülle; diese Prüfung hält
 * fest, dass es dabei bleibt.
 *
 * Geprüft wird die Form, nicht das Verhalten: die Datei ist ein gültiges klassisches Skript, und
 * auf oberster Ebene stehen nur sofort aufgerufene Funktionsausdrücke (davor höchstens Direktiven
 * wie `"use strict"`). Eine Zuweisung an `window` INNERHALB der Hülle sieht diese Prüfung nicht.
 * Für das Hauptbündel fängt sie der E2E-Test „legt keine Namen im Fenster der Gastseite an“
 * (`e2e/embed.spec.ts`, bis zum geöffneten Panel); die Nachlade-Module lädt er nicht — die laufen
 * im strikten Modus, ein stilles Global durch eine vergessene Deklaration gibt es dort nicht.
 *
 * Bekannte Lücke des Parsers: V8 liest `<!--` in einem klassischen Skript als Zeilenkommentar,
 * TypeScript nicht. Mit einer eigens gebauten Eingabe lässt sich die Prüfung so täuschen; in der
 * Ausgabe von esbuild kommt die Zeichenfolge nur in Texten und Mustern vor.
 *
 * Aufruf: node scripts/check-widget-huelle.mjs [datei.js …]
 * Ohne Argument: `dist/widget/browser/main.js` und alle Bündel in `dist/widget-module/`.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Script } from 'node:vm';

import ts from 'typescript';

const BUENDEL = 'dist/widget/browser/main.js';
const MODULE = 'dist/widget-module';

function ohneKlammern(knoten) {
  let k = knoten;
  while (ts.isParenthesizedExpression(k)) k = k.expression;
  return k;
}

/** `(()=>{…})()`, `(function(){…})()` oder `(function(){…}())` — auch `async`. Kein Generator:
 *  dessen Aufruf führt den Rumpf nicht aus. */
function istHuelle(anweisung) {
  if (!ts.isExpressionStatement(anweisung)) return false;
  const aufruf = ohneKlammern(anweisung.expression);
  if (!ts.isCallExpression(aufruf)) return false;
  const funktion = ohneKlammern(aufruf.expression);
  return ts.isArrowFunction(funktion) || (ts.isFunctionExpression(funktion) && !funktion.asteriskToken);
}

function istDeklaration(anweisung) {
  return ts.isVariableStatement(anweisung) || ts.isFunctionDeclaration(anweisung)
    || ts.isClassDeclaration(anweisung);
}

/**
 * Prüft den Text eines Bündels. Gibt die Verstöße zurück — leer heißt: nichts auf oberster Ebene
 * außer der Hülle.
 */
export function pruefe(code) {
  try {
    // Nur übersetzen, nicht ausführen. `import`/`export` oder ein `await` auf oberster Ebene wären
    // in der Hülle ein Syntaxfehler — das Widget lüde dann still gar nicht.
    new Script(code);
  } catch (fehler) {
    return [`kein gültiges klassisches Skript: ${fehler.message}`];
  }
  const quelle = ts.createSourceFile('buendel.js', code, ts.ScriptTarget.Latest, false, ts.ScriptKind.JS);
  const verstoesse = [];
  let huellen = 0;
  for (const anweisung of quelle.statements) {
    if (istHuelle(anweisung)) {
      huellen += 1;
      continue;
    }
    // Direktiven-Vorspann (`"use strict"`): nur vor der ersten Hülle ist ein Text eine Direktive.
    if (!huellen && !verstoesse.length && ts.isExpressionStatement(anweisung)
        && ts.isStringLiteral(anweisung.expression)) continue;
    const anfang = code.slice(anweisung.getStart(quelle), anweisung.end).replace(/\s+/g, ' ').slice(0, 60);
    verstoesse.push(`${istDeklaration(anweisung) ? 'Deklaration auf oberster Ebene' : 'Anweisung außerhalb der Hülle'}: ${anfang}`);
  }
  if (!huellen && !verstoesse.length) verstoesse.push('keine Hülle gefunden (leeres Bündel?)');
  return verstoesse;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let dateien = process.argv.slice(2).map((d) => resolve(d));
  if (!dateien.length) {
    // Der Bau legt den Ordner immer an, auch ohne Module. Fehlt er, wurde nicht (ganz) gebaut —
    // und „Module geprüft“ wäre eine leere Zusage.
    if (!existsSync(MODULE)) {
      console.error(`FEHLER: ${resolve(MODULE)} fehlt — erst bauen: npm run build:widget`);
      process.exit(1);
    }
    const module = readdirSync(MODULE).filter((n) => n.endsWith('.js')).sort();
    console.log(`Geprüft: das Bündel und ${module.length} Nachlade-Modul(e).`);
    dateien = [resolve(BUENDEL), ...module.map((n) => resolve(join(MODULE, n)))];
  }
  let rot = false;
  for (const datei of dateien) {
    let code;
    try {
      code = readFileSync(datei, 'utf8');
    } catch {
      console.error(`FEHLER: ${datei} fehlt — erst bauen: npm run build:widget`);
      process.exit(1);
    }
    const verstoesse = pruefe(code);
    if (!verstoesse.length) {
      console.log(`${datei}: in einer Hülle, nichts auf oberster Ebene.`);
      continue;
    }
    rot = true;
    console.error(`FEHLER: ${datei}: ${verstoesse.length} Verstoß/Verstöße`);
    for (const v of verstoesse.slice(0, 5)) console.error(`  - ${v}`);
    if (verstoesse.length > 5) console.error(`  … und ${verstoesse.length - 5} weitere`);
  }
  if (rot) process.exit(1);
}
