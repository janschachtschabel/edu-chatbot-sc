/**
 * Number and date rendering, in one place (9-5c).
 *
 * Written because the same two formatters had been copied by hand: the
 * `maximumFractionDigits: 2` decimal into two components, and the date — with
 * the same NaN guard — into four. 9-5c would have made that three and five. B2
 * folded the four date copies in here, so every view now shows the same thing
 * for the same input.
 *
 * **The locale is a parameter (C1-d4f).** Until then every formatter carried
 * `de-DE` hardcoded, which was right while the studio spoke one language and
 * silently wrong the moment it spoke two: an English interface would have
 * answered "24.7.2026" and "0,81". The tag itself is not decided here — it
 * comes from the catalogue as `format.locale`, and `StudioFormat` is what
 * reads it. `core` stays free of the catalogue, so the dependency keeps
 * pointing inward.
 *
 * Angular's `DecimalPipe`/`DatePipe` are still not used: the studio registers
 * no `LOCALE_ID`, and registering one per language would mean loading
 * Angular's locale data for a job `Intl` does from the platform.
 */

/**
 * Built formatters, keyed by locale and kind.
 *
 * A cache rather than constants because the locale is no longer fixed.
 * Building an `Intl` formatter is the expensive part; the map is a pure memo —
 * same key, same object, no observable state.
 */
const NUMBER_FORMATS = new Map<string, Intl.NumberFormat>();

function numberFormat(
  locale: string, kind: string, options: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = `${locale}|${kind}`;
  let format = NUMBER_FORMATS.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale, options);
    NUMBER_FORMATS.set(key, format);
  }
  return format;
}

/** A score or a rate as a number: "0,81" / "0.81". */
export function formatDecimal(locale: string, value: number): string {
  return numberFormat(locale, 'decimal', { maximumFractionDigits: 2 }).format(value);
}

/** A count: "12.345" / "12,345". */
export function formatWhole(locale: string, value: number): string {
  return numberFormat(locale, 'whole', { maximumFractionDigits: 0 }).format(value);
}

/**
 * A cost estimate: "0,14 $" / "US$0.14".
 *
 * Eval cost estimates are quoted in USD by the provider price table, so the
 * currency is fixed while the *formatting* follows the interface language —
 * German puts the symbol behind the number, and hardcoding "$0.14" would get
 * that wrong in both directions.
 */
export function formatUsd(locale: string, value: number): string {
  return numberFormat(locale, 'usd', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value);
}

/** A currency code `Intl` will accept — three ASCII letters, nothing else. */
const CURRENCY_CODE = /^[A-Za-z]{3}$/;

/** Beyond this, more places say nothing anyone can act on. */
const MAX_MONEY_DIGITS = 12;

/**
 * How many decimal places this amount needs so it does not read as zero.
 *
 * Decided on the STRING, not on a parsed number: the string is the exact value
 * the server computed with `Decimal`, and reading its digits cannot introduce
 * the drift the string exists to avoid.
 *
 * Two places normally. More only when the amount is below a cent *and* not
 * zero — then enough to show the first significant digit and one after it.
 */
function moneyDigits(amount: string): number {
  const [whole = '', fraction = ''] = amount.replace('-', '').split('.');
  const firstSignificant = fraction.search(/[1-9]/);
  if (whole !== '0' || firstSignificant < 2) return 2;
  return Math.min(firstSignificant + 2, MAX_MONEY_DIGITS);
}

/**
 * An exact amount, in the interface language's typography: "4,92 €" / "€4.92".
 *
 * Takes a string because that is how the amount leaves the server (K4): as a
 * JSON number, `13.27743099` would come back as `13.277430990000001` and the
 * whole `Decimal` calculation would be lost on the last metre. `Number()` is
 * used only for `Intl`, after the number of places has already been decided —
 * a double is exact far beyond the twelve places shown here.
 *
 * **Deliberately not always two places.** A single turn often costs fractions
 * of a cent, and "0,00 €" reads as "this cost nothing" — the same mistake K3
 * avoids for an unmaintained price table.
 *
 * `currency` comes from the studio config. Since 2026-08-12 the area model
 * rejects anything but a three-letter code, so the studio can no longer store
 * one that `Intl` refuses — but `seed_io.import_tree` writes unvalidated dicts,
 * so the path is still reachable. `Intl` throws a `RangeError` on an invalid
 * code, which would blank the whole view; an unusable code therefore still
 * falls back to a plain number with the raw code behind it, which is
 * wrong-looking rather than missing.
 */
