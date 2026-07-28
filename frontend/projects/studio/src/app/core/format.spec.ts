import { describe, expect, it } from 'vitest';

import {
  germanDateTime, formatDecimal, formatPercent, formatWhole, relativeGerman,
} from './format';

/** German typography puts a NO-BREAK space before the percent sign. */
const NBSP = '\u00A0';

describe('formatDecimal', () => {
  it('uses the German decimal comma and cuts at two places', () => {
    expect(formatDecimal(0.812)).toBe('0,81');
    expect(formatDecimal(1)).toBe('1');
  });
});

describe('formatPercent', () => {
  it('writes a rate as a percentage with a non-breaking space', () => {
    expect(formatPercent(0.025)).toBe(`2,5${NBSP}%`);
  });

  it('rounds to whole percent where a decimal would be noise', () => {
    expect(formatPercent(0.8, 0)).toBe(`80${NBSP}%`);
  });
});

describe('formatWhole', () => {
  it('groups thousands the German way', () => {
    expect(formatWhole(12345)).toBe('12.345');
  });
});

describe('germanDateTime', () => {
  it('renders an ISO timestamp in German order', () => {
    // Asserted on the date part only: the time depends on the runner's zone.
    expect(germanDateTime('2026-07-24T10:00:00Z')).toContain('24.7.2026');
  });

  it('returns unparseable input unchanged instead of "Invalid Date"', () => {
    // The four dashboards that hand-rolled this all had the same guard, because
    // a corrupt row must not paint "Invalid Date" across the table.
    expect(germanDateTime('irgendwas')).toBe('irgendwas');
  });

  it('survives an empty timestamp', () => {
    expect(germanDateTime('')).toBe('');
  });
});

describe('relativeGerman', () => {
  /** The reference instant is a parameter, so these are not timing-dependent. */
  const NOW = Date.parse('2026-07-26T12:00:00Z');
  const ago = (ms: number) => new Date(NOW - ms).toISOString();
  const MIN = 60_000;
  const HOUR = 60 * MIN;
  const DAY = 24 * HOUR;

  it('says "gerade eben" below a minute', () => {
    expect(relativeGerman(ago(5_000), NOW)).toBe('gerade eben');
  });

  it('counts minutes, hours, days and months', () => {
    expect(relativeGerman(ago(5 * MIN), NOW)).toBe('vor 5 Minuten');
    expect(relativeGerman(ago(3 * HOUR), NOW)).toBe('vor 3 Stunden');
    expect(relativeGerman(ago(2 * DAY), NOW)).toBe('vor 2 Tagen');
    expect(relativeGerman(ago(75 * DAY), NOW)).toBe('vor 2 Monaten');
  });

  it('gets the singular right', () => {
    // ALT concatenated `vor ${n} Tagen` and so wrote "vor 1 Tagen"
    // (HomeOverview.tsx:71). Intl owns the plural rules.
    expect(relativeGerman(ago(DAY), NOW)).toBe('vor 1 Tag');
    expect(relativeGerman(ago(HOUR), NOW)).toBe('vor 1 Stunde');
  });

  it('reads a clock skew forwards instead of printing "vor -2 h"', () => {
    // A snapshot stamped by the server can be ahead of the browser's clock.
    expect(relativeGerman(new Date(NOW + 2 * HOUR).toISOString(), NOW))
      .toBe('in 2 Stunden');
  });

  it('has one dash for "no timestamp" and for "unparseable"', () => {
    expect(relativeGerman('', NOW)).toBe('—');
    expect(relativeGerman('irgendwas', NOW)).toBe('—');
  });
});
