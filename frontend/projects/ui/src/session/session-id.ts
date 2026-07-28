/**
 * Session-ID persistence & validation for the widget (§7 `ui/session`).
 * Verbatim port of ALT `services/session-id.service.ts` — deliberately pure
 * functions, not an `@Injectable` (no instance state); the single piece of
 * state (`_resumedViaBsid`) lives in the chat shell and is threaded via the
 * `ResolvedSessionId` return value. The cookie config (`sessionKey`,
 * `sessionCookieDomain`, `sessionCookieMaxAge`) comes in as parameters.
 *
 * ⚠️ Security-relevant: `isValidSessionId` guards the URL `?bsid=` pickup
 * against injection by third-party pages ("?bsid=evil-tracking-id");
 * `resolvePersistedSessionId` implements the 3-stage URL → cookie → localStorage
 * resolution and strips a consumed `bsid` from the address bar. localStorage /
 * cookie / URL access stays in-module (jsdom-compatible — the spec runs against
 * it for real). Behaviour pinned by session-id.spec.ts (NEU: dedicated spec;
 * ALT pinned it indirectly via chat.component.spec.ts). No logic change.
 */

/** Cookie configuration of the component (`@Input()` trio) as a parameter
 *  bundle for {@link writeSessionEverywhere}. */
export interface SessionCookieConfig {
  /** Storage/cookie key (input `sessionKey`). */
  sessionKey: string;
  /** Cookie domain for cross-subdomain sharing (input `sessionCookieDomain`);
   *  empty = no cookie, localStorage only. */
  cookieDomain: string;
  /** Cookie lifetime in seconds (input `sessionCookieMaxAge`). */
  cookieMaxAge: number | string;
}

/** Result of the 3-stage resolution. `viaBsid` tells the caller whether the id
 *  was picked up from `?bsid=` in the URL (cross-origin handoff) — the component
 *  maintains its `_resumedViaBsid` flag from it. */
export interface ResolvedSessionId {
  id: string | null;
  viaBsid: boolean;
}

/** Strict format check for our session-IDs — schützt URL-bsid-Pickup vor
 *  Injection durch Drittseiten ("?bsid=evil-tracking-id"). */
export function isValidSessionId(s: string | null | undefined): boolean {
  if (!s || typeof s !== 'string') return false;
  // Format: "bb-" + 36-char UUID v4 (mit/ohne Bindestriche), max 80 chars
  return /^bb-[0-9a-f-]{32,40}$/i.test(s) && s.length <= 80;
}

/** 3-Stufen-Resolution. ``id: null`` wenn nichts gefunden / alle invalid. */
export function resolvePersistedSessionId(sessionKey: string): ResolvedSessionId {
  // Stufe A: URL-Parameter ?bsid=… (Cross-TLD-Handoff)
  try {
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get('bsid');
    if (isValidSessionId(fromUrl)) {
      // Aus URL entfernen, damit die ID nicht weiter sichtbar mitwandert
      // (Bookmark-Sharing, Referer-Leaks an Drittseiten).
      url.searchParams.delete('bsid');
      const cleaned = url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : '') + url.hash;
      try { history.replaceState({}, '', cleaned); } catch { /* ignore */ }
      return { id: fromUrl, viaBsid: true };
    }
  } catch { /* ignore — never fail boot on URL parse */ }

  // Stufe B: Cookie (Cross-Subdomain)
  const fromCookie = readSessionCookie(sessionKey);
  if (isValidSessionId(fromCookie)) return { id: fromCookie, viaBsid: false };

  // Stufe C: localStorage (Origin-spezifischer Default)
  try {
    const fromLs = localStorage.getItem(sessionKey);
    if (isValidSessionId(fromLs)) return { id: fromLs, viaBsid: false };
  } catch { /* ignore */ }

  return { id: null, viaBsid: false };
}

/** Schreibt die Session-ID in alle aktiven Storages. */
export function writeSessionEverywhere(id: string, cfg: SessionCookieConfig): void {
  try { localStorage.setItem(cfg.sessionKey, id); } catch { /* ignore */ }
  if (cfg.cookieDomain) {
    writeSessionCookie(cfg.sessionKey, id, cfg.cookieDomain, cfg.cookieMaxAge);
  }
}

/** Schreibt ein Session-Cookie mit konfigurierter Domain. */
export function writeSessionCookie(
  name: string, value: string, domain: string, maxAgeSeconds: number | string,
): void {
  try {
    const maxAge = typeof maxAgeSeconds === 'string'
      ? parseInt(maxAgeSeconds, 10) || 30 * 24 * 60 * 60
      : maxAgeSeconds;
    // Secure-Flag: nur über HTTPS schicken (Pflicht ab SameSite=None,
    // Best-Practice bei Lax). Lokal über http://localhost ignoriert
    // der Browser das Secure-Flag freundlicherweise.
    const isHttps = location.protocol === 'https:';
    const parts = [
      `${name}=${encodeURIComponent(value)}`,
      `Domain=${domain}`,
      `Path=/`,
      `Max-Age=${maxAge}`,
      `SameSite=Lax`,
    ];
    if (isHttps) parts.push('Secure');
    document.cookie = parts.join('; ');
  } catch { /* ignore */ }
}

/** Liest den Wert eines Cookies anhand des Namens. */
export function readSessionCookie(name: string): string | null {
  try {
    const re = new RegExp('(?:^|;\\s*)' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([^;]+)');
    const m = document.cookie.match(re);
    return m ? decodeURIComponent(m[1]) : null;
  } catch {
    return null;
  }
}

/** Löscht das Session-Cookie (nutzt Max-Age=0 unter derselben Domain). */
export function deleteSessionCookie(name: string, domain: string): void {
  if (!domain) return;
  try {
    document.cookie = `${name}=; Domain=${domain}; Path=/; Max-Age=0; SameSite=Lax`;
  } catch { /* ignore */ }
}

/** Erzeugt eine neue Session-ID im ``bb-<uuid>``-Format. */
export function generateSessionId(): string {
  // Prefer cryptographically strong UUID v4 (122 bits entropy, collision-safe).
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return 'bb-' + crypto.randomUUID();
    }
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
      const buf = new Uint8Array(16);
      crypto.getRandomValues(buf);
      return 'bb-' + Array.from(buf, b => b.toString(16).padStart(2, '0')).join('');
    }
  } catch { /* fall through */ }
  // Last-resort fallback for very old browsers
  return 'bb-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12);
}
