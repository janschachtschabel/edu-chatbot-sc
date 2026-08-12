#!/usr/bin/env node
/**
 * CI gate against hand-set corner radii (U4c).
 *
 * Why this needs a gate. Radii are the one design dimension that drifts without
 * anyone noticing: 3px here, 5px there, 6px in the next component — each looks
 * fine on its own, and together they read as "assembled from parts". The widget
 * had **eleven distinct values** before U4c (3, 4, 5, 6, 8, 10, 12, 14, 16, 18,
 * 20 px). Material 3 offers a scale of six (`--mat-sys-corner-*`), and the
 * point of a scale is that a change to it propagates instead of being
 * re-typed.
 *
 * The gate is therefore not "these numbers are wrong" but "a number here is a
 * decision that belongs to the theme".
 *
 * Usage: node scripts/check-radii.mjs [rootDir]
 * Without an argument it scans `projects/ui/src` and `projects/widget/src`.
 * The optional path exists so the gate can be pointed at a fixture — the same
 * seam `check-tokens.mjs` and `check-widget-budget.mjs` use.
 *
 * Deliberately NOT scanned: `projects/studio`. The studio is a stand-alone SPA
 * with its own token file (`theme/_studio-tokens.scss`) and does not load the
 * Material theme; `--mat-sys-corner-*` does not exist there.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const DEFAULT_ROOTS = ['projects/ui/src', 'projects/widget/src'];
const EXTENSIONS = new Set(['.scss', '.css', '.ts']);
const SKIP_DIRS = new Set(['node_modules', 'dist', '.angular']);

/** Matches `border-radius`, `border-top-left-radius`, … and SCSS `$…radius`. */
const RADIUS = /(?:^|[\s;{])((?:border(?:-[a-z]+)*-radius)|(?:\$[a-z-]*radius))\s*:\s*([^;}\n]+)/gi;

/**
 * Values that are NOT a hand-set corner size.
 *
 * `50%` and `inherit` are shape statements, not scale values: `50%` makes a
 * circle out of whatever box it is on (avatar, FAB, status dot), and `inherit`
 * copies the parent's decision. `0` is the explicit absence of a radius —
 * `--mat-sys-corner-none` would say the same thing in more characters.
 */
const ERLAUBT = [
  (v) => v.includes('var(--mat-sys-corner-'),
  (v) => v === '0',
  (v) => v === '50%',
  (v) => v === 'inherit',
];

/**
 * File-scoped exceptions. Each needs a reason — an unexplained entry here is
 * how a gate quietly stops gating.
 */
const AUSNAHMEN = new Map([
  [
    'ui/src/print/print-utils.ts',
    'Baut mit `window.open` + `document.write` ein EIGENES Dokument. Die '
    + '`--mat-sys-*`-Token leben am `:host` des Widgets und existieren dort '
    + 'nicht; ein `var()` darauf wäre eine ungültige Deklaration (und damit '
    + 'gar kein Radius).',
  ],
]);

const roots = process.argv[2] ? [process.argv[2]] : DEFAULT_ROOTS;

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) yield* walk(path);
    else if (EXTENSIONS.has(entry.slice(entry.lastIndexOf('.')))) yield path;
  }
}

/** `projects/ui/src/x.scss` → `ui/src/x.scss`, plattformunabhängig. */
function kurzpfad(path) {
  return relative(resolve('projects'), resolve(path)).replace(/\\/g, '/');
}

const funde = [];
const uebersprungen = new Set();
let dateien = 0;

for (const root of roots) {
  for (const path of walk(resolve(root))) {
    dateien += 1;
    const kurz = kurzpfad(path);
    if (AUSNAHMEN.has(kurz)) { uebersprungen.add(kurz); continue; }
    const lines = readFileSync(path, 'utf8').split('\n');
    lines.forEach((line, index) => {
      for (const [, eigenschaft, wert] of line.matchAll(RADIUS)) {
        const v = wert.trim();
        if (ERLAUBT.some((ok) => ok(v))) continue;
        funde.push({ ort: `${kurz}:${index + 1}`, eigenschaft, wert: v });
      }
    });
  }
}

console.log(`Wurzeln:     ${roots.join(', ')}`);
console.log(`Dateien:     ${dateien}`);
for (const kurz of uebersprungen) {
  console.log(`Ausnahme:    ${kurz} — ${AUSNAHMEN.get(kurz)}`);
}

if (funde.length) {
  console.error(`\n${funde.length} handgesetzte(r) Radius:`);
  for (const f of funde) console.error(`  - ${f.ort}  ${f.eigenschaft}: ${f.wert}`);
  console.error(
    '\nRadien gehören auf die M3-Skala: --mat-sys-corner-extra-small (4) | '
    + 'small (8) | medium (12) | large (16) | extra-large (28) | full (9999). '
    + 'Erlaubt bleiben 0, 50% und inherit — sie sagen eine Form, keine Größe.',
  );
  process.exit(1);
}
console.log('\nJeder Radius kommt aus der M3-Skala.');
