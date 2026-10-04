/**
 * The rating of the npm audit gate (Paket 4, L2) — pure, no network, no npm.
 *
 * Its own module so the entry point (`check-audit.mjs`) can run without an
 * "am I the main module?" guard: when that guard mismatched (symlinked
 * checkout, drive-letter case), the gate did nothing and exited 0 (review
 * 2026-10-04). Tested in `check-audit.test.mjs`.
 */

const SCHWELLE = new Set(['high', 'critical']);

/** The GHSA of an advisory, from its URL; the npm source id as a fallback. */
function kennung(advisory) {
  const ghsa = /GHSA-[\w-]+/.exec(String(advisory.url ?? ''));
  return ghsa ? ghsa[0] : `npm-${advisory.source}`;
}

/** Is this an `npm audit --json` report this gate understands? */
function erkannt(bericht) {
  const funde = bericht?.vulnerabilities;
  return bericht?.auditReportVersion === 2 && typeof funde === 'object' && funde !== null;
}

/**
 * Rate an `npm audit --json` report (auditReportVersion 2) against the
 * exceptions on day `heute` (`YYYY-MM-DD`).
 *
 * Threshold `high`: a finding of severity high or critical fails, unless the
 * exceptions list its GHSA with a reason and an expiry date (`bis`,
 * inclusive). An expired exception fails too — even one whose finding is gone,
 * so the list cannot rot into a silent allow-list. A report in any other shape
 * fails: read as "no findings", a changed npm output would turn the gate
 * silently green (review 2026-10-04).
 *
 * @returns {{ ok: boolean, fehler: string[], hinweise: string[] }}
 */
export function bewerte(bericht, ausnahmen, heute) {
  if (!erkannt(bericht)) {
    return {
      ok: false,
      fehler: ['npm audit lieferte keinen Bericht im erwarteten Format (auditReportVersion 2).'],
      hinweise: [],
    };
  }
  const fehler = [];
  const hinweise = [];
  const gueltig = new Map();
  for (const a of ausnahmen) {
    if (!a?.ghsa || !a?.grund || !/^\d{4}-\d{2}-\d{2}$/.test(String(a?.bis ?? ''))) {
      fehler.push(`Ausnahme unvollständig (ghsa, grund, bis): ${JSON.stringify(a)}`);
    } else if (a.bis < heute) {
      fehler.push(`Ausnahme ${a.ghsa} ist abgelaufen (bis ${a.bis}) — prüfen und streichen.`);
    } else {
      gueltig.set(a.ghsa, a);
    }
  }
  const gesehen = new Set();
  for (const paket of Object.values(bericht.vulnerabilities)) {
    for (const advisory of paket.via ?? []) {
      // A string names another vulnerable package; its advisory is listed there.
      if (typeof advisory !== 'object' || !SCHWELLE.has(advisory.severity)) continue;
      const id = kennung(advisory);
      if (gesehen.has(id)) continue;
      gesehen.add(id);
      const zeile = `${advisory.severity} ${id} in ${advisory.name} ${advisory.range ?? ''}: `
        + `${advisory.title ?? ''}`;
      const ausnahme = gueltig.get(id);
      if (ausnahme) {
        hinweise.push(`${zeile} — Ausnahme bis ${ausnahme.bis}: ${ausnahme.grund}`);
      } else if (!fehler.some((f) => f.includes(id))) {
        fehler.push(zeile);
      }
    }
  }
  return { ok: fehler.length === 0, fehler, hinweise };
}
