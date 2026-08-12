/**
 * Anmeldung beim WLO-MCP-Server (C5-c1) — OAuth 2.1 als **öffentlicher** Client.
 *
 * Warum dieser Weg und kein Einfügen von Hand: die Seiten, auf denen ein
 * Passwort getippt wird (`/auth*`, `/oauth/authorize`), senden bewusst keinen
 * CORS-Header — ein Anmeldeformular im Widget ist dort also gar nicht möglich,
 * und es wäre auch das falsche Muster: Menschen daran zu gewöhnen, WLO-Zugangs-
 * daten in ein Feld auf einer fremden Seite zu tippen, ist genau die Gestalt
 * eines Phishing-Angriffs. Der Vorgang hier führt sie stattdessen auf die
 * Herkunft des MCP-Servers, wo die Adresszeile prüfbar ist.
 *
 * `/oauth/register` und `/oauth/token` tragen dagegen den CORS-Platzhalter
 * (gemessen 2026-08-10 in `http-app.ts`), sind also aus dem Browser erreichbar.
 *
 * **Kein Client-Geheimnis.** Die Discovery meldet
 * `token_endpoint_auth_methods_supported: ["none"]`; PKCE ist das Einzige, was
 * einen abgefangenen Code wertlos macht.
 *
 * ⚠️ Zwei Prüfungen tragen die Sicherheit dieses Vorgangs, und beide sind
 * gepinnt: die Rückmeldung muss aus **genau dem Fenster** kommen, das wir
 * geöffnet haben (`event.source`), und ihr `state` muss zu diesem Versuch
 * gehören. Fällt eine weg, kann jedes andere Skript der Gastgeberseite dem
 * Widget einen fremden Code unterschieben.
 *
 * Der Rückgabewert unterscheidet **abgelehnt** von **kaputt**: „ablehnen" ist
 * eine Entscheidung, keine Panne, und die Oberfläche muss anders darauf
 * antworten.
 */

import { writeAccessBlock } from './mcp-access';
import { buildAuthorizeUrl, codeChallenge, createCodeVerifier, createState } from './oauth-pkce';

/** Die Adressen aus dem Discovery-Dokument (RFC 8414), soweit wir sie nutzen. */
export interface OauthEndpoints {
  authorization_endpoint: string;
  token_endpoint: string;
  registration_endpoint?: string;
}

/** Injizierbare Ränder — Netz und Fenster; im Test beide ersetzt. */
export interface OauthDeps {
  fetchImpl?: typeof fetch;
  openWindow?: (url: string) => Window | null;
  /** Wartezeit auf die Rückmeldung; Default 5 Minuten (eine Anmeldung dauert). */
  timeoutMs?: number;
}

/** Warum es nicht geklappt hat — jeder Fall braucht eine andere Antwort. */
export type SignInFailure =
  | 'unavailable'   // dieser Betrieb hat die Anmeldung gar nicht an
  | 'popup-blocked' // Browser hat das Fenster verhindert
  | 'denied'        // der Mensch hat abgelehnt
  | 'timeout'       // keine (gültige) Rückmeldung
  | 'exchange-failed';

export type SignInResult = { ok: true } | { ok: false; reason: SignInFailure };

/** Nachricht, die die Rückruf-Seite an das öffnende Fenster schickt. */
interface CallbackMessage {
  source?: string;
  code?: string;
  state?: string;
  error?: string;
}

const MESSAGE_SOURCE = 'boerdi-oauth';

/**
 * Liest das Discovery-Dokument. `null`, wenn dieser Betrieb keine Anmeldung
 * anbietet — ohne `WLO_AUTH_PRIVATE_KEY` antworten die Adressen mit 404, und
 * das ist kein Fehler, sondern eine Betriebsentscheidung.
 */
export async function discoverEndpoints(
  mcpBaseUrl: string,
  deps: OauthDeps = {},
): Promise<OauthEndpoints | null> {
  const fetchImpl = deps.fetchImpl ?? globalThis.fetch;
  const base = mcpBaseUrl.replace(/\/+$/, '');
  try {
    const resp = await fetchImpl(`${base}/.well-known/oauth-authorization-server`);
    if (!resp.ok) return null;
    const doc = (await resp.json()) as OauthEndpoints;
    return doc?.authorization_endpoint && doc?.token_endpoint ? doc : null;
  } catch {
    return null;
  }
}

/** Meldet uns als öffentlichen Client an (RFC 7591, dort offen). */
export async function registerClient(
  registrationEndpoint: string,
  redirectUri: string,
  deps: OauthDeps = {},
): Promise<string | null> {
  const fetchImpl = deps.fetchImpl ?? globalThis.fetch;
  try {
    const resp = await fetchImpl(registrationEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_name: 'BOERDi Chat',
        redirect_uris: [redirectUri],
        grant_types: ['authorization_code'],
        response_types: ['code'],
        token_endpoint_auth_method: 'none',
      }),
    });
    if (!resp.ok) return null;
    const doc = (await resp.json()) as { client_id?: string };
    return doc?.client_id ?? null;
  } catch {
    return null;
  }
}

