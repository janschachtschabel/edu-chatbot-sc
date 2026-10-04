/**
 * Die Bewertung des npm-Audit-Gates (Paket 4, L2) — ohne Netz, ohne npm.
 *
 * Aufruf: node --test scripts/check-audit.test.mjs
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { bewerte } from './audit-bewertung.mjs';

const HEUTE = '2026-10-03';

/** Ein `npm audit --json`-Bericht (auditReportVersion 2) mit einem Fund. */
function bericht(severity, ghsa = 'GHSA-aaaa-bbbb-cccc', paket = 'beispiel') {
  return {
    auditReportVersion: 2,
    vulnerabilities: {
      [paket]: {
        name: paket,
        severity,
        via: [{
          source: 1, name: paket, title: 'Beispiel-Lücke', severity,
          url: `https://github.com/advisories/${ghsa}`, range: '<1.0.0',
        }],
      },
      // Ein Paket, das nur ÜBER das andere betroffen ist: `via` ist ein Name.
      abhaengig: { name: 'abhaengig', severity, via: [paket] },
    },
  };
}

const ausnahme = (bis, ghsa = 'GHSA-aaaa-bbbb-cccc') => ({ ghsa, grund: 'Test', bis });

test('ein Fund ab high ohne Ausnahme ist rot und nennt die GHSA', () => {
  const ergebnis = bewerte(bericht('high'), [], HEUTE);
  assert.equal(ergebnis.ok, false);
  assert.match(ergebnis.fehler.join('\n'), /GHSA-aaaa-bbbb-cccc/);
});

test('critical zählt wie high', () => {
  assert.equal(bewerte(bericht('critical'), [], HEUTE).ok, false);
});

test('unter der Schwelle (moderate) ist grün', () => {
  assert.equal(bewerte(bericht('moderate'), [], HEUTE).ok, true);
});

test('mit gültiger Ausnahme grün — und die Ausnahme wird genannt', () => {
  const ergebnis = bewerte(bericht('high'), [ausnahme('2026-12-31')], HEUTE);
  assert.equal(ergebnis.ok, true);
  assert.match(ergebnis.hinweise.join('\n'), /GHSA-aaaa-bbbb-cccc/);
});

test('am Ablauftag gilt die Ausnahme noch', () => {
  assert.equal(bewerte(bericht('high'), [ausnahme(HEUTE)], HEUTE).ok, true);
});

test('mit abgelaufener Ausnahme rot', () => {
  const ergebnis = bewerte(bericht('high'), [ausnahme('2026-10-02')], HEUTE);
  assert.equal(ergebnis.ok, false);
  assert.match(ergebnis.fehler.join('\n'), /abgelaufen/);
});

test('eine abgelaufene Ausnahme ohne Fund ist auch rot — sie gehört gestrichen', () => {
  const ergebnis = bewerte(bericht('moderate'), [ausnahme('2026-01-01')], HEUTE);
  assert.equal(ergebnis.ok, false);
  assert.match(ergebnis.fehler.join('\n'), /abgelaufen/);
});

test('eine Ausnahme ohne Grund oder Datum ist rot', () => {
  const ergebnis = bewerte(bericht('high'), [{ ghsa: 'GHSA-aaaa-bbbb-cccc' }], HEUTE);
  assert.equal(ergebnis.ok, false);
});

test('ein Bericht in fremdem Format ist rot, nicht grün', () => {
  // Prüfer 2026-10-04: `{}` oder ein Bericht nach auditReportVersion 1 galt als
  // „kein Fund“ — das Gate wäre bei einer geänderten npm-Ausgabe still grün.
  for (const fremd of [{}, { auditReportVersion: 1, advisories: {} }, null]) {
    const ergebnis = bewerte(fremd, [], HEUTE);
    assert.equal(ergebnis.ok, false);
    assert.match(ergebnis.fehler.join('\n'), /Format/);
  }
});

test('ein leerer Bericht im erwarteten Format ist grün', () => {
  assert.equal(bewerte({ auditReportVersion: 2, vulnerabilities: {} }, [], HEUTE).ok, true);
});
