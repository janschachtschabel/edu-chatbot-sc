/**
 * M3 primary-color override (§7: the `--boerdi-primary` custom property).
 *
 * The host page may brand the widget through the `primary-color` element
 * attribute (§5.5 embed contract). That value is attacker-influenceable — the
 * embedding page controls it — so it is validated against a conservative
 * CSS-color allowlist and written to a *custom property* only; it is never
 * interpolated into a stylesheet string. An invalid or absent value clears the
 * override so the token falls back to the theme default.
 */

// #rgb / #rgba / #rrggbb / #rrggbbaa
const HEX = /^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
// rgb()/rgba()/hsl()/hsla() — digits, separators, percent, decimal, alpha slash only
const FUNC = /^(?:rgb|rgba|hsl|hsla)\(\s*[0-9.,%\s/]+\)$/;
// A bare CSS named color (letters only, bounded length) — e.g. "rebeccapurple"
const NAMED = /^[a-zA-Z]{3,20}$/;

export function isValidCssColor(value: string): boolean {
  const v = value.trim();
  return HEX.test(v) || FUNC.test(v) || NAMED.test(v);
}

export function applyPrimaryColor(host: HTMLElement, color: string | null | undefined): void {
  if (!host || !host.style) return;
  if (color && isValidCssColor(color)) {
    host.style.setProperty('--boerdi-primary', color.trim());
  } else {
    host.style.removeProperty('--boerdi-primary');
  }
}
