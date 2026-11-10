// Tests für scripts/build-nachlade-module.mjs (Paket U3-0). Lauf: node --test scripts/build-nachlade-module.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { baue } from './build-nachlade-module.mjs';

function manifest(name, laden) {
  return { name, version: 1, art: 'anzeigen', titel: { de: 'Probe' }, ...(laden ? { laden } : {}) };
}

function aufbau() {
  const wurzel = mkdtempSync(join(tmpdir(), 'nachladen-'));
  const quelle = join(wurzel, 'src');
  mkdirSync(join(quelle, 'ui-probe'), { recursive: true });
  writeFileSync(join(quelle, 'ui-probe', 'manifest.json'), JSON.stringify(manifest('ui_probe', 'bei_bedarf')));
  writeFileSync(join(quelle, 'ui-probe', 'probe.css'), '.probe { color: var(--mat-sys-primary); }');
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), [
    "import css from './probe.css';",
    'class Probe extends HTMLElement { stil = css as string; }',
    "if (!customElements.get('boerdi-ui-probe')) customElements.define('boerdi-ui-probe', Probe);",
  ].join('\n'));
  mkdirSync(join(quelle, 'ui-sofort'));
  writeFileSync(join(quelle, 'ui-sofort', 'manifest.json'), JSON.stringify(manifest('ui_sofort')));
  return { quelle, ausgabe: join(wurzel, 'dist'), index: join(wurzel, 'nachlade-index.build.ts') };
}

test('baut je nachgeladenes Modul ein Bündel mit Inhalts-Hash und schreibt den SRI-Index', async () => {
  const { quelle, ausgabe, index } = aufbau();
  const ergebnis = await baue({ quelle, ausgabe, index });
  assert.deepEqual(Object.keys(ergebnis), ['ui_probe']);
  const { datei, integritaet } = ergebnis.ui_probe;
  assert.match(datei, /^ui-probe\.[0-9a-f]{8}\.js$/);
  const bytes = readFileSync(join(ausgabe, datei));
  assert.equal(integritaet, 'sha384-' + createHash('sha384').update(bytes).digest('base64'));
  // CSS als Text eingebunden, IIFE ohne Importe (klassisches <script>)
  const text = bytes.toString('utf8');
  assert.match(text, /--mat-sys-primary/);
  assert.doesNotMatch(text, /^\s*import\s|export\s/m);
  const ts = readFileSync(index, 'utf8');
  assert.match(ts, /NACHLADE_INDEX: NachladeIndex = \{/);
  assert.ok(ts.includes(`ui_probe: { datei: '${datei}', integritaet: '${integritaet}' },`), ts);
});

test('derselbe Quelltext ergibt dieselbe Datei; alte Bündel werden entfernt', async () => {
  const { quelle, ausgabe, index } = aufbau();
  const erst = await baue({ quelle, ausgabe, index });
  const noch = await baue({ quelle, ausgabe, index });
  assert.equal(erst.ui_probe.datei, noch.ui_probe.datei);
  writeFileSync(join(quelle, 'ui-probe', 'probe.css'), '.probe { color: var(--mat-sys-secondary); }');
  const neu = await baue({ quelle, ausgabe, index });
  assert.notEqual(neu.ui_probe.datei, erst.ui_probe.datei);
  assert.deepEqual(readdirSync(ausgabe), [neu.ui_probe.datei]);
});

test('ohne nachgeladene Module: leerer Index, leeres Ausgabe-Verzeichnis', async () => {
  const { quelle, ausgabe, index } = aufbau();
  writeFileSync(join(quelle, 'ui-probe', 'manifest.json'), JSON.stringify(manifest('ui_probe')));
  const ergebnis = await baue({ quelle, ausgabe, index });
  assert.deepEqual(ergebnis, {});
  assert.ok(existsSync(ausgabe));
  assert.deepEqual(readdirSync(ausgabe), []);
  assert.match(readFileSync(index, 'utf8'), /NACHLADE_INDEX: NachladeIndex = \{\};/);
});

test('ein Bündel, das ein Angular-Paket einbindet, wird abgewiesen (Module bleiben rahmenlos)', async () => {
  const { quelle, ausgabe, index } = aufbau();
  writeFileSync(join(quelle, 'ui-probe', 'ui-probe.element.ts'), "import { Component } from '@angular/core';\nexport const x = Component;");
  await assert.rejects(baue({ quelle, ausgabe, index }), /@angular/);
});

test('BU-3: Widget-Teile ohne Manifest (zweite Quelle) werden gebaut und stehen im selben Index', async () => {
  const { quelle, ausgabe, index } = aufbau();
  const teile = join(quelle, '..', 'teile');
  mkdirSync(join(teile, 'ui-diagnose'), { recursive: true });
  writeFileSync(join(teile, 'ui-diagnose', 'ui-diagnose.element.ts'),
    "class D extends HTMLElement {}\nif (!customElements.get('boerdi-ui-diagnose')) customElements.define('boerdi-ui-diagnose', D);");
  mkdirSync(join(teile, 'ui-ohne-element'));                  // ohne Element-Datei: kein Teil
  mkdirSync(join(teile, '_hilfe'));                           // ohne ui-Präfix: kein Teil
  const ergebnis = await baue({ quelle, teile, ausgabe, index });
  assert.deepEqual(Object.keys(ergebnis).sort(), ['ui_diagnose', 'ui_probe']);
  assert.match(ergebnis.ui_diagnose.datei, /^ui-diagnose\.[0-9a-f]{8}\.js$/);
  assert.ok(readFileSync(index, 'utf8').includes(`ui_diagnose: { datei: '${ergebnis.ui_diagnose.datei}'`));
});

test('BU-3: derselbe Name als Modul und als Teil wird abgewiesen', async () => {
  const { quelle, ausgabe, index } = aufbau();
  const teile = join(quelle, '..', 'teile');
  mkdirSync(join(teile, 'ui-probe'), { recursive: true });
  writeFileSync(join(teile, 'ui-probe', 'ui-probe.element.ts'), 'export {};');
  await assert.rejects(baue({ quelle, teile, ausgabe, index }), /ui-probe/);
});
