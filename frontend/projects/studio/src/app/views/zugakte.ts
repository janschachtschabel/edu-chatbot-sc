/**
 * Die Zugakte einer Antwort, gelesen (Paket 18C/D, Phase 4).
 *
 * Seit Phase 1 legt der Server je Zug unter `debug._zugakte` ab, was das Log
 * nicht mehr enthält: jeden Werkzeugaufruf mit seinen Argumenten (wie sie
 * eingingen und wie sie gesendet wurden), Status, Dauer und Fehlertext, die
 * Umschreibungen der Antwort (Typ-Fokus, Wächter) und die Schnellwege. Das
 * Studio bekommt sie über seinen Proxy; die Fehlernummer aus einer Blase führt
 * hierher.
 *
 * **Jedes Feld wird geprüft statt vertraut** — wie in `agent-trace.ts`: der Block
 * ist gespeichertes JSON; was nicht passt, wird leer oder 0, nie eine Ausnahme,
 * die den ganzen Verlauf leert.
 *
 * Reine Logik, ohne DOM prüfbar.
 */
import type { Translate } from '../i18n/studio-language.service';

export interface Werkzeugaufruf {
  readonly name: string;
  /** `ok` | `tool` | `transport` | `timeout` | `auth`; leer, wenn er fehlt. */
  readonly status: string;
  readonly ausCache: boolean;
  readonly dauerMs: number;
  /** Länge der Antwort des Servers — trennt „leer“ von „voll“; `null` ohne Antwort. */
  readonly zeichen: number | null;
  readonly fehler: string;
  /** Formatiertes JSON. */
  readonly argumenteEingang: string;
  /** Formatiertes JSON — leer, wenn gleich den eingegangenen. */
  readonly argumenteGesendet: string;
}

export interface Umschreibung {
  readonly art: string;
  readonly original: string;
  readonly ersatz: string;
  readonly grund: string;
}

export interface Schnellweg {
  readonly art: string;
  readonly thema: string;
}

export interface Zugakte {
  readonly werkzeuge: readonly Werkzeugaufruf[];
  /** Aufrufe über dem Deckel (50 je Zug), nur gezählt. */
  readonly ausgelassen: number;
  readonly umschreibungen: readonly Umschreibung[];
  readonly schnellwege: readonly Schnellweg[];
}

/** So viele Zeichen der Trace-ID nennt die Fehlerblase (`obs/trace_id.FEHLERNUMMER_ZEICHEN`). */
const FEHLERNUMMER_ZEICHEN = 12;

type Row = Readonly<Record<string, unknown>>;

function isRow(value: unknown): value is Row {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
}

function json(value: unknown): string {
  return value === undefined || value === null ? '' : JSON.stringify(value, null, 2);
}

function zeilen(value: unknown): Row[] {
  return Array.isArray(value) ? value.filter(isRow) : [];
}

function werkzeug(row: Row): Werkzeugaufruf[] {
  const name = text(row['name']);
  if (!name) return [];
  const eingang = json(row['argumente_eingang']);
  const gesendet = json(row['argumente_gesendet']);
  const zeichen = row['zeichen'];
  return [{
    name,
    status: text(row['status']),
    ausCache: row['aus_cache'] === true,
    dauerMs: count(row['dauer_ms']),
    zeichen: typeof zeichen === 'number' && Number.isInteger(zeichen) && zeichen >= 0 ? zeichen : null,
    fehler: text(row['fehler']),
    argumenteEingang: eingang,
    argumenteGesendet: gesendet === eingang ? '' : gesendet,
  }];
}

/** Die Akte aus `debug._zugakte`; `null`, wenn nichts darin steht. */
export function readZugakte(raw: unknown): Zugakte | null {
  if (!isRow(raw)) return null;
  const akte: Zugakte = {
    werkzeuge: zeilen(raw['werkzeuge']).flatMap(werkzeug),
    ausgelassen: count(raw['werkzeuge_ausgelassen']),
    umschreibungen: zeilen(raw['umschreibungen']).map((u) => ({
      art: text(u['art']), original: text(u['original']), ersatz: text(u['ersatz']),
      grund: text(u['grund']),
    })),
    schnellwege: zeilen(raw['schnellwege']).map((s) => ({ art: text(s['art']), thema: text(s['thema']) })),
  };
  const leer = akte.werkzeuge.length + akte.ausgelassen + akte.umschreibungen.length
    + akte.schnellwege.length === 0;
  return leer ? null : akte;
}

/** Die Fehlernummer eines Zugs — der Anfang seiner Trace-ID; leer ohne Trace-ID. */
export function fehlernummer(traceId: unknown): string {
  return typeof traceId === 'string' ? traceId.slice(0, FEHLERNUMMER_ZEICHEN) : '';
}

/** Eine `Map`, damit ein Wert wie `toString` nicht den Objekt-Prototyp trifft. */
/** `ok` steht nicht darin: es heißt in beiden Sprachen so und kommt roh durch. */
const STATUS: ReadonlyMap<string, string> = new Map([
  ['tool', 'st.za.status.tool'],
  ['transport', 'st.za.status.transport'],
  ['timeout', 'st.za.status.timeout'],
  ['auth', 'st.za.status.auth'],
]);

const UMSCHREIBUNG: ReadonlyMap<string, string> = new Map([
  ['typ_fokus', 'st.za.rewrite.typ_fokus'],
  ['waechter', 'st.za.rewrite.waechter'],
]);

const SCHNELLWEG: ReadonlyMap<string, string> = new Map([
  ['canvas', 'st.za.shortcut.canvas'],
  ['lernpfad', 'st.za.shortcut.lernpfad'],
]);

/** Erlaubnisliste wie `stopReasonLabel`: Unbekanntes kommt roh durch. */
export function statusLabel(status: string, t: Translate): string {
  const key = STATUS.get(status);
  return key ? t(key) : status;
}

export function umschreibungLabel(art: string, t: Translate): string {
  const key = UMSCHREIBUNG.get(art);
  return key ? t(key) : art;
}

export function schnellwegLabel(art: string, t: Translate): string {
  const key = SCHNELLWEG.get(art);
  return key ? t(key) : art;
}
