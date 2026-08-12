#!/usr/bin/env node
/**
 * CI gate for the widget embed contract (spec §5.5, "Bundle-Budget").
 *
 * Two properties are enforced, both of which the embed contract depends on:
 *   1. Single file — the host page embeds exactly one `<script src="…">`.
 *      Anything else in the output directory (a lazy chunk from a dynamic
 *      `import()`, an extracted stylesheet, a copied asset) breaks that embed
 *      silently, because nothing on the host page loads it.
 *   2. Size — ≤ 600 kB raw and ≤ 175 kB gzip, kB decimal (1000 bytes).
 *
 * On raw size this gate is a *duplicate* of the build-time budget, not a
 * stricter one: `@angular/build` defines `BYTES_IN_KILOBYTE = 1000`
 * (utils/bundle-calculator.js), so `maximumError: "600kb"` in angular.json is
 * the same 600 000 bytes as RAW_MAX here and the build already fails first.
 * What this gate adds is the **gzip** limit and the **single-file** check —
 * neither of which Angular's budgets can express.
 *
 * **Raised 2026-07-31 from 420 kB / 140 kB.** Angular Material 3 was adopted on
 * the user's instruction ("das Größenlimit darf dafür steigen"), which cost a
 * measured **+75,8 kB raw / +33 kB gzip** (416,57 → 492,41 kB raw). The
 * angular.json budget was raised in the same slice; THIS file and the §5.5 text
 * were not — so `npm run budget` was red for nine slices while the build stayed
 * green. Classic paired-config drift: two places state the same limit, one gets
 * updated. If the limit moves again, all three move together:
 * `angular.json` (build-widget budgets) · this file · spec §5.5 "Bundle-Budget".
 *
 * GZIP_MAX is derived, not guessed: today's bundle compresses to 29,1 % of raw,
 * so 600 kB raw lands at ~175 kB gzip. Both ceilings are therefore reached at
 * the same amount of growth — neither is the silently stricter one.
 *
 * Usage: node scripts/check-widget-budget.mjs [bundle.js]
 * Without an argument it measures the real `build:widget` output. The optional
 * path exists so the gate itself can be tested against an oversized fixture.
 * Exits 1 on any breach; prints the measurements either way.
 */
import { gzipSync } from 'node:zlib';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const RAW_MAX = 600_000;
const GZIP_MAX = 175_000;
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

/**
 * Dateien, die bewusst NEBEN dem Bündel liegen dürfen — namentlich, nie per
 * Endung. Der Grund der Single-File-Regel ist „nichts auf der Gastseite lädt
 * es"; auf diese eine Datei trifft das nicht zu: das OAuth-Fenster ruft sie als
 * `redirect_uri` selbst auf (`session/sign-in-flow.OAUTH_CALLBACK_PATH`), sie
 * ist also kein toter Anhang, sondern ein zweiter, eigener Einstiegspunkt.
 * Eine Endungs-Ausnahme wäre hier falsch: ein versehentlich ausgelagertes
 * Stylesheet oder ein zweiter JS-Chunk muss weiterhin auffallen.
 */
const ERLAUBTE_BEIGABEN = new Set(['oauth-callback.html']);

const chunks = readdirSync(dirname(bundle));
const embed = chunks.filter((f) => !ERLAUBTE_BEIGABEN.has(f));
const gzip = gzipSync(raw).length;
const breaches = [];

if (embed.length !== 1) {
  breaches.push(`Single-File verletzt: ${embed.length} Dateien (${embed.join(', ')})`);
}
if (raw.length > RAW_MAX) {
  breaches.push(`raw ${kb(raw.length)} > ${kb(RAW_MAX)}`);
}
if (gzip > GZIP_MAX) {
  breaches.push(`gzip ${kb(gzip)} > ${kb(GZIP_MAX)}`);
}

console.log(`Bundle:  ${bundle}`);
console.log(`Dateien: ${chunks.length} (${chunks.join(', ')})`);
console.log(`Embed:   ${embed.length} (${embed.join(', ')})`);
console.log(`raw:     ${kb(raw.length)} / ${kb(RAW_MAX)}  (${(100 * raw.length / RAW_MAX).toFixed(1)} %)`);
console.log(`gzip:    ${kb(gzip)} / ${kb(GZIP_MAX)}  (${(100 * gzip / GZIP_MAX).toFixed(1)} %)`);

if (breaches.length) {
  console.error('\n§5.5-Budget verletzt:');
  for (const b of breaches) console.error(`  - ${b}`);
  process.exit(1);
}
console.log('\n§5.5-Budget eingehalten.');
