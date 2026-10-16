/**
 * Die Antwort auf eine Frage aus dem Verlauf holen (Paket 7, P2 — P5-2).
 *
 * Bricht der Strom ab, NACHDEM der Server die Frage angenommen hat (`connected`),
 * rechnet er sie zu Ende und speichert die Antwort; seine Sitzungssperre hält
 * bis dahin. Bis Paket 7 schickte das Widget die Frage dann ein zweites Mal
 * (`POST /chat`) — doppelte Kosten, und auf einer anderen Kopie ein paralleler
 * Zug. Jetzt fragt es den Verlauf, bis die Antwort da ist.
 *
 * Nach dem Review: zugeordnet wird über die höchste Nachrichten-ID vor dem Zug
 * (`connected.after_id`, C-4), gefragt mit wachsendem Abstand und mit Rücksicht
 * auf das Ratenlimit (C-3), und die Antwort bringt ihre Ergebnis-Boxen und die
 * Themenseite mit (C-2).
 *
 * Rein: der Lader und das Warten kommen herein (Tests ohne Uhr und Netz).
 */
import type {
  ChatResponse, InlineDocument, PreparedWriteOut, TopicPageView,
} from '../grouping/message-types';
import type { HistoryMessage } from '../stream/chat-api';

/** Abstände zwischen den Abrufen; der letzte gilt danach weiter. Höchstens 15
 *  Abrufe je Minute: das Ratenlimit des Verlaufs gilt je IP und Route (Vorgabe
 *  20/min), hinter einer Schul-NAT für alle Widgets zusammen. */
const ABSTAENDE_MS = [2_000, 3_000, 5_000, 8_000, 10_000];
/** So lange wie der Stale-Wächter des Stroms (B10): Lesefrist 75 s + Puffer. */
const GESAMT_MS = 100_000;
/** Bis dahin steht die Frage im Verlauf — die Sitzungssperre wartet höchstens
 *  20 s, dazu kommen Vorlauf und Seitenkontext. Sonst endete der Zug, ohne sie
 *  abzulegen (Sitzung beschäftigt, Absturz), und eine Antwort kommt nie. */
const FRAGE_FRIST_MS = 40_000;
/** Pause nach einem 429 ohne `Retry-After`. */
const RATENLIMIT_PAUSE_MS = 15_000;
/** Frist je Abruf (Paket 9): ein hängender Abruf zählt sonst nicht und hält auf. */
const ABRUF_FRIST_MS = 15_000;

/** Nur was nach der letzten vor dem Zug bekannten Nachricht kam — ohne ID alles. */
function neuerAls(verlauf: readonly HistoryMessage[], nachId?: number | null): readonly HistoryMessage[] {
  if (typeof nachId !== 'number') return verlauf;
  return verlauf.filter((m) => typeof m['id'] === 'number' && m['id'] > nachId);
}

/** Die Bot-Nachricht nach der LETZTEN gleichen Frage — `null`, solange sie fehlt.
 *  Eine früher schon beantwortete gleiche Frage ist nicht die gesuchte; mit
 *  `nachId` zählt sie auch dann nicht, wenn die neue noch nicht gespeichert ist. */
export function antwortAuf(
  verlauf: readonly HistoryMessage[], frage: string, nachId?: number | null,
): HistoryMessage | null {
  const neu = neuerAls(verlauf, nachId);
  for (let i = neu.length - 1; i >= 0; i--) {
    if (neu[i].role === 'user' && neu[i].content === frage) {
      return neu.slice(i + 1).find((m) => m.role === 'assistant') ?? null;
    }
  }
  return null;
}

