/**
 * Anmeldung aus der Sitzung der Gastgeberseite — der zweite stille Weg neben
 * `ticket-login.ts` (Plan 2026-11-15, SA-1 bis SA-6).
 *
 * Der Fall: das Widget sitzt in einer Seite des Repositorys, und dort ist schon
 * jemand angemeldet. Der MCP-Server tauscht diese Sitzung gegen einen
 * gewöhnlichen Zugangsblock. Der Pfad dafür liegt auf dem Host des Repositorys
 * (nur dorthin schickt der Browser das Sitzungs-Cookie) und führt zu unserem
 * Backend, das den Tausch weiterreicht (Plan SA-16) — oder, wenn der MCP dort
 * eingehängt ist, direkt zu ihm; für dieses Modul ist beides gleich. Das Cookie
 * selbst sieht es nie: es ist für JavaScript nicht lesbar.
 *
 * ⚠️ Security-relevant. Vier Regeln, jede mit ihrem Grund:
 *
 * 1. **Nur auf der eigenen Herkunft, nur ein Pfad auf `/auth/session`.** Die
 *    Adresse kommt aus dem Config-Bündel, also über das Netz. Sie darf das
 *    Widget nicht zu einem beliebigen POST mit den Cookies der Seite bringen.
 *    Die Anfrage entsteht aus `origin() + Pfad`, nie aus der Adresse selbst
 *    (dieselbe Regel wie in `prepared-write.ts`).
 * 2. **Erst fragen, wer da ist.** Ein Gast wird nicht getauscht. Geprüft wird
 *    die gemeldete Person, nie der Status: eine ungültige Sitzung antwortet
 *    beim Repository still als Gast mit 200.
 * 3. **Die Person vergleichen.** Nennt der Tausch jemand anderen als die Seite,
 *    wird der Block verworfen.
 * 4. **Nur im Arbeitsspeicher** (`holdAccessBlock`). Nach dem Neuladen wird
 *    neu getauscht; ein abgelegter Block überlebte einen Wechsel der Person.
 *
 * Dazu `readSessionPerson`: die Shell fragt damit vor jedem Zug, ob die Seite
 * noch dieselbe Person zeigt (SA-13) — ein Wechsel der Person ohne Neuladen
 * fiele sonst erst auf, wenn das Repository den alten Block ablehnt.
 *
 * Still wie der Ticket-Tausch: das Ergebnis zeigt der Anmelde-Knopf, für die
 * Betreiberseite bleibt eine `console.warn`-Zeile in der Shell.
 */

import { clearAccessBlock, holdAccessBlock, sessionBlockOwner } from './mcp-access';
import { ANONYMOUS_AUTHORITY, IDENTITY_SUFFIX, readAuthority } from './prepared-write';
import { wartezeitMs } from './ticket-login';

/** Die Ausgänge. `done` legt einen Block ab. Jeder Ausgang nach der Frage „wer ist da“ kann
 *  einen Block aus der Sitzung verworfen haben, der einer anderen Person gehörte. */
export type SessionLoginOutcome =
  | 'done'
  /** Kein Weg für diese Seite (keine Adresse, andere Herkunft, unbrauchbarer Pfad). */
  | 'off'
  /** Hier ist niemand angemeldet (Gast), oder die Tauschstelle sieht keine Sitzung. */
  | 'no-session'
  /** Der Weg ist an diesem MCP-Server oder am Repository nicht eingerichtet. */
  | 'unavailable'
  /** Diese Seite steht nicht auf der Liste des MCP-Servers. */
  | 'not-allowed'
  | 'rejected'
  | 'unreachable'
  /** Der Tausch nennt eine andere Person als die Seite. */
  | 'mismatch'
  | 'store-failed';

export interface SessionLoginResult {
  outcome: SessionLoginOutcome;
  /** Anzeigename der Person, nur bei `done` und nur, wenn der Server ihn nennt. */
  displayName: string;
  /** Die Person, für die der Block gilt (`authorityName` der Seite), nur bei `done`. */
  authority: string;
}

/** Was der Vorgang von der Shell braucht (deferred Arrows wie beim Ticket). */
export interface SessionLoginContext {
  /** Adresse des Tauschs aus dem Config-Bündel (`mcp_session_url`). Leer = nicht angeboten. */
  sessionUrl: () => string;
  /** `window.location.origin` — als Funktion, damit der Test ohne Fenster auskommt. */
  origin: () => string;
  /** Nur für den Test. */
  fetchImpl?: typeof fetch;
  /** Nur für den Test: das Warten vor dem zweiten Versuch. */
  warten?: (ms: number) => Promise<void>;
  /** Nur für den Test: die Frist eines Abrufs (Vorgabe `ABRUF_FRIST_MS`). */
  fristMs?: number;
}

