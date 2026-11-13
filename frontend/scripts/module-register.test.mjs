// Tests für scripts/module-register.mjs (Paket U1-a). Lauf: node --test scripts/module-register.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { erzeuge, pascal } from './module-register.mjs';

function manifest(name, mehr = {}) {
  return {
    name, version: 1, art: 'anzeigen', titel: { de: 'Probe' },
    beschreibung: 'Zeigt eine Probe für die Tests an.',
    eingabe: { type: 'object', properties: { text: { type: 'string' } } },
    textfassung: { vorlage: 'markdown', feld: 'text' },
    beispiele: [{ titel: 'Kurz', daten: { text: 'Hallo' } }],
    faehigkeiten: ['herunterladen'],
    ...mehr,
  };
}

function aufbau(module) {
  const wurzel = mkdtempSync(join(tmpdir(), 'modreg-'));
  const quelle = join(wurzel, 'src');
  const backend = join(wurzel, 'backend');
  mkdirSync(join(quelle, '_vertrag'), { recursive: true });
  mkdirSync(backend, { recursive: true });
  writeFileSync(join(quelle, '_vertrag', 'manifest.schema.json'), '{"title":"Schema"}');
  for (const [ordner, m, mitKomponente = true] of module) {
    mkdirSync(join(quelle, ordner));
    writeFileSync(join(quelle, ordner, 'manifest.json'), JSON.stringify(m));
    if (mitKomponente) writeFileSync(join(quelle, ordner, `${ordner}.component.ts`), `export class ${pascal(ordner)} {}`);
  }
  return { quelle, backend };
}

test('pascal macht aus dem Ordnernamen den Klassennamen', () => {
  assert.equal(pascal('ui-inhaltsrahmen'), 'UiInhaltsrahmen');
  assert.equal(pascal('ui-link-box'), 'UiLinkBox');
});

test('erzeugt Register, Manifeste und Schema-Kopie, sortiert nach Name', () => {
  const { quelle, backend } = aufbau([
    ['ui-zeta', manifest('ui_zeta')],
    ['ui-alpha', manifest('ui_alpha')],
  ]);
  erzeuge({ quelle, backend });
  const register = readFileSync(join(quelle, 'register.generated.ts'), 'utf8');
  assert.match(register, /import \{ UiAlpha \} from '\.\/ui-alpha\/ui-alpha\.component';/);
  assert.ok(register.indexOf('ui_alpha') < register.indexOf('ui_zeta'));
  // im Bündel nur die Laufzeit-Felder, keine Beschreibung, keine Beispiele
  assert.doesNotMatch(register, /beschreibung|beispiele|eingabe/);
  const manifeste = JSON.parse(readFileSync(join(backend, 'manifeste.json'), 'utf8'));
  assert.deepEqual(manifeste.map((m) => m.name), ['ui_alpha', 'ui_zeta']);
  assert.equal(manifeste[0].beschreibung, 'Zeigt eine Probe für die Tests an.');
  assert.equal(readFileSync(join(backend, 'manifest.schema.json'), 'utf8'), '{"title":"Schema"}');
});

test('pruefen meldet veraltete Ausgaben, ohne zu schreiben', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_alpha')]]);
  assert.deepEqual(erzeuge({ quelle, backend, pruefen: true }).veraltet.sort(),
    ['manifest.schema.json', 'manifeste.json', 'nachlade-quellen.generated.ts', 'register.generated.ts']);
  erzeuge({ quelle, backend });
  assert.deepEqual(erzeuge({ quelle, backend, pruefen: true }).veraltet, []);
});

test('Name muss zum Ordner passen', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_beta')]]);
  assert.throws(() => erzeuge({ quelle, backend }), /ui-alpha.*ui_beta|ui_beta.*ui-alpha/);
});

test('ohne Komponente kein Eintrag', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_alpha'), false]]);
  assert.throws(() => erzeuge({ quelle, backend }), /ui-alpha\.component\.ts/);
});

test('Pflichtfelder fehlen', () => {
  const ohne = manifest('ui_alpha');
  delete ohne.eingabe;
  const { quelle, backend } = aufbau([['ui-alpha', ohne]]);
  assert.throws(() => erzeuge({ quelle, backend }), /eingabe/);
});

