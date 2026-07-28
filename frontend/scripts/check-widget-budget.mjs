#!/usr/bin/env node
/**
 * CI gate for the widget embed contract (spec §5.5, "Bundle-Budget").
 *
 * Two properties are enforced, both of which the embed contract depends on:
 *   1. Single file — the host page embeds exactly one `<script src="…">`.
 *      Anything else in the output directory (a lazy chunk from a dynamic
 *      `import()`, an extracted stylesheet, a copied asset) breaks that embed
 *      silently, because nothing on the host page loads it.
 *   2. Size — ≤ 420 kB raw and ≤ 140 kB gzip, kB decimal (1000 bytes).
 *
 * On raw size this gate is a *duplicate* of the build-time budget, not a
 * stricter one: `@angular/build` defines `BYTES_IN_KILOBYTE = 1000`
 * (utils/bundle-calculator.js), so `maximumError: "420kb"` in angular.json is
 * the same 420 000 bytes as RAW_MAX here and the build already fails first.
 * What this gate adds is the **gzip** limit and the **single-file** check —
 * neither of which Angular's budgets can express.
 *
 * Usage: node scripts/check-widget-budget.mjs [bundle.js]
 * Without an argument it measures the real `build:widget` output. The optional
 * path exists so the gate itself can be tested against an oversized fixture.
 * Exits 1 on any breach; prints the measurements either way.
 */
import { gzipSync } from 'node:zlib';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const RAW_MAX = 420_000;
const GZIP_MAX = 140_000;
const DEFAULT_BUNDLE = 'dist/widget/browser/main.js';

const bundle = resolve(process.argv[2] ?? DEFAULT_BUNDLE);
const kb = (bytes) => (bytes / 1000).toFixed(2).replace('.', ',') + ' kB';

let raw;
try {
  raw = readFileSync(bundle);
} catch {
  console.error(`FEHLER: Bundle nicht gefunden: ${bundle}`);
  console.error('Erst bauen: npm run build:widget');
  process.exit(1);
}

// Bewusst OHNE Endungs-Filter: eine ausgelagerte CSS-Datei oder ein kopiertes
// Asset bricht den Embed-Vertrag genauso wie ein zweiter JS-Chunk.
const chunks = readdirSync(dirname(bundle));
const gzip = gzipSync(raw).length;
const breaches = [];

if (chunks.length !== 1) {
  breaches.push(`Single-File verletzt: ${chunks.length} Dateien (${chunks.join(', ')})`);
}
if (raw.length > RAW_MAX) {
  breaches.push(`raw ${kb(raw.length)} > ${kb(RAW_MAX)}`);
}
if (gzip > GZIP_MAX) {
  breaches.push(`gzip ${kb(gzip)} > ${kb(GZIP_MAX)}`);
}

console.log(`Bundle:  ${bundle}`);
console.log(`Dateien: ${chunks.length} (${chunks.join(', ')})`);
console.log(`raw:     ${kb(raw.length)} / ${kb(RAW_MAX)}  (${(100 * raw.length / RAW_MAX).toFixed(1)} %)`);
console.log(`gzip:    ${kb(gzip)} / ${kb(GZIP_MAX)}  (${(100 * gzip / GZIP_MAX).toFixed(1)} %)`);

if (breaches.length) {
  console.error('\n§5.5-Budget verletzt:');
  for (const b of breaches) console.error(`  - ${b}`);
  process.exit(1);
}
console.log('\n§5.5-Budget eingehalten.');
