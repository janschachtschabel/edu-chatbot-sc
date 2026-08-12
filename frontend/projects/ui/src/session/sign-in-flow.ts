/**
 * Der Anmeldevorgang, wie ihn der Chat erlebt (C5-c2) — die Naht zwischen dem
 * Klick auf den Chip und dem Satz, der danach in der Blase steht.
 *
 * `mcp-oauth.ts` (C5-c1) kennt das Protokoll und gibt einen Ausgang zurück;
 * hier wird daraus eine Nachricht. Getrennt gehalten, weil das zwei
 * Verantwortungen sind — und weil diese hier ohne TestBed prüfbar bleibt
 * (dasselbe Muster wie `shell/input-routing.ts`: reine Funktionen hinter einem
 * Kontext, die Shell hält nur den dünnen Delegaten).
 *
 * **Jeder Ausgang bekommt einen eigenen Satz.** „Abgelehnt" ist eine
 * Entscheidung der Person, „blockiert" ein Hinweis mit Handlungsanweisung,
 * „nicht angeboten" eine Eigenschaft der Installation. Ein gemeinsames „hat
 * nicht geklappt" wäre für fünf der sechs Fälle unwahr — und im ersten Fall
 * würde es einer Person, die gerade bewusst abgelehnt hat, einen Fehler
 * unterstellen.
 */

import type { TranslateFn } from '../i18n/i18n';
import { signIn } from './mcp-oauth';
import type { OauthDeps, SignInResult } from './mcp-oauth';

/**
 * Rückkehr-Ziel des Anmeldefensters. Eine Datei im Widget-Bündel, keine Route
 * — die Widget-Pfade stehen im eingefrorenen OpenAPI-Vertrag, und der
 * vorhandene Sammelpfad `/widget/{asset_name}` liefert sie mit aus.
 */
export const OAUTH_CALLBACK_PATH = '/widget/oauth-callback.html';

/** Katalog-Schlüssel für den Ausgang des Vorgangs. */
export function signInMessageKey(result: SignInResult): string {
  if (result.ok) return 'auth.done';
  switch (result.reason) {
    case 'denied': return 'auth.denied';
    case 'popup-blocked': return 'auth.popupBlocked';
    case 'unavailable': return 'auth.unavailable';
    case 'timeout': return 'auth.timeout';
    default: return 'auth.failed';
  }
}

/**
 * Die Adresse der Rückkehr-Seite.
 *
 * `apiUrl` ist gesetzt, wenn das Backend woanders steht als die
 * Gastgeberseite; sonst liegt das Widget-Bündel auf derselben Herkunft. In
 * beiden Fällen gilt: die Seite kommt vom BACKEND, nie von der Gastgeberseite
 * — die kennt sie gar nicht.
 */
export function callbackUrl(apiUrl: string, origin: string): string {
  const basis = (apiUrl || '').trim().replace(/\/+$/, '') || (origin || '').replace(/\/+$/, '');
  return `${basis}${OAUTH_CALLBACK_PATH}`;
}

/** Was der Vorgang von der Shell braucht (deferred Arrows wie beim Routing). */
export interface SignInFlowContext {
  /** Herkunft des MCP-Servers aus dem öffentlichen Config-Bündel. Leer heisst
   *  „diese Installation bietet keine Anmeldung an". */
  mcpAuthBase: () => string;
  /** `[apiUrl]` der Shell; leer = gleiche Herkunft wie die Seite. */
  apiUrl: () => string;
  /** `window.location.origin` — als Funktion, damit der Test ohne Fenster auskommt. */
  origin: () => string;
  /** Einen Satz in den Verlauf schreiben (Bot-Blase). */
  say: (text: string) => void;
  translate: TranslateFn;
  /** Nur für den Test: der eigentliche Vorgang. */
  signInImpl?: (base: string, redirectUri: string, deps?: OauthDeps) => Promise<SignInResult>;
}

/**
 * Anmeldung starten und das Ergebnis ansagen.
 *
 * MUSS aus einer Nutzergeste heraus laufen (Chip-Klick) — sonst blockt der
 * Browser das Fenster, und der Vorgang endet in `popup-blocked`.
 */
export async function runSignIn(ctx: SignInFlowContext): Promise<void> {
  const basis = (ctx.mcpAuthBase() || '').trim();
  if (!basis) {
    // Ohne Adresse gar nicht erst ein Fenster öffnen: das Ergebnis stünde
    // ohnehin fest, und ein aufblitzendes leeres Fenster wäre irritierend.
    ctx.say(ctx.translate('auth.unavailable'));
    return;
  }
  const vorgang = ctx.signInImpl ?? signIn;
  let ergebnis: SignInResult;
  try {
    ergebnis = await vorgang(basis, callbackUrl(ctx.apiUrl(), ctx.origin()));
  } catch {
    // Der Vorgang fängt Netz- und Fensterfehler selbst ab, aber nicht alles:
    // `crypto.subtle` fehlt auf unsicherer Herkunft (http://) und WIRFT. Ohne
    // diesen Zweig bliebe eine abgewiesene Zusage übrig — der Chip täte
    // scheinbar nichts, und der Fehler landete als unbeachtete Zusage in der
    // Konsole statt im Chat.
    ergebnis = { ok: false, reason: 'exchange-failed' };
  }
  ctx.say(ctx.translate(signInMessageKey(ergebnis)));
}
