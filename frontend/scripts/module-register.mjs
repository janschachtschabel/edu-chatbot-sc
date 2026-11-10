#!/usr/bin/env node
/**
 * Erzeugt aus den Modul-Ordnern das Register der UI-Module (Paket U1-a).
 *
 * Quelle: projects/ui-module/src/ui-<name>/manifest.json + ui-<name>.component.ts.
 * Ausgaben (alle erzeugt, nie von Hand ändern):
 *   - projects/ui-module/src/register.generated.ts — statische Importe der Komponenten und je
 *     Modul nur die Laufzeit-Felder des Manifests (Name, Version, Art, Titel, Fähigkeiten,
 *     Darstellung). Statisch, weil das Widget eine einzige Datei ist (Bündel-Regel).
 *     Ausnahme (Paket U3-0): ein Modul mit `laden: "bei_bedarf"` hat statt der Komponente ein
 *     rahmenloses Custom Element `ui-<name>.element.ts`, das ein eigenes Bündel wird
 *     (`scripts/build-nachlade-module.mjs`); im Register steht dafür der gemeinsame Platzhalter
 *     und der Element-Name `boerdi-ui-<name>`.
 *   - backend/src/boerdi/ui_module/manifeste.json — alle Manifeste vollständig; das Backend
 *     baut daraus die Werkzeugbeschreibungen und prüft gegen das Schema.
 *   - backend/src/boerdi/ui_module/manifest.schema.json — Kopie des Vertrags-Schemas.
 *   - ui-<name>/ui-<name>.stil.generated.ts (Paket BU-2) — nur für nachgeladene Module mit
 *     `ui-<name>.element.scss`: die SCSS mit dem dart-sass des Projekts übersetzt (komprimiert)
 *     als `STIL`. So teilen Element und Komponenten dieselben SCSS-Bausteine (`_baum/`), und das
 *     Element-Bündel (esbuild, ohne SCSS) setzt den fertigen Text in seinen Shadow Root.
 *
 * Hier wird nur der Aufbau geprüft (Pflichtfelder, Name = Ordner, Komponente vorhanden); die
 * volle Schema-Prüfung samt Beispielen macht das Backend (tests/test_ui_modul_katalog.py).
 *
 * Aufruf: node scripts/module-register.mjs [--pruefen]
 *   --pruefen schreibt nichts und endet mit 1, wenn eine Ausgabe veraltet ist (CI).
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { compile } from 'sass';

const PFLICHT = ['name', 'version', 'art', 'titel', 'beschreibung', 'eingabe', 'textfassung', 'beispiele'];
const LAUFZEIT = ['name', 'version', 'art', 'titel', 'faehigkeiten', 'darstellung'];

/** `ui-link-box` → `UiLinkBox` */
export function pascal(ordner) {
  return ordner.split('-').map((t) => t.charAt(0).toUpperCase() + t.slice(1)).join('');
}

function leseModule(quelle) {
  const ordner = readdirSync(quelle, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith('ui-'))
    .map((e) => e.name);
  const module = [];
  for (const name of ordner) {
    const pfad = join(quelle, name, 'manifest.json');
    if (!existsSync(pfad)) throw new Error(`${name}: manifest.json fehlt`);
    // Manche Editoren unter Windows schreiben ein BOM; JSON.parse lehnt es ab.
    const manifest = JSON.parse(readFileSync(pfad, 'utf8').replace(/^\uFEFF/, ''));
    const fehlend = PFLICHT.filter((k) => !(k in manifest));
    if (fehlend.length) throw new Error(`${name}/manifest.json: Pflichtfelder fehlen: ${fehlend.join(', ')}`);
    if (manifest.name !== name.replace(/-/g, '_')) {
      throw new Error(`${name}/manifest.json: name „${manifest.name}“ passt nicht zum Ordner ${name}`);
    }
    const datei = istNachgeladen(manifest) ? `${name}.element.ts` : `${name}.component.ts`;
    if (!existsSync(join(quelle, name, datei))) throw new Error(`${name}: ${datei} fehlt`);
    module.push({ ordner: name, manifest });
  }
  // Codepunkte statt localeCompare: gleiche Reihenfolge auf jeder Maschine und wie Pythons sorted().
  return module.sort((a, b) => (a.manifest.name < b.manifest.name ? -1 : a.manifest.name > b.manifest.name ? 1 : 0));
}

/** Paket U3-0: wird das Modul erst bei Bedarf als eigenes Bündel geladen? */
export function istNachgeladen(manifest) {
  return manifest.laden === 'bei_bedarf';
}

/** Name des Custom Elements eines nachgeladenen Moduls: `ui-upload` → `boerdi-ui-upload`. */
export function elementName(ordner) {
  return `boerdi-${ordner}`;
}

function registerText(module) {
  const sofort = module.filter(({ manifest }) => !istNachgeladen(manifest));
  const importe = sofort.map(({ ordner }) => `import { ${pascal(ordner)} } from './${ordner}/${ordner}.component';`);
  if (sofort.length < module.length) {
    importe.unshift("import { NachladePlatzhalter } from './_nachladen/nachlade-platzhalter.component';");
  }
  const eintraege = module.map(({ ordner, manifest }) => {
    const laufzeit = Object.fromEntries(LAUFZEIT.filter((k) => k in manifest).map((k) => [k, manifest[k]]));
    const ziel = istNachgeladen(manifest)
      ? `komponente: NachladePlatzhalter, element: '${elementName(ordner)}'`
      : `komponente: ${pascal(ordner)}`;
    return `  ${manifest.name}: { manifest: ${JSON.stringify(laufzeit)}, ${ziel} },`;
  });
  return [
    '// ERZEUGT von `npm run module:register` — nicht von Hand ändern.',
    '// Quelle: die Modul-Ordner unter projects/ui-module/src/ui-*/ (manifest.json + Komponente).',
    "import type { ModulRegister } from './_vertrag/register';",
    ...importe,
    '',
    module.length ? `export const MODUL_REGISTER: ModulRegister = {\n${eintraege.join('\n')}\n};` : 'export const MODUL_REGISTER: ModulRegister = {};',
    '',
  ].join('\n');
}

