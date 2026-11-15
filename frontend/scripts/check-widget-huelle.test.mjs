// Tests für scripts/check-widget-huelle.mjs. Lauf: node --test scripts/check-widget-huelle.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { pruefe } from './check-widget-huelle.mjs';

test('ein Bündel in einer Hülle besteht — Pfeil, function, mit Direktive davor', () => {
  assert.deepEqual(pruefe('(()=>{var a=1;function b(){return a}b()})();'), []);
  assert.deepEqual(pruefe('(function(){let a=1;class K{}})();'), []);
  assert.deepEqual(pruefe('(function(){const a=1}());'), []);
  // So schreibt esbuild die Nachlade-Module (`format: 'iife'`).
  assert.deepEqual(pruefe('"use strict";(()=>{var a=1})();'), []);
  assert.deepEqual(pruefe('(async()=>{await 0})();'), []);
});

test('jede Art Deklaration auf oberster Ebene fällt auf', () => {
  for (const code of ['var a=1;', 'let a=1;', 'const a=1;', 'function f(){}', 'class K{}']) {
    const verstoesse = pruefe(code);
    assert.equal(verstoesse.length, 1, code);
    assert.match(verstoesse[0], /Deklaration auf oberster Ebene/, code);
  }
});

test('das ungehüllte Bündel des Angular-Builders: jede Deklaration ein Verstoß', () => {
  const verstoesse = pruefe('var hE=Object.defineProperty;function lesen(){return hE}var block=null;lesen();');
  assert.equal(verstoesse.length, 4);
  assert.match(verstoesse[0], /var hE=Object\.defineProperty/);
  assert.match(verstoesse[3], /Anweisung außerhalb der Hülle: lesen\(\)/);
});

test('etwas neben der Hülle fällt auf, davor wie danach', () => {
  assert.match(pruefe('(()=>{})();var a=1;')[0], /Deklaration auf oberster Ebene: var a=1/);
  assert.match(pruefe('a=1;(()=>{})();')[0], /Anweisung außerhalb der Hülle: a=1/);
  assert.match(pruefe('if(x){var a=1}(()=>{})();')[0], /Anweisung außerhalb der Hülle/);
  // Ein Text NACH der Hülle ist keine Direktive mehr, sondern eine lose Anweisung.
  assert.equal(pruefe('(()=>{})();"use strict";').length, 1);
});

test('kein gültiges klassisches Skript: import, export, await auf oberster Ebene', () => {
  for (const code of ['export const a=1;', 'import x from "y";', '(()=>{await 0})();', '(()=>{export const a=1})();', '(()=>{']) {
    const verstoesse = pruefe(code);
    assert.equal(verstoesse.length, 1, code);
    assert.match(verstoesse[0], /kein gültiges klassisches Skript/, code);
  }
});

test('ein leeres Bündel ist ein Fehler, kein Freibrief', () => {
  assert.match(pruefe('')[0], /keine Hülle gefunden/);
  assert.match(pruefe('/* nur Lizenzen */')[0], /keine Hülle gefunden/);
  assert.match(pruefe('"use strict";')[0], /keine Hülle gefunden/);
});

test('eine Generator-Hülle zählt nicht: ihr Aufruf führt den Rumpf nie aus', () => {
  assert.match(pruefe('(function*(){var a=1})();')[0], /Anweisung außerhalb der Hülle/);
});

test('Kommentare neben der Hülle stören nicht', () => {
  assert.deepEqual(pruefe('/*! Lizenz */\n(()=>{var a=1})();\n/*! noch eine */\n'), []);
});