export interface NachfrageOptionen {
  /** Höchste Nachrichten-ID vor dem Zug (`connected.after_id`); fehlt sie, wird
   *  nur über den Text zugeordnet. */
  nachId?: number | null;
  /** `true` → nicht weiter fragen (neue Sitzung, Widget entfernt). */
  abgebrochen?: () => boolean;
  /** Bricht die Nachfrage samt laufendem Abruf ab (Widget entfernt, Paket 9). */
  signal?: AbortSignal;
  /** Vermerk an einer Box, die der Verlauf gekürzt hat (C-2). */
  gekuerztHinweis?: string;
  warten?: (ms: number) => Promise<void>;
  /** Die Uhr in Millisekunden (Vorgabe `Date.now`). */
  jetzt?: () => number;
}

/** Ein Abruf mit eigener Frist, abgebrochen auch mit der ganzen Nachfrage. */
async function ladenMitFrist(
  laden: (signal?: AbortSignal) => Promise<HistoryMessage[]>, ganz?: AbortSignal,
): Promise<HistoryMessage[]> {
  const steuerung = new AbortController();
  const frist = setTimeout(() => steuerung.abort(), ABRUF_FRIST_MS);
  const mit = (): void => steuerung.abort();
  ganz?.addEventListener('abort', mit, { once: true });
  try {
    return await laden(steuerung.signal);
  } finally {
    clearTimeout(frist);
    ganz?.removeEventListener('abort', mit);
  }
}

const pause = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Fragt den Verlauf, bis die Antwort da ist — oder gibt auf: nach der
 *  Gesamtfrist, wenn die Frage nach {@link FRAGE_FRIST_MS} noch nicht gespeichert
 *  ist, oder wenn der Zug nicht mehr zählt (auch, wenn das erst während eines
 *  Abrufs geschah). Ein 429 verlängert die Pause (`retryAfterMs`, höchstens bis
 *  zum Ende der Frist), ein Netzfehler ist nur ein Aussetzer.
 *
 *  Paket 9 (Review Paket 7, MINOR 23/24/26): die Fristen zählen die Uhr, nicht nur
 *  die Pausen; jeder Abruf hat eine eigene Frist; `Retry-After: 0` hält den Takt,
 *  ein langes wartet bis zum Ende der Frist und fragt dann noch einmal. */
export async function antwortAusVerlauf(
  laden: (signal?: AbortSignal) => Promise<HistoryMessage[]>,
  frage: string,
  opts: NachfrageOptionen = {},
): Promise<HistoryMessage | null> {
  const warten = opts.warten ?? pause;
  const jetzt = opts.jetzt ?? Date.now;
  const start = jetzt();
  let pausen = 0;
  // Was größer ist: die Uhr oder die Summe der Pausen (Tests warten ohne Uhr).
  const verstrichen = (): number => Math.max(pausen, jetzt() - start);
  const vorbei = (): boolean => !!opts.signal?.aborted || !!opts.abgebrochen?.();
  let frageGesehen = false;
  for (let i = 0; !vorbei(); i++) {
    let abstand = ABSTAENDE_MS[Math.min(i, ABSTAENDE_MS.length - 1)];
    try {
      const verlauf = await ladenMitFrist(laden, opts.signal);
      if (vorbei()) return null;
      const antwort = antwortAuf(verlauf, frage, opts.nachId);
      if (antwort) return antwort;
      frageGesehen ||= neuerAls(verlauf, opts.nachId)
        .some((m) => m.role === 'user' && m.content === frage);
    } catch (e) {
      if (vorbei()) return null;
      const fehler = e as { status?: number; retryAfterMs?: number } | null;
      if (fehler?.status === 429) {
        abstand = Math.max(abstand, fehler.retryAfterMs ?? RATENLIMIT_PAUSE_MS);
      }
    }
    if (!frageGesehen && verstrichen() >= FRAGE_FRIST_MS) return null;
    const rest = GESAMT_MS - verstrichen();
    if (rest <= 0) return null;
    abstand = Math.min(abstand, rest);
    await warten(abstand);
    pausen += abstand;
  }
  return null;
}

/** Die gezeigten Boxen eines Zugs, wie `turn_persist` sie an der Antwort ablegt
 *  (`debug._dokumente`, je Box gedeckelt). Bei `zeige_dokument` steht im Text nur
 *  der Begleitsatz — ohne sie fehlte das Ergebnis. */