export function formatMoney(locale: string, amount: string, currency: string): string {
  const value = Number(amount);
  if (!amount.trim() || !Number.isFinite(value)) return amount;
  const digits = moneyDigits(amount.trim());

  if (!CURRENCY_CODE.test(currency)) {
    const plain = numberFormat(locale, `money:plain:${digits}`, {
      minimumFractionDigits: 2, maximumFractionDigits: digits,
    }).format(value);
    return currency ? `${plain} ${currency}` : plain;
  }
  return numberFormat(locale, `money:${currency}:${digits}`, {
    style: 'currency', currency,
    minimumFractionDigits: 2, maximumFractionDigits: digits,
  }).format(value);
}

/**
 * A 0…1 ratio as a percentage: "2,5 %" / "2.5%".
 *
 * `Intl` sets the non-breaking space German typography wants before the sign —
 * and omits it in English, where the convention is the other one.
 */
export function formatPercent(locale: string, value: number, digits = 1): string {
  return numberFormat(locale, `percent:${digits}`, {
    style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(value);
}

/**
 * `numeric: 'always'`, not `'auto'`: a status line reads as a measurement, and
 * 'auto' answers a one-day-old snapshot with "gestern" — a different register
 * next to "vor 3 Stunden" in the neighbouring card. The friendly case is
 * covered by the `justNow` text the caller passes in.
 */
const RELATIVE_FORMATS = new Map<string, Intl.RelativeTimeFormat>();

function relativeFormat(locale: string): Intl.RelativeTimeFormat {
  let format = RELATIVE_FORMATS.get(locale);
  if (!format) {
    format = new Intl.RelativeTimeFormat(locale, { numeric: 'always' });
    RELATIVE_FORMATS.set(locale, format);
  }
  return format;
}

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
 * How long ago a timestamp was: "vor 5 Minuten", "vor 1 Tag", "2 days ago".
 *
 * `nowMs` is a parameter rather than a `Date.now()` call inside, so callers in
 * tests get a fixed answer without fake timers. `justNow` is a parameter for
 * the same kind of reason: `Intl.RelativeTimeFormat` has no sub-minute case, so
 * that one text is editorial — and editorial text lives in the catalogue,
 * which `core` must not reach into.
 *
 * `Intl.RelativeTimeFormat` owns the wording, which ALT's string concatenation
 * did not: it wrote "vor 1 Tagen" for a one-day-old snapshot and "vor -2 Min"
 * whenever the server's clock ran ahead of the browser's
 * (HomeOverview.tsx:65-73). A skew now reads forwards ("in 2 Stunden").
 */
export function formatRelative(
  locale: string, iso: string, nowMs: number, justNow: string,
): string {
  if (!iso) return '—';
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '—';
  const seconds = (then - nowMs) / 1000;
  const age = Math.abs(seconds);
  if (age < 60) return justNow;
  // Truncated, not rounded: 90 minutes have "vor 1 Stunde" behind them, and
  // rounding up would claim an age that has not been reached yet. Truncation
  // toward zero reads the same way in both directions.
  const format = relativeFormat(locale);
  for (const { bound, unit, length } of RELATIVE_UNITS) {
    if (age < bound) return format.format(Math.trunc(seconds / length), unit);
  }
  return format.format(Math.trunc(seconds / MONTH_SECONDS), 'month');
}

/**
 * An ISO timestamp in the interface language's order, or the input unchanged
 * when it will not parse — a corrupt row must not paint "Invalid Date" across
 * a table.
 */
export function formatDateTime(locale: string, iso: string): string {
  if (!iso) return iso;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString(locale);
}
