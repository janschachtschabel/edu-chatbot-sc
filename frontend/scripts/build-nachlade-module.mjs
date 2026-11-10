#!/usr/bin/env node
/**
 * Baut die Bündel der nachgeladenen UI-Module (Paket U3-0).
 *
 * Ein Modul mit `laden: "bei_bedarf"` (manifest.json) ist ein rahmenloses Custom Element in
 * `ui-<name>/ui-<name>.element.ts`. Jedes wird mit esbuild zu einer eigenen Datei gebaut:
 *   - `format: iife` — ein klassisches `<script>` ohne `import`/`export`, wie das Widget selbst,
 *     damit jede Einbettung, die das Widget lädt, auch das Modul laden kann;
 *   - CSS-Dateien als Text (das Element setzt sie in seinen Shadow Root);
 *   - Dateiname mit Inhalts-Hash (`ui-<name>.<sha256-8>.js`), weil das Backend sie unveränderlich
 *     ausliefert; dazu der SRI-Wert (`sha384`).
 * Angular-Pakete sind verboten: sie würden das Framework ein zweites Mal ausliefern.
 *
 * Paket BU-3: eine zweite Quelle für **Widget-Teile ohne Manifest** (`projects/ui/src/nachgeladen/`,
 * je `ui-<name>/ui-<name>.element.ts`, etwa das Debug-Panel) — kein KI-Werkzeug, nicht im Register,
 * aber derselbe Bau, derselbe Index und derselbe Pfad `/widget/module/`. Ein Name darf nur einmal
 * vorkommen.
 *
 * Ausgaben: die Bündel in `dist/widget-module/` (alte werden entfernt) und der Index
 * `projects/ui/src/ui-bloecke/nachlade-index.build.ts` (nicht eingecheckt), den der Widget-Build per
 * `fileReplacements` statt des leeren `nachlade-index.ts` einbindet.
 *
 * Aufruf: node scripts/build-nachlade-module.mjs   (läuft in `npm run build:widget` zuerst)
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { build } from 'esbuild';

import { erzeuge, widgetTeile } from './module-register.mjs';

/** Gleiche Regel wie `module-register.mjs`: nur `ui-*`-Ordner mit `laden: "bei_bedarf"`. */
function nachgeladeneModule(quelle) {
  return readdirSync(quelle, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith('ui-'))
    .map((e) => e.name)
    .filter((ordner) => {
      const pfad = join(quelle, ordner, 'manifest.json');
      if (!existsSync(pfad)) return false;
      const manifest = JSON.parse(readFileSync(pfad, 'utf8').replace(/^\uFEFF/, ''));
      return manifest.laden === 'bei_bedarf';
    })
    .sort();
}

const OHNE_ANGULAR = {
  name: 'ohne-angular',
  setup(b) {
    b.onResolve({ filter: /^@angular\// }, (args) => ({
      errors: [{ text: `${args.path}: nachgeladene Module bleiben rahmenlos (kein @angular-Import)` }],
    }));
  },
};

async function baueModul(quelle, ordner) {
  const ergebnis = await build({
    entryPoints: [join(quelle, ordner, `${ordner}.element.ts`)],
    bundle: true,
    write: false,
    format: 'iife',
    platform: 'browser',
    target: 'es2022',
    minify: true,
    legalComments: 'none',
    charset: 'utf8',
    loader: { '.css': 'text' },
    plugins: [OHNE_ANGULAR],
    logLevel: 'silent',
  });
  return Buffer.from(ergebnis.outputFiles[0].contents);
}

function indexText(eintraege) {
  const zeilen = Object.entries(eintraege)
    .map(([name, e]) => `  ${name}: { datei: '${e.datei}', integritaet: '${e.integritaet}' },`);
  return [
    '// ERZEUGT von scripts/build-nachlade-module.mjs beim Widget-Build — nicht einchecken, nicht von Hand ändern.',
    "import type { NachladeIndex } from './nachladen';",
    '',
    zeilen.length ? `export const NACHLADE_INDEX: NachladeIndex = {\n${zeilen.join('\n')}\n};` : 'export const NACHLADE_INDEX: NachladeIndex = {};',
    '',
  ].join('\n');
}

/** Baut alle nachgeladenen Module; gibt Name → {datei, integritaet} zurück. */
export async function baue({ quelle, teile = null, ausgabe, index }) {
  const eintraege = {};
  const dateien = new Map();
  const module = nachgeladeneModule(quelle).map((ordner) => [quelle, ordner]);
  const zweite = widgetTeile(teile).map((ordner) => [teile, ordner]);
  const doppelt = zweite.filter(([, o]) => module.some(([, m]) => m === o)).map(([, o]) => o);
  if (doppelt.length) throw new Error(`Name als Modul und als Widget-Teil: ${doppelt.join(', ')}`);
  for (const [wurzel, ordner] of [...module, ...zweite]) {
    const bytes = await baueModul(wurzel, ordner);
    const datei = `${ordner}.${createHash('sha256').update(bytes).digest('hex').slice(0, 8)}.js`;
    eintraege[ordner.replace(/-/g, '_')] = {
      datei, integritaet: 'sha384-' + createHash('sha384').update(bytes).digest('base64'),
    };
    dateien.set(datei, bytes);
  }
  // Erst bauen, dann ersetzen: scheitert ein Modul, bleibt der alte Stand unberührt.
  rmSync(ausgabe, { recursive: true, force: true });
  mkdirSync(ausgabe, { recursive: true });
  for (const [datei, bytes] of dateien) writeFileSync(join(ausgabe, datei), bytes);
  writeFileSync(index, indexText(eintraege));
  return eintraege;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  // Review BU-2, Befund 8: ein erzeugter Stil, der nicht mehr zur SCSS passt, ginge sonst still alt
  // ins Bündel — die CI prüft es, ein lokaler Bau bisher nicht.
  const { veraltet } = erzeuge({
    quelle: join(frontend, 'projects', 'ui-module', 'src'),
    backend: join(frontend, '..', 'backend', 'src', 'boerdi', 'ui_module'),
    teile: join(frontend, 'projects', 'ui', 'src', 'nachgeladen'),
    pruefen: true,
  });
  const stile = veraltet.filter((name) => name.endsWith('.stil.generated.ts'));
  if (stile.length) {
    console.error(`Veralteter Stil: ${stile.join(', ')} — erst npm run module:register ausführen.`);
    process.exit(1);
  }
  const eintraege = await baue({
    quelle: join(frontend, 'projects', 'ui-module', 'src'),
    teile: join(frontend, 'projects', 'ui', 'src', 'nachgeladen'),
    ausgabe: join(frontend, 'dist', 'widget-module'),
    index: join(frontend, 'projects', 'ui', 'src', 'ui-bloecke', 'nachlade-index.build.ts'),
  });
  const namen = Object.entries(eintraege).map(([n, e]) => `${n} → ${e.datei}`);
  console.log(`Nachgeladene Module: ${namen.length}${namen.length ? '\n  ' + namen.join('\n  ') : ''}`);
}
