/**
 * PKCE und die URLs des Anmeldevorgangs (C5-c1) — reine Funktionen, kein Fenster,
 * kein Netz.
 *
 * Der WLO-MCP-Server spricht OAuth 2.1 nach der MCP-Spezifikation; seine
 * Discovery meldet `code_challenge_methods_supported: ["S256"]` und
 * `token_endpoint_auth_methods_supported: ["none"]` (live geprüft 2026-08-10).
 * Wir sind also ein **öffentlicher** Client: es gibt kein Client-Geheimnis, und
 * PKCE ist das Einzige, was einen abgefangenen Code wertlos macht.
 *
 * ⚠️ `plain` ist kein Rückfall. Der „Beweis" wäre dann genau die Zeichenkette,
 * die vorher in der Adresszeile stand — der Server bietet es zu Recht nicht an,
 * und wir fragen es nicht nach.
 *
 * Alles hier nutzt WebCrypto aus der Plattform (Entscheidungsleiter Stufe 3):
 * keine Abhängigkeit für Zufall oder SHA-256.
 */

/** Zeichenvorrat des `code_verifier` (RFC 7636 §4.1: unreserved characters). */
const UNRESERVED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';

/** Base64url ohne Füllzeichen — die Kodierung, die RFC 7636 §4.2 vorschreibt. */
function base64url(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Ein zufälliges Wort aus dem unreservierten Vorrat, `length` Zeichen lang. */
function randomUnreserved(length: number): string {
  const buf = new Uint8Array(length);
  crypto.getRandomValues(buf);
  // Modulo über 64 Zeichen bei 256 Werten: 256/64 = 4, geht glatt auf, also
  // keine Verzerrung — bei einem Vorrat, der nicht teilt, wäre das falsch.
  return Array.from(buf, (b) => UNRESERVED[b % UNRESERVED.length]).join('');
}

/**
 * Ein frischer `code_verifier` (64 Zeichen, innerhalb der 43–128 aus §4.1).
 *
 * 64 statt der Mindestlänge, weil das Geheimnis nichts kostet und die Grenze
 * eine Untergrenze ist.
 */
export function createCodeVerifier(): string {
  return randomUnreserved(64);
}

/** Der `state` — bindet die Rückkehr an genau diesen Anmeldeversuch. */
export function createState(): string {
  return randomUnreserved(43);
}

/** Die S256-Ableitung: `base64url(SHA-256(verifier))`. */
export async function codeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(digest));
}

/** Felder, aus denen die Zustimmungs-Adresse gebaut wird. */
export interface AuthorizeUrlOptions {
  authorizationEndpoint: string;
  clientId: string;
  redirectUri: string;
  state: string;
  codeChallenge: string;
  scope: string;
}

/** Die Adresse, auf die das Anmeldefenster geschickt wird. */
export function buildAuthorizeUrl(opts: AuthorizeUrlOptions): string {
  const u = new URL(opts.authorizationEndpoint);
  u.searchParams.set('response_type', 'code');
  u.searchParams.set('client_id', opts.clientId);
  u.searchParams.set('redirect_uri', opts.redirectUri);
  u.searchParams.set('state', opts.state);
  u.searchParams.set('code_challenge', opts.codeChallenge);
  u.searchParams.set('code_challenge_method', 'S256');
  u.searchParams.set('scope', opts.scope);
  return u.toString();
}

/** Was die Rückkehr-Adresse trägt — genau eines von `code` und `error`. */
export interface CallbackParams {
  code: string | null;
  state: string | null;
  error: string | null;
}

/**
 * Liest `?code=…&state=…` bzw. `?error=…` aus einer Rückkehr-URL.
 *
 * `error` bleibt eine eigene Angabe: „ablehnen" ist eine Entscheidung des
 * Menschen (`access_denied`) und darf nicht als Panne erscheinen.
 */
export function readCallbackParams(search: string): CallbackParams {
  const p = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  return {
    code: p.get('code'),
    state: p.get('state'),
    error: p.get('error'),
  };
}
