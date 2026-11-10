#!/usr/bin/env node
/**
 * CI gate for the widget embed contract (spec §5.5, "Bundle-Budget").
 *
 * Two properties are enforced, both of which the embed contract depends on:
 *   1. Single file — the host page embeds exactly one `<script src="…">`.
 *      Anything else in the output directory (a lazy chunk from a dynamic
 *      `import()`, an extracted stylesheet, a copied asset) breaks that embed
 *      silently, because nothing on the host page loads it.
 *   2. Size — ≤ 700 kB raw and ≤ 210 kB gzip, kB decimal (1000 bytes); warning above 200 kB gzip.
 *
 * On raw size this gate is a *duplicate* of the build-time budget, not a
 * stricter one: `@angular/build` defines `BYTES_IN_KILOBYTE = 1000`
 * (utils/bundle-calculator.js), so `maximumError: "700kb"` in angular.json is
 * the same 700 000 bytes as RAW_MAX here and the build already fails first.
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
 * **Raised 2026-11-10 to 700 kB / 210 kB (warning from 200 kB gzip)** for the formula
 * rendering (Plan 2026-11-10, TB-E4); before: 690 / 200 / 190 (2026-11-02).
 * **Raised 2026-11-02 to 690 kB / 200 kB (warning from 190 kB gzip)** for the UI modules
 * (Paket U1, user decision U-F2): small, frequent modules ship in the bundle; anything larger
 * or rarely used is lazy-loaded instead of raising the limit again.
 * GZIP_MAX is derived, not guessed: today's bundle compresses to 29,1 % of raw,
 * so 690 kB raw lands at ~200 kB gzip. Both ceilings are therefore reached at
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

// Plan 2026-11-10, TB-E4 (Nutzer-Entscheid N5): +10 kB für die Formel-Darstellung.
const RAW_MAX = 700_000;
const GZIP_MAX = 210_000;
/** Above this the gate stays green but warns: lazy-load instead of growing further. */
const GZIP_WARN = 200_000;
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
 *
 * `edu-sharing-demo.html` steht aus demselben Grund hier (2026-08-18): sie wird
 * von KEINER Gastseite geladen — sie IST eine Seite, die ein Mensch unter
 * `/widget/edu-sharing-demo.html` aufruft (`api/widget.py`, Route
 * `/{asset_name}`; angeboten in docs/browser-plugin-einbindung.md). Die Datei
 * kam mit der Probierseite dazu und ließ diese Gate stumm auflaufen, weil sie
 * nur in CI läuft.
 */
const ERLAUBTE_BEIGABEN = new Set(['oauth-callback.html', 'edu-sharing-demo.html']);

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
if (gzip > GZIP_WARN) {
  console.warn(`\nWarnung: gzip ${kb(gzip)} > ${kb(GZIP_WARN)} — große oder seltene UI-Module nachladen.`);
}
console.log('\n§5.5-Budget eingehalten.');