/** Die zwei Pfade des Vorgangs, beide auf der Herkunft der Seite. */
export interface SessionLoginTarget {
  exchangePath: string;
  identityPath: string;
}

/**
 * Der Pfad des Tauschs: die Wurzel des Repositorys (Gruppe 1, etwa `edu-sharing`),
 * höchstens sechs schlichte Stufen, dann `/auth/session`.
 *
 * Verankert an beiden Enden, ohne `%`, `.` und leere Stufen: es lässt sich weder
 * aufsteigen noch etwas anhängen. Die Wurzel ist Pflicht — unterhalb von ihr gilt
 * das Sitzungs-Cookie, und aus ihr entsteht der Wer-bin-ich-Pfad.
 */
const EXCHANGE_PATH = /^\/([A-Za-z0-9_-]{1,64})(?:\/[A-Za-z0-9_-]{1,64}){0,6}\/auth\/session$/;

/** Höchstlänge des Anzeigenamens am Knopf. */
const NAME_MAX = 80;

/** Frist je Abruf. Ohne sie bliebe ein hängender Tausch für immer „laufend“, und jeder spätere
 *  Anlass (Frist, Abweisung) hinge sich an ihn. */
export const ABRUF_FRIST_MS = 10_000;

/** Ein Abbruch-Signal nach `ms`. Ältere Browser kennen `AbortSignal.timeout` nicht; dort über
 *  einen eigenen Zeitgeber — ohne Frist hielte ein hängender Abruf jeden Zug auf. */
function frist(ms: number): { signal?: AbortSignal } {
  if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
    return { signal: AbortSignal.timeout(ms) };
  }
  if (typeof AbortController === 'undefined') return {};
  const abbruch = new AbortController();
  setTimeout(() => abbruch.abort(), ms);
  return { signal: abbruch.signal };
}

/**
 * Die ganze Adresse, Zeichen für Zeichen, wie der Betrieb sie eingetragen hat: Schema, Host (Name
 * oder IPv6 in Klammern), Port, Pfad (Gruppe 1). Dasselbe Muster prüft das Backend
 * (`domain/mcp_herkunft.py`, `_TAUSCH_ADRESSE`). Was ein Browser anders liest, als es dasteht —
 * Rückstrich, Leerraum, Punkt-Stufen, Kodierung, ein leerer Port —, fällt hier durch: geprüft
 * werden soll der eingetragene Wert, nicht seine Deutung.
 */
const ADRESSE = /^https?:\/\/(?:[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|\[[0-9A-Fa-f:.]{2,45}\])(?::[0-9]{1,5})?(\/[A-Za-z0-9_/-]{1,512})$/;

/**
 * Gilt der Weg auf dieser Seite? Gibt die zwei Pfade zurück, sonst `null`.
 *
 * @param url Die eingestellte Adresse (`scheme://host/…/auth/session`).
 * @param origin Die Herkunft der Seite, in der das Widget sitzt.
 */
export function sessionLoginTarget(url: string, origin: string): SessionLoginTarget | null {
  const herkunft = (origin || '').trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(herkunft)) return null;
  const roh = (url || '').trim();
  const geschrieben = ADRESSE.exec(roh);
  if (!geschrieben) return null;
  let ziel: URL;
  try {
    ziel = new URL(roh);
  } catch {
    return null;
  }
  if (ziel.origin !== herkunft) return null;
  if (ziel.username || ziel.password || ziel.search || ziel.hash) return null;
  const treffer = EXCHANGE_PATH.exec(ziel.pathname);
  // Der Pfad, den der Browser liest, muss der geschriebene sein.
  if (!treffer || geschrieben[1] !== ziel.pathname) return null;
  return { exchangePath: ziel.pathname, identityPath: `/${treffer[1]}${IDENTITY_SUFFIX}` };
}

const ende = (outcome: SessionLoginOutcome, displayName = '', authority = ''): SessionLoginResult =>
  ({ outcome, displayName, authority });

/**
 * Wer ist auf dieser Seite angemeldet? Die `authorityName` des Repositorys (`esguest` für einen
 * Gast) — oder `null`, wenn es keine Aussage gibt: der Weg gilt hier nicht, das Netz ist weg,
 * die Antwort ist keine des Repositorys. `null` ist nie ein Urteil über die Sitzung.
 *
 * `redirect: 'error'`: ein Repository leitet diese Abfrage nicht um.
 */