test('module:neu legt ein Gerüst an, das das Register annimmt', async () => {
  const { geruest } = await import('./module-neu.mjs');
  const { quelle, backend } = aufbau([]);
  const { ordner, register } = geruest({ quelle, backend, kurzname: 'probe-box', abfragen: true });
  assert.equal(ordner, 'ui-probe-box');
  assert.equal(register.anzahl, 1);
  const m = JSON.parse(readFileSync(join(quelle, ordner, 'manifest.json'), 'utf8'));
  assert.equal(m.name, 'ui_probe_box');
  assert.equal(m.art, 'abfragen');
  assert.ok(m.antwort && m.beispiele[0].antwort);
  assert.match(readFileSync(join(quelle, ordner, `${ordner}.component.ts`), 'utf8'), /export class UiProbeBox/);
  // Ab U1-b: die Spec des Gerüsts rendert jedes Beispiel aus dem Manifest, mit vollem Kontext.
  const spec = readFileSync(join(quelle, ordner, `${ordner}.component.spec.ts`), 'utf8');
  assert.match(spec, /import manifest from '\.\/manifest\.json';/);
  assert.match(spec, /for \(const beispiel of manifest\.beispiele\)/);
  assert.match(spec, /schriftSkala/);
  assert.throws(() => geruest({ quelle, backend, kurzname: 'probe-box' }), /gibt es schon/);
  assert.throws(() => geruest({ quelle, backend, kurzname: 'Ui_X' }), /Kleinbuchstaben/);
});

test('R3-g: module:neu trägt das Manifest in die Vorschau-Spec des Studios ein', async () => {
  const { geruest } = await import('./module-neu.mjs');
  const { quelle, backend } = aufbau([]);
  const vorschau = join(quelle, 'vorschau.spec.ts');
  writeFileSync(vorschau, [
    "import alpha from '@boerdi/ui-module/ui-alpha/manifest.json';",
    "import { MODUL_REGISTER } from '@boerdi/ui-module/register.generated';",
    '',
    'const MANIFESTE = [alpha] as unknown as UiModulManifest[];',
    '',
  ].join('\n'));
  geruest({ quelle, backend, kurzname: 'probe-box', vorschauSpec: vorschau });
  const text = readFileSync(vorschau, 'utf8');
  assert.match(text, /import probeBox from '@boerdi\/ui-module\/ui-probe-box\/manifest\.json';\nimport \{ MODUL_REGISTER \}/);
  assert.match(text, /const MANIFESTE = \[alpha, probeBox\] as unknown/);
});

test('Querschnitts-Review, NIT 11: ein Name, den die Spec schon trägt, bekommt ein Präfix', async () => {
  const { inVorschauEintragen } = await import('./module-neu.mjs');
  const { quelle } = aufbau([]);
  const vorschau = join(quelle, 'vorschau2.spec.ts');
  writeFileSync(vorschau, [
    "import { MODUL_REGISTER } from '@boerdi/ui-module/register.generated';",
    'const MANIFESTE = [alpha] as unknown as UiModulManifest[];',
    'function text(e: Element | null): string { return String(e); }',
  ].join('\n'));
  assert.equal(inVorschauEintragen(vorschau, 'ui-text'), true);
  const neu = readFileSync(vorschau, 'utf8');
  assert.match(neu, /import manifestText from '@boerdi\/ui-module\/ui-text\/manifest\.json';/);
  assert.match(neu, /\[alpha, manifestText\]/);
});

test('sortiert nach Codepunkten, unabhängig von der Sprachumgebung', () => {
  // localeCompare stellt `_` vor Ziffern, Codepunkte (und Pythons sorted) umgekehrt.
  const { quelle, backend } = aufbau([
    ['ui-ab-c', manifest('ui_ab_c')],
    ['ui-ab1', manifest('ui_ab1')],
  ]);
  erzeuge({ quelle, backend });
  const manifeste = JSON.parse(readFileSync(join(backend, 'manifeste.json'), 'utf8'));
  assert.deepEqual(manifeste.map((m) => m.name), ['ui_ab1', 'ui_ab_c']);
});

