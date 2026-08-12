#!/usr/bin/env node
/**
 * CI gate against `var(--token)` reads of a custom property nobody defines
 * (rubric item B1).
 *
 * Why this needs a gate at all: an undefined custom property does not fall back
 * to anything and does not warn — the *whole declaration* becomes invalid and is
 * dropped. `background: var(--st-surface-variant)` on an undefined name renders
 * as transparent, `outline: 2px solid var(--st-focus)` renders as no outline.
 * Nothing in the build, the linter or the test suite notices, and a screenshot
 * only shows it if you happen to know what the surface should look like.
 *
 * The same class was found by hand three times: `--st-surface-variant` read in
 * nine stylesheets and never defined (9-5b), `--st-mono` and `--st-radius-sm`
 * (9-5c). Every one of those was invisible until someone diffed the two lists.
 *
 * Usage: node scripts/check-tokens.mjs [rootDir]
 * Without an argument it scans `projects/`. The optional path exists so the gate
 * itself can be pointed at a fixture — the same seam `check-widget-budget.mjs`
 * uses for its oversized-bundle fixture.
 *
 * **Known limit, deliberate:** definitions are pooled across the whole tree
 * rather than resolved per `@use` graph, so this catches "defined nowhere" (the
 * bug class above) but not "defined only in a stylesheet this one never loads".
 * Modelling the real cascade would mean resolving Sass imports AND the Shadow
 * DOM boundary; with four files defining tokens in total, that is not worth the
 * machinery.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const DEFAULT_ROOT = 'projects';
const EXTENSIONS = new Set(['.scss', '.css', '.html', '.ts']);
const SKIP_DIRS = new Set(['node_modules', 'dist', '.angular']);

/** `--name:` — a declaration. `var(--name)` has no colon, so it cannot match. */
const DEFINITION = /(--[a-z0-9-]+)\s*:/gi;
const USAGE = /var\(\s*(--[a-z0-9-]+)/gi;

const root = resolve(process.argv[2] ?? DEFAULT_ROOT);

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) yield* walk(path);
    else if (EXTENSIONS.has(entry.slice(entry.lastIndexOf('.')))) yield path;
  }
}

const defined = new Set();
/** token → `file:line` list, in scan order. */
const used = new Map();

let files = 0;
for (const path of walk(root)) {
  files += 1;
  const lines = readFileSync(path, 'utf8').split('\n');
  lines.forEach((line, index) => {
    for (const [, name] of line.matchAll(DEFINITION)) defined.add(name);
    for (const [, name] of line.matchAll(USAGE)) {
      const where = `${relative(root, path).replace(/\\/g, '/')}:${index + 1}`;
      const seen = used.get(name);
      if (seen) seen.push(where);
      else used.set(name, [where]);
    }
  });
}

// Angular Materials `--mat-sys-*`/`--mat-*`-Token stehen in KEINER Projektdatei
// — `mat.theme()` erzeugt sie beim Kompilieren. Statt sie per Präfix pauschal
// durchzuwinken (ein Tippfehler bliebe unentdeckt), wird das Widget-Theme hier
// wirklich kompiliert und seine Deklarationen eingesammelt.
async function materialTokens() {
  const eintrag = resolve('projects/widget/src/app/widget/widget.component.scss');
  const sass = await import('sass');
  const css = sass.compile(eintrag, {
    loadPaths: [
      resolve('projects/ui/src'),
      resolve('projects/widget/src/app/widget'),
      resolve('node_modules'),
    ],
  }).css;
  const namen = new Set();
  for (const [, name] of css.matchAll(DEFINITION)) namen.add(name);
  return namen;
}

try {
  const vomTheme = await materialTokens();
  for (const name of vomTheme) defined.add(name);
  console.log(`aus mat.theme: ${vomTheme.size}`);
} catch (fehler) {
  console.error(
    'Das Widget-Theme ließ sich nicht kompilieren — `--mat-sys-*` kann nicht '
    + 'geprüft werden:\n  ' + fehler.message,
  );
  process.exit(1);
}

const missing = [...used.entries()].filter(([name]) => !defined.has(name));

console.log(`Wurzel:      ${root}`);
console.log(`Dateien:     ${files}`);
console.log(`definiert:   ${defined.size}`);
console.log(`gelesen:     ${used.size}`);

if (missing.length) {
  console.error(`\n${missing.length} gelesene(s) Token ohne Definition:`);
  for (const [name, places] of missing) {
    console.error(`  - ${name}  (${places.length}×)`);
    for (const place of places) console.error(`      ${place}`);
  }
  console.error('\nEin undefiniertes var() macht die ganze Deklaration ungültig —'
    + ' Hintergrund transparent, Rahmen weg, ohne Fehlermeldung.');
  process.exit(1);
}
console.log('\nJedes gelesene Token ist definiert.');
