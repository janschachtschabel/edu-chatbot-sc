import { describe, expect, it } from 'vitest';

import {
  formatBytes, formatCalendarDay, formatDateTime, formatDecimal, formatMoney, formatPercent, formatRelative,
  formatSeconds, formatWhole,
} from './format';

/** German typography puts a NO-BREAK space before the percent sign. */
const NBSP = ' ';

/** The two tags the catalogue carries as `format.locale` (C1-d4f). */
const DE = 'de-DE';
const EN = 'en-GB';

describe('formatDecimal', () => {
  it('uses the German decimal comma and cuts at two places', () => {
    expect(formatDecimal(DE, 0.812)).toBe('0,81');
    expect(formatDecimal(DE, 1)).toBe('1');
  });

  it('uses the decimal point in English', () => {
    expect(formatDecimal(EN, 0.812)).toBe('0.81');
  });
});

describe('formatPercent', () => {
  it('writes a rate as a percentage with a non-breaking space', () => {
    expect(formatPercent(DE, 0.025)).toBe(`2,5${NBSP}%`);
  });

  it('rounds to whole percent where a decimal would be noise', () => {
    expect(formatPercent(DE, 0.8, 0)).toBe(`80${NBSP}%`);
  });

  it('follows English typography, which sets no space before the sign', () => {
    expect(formatPercent(EN, 0.025)).toBe('2.5%');
  });
});

describe('formatWhole', () => {
  it('groups thousands the German way', () => {
    expect(formatWhole(DE, 12345)).toBe('12.345');
  });

  it('groups them the English way', () => {
    expect(formatWhole(EN, 12345)).toBe('12,345');
  });
});

describe('formatBytes', () => {
  it('picks the largest unit that keeps the number at one or more', () => {
    expect(formatBytes(DE, 512)).toBe('512 Byte');
    expect(formatBytes(DE, 1536)).toBe('1,5 kB');
    expect(formatBytes(DE, 20.47 * 1024 ** 2)).toBe('20,5 MB');
    // ICU's German data joins "GB" (only "GB") with a no-break space
    expect(formatBytes(DE, 2 * 1024 ** 3)).toBe(`2${NBSP}GB`);
  });

  it('counts in steps of 1024, as PostgreSQL reports its sizes', () => {
    // pg_size_pretty says "8192 bytes" → "8 kB"; the studio must not answer
    // the same database with a second, decimal number.
    expect(formatBytes(DE, 8192)).toBe('8 kB');
    expect(formatBytes(DE, 1023)).toBe('1.023 Byte');
  });

  it('follows English typography', () => {
    expect(formatBytes(EN, 1536)).toBe('1.5 kB');
    expect(formatBytes(EN, 512)).toBe('512 byte');
  });

  it('picks the unit by magnitude, so a negative difference keeps its unit', () => {
    expect(formatBytes(DE, -8192)).toBe('-8 kB');
  });
});

describe('formatSeconds (ST-7b)', () => {
  it('turns milliseconds into seconds with one place and the SI symbol', () => {
    // Das Einheitenzeichen ist sprachneutral; ICU schreibt „Sek." oder „s" je
    // nach Version — die Zugdauer soll überall gleich aussehen.
    expect(formatSeconds(DE, 12340)).toBe(`12,3${NBSP}s`);
    expect(formatSeconds(DE, 960)).toBe(`1,0${NBSP}s`);
    expect(formatSeconds(EN, 21800)).toBe(`21.8${NBSP}s`);
  });

  it('groups thousands in long runs', () => {
    expect(formatSeconds(DE, 1_234_000)).toBe(`1.234,0${NBSP}s`);
  });
});

describe('formatDateTime', () => {
  it('renders an ISO timestamp in German order', () => {
    // Asserted on the date part only: the time depends on the runner's zone.
    expect(formatDateTime(DE, '2026-07-24T10:00:00Z')).toContain('24.7.2026');
  });

  it('renders it in English order', () => {
    expect(formatDateTime(EN, '2026-07-24T10:00:00Z')).toContain('24/07/2026');
  });

  it('returns unparseable input unchanged instead of "Invalid Date"', () => {
    // The four dashboards that hand-rolled this all had the same guard, because
    // a corrupt row must not paint "Invalid Date" across the table.
    expect(formatDateTime(DE, 'irgendwas')).toBe('irgendwas');
  });

  it('survives an empty timestamp', () => {
    expect(formatDateTime(DE, '')).toBe('');
  });
});

