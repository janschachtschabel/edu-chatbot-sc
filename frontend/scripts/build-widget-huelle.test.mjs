// Tests für scripts/build-widget-huelle.mjs. Lauf: node --test scripts/build-widget-huelle.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runInNewContext } from 'node:vm';

import { huelle, huelleDatei } from './build-widget-huelle.mjs';
import { pruefe } from './check-widget-huelle.mjs';

/** Ein Bündel, wie der Angular-Builder es schreibt: alles auf oberster Ebene. */
const BUENDEL = 'var block="geheim";function lesen(){return block}let a=1;const b=2;class K{}'
  + 'globalThis.ergebnis=lesen()+a+b+typeof K;';

function datei(inhalt) {
  const pfad = join(mkdtempSync(join(tmpdir(), 'huelle-')), 'main.js');
  writeFileSync(pfad, inhalt);
  return pfad;
}

/** Führt den Text als klassisches Skript aus und gibt zurück, was danach am Fenster hängt. */
function fensterNach(code) {
  const fenster = {};
  runInNewContext(code, fenster);
  return fenster;
}

test('ohne Hülle hängen die Namen am Fenster — mit Hülle nur, was das Bündel ausdrücklich setzt', () => {
  const ohne = fensterNach(BUENDEL);
  assert.equal(typeof ohne.lesen, 'function');
  assert.equal(ohne.lesen(), 'geheim');           // genau der Befund: die Seite liest mit

  const mit = fensterNach(huelle(BUENDEL));
  assert.deepEqual(Object.keys(mit), ['ergebnis']);
  assert.equal(mit.ergebnis, 'geheim12function');  // das Bündel selbst läuft unverändert
});

test('auch let/const/class sind danach für ein zweites Skript der Seite unsichtbar', () => {
  // Sie werden nie zu Eigenschaften von `window`, stehen ohne Hülle aber im gemeinsamen Namensraum.
  const fenster = {};
  runInNewContext(huelle(BUENDEL), fenster);
  assert.equal(runInNewContext('typeof a + typeof b + typeof K + typeof lesen', fenster),
    'undefinedundefinedundefinedundefined');
});

test('this bleibt, was es auf oberster Ebene war', () => {
  assert.equal(fensterNach(huelle('globalThis.gleich = this === globalThis;')).gleich, true);
});

test('die Hülle macht das Bündel nicht strikt — es lief vorher nachlässig und bleibt es', () => {
  // Im strikten Modus wäre `this` in einem schlichten Funktionsaufruf `undefined`.
  assert.equal(fensterNach(huelle('globalThis.r=(function(){return this})()===globalThis;')).r, true);
});

test('ein Zeilenkommentar am Ende verschluckt die Hülle nicht', () => {
  const gehuellt = huelle('var a=1;globalThis.a2=a*2; // Ende ohne Zeilenumbruch');
  assert.deepEqual(pruefe(gehuellt), []);
  assert.equal(fensterNach(gehuellt).a2, 2);
});

test('der Lizenzblock am Ende des echten Bündels stört nicht', () => {
  assert.deepEqual(pruefe(huelle('var a=1;\n/*! @license Beispiel\n   (*! verschachtelt *)\n*/\n')), []);
});

test('huelleDatei schreibt die Hülle, und ein zweiter Lauf ändert nichts mehr', () => {
  const pfad = datei(BUENDEL);
  assert.equal(huelleDatei(pfad), true);
  const einmal = readFileSync(pfad, 'utf8');
  assert.deepEqual(pruefe(einmal), []);
  assert.equal(huelleDatei(pfad), false);
  assert.equal(readFileSync(pfad, 'utf8'), einmal);
});

test('was in der Hülle kein gültiges Skript wäre, bleibt unberührt und ist ein Fehler', () => {
  for (const inhalt of ['export const a=1;', 'var a=await 0;', 'var a=import.meta.url;']) {
    const pfad = datei(inhalt);
    assert.throws(() => huelleDatei(pfad), /lässt sich nicht hüllen/, inhalt);
    assert.equal(readFileSync(pfad, 'utf8'), inhalt, inhalt);
  }
});