/** Felder des Code-Tauschs. */
export interface ExchangeOptions {
  tokenEndpoint: string;
  clientId: string;
  code: string;
  codeVerifier: string;
  redirectUri: string;
}

/** Tauscht den Code gegen den Zugangsblock. `null`, wenn der Server ablehnt. */
export async function exchangeCode(
  opts: ExchangeOptions,
  deps: OauthDeps = {},
): Promise<string | null> {
  const fetchImpl = deps.fetchImpl ?? globalThis.fetch;
  const felder = new URLSearchParams({
    grant_type: 'authorization_code',
    code: opts.code,
    redirect_uri: opts.redirectUri,
    client_id: opts.clientId,
    code_verifier: opts.codeVerifier,
  });
  try {
    const resp = await fetchImpl(opts.tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: felder.toString(),
    });
    if (!resp.ok) return null;
    const doc = (await resp.json()) as { access_token?: string };
    return doc?.access_token ?? null;
  } catch {
    return null;
  }
}

/** Wartet auf die Rückmeldung des Anmeldefensters — oder auf die Zeitgrenze. */
function warteAufRueckmeldung(
  fenster: Window,
  state: string,
  timeoutMs: number,
): Promise<CallbackMessage | null> {
  return new Promise((resolve) => {
    let fertig = false;
    const beenden = (wert: CallbackMessage | null) => {
      if (fertig) return;
      fertig = true;
      window.removeEventListener('message', horcher);
      clearTimeout(uhr);
      resolve(wert);
    };
    const horcher = (e: MessageEvent) => {
      // Beide Prüfungen sind nötig: das Fenster, WEIL sonst jedes Skript der
      // Gastgeberseite senden könnte — und der state, WEIL ein mitgelesener
      // state sonst aus einem anderen Fenster wiederverwendet würde.
      if (e.source !== fenster) return;
      const m = e.data as CallbackMessage;
      if (!m || m.source !== MESSAGE_SOURCE) return;
      if (m.error) return beenden(m);
      if (m.state !== state) return;
      beenden(m);
    };
    const uhr = setTimeout(() => beenden(null), timeoutMs);
    window.addEventListener('message', horcher);
  });
}

/**
 * Der ganze Vorgang: Discovery → Registrierung → Zustimmungsfenster → Tausch →
 * Block ablegen.
 *
 * `openWindow` muss aus einer **Nutzergeste** heraus gerufen werden (Klick),
 * sonst blockt der Browser das Fenster — deshalb ist `popup-blocked` ein
 * eigener Fall und keine allgemeine Panne.
 */
export async function signIn(
  mcpBaseUrl: string,
  redirectUri: string,
  deps: OauthDeps = {},
): Promise<SignInResult> {
  const endpunkte = await discoverEndpoints(mcpBaseUrl, deps);
  if (!endpunkte?.registration_endpoint) return { ok: false, reason: 'unavailable' };

  const clientId = await registerClient(endpunkte.registration_endpoint, redirectUri, deps);
  if (!clientId) return { ok: false, reason: 'unavailable' };

  const verifier = createCodeVerifier();
  const state = createState();
  const url = buildAuthorizeUrl({
    authorizationEndpoint: endpunkte.authorization_endpoint,
    clientId,
    redirectUri,
    state,
    codeChallenge: await codeChallenge(verifier),
    scope: 'wlo',
  });

  const oeffnen = deps.openWindow ?? ((u: string) => window.open(u, 'boerdi-wlo-anmeldung',
    'width=520,height=680'));
  const fenster = oeffnen(url);
  if (!fenster) return { ok: false, reason: 'popup-blocked' };

  const antwort = await warteAufRueckmeldung(fenster, state, deps.timeoutMs ?? 300_000);
  try {
    fenster.close();
  } catch {
    /* schon zu — kein Grund, den Vorgang scheitern zu lassen */
  }

  if (!antwort) return { ok: false, reason: 'timeout' };
  if (antwort.error) return { ok: false, reason: 'denied' };
  if (!antwort.code) return { ok: false, reason: 'timeout' };

  const block = await exchangeCode(
    { tokenEndpoint: endpunkte.token_endpoint, clientId, code: antwort.code,
      codeVerifier: verifier, redirectUri },
    deps,
  );
  if (!block || !writeAccessBlock(block)) return { ok: false, reason: 'exchange-failed' };
  return { ok: true };
}
