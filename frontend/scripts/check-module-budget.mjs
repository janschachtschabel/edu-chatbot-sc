#!/usr/bin/env node
/**
 * Budget der nachgeladenen UI-Module (Paket U3-0), Gegenstück zu `check-widget-budget.mjs`.
 *
 * Ein nachgeladenes Modul kostet erst, wenn sein Block erscheint — aber dann auf dem Gerät der Person,
 * oft im Mobilnetz. Deshalb je Bündel höchstens 20 kB gzip und alle zusammen höchstens 60 kB gzip
 * (kB dezimal, wie das Widget-Budget). Im Verzeichnis dürfen nur gehashte Bündel liegen
 * (`<ordner>.<8 hex>.js`) — alles andere würde das Backend nie ausliefern.
 *
 * Aufruf: node scripts/check-module-budget.mjs [verzeichnis]   (Vorgabe: dist/widget-module)
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

// U3-3b (2026-11-06): 15 → 20 kB — `ui_upload` trägt drei Aufgaben (Erfassen, Dokument, Übertragen,
// je zweisprachig) und lag bei 15,7 kB; ein Bündel lässt sich nicht weiter nachladend teilen (SRI).
export const JE_MODUL_GZIP = 20_000;
export const ZUSAMMEN_GZIP = 60_000;
const DATEI = /^ui-[a-z0-9-]+\.[0-9a-f]{8}\.js$/;

export function pruefe(ort) {
  const fehler = [];
  const module = [];
  for (const name of readdirSync(ort).sort()) {
    if (!DATEI.test(name)) {
      fehler.push(`${name}: kein gehashtes Modul-Bündel`);
      continue;
    }
    const roh = readFileSync(join(ort, name));
    const gzip = gzipSync(roh, { level: 9 }).length;
    module.push({ name, roh: roh.length, gzip });
    if (gzip > JE_MODUL_GZIP) fehler.push(`${name}: ${gzip} B gzip > ${JE_MODUL_GZIP} B`);
  }
  const summe = module.reduce((s, m) => s + m.gzip, 0);
  if (summe > ZUSAMMEN_GZIP) fehler.push(`alle Module zusammen: ${summe} B gzip > ${ZUSAMMEN_GZIP} B`);
  return { fehler, module, summe };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const ort = resolve(process.argv[2] ?? 'dist/widget-module');
  let ergebnis;
  try {
    ergebnis = pruefe(ort);
  } catch {
    console.error(`FEHLER: ${ort} fehlt — erst bauen: npm run build:widget`);
    process.exit(1);
  }
  for (const m of ergebnis.module) console.log(`${m.name}: ${m.roh} B roh, ${m.gzip} B gzip`);
  console.log(`zusammen: ${ergebnis.summe} B gzip (Grenze ${ZUSAMMEN_GZIP} B)`);
  if (ergebnis.fehler.length) {
    for (const f of ergebnis.fehler) console.error(`FEHLER: ${f}`);
    process.exit(1);
  }
}
