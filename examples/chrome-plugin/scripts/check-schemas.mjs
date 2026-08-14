/**
 * Prüfung für `schemas.js` — die Schema-Prüfung und die Vorlagen selbst.
 *
 * Zwei Klassen von Fehlern, die sonst erst im Betrieb auffallen:
 *
 * 1. **„leer" gegen „kaputt".** Beide Fälle liefern kein Schema, aber nur einer
 *    darf den Zug starten lassen. Wer sie zusammenwirft, löst bei einem
 *    Tippfehler einen vollen Agent-Zug ohne Ergebnis aus (Befund 2026-08-14).
 * 2. **Der 10 000-Zeichen-Deckel.** Wer eine Vorlage erweitert, merkt ihn sonst
 *    erst am 422 des Backends — und dann steht die Ursache in keiner Meldung.
 *
 *     node scripts/check-schemas.mjs
 */
import { MAX_SCHEMA_ZEICHEN, VORLAGEN, pruefeSchema } from '../schemas.js';

let geprueft = 0;
const fehler = [];

function gleich(was, ist, soll) {
  geprueft++;
  const a = JSON.stringify(ist);
  const b = JSON.stringify(soll);
  if (a !== b) fehler.push(`${was}\n    ist:  ${a}\n    soll: ${b}`);
}

function stimmt(was, bedingung) {
  geprueft++;
  if (!bedingung) fehler.push(was);
}

// ── Der Unterschied, auf den es ankommt ────────────────────────────

gleich('leeres Feld ist GÜLTIG (Chat ohne Schema ist ein erlaubter Start)',
  pruefeSchema('').gueltig, true);
gleich('leeres Feld liefert kein Schema', pruefeSchema('  ').schema, null);

gleich('kaputtes JSON ist UNGÜLTIG', pruefeSchema('{"type": objekt,,}').gueltig, false);
gleich('kaputtes JSON liefert kein Schema', pruefeSchema('{kaputt').schema, null);

gleich('ein Array ist kein Schema', pruefeSchema('[1,2,3]').gueltig, false);
gleich('eine Zahl ist kein Schema', pruefeSchema('42').gueltig, false);
gleich('null ist kein Schema', pruefeSchema('null').gueltig, false);

gleich('ein Objekt ist gültig', pruefeSchema('{"type":"object"}').gueltig, true);
gleich('und kommt geparst zurück',
  pruefeSchema('{"type":"object"}').schema, { type: 'object' });

// Der Deckel: eine Zeichenkette bauen, die serialisiert sicher darüber liegt.
const zuGross = JSON.stringify({ type: 'object', beschreibung: 'x'.repeat(MAX_SCHEMA_ZEICHEN) });
gleich('über dem Deckel ist ungültig', pruefeSchema(zuGross).gueltig, false);
stimmt('die Meldung nennt den Deckel',
  pruefeSchema(zuGross).text.includes(String(MAX_SCHEMA_ZEICHEN)));

stimmt('jede Meldung ist ein Satz für Menschen, nicht leer',
  ['', '{kaputt', '[1]', '{"a":1}'].every((r) => pruefeSchema(r).text.trim().length > 10));

// ── Die Vorlagen selbst ────────────────────────────────────────────

stimmt('es gibt Vorlagen', VORLAGEN.length > 0);

for (const v of VORLAGEN) {
  const roh = JSON.stringify(v.schema);
  stimmt(`Vorlage "${v.id}": Schema bleibt unter ${MAX_SCHEMA_ZEICHEN} Zeichen `
    + `(ist ${roh.length})`, roh.length <= MAX_SCHEMA_ZEICHEN);
  gleich(`Vorlage "${v.id}": ihr eigenes Schema besteht die Prüfung`,
    pruefeSchema(roh).gueltig, true);
  stimmt(`Vorlage "${v.id}": hat einen Auftrag`, (v.auftrag || '').trim().length > 0);
  stimmt(`Vorlage "${v.id}": hat einen Namen`, (v.name || '').trim().length > 0);
}

// ── Ausgabe ────────────────────────────────────────────────────────

if (fehler.length) {
  console.error(`\n  ${fehler.length} von ${geprueft} Prüfungen fehlgeschlagen:\n`);
  for (const f of fehler) console.error(`  ✗ ${f}\n`);
  process.exit(1);
}
console.log(`  ${geprueft} Prüfungen bestanden (${VORLAGEN.length} Vorlagen).`);