/** U3-1a: Quellen der nachgeladenen Elemente — NUR fürs Studio (Vorschau ohne Bündel). Das Widget
 *  importiert diese Datei nie: jeder `import()` darin würde dort ein zweites Bündel erzeugen. */
function quellenText(module) {
  const zeilen = module.filter(({ manifest }) => istNachgeladen(manifest))
    .map(({ ordner, manifest }) => `  ${manifest.name}: () => import('./${ordner}/${ordner}.element'),`);
  const typ = 'Readonly<Record<string, () => Promise<unknown>>>';
  return [
    '// ERZEUGT von `npm run module:register` — nicht von Hand ändern. Nur fürs Studio importieren,',
    '// nie im Widget (jeder import() hier würde dort ein zweites Bündel erzeugen).',
    '',
    zeilen.length
      ? `export const NACHLADE_QUELLEN: ${typ} = {\n${zeilen.join('\n')}\n};`
      : `export const NACHLADE_QUELLEN: ${typ} = {};`,
    '',
  ].join('\n');
}

/** BU-2: je nachgeladenem Modul (BU-3: und je Widget-Teil der zweiten Quelle) mit
 *  `ui-<name>.element.scss` die erzeugte Stil-Datei. `ordner` sind `[wurzel, ordner]`. */
function stilAusgaben(ordner) {
  return ordner.flatMap(([wurzel, name]) => {
    const scss = join(wurzel, name, `${name}.element.scss`);
    if (!existsSync(scss)) return [];
    // `charset: false`: sonst setzt dart-sass bei Nicht-ASCII ein BOM davor — im `<style>` Teil des
    // ersten Selektors (Review BU-2, Befund 3).
    const css = compile(scss, { style: 'compressed', charset: false }).css;
    return [[join(wurzel, name, `${name}.stil.generated.ts`), [
      '// ERZEUGT von `npm run module:register` aus ' + `${name}.element.scss` + ' — nicht von Hand ändern.',
      `export const STIL = ${JSON.stringify(css)};`,
      '',
    ].join('\n')]];
  });
}

/** BU-3: Widget-Teile der zweiten Quelle — `ui-*`-Ordner mit Element-Datei, ohne Manifest; sortiert.
 *  Auch vom Bau-Skript genutzt (`build-nachlade-module.mjs`). */
export function widgetTeile(teile) {
  if (!teile || !existsSync(teile)) return [];
  return readdirSync(teile, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith('ui-') && existsSync(join(teile, e.name, `${e.name}.element.ts`)))
    .map((e) => e.name)
    .sort();
}

/** Erzeugt (oder prüft mit `pruefen`) die Ausgaben; gibt die veralteten Dateinamen zurück. `teile`
 *  (BU-3) ist die zweite Quelle der Widget-Teile — sie bekommen nur ihren Stil, nie einen Eintrag. */
export function erzeuge({ quelle, backend, teile = null, pruefen = false }) {
  const module = leseModule(quelle);
  const nachgeladen = module.filter(({ manifest }) => istNachgeladen(manifest)).map(({ ordner }) => [quelle, ordner]);
  const ausgaben = [
    [join(quelle, 'register.generated.ts'), registerText(module)],
    [join(quelle, 'nachlade-quellen.generated.ts'), quellenText(module)],
    [join(backend, 'manifeste.json'), JSON.stringify(module.map((m) => m.manifest), null, 2) + '\n'],
    [join(backend, 'manifest.schema.json'), readFileSync(join(quelle, '_vertrag', 'manifest.schema.json'), 'utf8')],
    ...stilAusgaben([...nachgeladen, ...widgetTeile(teile).map((name) => [teile, name])]),
  ];
  const veraltet = [];
  for (const [pfad, text] of ausgaben) {
    const alt = existsSync(pfad) ? readFileSync(pfad, 'utf8').replace(/\r\n/g, '\n') : null;
    if (alt === text.replace(/\r\n/g, '\n')) continue;
    veraltet.push(pfad.split(/[\\/]/).pop());
    if (!pruefen) writeFileSync(pfad, text);
  }
  return { veraltet, anzahl: module.length };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const pruefen = process.argv.includes('--pruefen');
  const { veraltet, anzahl } = erzeuge({
    quelle: join(frontend, 'projects', 'ui-module', 'src'),
    backend: join(frontend, '..', 'backend', 'src', 'boerdi', 'ui_module'),
    teile: join(frontend, 'projects', 'ui', 'src', 'nachgeladen'),
    pruefen,
  });
  console.log(`UI-Module: ${anzahl}`);
  if (pruefen && veraltet.length) {
    console.error(`Veraltet: ${veraltet.join(', ')} — npm run module:register ausführen.`);
    process.exit(1);
  }
  console.log(veraltet.length ? `geschrieben: ${veraltet.join(', ')}` : 'alles aktuell');
}
