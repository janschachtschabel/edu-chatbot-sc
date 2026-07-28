/**
 * Validate the `?from=` login redirect (P9-2).
 *
 * ALT assigned the raw query value to `window.location.href`
 * (studio/src/app/login/page.tsx:26-28). The value normally comes from its own
 * middleware, but nothing enforced that, so `/login?from=https://evil.example`
 * turned a successful login into an off-site redirect — a phishing primitive
 * reachable with a single crafted link.
 *
 * Allow-list, not deny-list: exactly one leading `/`, then only characters that
 * can appear in a path/query, and never back to /login.
 */
import { DEFAULT_VIEW } from '../studio-views';

const FALLBACK = `/${DEFAULT_VIEW}`;

/**
 * `//host` and `/\host` are both protocol-relative to browsers, so a single
 * leading slash is not enough — the second character must not be `/` or `\`.
 * The rest is a conservative path/query allow-list (no whitespace, no control
 * characters, no backslash anywhere).
 */
const INTERNAL_PATH = /^\/(?![/\\])[\w\-./~%?&=+:@[\]!$'()*,;]*$/;

export function safeRedirectTarget(raw: string | null | undefined): string {
  // Deliberately NOT trimmed: the app never produces a padded value, so
  // whitespace means the parameter was hand-crafted — reject rather than repair.
  const value = raw ?? '';
  if (!INTERNAL_PATH.test(value)) return FALLBACK;
  // Redirecting to the login page would loop straight back here.
  if (value === '/login' || value.startsWith('/login?') || value.startsWith('/login/')) {
    return FALLBACK;
  }
  return value;
}