export async function readSessionPerson(ctx: SessionLoginContext): Promise<string | null> {
  const herkunft = (ctx.origin() || '').trim().replace(/\/+$/, '');
  const ziel = sessionLoginTarget(ctx.sessionUrl(), herkunft);
  if (!ziel) return null;
  try {
    const res = await (ctx.fetchImpl ?? fetch)(`${herkunft}${ziel.identityPath}`, {
      credentials: 'same-origin',
      redirect: 'error',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      ...frist(ctx.fristMs ?? ABRUF_FRIST_MS),
    });
    // 401 auf der eigenen Herkunft: ein Repository ohne Gast-Zugang sagt so „niemand
    // angemeldet“ (gemessen an Staging mit `DisableGuest`). Wie ein Gast zu lesen — sonst fiele
    // das Abmelden dort nie auf, und der Block bliebe, bis der Server ihn ablehnt.
    if (res.status === 401) return ANONYMOUS_AUTHORITY;
    if (!res.ok) return null;
    return readAuthority(await res.json()) || null;
  } catch {
    // Netzfehler, Frist, oder die Seite ist gar kein Repository und antwortet HTML.
    return null;
  }
}

/**
 * Die Sitzung der Seite gegen einen Zugangsblock tauschen und ihn im Arbeitsspeicher halten.
 *
 * Wirft nie; jeder Ausgang ist ein Wort, das die Shell protokollieren kann. Ein Fehlschlag
 * lässt einen vorhandenen Block stehen — mit einer Ausnahme: ein Block aus der Sitzung, der für
 * eine andere Person gilt, als die Seite jetzt zeigt, fällt weg.
 */
export async function runSessionLogin(ctx: SessionLoginContext): Promise<SessionLoginResult> {
  const herkunft = (ctx.origin() || '').trim().replace(/\/+$/, '');
  const ziel = sessionLoginTarget(ctx.sessionUrl(), herkunft);
  if (!ziel) return ende('off');
  const doFetch = ctx.fetchImpl ?? fetch;

  // 1. Wer ist hier angemeldet?
  const person = await readSessionPerson(ctx);
  if (person === null) return ende('unreachable');
  // Ein Block aus der Sitzung, den eine frühere Instanz des Widgets hinterließ, gilt für eine
  // andere Person, als die Seite jetzt zeigt: er gehört nicht mehr hierher (Review 2026-11-15).
  const gehalten = sessionBlockOwner();
  if (gehalten !== null && gehalten.authority !== person) clearAccessBlock();
  if (person === ANONYMOUS_AUTHORITY) return ende('no-session');

  // 2. Tauschen. Nur das Cookie der Seite geht mit — keine `Authorization`, kein Rumpf mit Inhalt.
  const tauschen = () => doFetch(`${herkunft}${ziel.exchangePath}`, {
    method: 'POST',
    credentials: 'same-origin',
    redirect: 'error',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    ...frist(ctx.fristMs ?? ABRUF_FRIST_MS),
  });
  let data: { ok?: unknown; block?: unknown; authority?: unknown; displayName?: unknown };
  try {
    let res = await tauschen();
    // 503 `upstream_unreachable`: das Repository hat die Prüfung nicht beantwortet — kein Urteil
    // über die Sitzung. 429: zu viele Anmeldungen von dieser Adresse (hinter einem gemeinsamen
    // Anschluss kein seltener Fall). Beide nennen eine Wartezeit; danach EINMAL erneut.
    if (res.status === 503 || res.status === 429) {
      await (ctx.warten ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms))))(await wartezeitMs(res));
      res = await tauschen();
      if (res.status === 503) return ende('unreachable');
    }
    if (res.status === 400) return ende('no-session');
    if (res.status === 403) return ende('not-allowed');
    if (res.status === 404) return ende('unavailable');
    if (!res.ok) return ende('rejected');
    try {
      data = await res.json();
    } catch {
      // 200 ohne JSON: der Pfad führt nicht zur Tauschstelle, das Repository antwortet mit einer Seite.
      return ende('unavailable');
    }
  } catch {
    return ende('unreachable');
  }

  if (!data || data.ok !== true || typeof data.block !== 'string') return ende('rejected');
  // 3. Dieselbe Person wie die Seite? Ohne genannte Person gilt der Tausch nicht. Der Server
  //    nennt den Kontonamen bereinigt (Leerraum zusammengezogen, Steuerzeichen entfernt, bei 120
  //    Zeichen gekappt): ein Konto mit solchem Namen bleibt hier bei `mismatch` — sicher, nur
  //    ohne Anmeldung.
  if (data.authority !== person) return ende('mismatch');
  // 4. `holdAccessBlock` prüft die Form noch einmal und lehnt ab, was kein Block ist.
  const name = typeof data.displayName === 'string' ? data.displayName.trim().slice(0, NAME_MAX) : '';
  if (!holdAccessBlock(data.block, { authority: person, displayName: name })) return ende('store-failed');
  return ende('done', name, person);
}
