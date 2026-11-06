// Tests für scripts/check-module-budget.mjs (Paket U3-0). Lauf: node --test scripts/check-module-budget.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { pruefe } from './check-module-budget.mjs';

function verzeichnis(dateien) {
  const ort = mkdtempSync(join(tmpdir(), 'modbudget-'));
  for (const [name, inhalt] of Object.entries(dateien)) writeFileSync(join(ort, name), inhalt);
  return ort;
}

test('kleine Bündel bestehen; gemessen wird gzip', () => {
  const ort = verzeichnis({ 'ui-a.0123abcd.js': 'x'.repeat(50_000) });   // komprimiert winzig
  const { fehler, module } = pruefe(ort);
  assert.deepEqual(fehler, []);
  assert.equal(module.length, 1);
  assert.ok(module[0].gzip < 1000);
});

test('ein Bündel über 20 kB gzip fällt durch', () => {
  // Zufallsbytes komprimieren kaum: 25 kB roh ≈ 25 kB gzip.
  const ort = verzeichnis({ 'ui-gross.0123abcd.js': randomBytes(25_000).toString('base64') });
  const { fehler } = pruefe(ort);
  assert.equal(fehler.length, 1);
  assert.match(fehler[0], /ui-gross/);
});

test('alle zusammen höchstens 60 kB gzip', () => {
  const dateien = {};
  // je ~12 kB gzip (unter der Einzelgrenze), sechs zusammen ~73 kB
  for (let i = 0; i < 6; i++) dateien[`ui-m${i}.0123abc${i}.js`] = randomBytes(12_000).toString('base64');
  const { fehler } = pruefe(verzeichnis(dateien));
  assert.ok(fehler.some((f) => /zusammen/.test(f)));
});

test('fremde Dateien im Verzeichnis sind ein Fehler (nur gehashte Bündel)', () => {
  const { fehler } = pruefe(verzeichnis({ 'ui-a.0123abcd.js': 'x', 'notiz.txt': 'y' }));
  assert.ok(fehler.some((f) => /notiz\.txt/.test(f)));
});
