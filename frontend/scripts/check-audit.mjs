#!/usr/bin/env node
/**
 * CI gate: known vulnerabilities in the npm tree (Paket 4, L2; external audit F20).
 *
 * The backend has `pip-audit` and both trees have a license gate, but nothing
 * failed the build on an npm advisory — the Angular/DOMPurify CVEs of 2026-07
 * and the piscina advisory of 2026-10 were found by hand.
 *
 * Threshold `high`: a finding of severity high or critical fails, unless
 * `audit-ausnahmen.json` lists its GHSA with a reason and an expiry date
 * (`bis`, inclusive). An expired exception fails too — even one whose finding
 * is gone, so the list cannot rot into a silent allow-list.
 *
 * `npm audit` sends the names and versions of the public packages in the lock
 * file to the registry — the same list `npm ci` downloads anyway.
 *
 * Usage: node scripts/check-audit.mjs   (from `frontend/`; needs the network)
 * The rating itself is `bewerte()` in `audit-bewertung.mjs`, tested offline in
 * `check-audit.test.mjs`. This file is only the entry point and always runs.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { bewerte } from './audit-bewertung.mjs';

const AUSNAHMEN = resolve('audit-ausnahmen.json');

// `npm audit` exits non-zero whenever it finds anything — the JSON decides.
// Windows: Node starts `npm.cmd` only through a shell; the arguments are fixed.
const lauf = spawnSync('npm', ['audit', '--json'], {
  encoding: 'utf8', shell: process.platform === 'win32', maxBuffer: 64 * 1024 * 1024,
});
let bericht;
try {
  bericht = JSON.parse(lauf.stdout);
} catch {
  console.error('npm audit lieferte kein JSON:', (lauf.stderr || lauf.stdout).slice(0, 500));
  process.exit(2);
}
if (bericht?.error) {
  console.error('npm audit scheiterte:', JSON.stringify(bericht.error).slice(0, 500));
  process.exit(2);
}
const { ausnahmen = [] } = JSON.parse(readFileSync(AUSNAHMEN, 'utf8'));
const heute = new Date().toISOString().slice(0, 10);
const { ok, fehler, hinweise } = bewerte(bericht, ausnahmen, heute);
for (const h of hinweise) console.log(`  erlaubt  ${h}`);
for (const f of fehler) console.error(`  FEHLER   ${f}`);
console.log(ok ? '\nKein Fund ab high ohne gültige Ausnahme.' : '\nnpm-Audit-Gate: rot.');
process.exit(ok ? 0 : 1);
