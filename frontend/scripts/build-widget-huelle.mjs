#!/usr/bin/env node
/**
 * Setzt das Widget-Bündel in eine Hülle (letzter Schritt von `npm run build:widget`).
 *
 * Der Angular-Builder (`@angular/build:application`) schreibt `main.js` als ES-Modul: alle
 * Deklarationen stehen auf oberster Ebene, was in einem Modul folgenlos ist. Ausgeliefert wird das
 * Bündel aber als klassisches Skript (`<script src="…/widget/boerdi-widget.js" defer>`), und dort
 * gehört die oberste Ebene der Gastseite: rund 2 000 Namen des Bündels hingen am `window` (gemessen
 * 2026-11-15) — aufrufbar für jedes Skript der Seite, darunter die Funktion, die den Zugangsblock
 * liest, und im Zusammenstoß mit Namen der Seite (`$` war dabei). Der Builder kennt kein anderes
 * Ausgabeformat, deshalb dieser Nachschritt. Die Nachlade-Module brauchen ihn nicht: esbuild baut
 * sie gleich mit `format: 'iife'`.
 *
 * Die Hülle ist eine Pfeilfunktion: `this` bleibt, was es auf oberster Ebene war. Bewusst ohne
 * `"use strict"` — das Bündel lief bisher im nachlässigen Modus, und dieser Schritt soll nur die
 * Sichtbarkeit der Namen ändern, nicht das Verhalten.
 *
 * Grenze: Das ist Hygiene, kein Schutz vor der Gastseite. Ein Skript der Seite kann weiterhin
 * `fetch` oder `XMLHttpRequest` umbiegen (der Zugangsblock reist über beide) oder die Tauschstelle
 * selbst rufen (docs/mcp-und-anmeldung.md, R6).
 *
 * Preis: Im kalten Laden kostet die Hülle Zeit — gemessen am 2026-11-15 im Chromium ohne
 * Oberfläche rund 15 bis 25 ms bis zum definierten Element (Median 79 → 100 ms). Eine
 * `function`-Hülle misst sich gleich; jedes Bündel in dieser Form zahlt das.
 *
 * Aufruf: node scripts/build-widget-huelle.mjs [bundle.js]   (Vorgabe: dist/widget/browser/main.js)
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { pruefe } from './check-widget-huelle.mjs';

const BUENDEL = 'dist/widget/browser/main.js';

/** Der Zeilenumbruch vor dem Ende ist Pflicht: endet das Bündel mit einem Zeilenkommentar,
 *  verschluckte der sonst die schließende Klammer. */
export function huelle(code) {
  return `(()=>{${code}\n})();\n`;
}

/**
 * Hüllt die Datei, falls sie es nicht schon ist. Geschrieben wird nur ein Ergebnis, das die
 * Prüfung besteht — sonst bleibt die Datei, wie sie war, und es gibt einen Fehler.
 * Gibt `true` zurück, wenn geschrieben wurde.
 */
export function huelleDatei(pfad) {
  const code = readFileSync(pfad, 'utf8');
  if (!pruefe(code).length) return false;
  const gehuellt = huelle(code);
  const verstoesse = pruefe(gehuellt);
  if (verstoesse.length) throw new Error(`${pfad} lässt sich nicht hüllen: ${verstoesse.join('; ')}`);
  writeFileSync(pfad, gehuellt);
  return true;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const pfad = resolve(process.argv[2] ?? BUENDEL);
  try {
    console.log(huelleDatei(pfad) ? `Hülle gesetzt: ${pfad}` : `Schon in einer Hülle: ${pfad}`);
  } catch (fehler) {
    console.error(`FEHLER: ${fehler.message}`);
    process.exit(1);
  }
}
