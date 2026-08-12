/**
 * Der Ausführer für eine vorbereitete Änderung — und sein Riegel (E4).
 *
 * Der Weg dahin: der MCP-Server **beschreibt** eine bestätigte Änderung, statt
 * sie zu schreiben (E2), das Backend reicht sie als `ChatResponse.prepared_write`
 * durch (E3), und hier wird sie abgesetzt — mit der Anmeldung, die auf der
 * Repository-Seite ohnehin schon besteht. Dadurch trägt die Änderung den Namen
 * einer Person und nicht den eines Sammelkontos, und das Repository braucht
 * dafür keine einzige Zeile Änderung. Bauvorschlag:
 * `docs/plans/2026-08-12-einbettung-ohne-repo-aenderung.md`.
 *
 * **Der Riegel ist der eigentliche Teil dieses Moduls.** Ohne ihn wäre das
 * Widget ein Universal-Ausführer mit fremden Rechten: irgendwer bestimmt die
 * Anfrage, und der Browser setzt sie mit den Rechten der angemeldeten Person ab.
 * Drei Regeln halten das klein:
 *
 * 1. **Nur die Herkunft der Seite.** Die Adresse entsteht aus
 *    `origin() + path` — die Herkunft kommt also nie aus der Anfrage. Eine
 *    relative Anfrage täte es fast auch, folgte aber einem `<base href>` der
 *    Gastgeberseite; hier kann nichts umgelenkt werden.
 * 2. **Nur die Erlaubnisliste.** Methode plus Pfadmuster, hier im Bündel
 *    festgeschrieben — nicht vom Backend geliefert, sonst wäre sie kein Riegel,
 *    sondern eine Bitte. Sie deckt genau die Anfragen ab, die E2 vorbereiten
 *    kann; alles andere wird abgewiesen und nicht abgesetzt.
 * 3. **Erst fragen, wer hier ist.** Eine ungültige Sitzung scheitert bei
 *    edu-sharing **lautlos**: die API antwortet `200` und meldet `esguest`
 *    (gemessen, §1 des Bauvorschlags). Über den Statuscode sähe eine
 *    abgelaufene Sitzung wie ein Erfolg aus — geprüft wird deshalb die
 *    gemeldete `authority`, und ohne Person wird gar nicht erst geschrieben.
 *
 * Was hier NICHT passiert: fragen, ob die Änderung gewollt ist. Vorschau,
 * Rückfrage und Zustimmung liegen im Gespräch, und der Bestätigungs-Wall des
 * Backends lässt je Zug höchstens eine Anfrage heraus. Hier wird ausgeführt,
 * was dort beschlossen wurde — oder eben nicht.
 */

import type { PreparedWriteOut } from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';

/** Die Kennung, die edu-sharing für „gar nicht angemeldet" meldet. */
export const ANONYMOUS_AUTHORITY = 'esguest';

/** Der Endpunkt, der die angemeldete Person nennt (`person.authorityName`). */
const IDENTITY_SUFFIX = '/rest/iam/v1/people/-home-/-me-';

interface WriteRule {
  readonly method: string;
  readonly path: RegExp;
}

/**
 * Das Muster der Sammlungs-Zugehörigkeit, für beide Richtungen dasselbe.
 *
 * Gruppe 1 ist die Wurzel des Repositoriums (`edu-sharing`) — sie steht in der
 * Konfiguration des MCP-Servers und wird deshalb gelesen statt fest verdrahtet;
 * fest verdrahtet wäre sie in einer anders benannten Installation still falsch.
 *
 * Verankert an beiden Enden und ohne `%`, `.` und `/` im Zeichenvorrat der
 * Kennungen: damit kann weder ein Pfadteil angehängt noch aufgestiegen noch
 * eine Abfrage angeklebt werden. Eine Kennung, die eine Kodierung bräuchte,
 * fällt damit durch — der Riegel schließt lieber zu viel als zu wenig.
 */
const COLLECTION_REFERENCE =
  /^\/([A-Za-z0-9_-]{1,64})\/rest\/collection\/v1\/collections\/-home-\/[A-Za-z0-9_-]{1,64}\/references\/[A-Za-z0-9_-]{1,64}$/;