function dokumente(debug: Record<string, any> | undefined, hinweis?: string): InlineDocument[] | undefined {
  const roh = debug?.['_dokumente'];
  if (!Array.isArray(roh)) return undefined;
  const boxen = roh
    .filter((d) => d && typeof d === 'object' && typeof d.content === 'string' && d.content.trim())
    .map((d) => ({
      kind: typeof d.kind === 'string' && d.kind ? d.kind : 'ki_material',
      title: typeof d.title === 'string' ? d.title : '',
      content: d.gekuerzt === true && hinweis ? `${d.content}\n\n${hinweis}` : d.content,
    }));
  return boxen.length ? boxen : undefined;
}

function themenseite(debug: Record<string, any> | undefined): TopicPageView | null {
  const v = debug?.['_topic_page_view'];
  return v && typeof v === 'object' && Array.isArray(v.swimlanes) ? (v as TopicPageView) : null;
}

/** Die ausgelieferte Änderung des Zugs (`debug._prepared_write`, Paket 9): reißt
 *  beim „ja“ der Strom ab, löst der Server den Vorgang trotzdem ein, und nur diese
 *  Nachfrage kann die Anfrage noch an die Seite geben. Die Wiederherstellung beim
 *  Laden liest den Eintrag nie — sonst liefe die Änderung erneut. Was die Seite
 *  absetzen darf, prüft die Erlaubnisliste beim Ausführen (E4). */
function vorbereitet(debug: Record<string, any> | undefined): PreparedWriteOut | null {
  const roh = debug?.['_prepared_write'];
  if (!roh || typeof roh !== 'object') return null;
  const { method, path, body, done_message } = roh as Record<string, unknown>;
  if (typeof method !== 'string' || typeof path !== 'string' || !path.startsWith('/')) return null;
  return {
    method, path,
    body: typeof body === 'string' ? body : null,
    done_message: typeof done_message === 'string' ? done_message : '',
  };
}

/** Wie {@link antwortAusVerlauf}, aber als Antwort, wie die Shell sie zeigt —
 *  ohne Schnellantworten: die stehen nicht im Verlauf.
 *
 *  simplify: `turn_persist` speichert die Antwort zuerst ohne Boxen und
 *  Themenseite und ergänzt sie Millisekunden später (F-6; bei M16 nach einem
 *  MCP-Abruf). Trifft ein Abruf genau dazwischen, fehlen sie hier. Ausweg, falls
 *  es auffällt: ein Merker am ersten Schreiben, den das zweite entfernt. */
export async function antwortAusVerlaufHolen(
  laden: (signal?: AbortSignal) => Promise<HistoryMessage[]>,
  frage: string,
  sessionId: string,
  opts: NachfrageOptionen = {},
): Promise<ChatResponse | null> {
  const eintrag = await antwortAusVerlauf(laden, frage, opts);
  if (!eintrag) return null;
  const schreiben = vorbereitet(eintrag.debug);
  // Eine Änderung nur bei sicherer Zuordnung (Review Paket 9): ohne `nachId` zählt
  // allein der Text, und vor dem Speichern der neuen Frage träfe ein früheres „Ja, so
  // ausführen“ — seine Änderung liefe noch einmal. Dann lieber der ehrliche Hinweis.
  if (schreiben && typeof opts.nachId !== 'number') return null;
  return {
    session_id: sessionId,
    content: eintrag.content,
    cards: eintrag.cards ?? [],
    follow_up: '',
    quick_replies: [],
    debug: (eintrag.debug ?? {}) as ChatResponse['debug'],
    page_action: null,
    pagination: null,
    web_links: eintrag.webLinks,
    query_metas: eintrag.queryMetas,
    inline_documents: dokumente(eintrag.debug, opts.gekuerztHinweis),
    topic_page: themenseite(eintrag.debug),
    prepared_write: schreiben,
  };
}
