/**
 * German number and date rendering, in one place (9-5c).
 *
 * Written because the same two formatters had been copied by hand: the
 * `maximumFractionDigits: 2` decimal into two components, and the
 * `toLocaleString('de-DE')` date — with the same NaN guard — into four. 9-5c
 * would have made that three and five. B2 folded the four date copies in here,
 * so every view now shows the same thing for the same input.
 *
 * Locale-explicit on purpose. The studio registers no `LOCALE_ID`, so Angular's
 * `DecimalPipe`/`DatePipe` would format in en-US ("0.81", "7/24/2026"); every
 * view therefore passes `de-DE` itself, and that convention is kept here rather
 * than changed underneath six existing views.
 */

const DECIMAL = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 });
const WHOLE = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 });

/**
 * Eval cost estimates are quoted in USD by the provider price table, so the
 * currency is fixed while the *formatting* follows the interface language —
 * German puts the symbol behind the number, and hardcoding "$0.14" would get
 * that wrong in both directions.
 */
const USD = new Intl.NumberFormat('de-DE', {
  style: 'currency', currency: 'USD',
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

/** One place per digit count; building an `Intl` formatter per call is wasteful. */
const PERCENT = new Map<number, Intl.NumberFormat>();

/** A score or a rate as a number: "0,81". */
export function formatDecimal(value: number): string {
  return DECIMAL.format(value);
}

/** A count: "12.345". */
export function formatWhole(value: number): string {
  return WHOLE.format(value);
}

/** A cost estimate: "0,14 $". */
export function formatUsd(value: number): string {
  return USD.format(value);
}

/**
 * A 0…1 ratio as a percentage: "2,5 %".
 *
 * `Intl` inserts the non-breaking space German typography wants before the sign,
 * so the number never wraps away from its unit.
 */
export function formatPercent(value: number, digits = 1): string {
  let format = PERCENT.get(digits);
  if (!format) {
    format = new Intl.NumberFormat('de-DE', {
      style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
    PERCENT.set(digits, format);
  }
  return format.format(value);
}

/**
 * `numeric: 'always'`, not `'auto'`: a status line reads as a measurement, and
 * 'auto' answers a one-day-old snapshot with "gestern" — a different register
 * next to "vor 3 Stunden" in the neighbouring card. The friendly case is covered
 * by the explicit "gerade eben" below.
 */
const RELATIVE = new Intl.RelativeTimeFormat('de-DE', { numeric: 'always' });

/** Smallest unit first; the first bound the age fits into wins. */
const RELATIVE_UNITS: readonly {
  readonly bound: number; readonly unit: Intl.RelativeTimeFormatUnit; readonly length: number;
}[] = [
  { bound: 3600, unit: 'minute', length: 60 },
  { bound: 86_400, unit: 'hour', length: 3600 },
  { bound: 86_400 * 30, unit: 'day', length: 86_400 },
];

const MONTH_SECONDS = 86_400 * 30;

/**
 * How long ago a timestamp was: "vor 5 Minuten", "vor 1 Tag", "vor 2 Monaten".
 *
 * `nowMs` is a parameter rather than a `Date.now()` call inside, so callers in
 * tests get a fixed answer without fake timers.
 *
 * `Intl.RelativeTimeFormat` owns the wording, which ALT's string concatenation
 * did not: it wrote "vor 1 Tagen" for a one-day-old snapshot and "vor -2 Min"
 * whenever the server's clock ran ahead of the browser's
 * (HomeOverview.tsx:65-73). A skew now reads forwards ("in 2 Stunden").
 */
export function relativeGerman(iso: string, nowMs: number): string {
  if (!iso) return '—';
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '—';
  const seconds = (then - nowMs) / 1000;
  const age = Math.abs(seconds);
  if (age < 60) return 'gerade eben';
  // Truncated, not rounded: 90 minutes have "vor 1 Stunde" behind them, and
  // rounding up would claim an age that has not been reached yet. Truncation
  // toward zero reads the same way in both directions.
  for (const { bound, unit, length } of RELATIVE_UNITS) {
    if (age < bound) return RELATIVE.format(Math.trunc(seconds / length), unit);
  }
  return RELATIVE.format(Math.trunc(seconds / MONTH_SECONDS), 'month');
}

/**
 * An ISO timestamp in German order, or the input unchanged when it will not
 * parse — a corrupt row must not paint "Invalid Date" across a table.
 */
export function germanDateTime(iso: string): string {
  if (!iso) return iso;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('de-DE');
}