test('ein Manifest mit BOM am Anfang wird gelesen', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_alpha')]]);
  const pfad = join(quelle, 'ui-alpha', 'manifest.json');
  writeFileSync(pfad, '\uFEFF' + readFileSync(pfad, 'utf8'));
  erzeuge({ quelle, backend });
  const manifeste = JSON.parse(readFileSync(join(backend, 'manifeste.json'), 'utf8'));
  assert.deepEqual(manifeste.map((m) => m.name), ['ui_alpha']);
});

test('ein gemeinsamer Ordner ohne ui-Präfix (_baum, Paket U2) ist kein Modul', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_alpha')]]);
  mkdirSync(join(quelle, '_baum'));
  writeFileSync(join(quelle, '_baum', 'baum-tasten.ts'), 'export const x = 1;');
  erzeuge({ quelle, backend });
  const manifeste = JSON.parse(readFileSync(join(backend, 'manifeste.json'), 'utf8'));
  assert.deepEqual(manifeste.map((m) => m.name), ['ui_alpha']);
  assert.doesNotMatch(readFileSync(join(quelle, 'register.generated.ts'), 'utf8'), /_baum/);
});

// Paket U3-0: ein selten gebrauchtes Modul wird bei Bedarf nachgeladen. Es hat statt der
// Angular-Komponente ein rahmenloses Custom Element; im Register steht der gemeinsame Platzhalter.
test('ein Modul mit laden: bei_bedarf bekommt den Platzhalter und seinen Element-Namen', () => {
  const { quelle, backend } = aufbau([
    ['ui-alpha', manifest('ui_alpha')],
    ['ui-probe', manifest('ui_probe', { laden: 'bei_bedarf' }), false],
  ]);
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), 'export {};');
  erzeuge({ quelle, backend });
  const register = readFileSync(join(quelle, 'register.generated.ts'), 'utf8');
  assert.match(register, /import \{ NachladePlatzhalter \} from '\.\/_nachladen\/nachlade-platzhalter\.component';/);
  assert.match(register, /ui_probe: \{ manifest: .*, komponente: NachladePlatzhalter, element: 'boerdi-ui-probe' \},/);
  // nichts aus dem Element-Quelltext im Haupt-Bündel
  assert.doesNotMatch(register, /ui-probe\.element/);
  assert.doesNotMatch(register, /UiProbe\b/);
});

test('ein nachgeladenes Modul ohne Element-Datei wird abgewiesen', () => {
  const { quelle, backend } = aufbau([['ui-probe', manifest('ui_probe', { laden: 'bei_bedarf' }), false]]);
  assert.throws(() => erzeuge({ quelle, backend }), /ui-probe\.element\.ts/);
});

test('ohne nachgeladene Module kein Import des Platzhalters', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_alpha', { laden: 'sofort' })]]);
  erzeuge({ quelle, backend });
  assert.doesNotMatch(readFileSync(join(quelle, 'register.generated.ts'), 'utf8'), /NachladePlatzhalter/);
});

test('U3-1a: die Element-Quellen der nachgeladenen Module stehen in einer eigenen Datei (nur fürs Studio)', () => {
  const { quelle, backend } = aufbau([
    ['ui-alpha', manifest('ui_alpha')],
    ['ui-probe', manifest('ui_probe', { laden: 'bei_bedarf' }), false],
  ]);
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), 'export {};');
  erzeuge({ quelle, backend });
  const quellen = readFileSync(join(quelle, 'nachlade-quellen.generated.ts'), 'utf8');
  assert.match(quellen, /ui_probe: \(\) => import\('\.\/ui-probe\/ui-probe\.element'\),/);
  assert.doesNotMatch(quellen, /ui_alpha/);
  // das Register selbst importiert keine Element-Quelle (sonst landete sie im Widget-Bündel)
  assert.doesNotMatch(readFileSync(join(quelle, 'register.generated.ts'), 'utf8'), /import\(/);
});