/**
 * Metadaten zu einem Datensatz **vorschlagen** — nicht ihn ändern.
 *
 * Der Datensatz bleibt, wie er ist; hinterlegt wird, was ein Modell für besser
 * hält, und ein Mensch entscheidet später darüber. Genau deshalb steht dieser
 * eine Schreibzugriff über der Sammlungs-Zugehörigkeit hier drin
 * (Nutzer-Entscheid 2026-08-12).
 *
 * **Die Abfrage ist Teil der Regel, nicht Beiwerk.** `type=AI` ist die
 * Herkunftsangabe, die das Repositorium mitspeichert: ein Modell hat das
 * geschrieben. Sie hier festzuschreiben heißt, dass über diesen Weg kein
 * Vorschlag abgesetzt werden kann, der einen Menschen als Urheber behauptet.
 * `version` bleibt offen, weil sie sich am Server ändern darf; die Reihenfolge
 * ist die von `createParams()` und damit fest.
 */
const METADATA_SUGGESTION =
  /^\/([A-Za-z0-9_-]{1,64})\/rest\/suggestions\/v1\/-home-\/[A-Za-z0-9_-]{1,64}\?type=AI&version=[A-Za-z0-9._-]{1,32}$/;

/**
 * Die Erlaubnisliste. Genau die Anfragen, die E2 vorbereiten kann: Material in
 * eine Sammlung legen (`PUT`), wieder herausnehmen (`DELETE`), Metadaten
 * vorschlagen (`POST`).
 *
 * Sie endet hier nicht aus Bequemlichkeit: eine vorbereitete Anfrage ist EINE
 * Anfrage, und Anlegen/Umbenennen/Inhalt-Ändern brauchen mehrere. Kommt ein
 * Werkzeug dazu, gehört sein Muster in diese Liste — bewusst, in einem Zug mit
 * der Erweiterung drüben, und nicht durch eine Antwort über die Leitung.
 */
const RULES: readonly WriteRule[] = [
  { method: 'PUT', path: COLLECTION_REFERENCE },
  { method: 'DELETE', path: COLLECTION_REFERENCE },
  { method: 'POST', path: METADATA_SUGGESTION },
];

function matchRule(write: PreparedWriteOut | null | undefined): RegExpExecArray | null {
  const method = write?.method;
  const path = write?.path;
  if (typeof method !== 'string' || typeof path !== 'string') return null;
  for (const rule of RULES) {
    if (rule.method !== method) continue;
    const treffer = rule.path.exec(path);
    if (treffer) return treffer;
  }
  return null;
}

/** Darf diese eine Anfrage abgesetzt werden? */
export function isAllowedPreparedWrite(write: PreparedWriteOut | null | undefined): boolean {
  return matchRule(write) !== null;
}

/**
 * Der Pfad, unter dem dieselbe Installation sagt, wer angemeldet ist — leer,
 * wenn die Anfrage schon am Riegel scheitert.
 *
 * Abgeleitet aus der Wurzel der Anfrage selbst: so gibt es keinen zweiten
 * Konfigurationsknopf, der auseinanderlaufen könnte, und die Frage kann nirgends
 * hinzeigen, wo die Anfrage nicht ohnehin hindürfte.
 */
export function identityPathFor(write: PreparedWriteOut | null | undefined): string {
  const treffer = matchRule(write);
  return treffer ? `/${treffer[1]}${IDENTITY_SUFFIX}` : '';
}

/** Die fünf Ausgänge des Vorgangs. */
export type PreparedWriteOutcome = 'done' | 'blocked' | 'signed-out' | 'unreachable' | 'failed';

/**
 * Katalog-Schlüssel je Ausgang.
 *
 * Jeder bekommt einen eigenen Satz — wie beim Anmeldevorgang und aus demselben
 * Grund: „nicht angemeldet" verlangt eine Anmeldung, „abgewiesen" ist eine
 * Eigenschaft dieser Installation, „abgelehnt" eine Entscheidung des
 * Repositoriums. Ein gemeinsames „hat nicht geklappt" wäre für die meisten
 * schlicht unwahr. Gemeinsam ist ihnen nur der wichtigste Teil: es wurde
 * nichts geändert.
 */
