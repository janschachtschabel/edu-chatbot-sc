// Tests für scripts/module-register.mjs (Paket U1-a). Lauf: node --test scripts/module-register.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
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
    ['manifest.schema.json', 'manifeste.json', 'register.generated.ts']);
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