test('BU-2: die SCSS eines nachgeladenen Moduls wird zu einer erzeugten Stil-Datei (samt @use)', () => {
  const { quelle, backend } = aufbau([['ui-probe', manifest('ui_probe', { laden: 'bei_bedarf' }), false]]);
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), 'export {};');
  mkdirSync(join(quelle, '_teil'));
  writeFileSync(join(quelle, '_teil', '_farbe.scss'), '@mixin rand($p) { .#{$p} { border: 1px solid red; } }');
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.scss'),
    "@use '../_teil/farbe';\n:host { display: block; }\n@include farbe.rand('p');\n.p__x { a { color: blue; } }");
  erzeuge({ quelle, backend });
  const stil = readFileSync(join(quelle, 'ui-probe', 'ui-probe.stil.generated.ts'), 'utf8');
  assert.match(stil, /^\/\/ ERZEUGT von `npm run module:register`/);
  const css = JSON.parse(stil.match(/export const STIL = (".*");/)[1]);
  assert.equal(css, ':host{display:block}.p{border:1px solid red}.p__x a{color:blue}');
  // ein veralteter Stil fällt der CI-Prüfung auf
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.scss'), ':host { display: grid; }');
  assert.deepEqual(erzeuge({ quelle, backend, pruefen: true }).veraltet, ['ui-probe.stil.generated.ts']);
});

test('BU-2: ohne SCSS keine Stil-Datei; ein sofort geladenes Modul bekommt nie eine', () => {
  const { quelle, backend } = aufbau([
    ['ui-alpha', manifest('ui_alpha')],
    ['ui-probe', manifest('ui_probe', { laden: 'bei_bedarf' }), false],
  ]);
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), 'export {};');
  writeFileSync(join(quelle, 'ui-alpha', 'ui-alpha.element.scss'), ':host { display: block; }');
  erzeuge({ quelle, backend });
  assert.equal(existsSync(join(quelle, 'ui-probe', 'ui-probe.stil.generated.ts')), false);
  assert.equal(existsSync(join(quelle, 'ui-alpha', 'ui-alpha.stil.generated.ts')), false);
});

test('Review BU-2, Befund 3: Nicht-ASCII im Stil setzt kein BOM vor die erste Regel', () => {
  const { quelle, backend } = aufbau([['ui-probe', manifest('ui_probe', { laden: 'bei_bedarf' }), false]]);
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), 'export {};');
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.scss'), ':host { display: block; }\n.p::after { content: "…"; }');
  erzeuge({ quelle, backend });
  const stil = readFileSync(join(quelle, 'ui-probe', 'ui-probe.stil.generated.ts'), 'utf8');
  const css = JSON.parse(stil.match(/export const STIL = (".*");/)[1]);
  assert.ok(css.startsWith(':host{display:block}'), JSON.stringify(css.slice(0, 12)));
});

test('BU-3: auch Widget-Teile (zweite Quelle, ohne Manifest) bekommen ihren Stil — und nie ins Register', () => {
  const { quelle, backend } = aufbau([['ui-alpha', manifest('ui_alpha')]]);
  const teile = join(quelle, '..', 'teile');
  mkdirSync(join(teile, 'ui-diagnose'), { recursive: true });
  writeFileSync(join(teile, 'ui-diagnose', 'ui-diagnose.element.ts'), 'export {};');
  writeFileSync(join(teile, 'ui-diagnose', 'ui-diagnose.element.scss'), '.d { a { color: red; } }');
  erzeuge({ quelle, backend, teile });
  const stil = readFileSync(join(teile, 'ui-diagnose', 'ui-diagnose.stil.generated.ts'), 'utf8');
  assert.equal(JSON.parse(stil.match(/export const STIL = (".*");/)[1]), '.d a{color:red}');
  assert.doesNotMatch(readFileSync(join(quelle, 'register.generated.ts'), 'utf8'), /diagnose/);
  writeFileSync(join(teile, 'ui-diagnose', 'ui-diagnose.element.scss'), '.d { color: blue; }');
  assert.deepEqual(erzeuge({ quelle, backend, teile, pruefen: true }).veraltet, ['ui-diagnose.stil.generated.ts']);
});