describe('formatRelative', () => {
  /** The reference instant is a parameter, so these are not timing-dependent. */
  const NOW = Date.parse('2026-07-26T12:00:00Z');
  const ago = (ms: number) => new Date(NOW - ms).toISOString();
  const MIN = 60_000;
  const HOUR = 60 * MIN;
  const DAY = 24 * HOUR;

  it('hands the sub-minute case back to the caller, who owns the wording', () => {
    // `Intl.RelativeTimeFormat` has no "just now"; the text is a catalogue
    // entry, and `core` must not reach into the catalogue (dependency
    // direction) — so it arrives as an argument.
    expect(formatRelative(DE, ago(5_000), NOW, 'gerade eben')).toBe('gerade eben');
    expect(formatRelative(EN, ago(5_000), NOW, 'just now')).toBe('just now');
  });

  it('counts minutes, hours, days and months', () => {
    expect(formatRelative(DE, ago(5 * MIN), NOW, '')).toBe('vor 5 Minuten');
    expect(formatRelative(DE, ago(3 * HOUR), NOW, '')).toBe('vor 3 Stunden');
    expect(formatRelative(DE, ago(2 * DAY), NOW, '')).toBe('vor 2 Tagen');
    expect(formatRelative(DE, ago(75 * DAY), NOW, '')).toBe('vor 2 Monaten');
  });

  it('counts them in English too', () => {
    expect(formatRelative(EN, ago(5 * MIN), NOW, '')).toBe('5 minutes ago');
    expect(formatRelative(EN, ago(2 * DAY), NOW, '')).toBe('2 days ago');
  });

  it('gets the singular right', () => {
    // ALT concatenated `vor ${n} Tagen` and so wrote "vor 1 Tagen"
    // (HomeOverview.tsx:71). Intl owns the plural rules.
    expect(formatRelative(DE, ago(DAY), NOW, '')).toBe('vor 1 Tag');
    expect(formatRelative(DE, ago(HOUR), NOW, '')).toBe('vor 1 Stunde');
    expect(formatRelative(EN, ago(DAY), NOW, '')).toBe('1 day ago');
  });

  it('reads a clock skew forwards instead of printing "vor -2 h"', () => {
    // A snapshot stamped by the server can be ahead of the browser's clock.
    expect(formatRelative(DE, new Date(NOW + 2 * HOUR).toISOString(), NOW, ''))
      .toBe('in 2 Stunden');
  });

  it('has one dash for "no timestamp" and for "unparseable"', () => {
    expect(formatRelative(DE, '', NOW, '')).toBe('—');
    expect(formatRelative(DE, 'irgendwas', NOW, '')).toBe('—');
  });
});

describe('formatMoney', () => {
  // Der Betrag kommt als ZEICHENKETTE vom Server (K4): als JSON-Zahl würde aus
  // 13.27743099 wieder 13.277430990000001. Die Nachkommastellen wählt darum die
  // Zeichenkette selbst, nicht ein Gleitkommawert.

  it('setzt Symbol und Trennzeichen nach der Oberflächensprache', () => {
    expect(formatMoney(DE, '1234.5', 'EUR')).toBe(`1.234,50${NBSP}€`);
    expect(formatMoney(EN, '1234.5', 'EUR')).toBe('€1,234.50');
  });

  it('zeigt zwei Nachkommastellen, wo zwei genügen', () => {
    expect(formatMoney(DE, '4.92', 'EUR')).toBe(`4,92${NBSP}€`);
    expect(formatMoney(DE, '3', 'EUR')).toBe(`3,00${NBSP}€`);
  });

  it('lässt einen winzigen Betrag NICHT auf null runden', () => {
    // Ein einzelner Zug kostet oft Bruchteile eines Cents. „0,00 €" läse sich
    // wie „hat nichts gekostet" — derselbe Fehler, den K3 bei der ungepflegten
    // Preistafel vermeidet.
    expect(formatMoney(DE, '0.00004921', 'EUR')).toBe(`0,000049${NBSP}€`);
    expect(formatMoney(DE, '0.0049', 'EUR')).toBe(`0,0049${NBSP}€`);
  });

  it('rundet eine echte Null auf zwei Stellen, statt Stellen zu erfinden', () => {
    expect(formatMoney(DE, '0', 'EUR')).toBe(`0,00${NBSP}€`);
    expect(formatMoney(DE, '0.00', 'EUR')).toBe(`0,00${NBSP}€`);
  });

  it('überlebt eine Währung, die keine ist', () => {
    // `currency` ist ein freies Feld der Studio-Config. `Intl` wirft bei einem
    // ungültigen Code einen RangeError — der leerte sonst die ganze Ansicht,
    // weil eine Redakteurin „Euro" statt „EUR" getippt hat.
    expect(formatMoney(DE, '4.92', 'Euro')).toBe('4,92 Euro');
    expect(formatMoney(DE, '4.92', '')).toBe('4,92');
  });

  it('gibt eine unlesbare Zahl unverändert zurück, statt NaN zu malen', () => {
    expect(formatMoney(DE, 'kaputt', 'EUR')).toBe('kaputt');
    expect(formatMoney(DE, '', 'EUR')).toBe('');
  });
});

describe('formatCalendarDay (Paket 16, D2)', () => {
  it('nimmt den Kalendertag, wie er ist — ohne Zeitzone, die ihn verschieben könnte', () => {
    expect(formatCalendarDay(DE, '2026-03-11')).toBe('11.3.2026');
    expect(formatCalendarDay(EN, '2026-03-11')).toBe('11/03/2026');
  });

  it('gibt Unlesbares unverändert zurück', () => {
    expect(formatCalendarDay(DE, 'gestern')).toBe('gestern');
  });
});