export function preparedWriteMessageKey(outcome: PreparedWriteOutcome): string {
  switch (outcome) {
    case 'done': return 'prepared.done';
    case 'blocked': return 'prepared.blocked';
    case 'signed-out': return 'prepared.signedOut';
    case 'unreachable': return 'prepared.unreachable';
    default: return 'prepared.failed';
  }
}

/** Was der Ausführer von der Shell braucht (deferred Arrows wie beim Anmelden). */
export interface PreparedWriteContext {
  /** `window.location.origin` — als Funktion, damit der Test ohne Fenster auskommt. */
  origin: () => string;
  /** Einen Satz in den Verlauf schreiben (Bot-Blase). */
  say: (text: string) => void;
  translate: TranslateFn;
  /** Nur für den Test. */
  fetchImpl?: typeof fetch;
}

/** Die gemeldete Person, oder leer wenn die Antwort nichts hergibt. */
function readAuthority(data: unknown): string {
  const person = (data as { person?: { authorityName?: unknown } } | null)?.person;
  return typeof person?.authorityName === 'string' ? person.authorityName : '';
}

/**
 * Die vorbereitete Änderung absetzen und ansagen, was daraus wurde.
 *
 * Wirft nie: jeder Ausgang endet in einem Satz im Verlauf. Eine stumme Panne
 * wäre hier besonders teuer — die Person hat einer Änderung zugestimmt und
 * hätte keinen Anhaltspunkt, ob sie geschehen ist.
 */
export async function runPreparedWrite(
  write: PreparedWriteOut, ctx: PreparedWriteContext,
): Promise<PreparedWriteOutcome> {
  const melde = (outcome: PreparedWriteOutcome): PreparedWriteOutcome => {
    ctx.say(ctx.translate(preparedWriteMessageKey(outcome)));
    return outcome;
  };

  if (!isAllowedPreparedWrite(write)) {
    // Entweder ein Fehler auf unserer Seite oder ein Versuch, an der Liste
    // vorbeizukommen. Beides gehört ins Protokoll: ohne diese Zeile bliebe der
    // einzige Hinweis ein Satz im Chat, den niemand mehr zuordnen kann.
    console.warn('vorbereitete Änderung abgewiesen — nicht auf der Erlaubnisliste:',
      write?.method, write?.path);
    return melde('blocked');
  }
  const identityPath = identityPathFor(write);

  const herkunft = (ctx.origin() || '').replace(/\/+$/, '');
  if (!herkunft) return melde('unreachable');
  const doFetch = ctx.fetchImpl ?? fetch;

  // 1. Wer ist hier angemeldet? Ohne Person wird nicht geschrieben — und ein
  //    stiller Gast-Modus ist genau das, was hier nicht passieren darf.
  let authority = '';
  try {
    const res = await doFetch(`${herkunft}${identityPath}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return melde('unreachable');
    authority = readAuthority(await res.json());
  } catch {
    // Netzfehler, oder die Seite ist gar kein Repositorium und antwortet HTML.
    return melde('unreachable');
  }
  if (!authority) return melde('unreachable');
  if (authority === ANONYMOUS_AUTHORITY) return melde('signed-out');

  // 2. Absetzen. `credentials` ausdrücklich, obwohl same-origin die Vorgabe ist:
  //    dass die Sitzung der Seite mitgeht, ist hier der ganze Sinn der Sache.
  try {
    const res = await doFetch(`${herkunft}${write.path}`, {
      method: write.method,
      credentials: 'same-origin',
      ...(write.body ? { headers: { 'Content-Type': 'application/json' }, body: write.body } : {}),
    });
    if (!res.ok) return melde('failed');
  } catch {
    return melde('failed');
  }

  // Der Satz des Werkzeugs, das die Änderung kennt — es weiß, welches Material
  // in welche Sammlung ging; hier ist davon nur eine Kennung übrig.
  ctx.say(write.done_message?.trim() || ctx.translate('prepared.done'));
  return 'done';
}
