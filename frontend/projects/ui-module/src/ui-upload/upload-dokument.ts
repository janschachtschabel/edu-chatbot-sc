/**
 * Strukturdokumente im Chat lesen lassen (Paket U3-2c, Plan §16.6) — Regeln ohne DOM.
 *
 * Das Modul lädt die markierten Strukturdokumente über den Host hoch (`host.hochladen`, Fähigkeit
 * `hochladen`); das Backend liest jedes und gibt nur den Befund zurück. Daraus entsteht die Antwort
 * `aktion: "dokument"`. Plan 2026-11-16, TG-1 (G-E4): ohne Ziel — das Feld stellt nur bereit; was
 * mit den Dokumenten geschieht, entscheiden die nächsten Schritte eines Ablaufs oder die KI mit der
 * Person (früher `ziel: "themenbaum"`; alte Antworten nimmt das Backend noch an).
 *
 * Plan 2026-11-16, TG-3e: bis zu fünf markierte Dokumente, nacheinander gelesen — jedes über einen
 * eigenen `POST /api/ui/dokumente`. Die Antwort trägt das erste in `dokument` (wie bisher) und, bei
 * mehreren, alle in `dokumente`. Mit einem Dokument bleibt die Antwort wie vorher.
 *
 * Erlaubt ist das nur, wenn das System es im Block erlaubt (`schalter.dokument_im_chat` — Studio und
 * Anmeldung) und ein Strukturdokument markiert ist; welche Dateiarten gehen, regelt schon die Rolle
 * (`kannStrukturSein`).
 */
import { antwortDaten, einZeiler, type UploadAntwort } from './upload-antwort';
import type { ErfassteDatei, Erfassung } from './upload-erfassen';

const MAX_VORSCHAU = 8;
const GLIEDERUNG = new Set(['ueberschriften', 'nummeriert', 'teile']);
const WARNUNGEN = new Set(['bilder_entfernt', 'wenig_text', 'keine_gliederung', 'gekuerzt']);
const FORMATE = new Set(['pdf', 'docx', 'txt', 'md']);
/** Codes, bei denen ein neuer Versuch helfen kann (Netz, Last, Frist). */
const WIEDERHOLBAR = new Set(['netz', 'zu_langsam', 'ausgelastet', 'gedrosselt', 'laeuft_schon', 'pruefung_fehlt', 'fehler']);

/** Ein gelesenes Dokument, wie es in der Antwort steht (kein Text). */
export type GelesenesDokument = NonNullable<UploadAntwort['dokument']>;

/** TG-3e: welches Dokument gerade dran ist — `nr` ab 1, `von` alle markierten, dazu sein Name. */
export interface DokumentStelle {
  readonly nr: number;
  readonly von: number;
  readonly name: string;
}

/** Wo das Lesen steht: senden (mit Anteil), lesen (Backend), fertig (Befund, Antwort noch nicht
 *  gesendet, weil gerade ein Zug lief) oder Fehler (mit Code). TG-3e: `sendet`, `liest` und
 *  `fehler` nennen das Dokument (`stelle`); `fehler` hält, was schon gelesen ist (`bisher`) — „Noch
 *  einmal“ macht mit demselben Dokument weiter, „Ohne dieses weiter“ mit dem nächsten. */
export type DokumentLauf =
  | { readonly phase: 'sendet'; readonly anteil: number; readonly stelle?: DokumentStelle }
  | { readonly phase: 'liest'; readonly stelle?: DokumentStelle }
  | { readonly phase: 'fertig'; readonly antwort: UploadAntwort }
  | {
    readonly phase: 'fehler'; readonly code: string; readonly stelle?: DokumentStelle;
    readonly bisher?: readonly GelesenesDokument[];
  };

/** TG-3e: alle markierten Strukturdokumente in der Reihenfolge der Auswahl. */
export function strukturDateien<T>(e: Erfassung<T>): ErfassteDatei<T>[] {
  return e.dateien.filter((d) => d.rolle === 'struktur');
}

/** Das erste markierte Strukturdokument (vor TG-3e das einzige). */
export function strukturDatei<T>(e: Erfassung<T>): ErfassteDatei<T> | null {
  return strukturDateien(e)[0] ?? null;
}

/** Darf dieses Auswahlfeld ein Dokument lesen lassen? Das sagt allein das System (`schalter`). */
export function dokumentErlaubt(daten: Readonly<Record<string, unknown>>): boolean {
  const schalter = daten['schalter'];
  return !!schalter && typeof schalter === 'object' && (schalter as Record<string, unknown>)['dokument_im_chat'] === true;
}

export function wiederholbar(code: string): boolean {
  return WIEDERHOLBAR.has(code);
}

/** Der Code eines abgelehnten Hochladens (`status`/`code` aus dem Transport); 429 heißt gedrosselt. */
export function codeVon(fehler: unknown): string {
  const f = fehler as { status?: unknown; code?: unknown; name?: unknown } | null;
  if (f?.status === 429) return 'gedrosselt';
  // Die Rumpf-Grenze des Pfads antwortet vor dem Endpunkt, mit Text statt Code (Review U3-2, 8).
  if (f?.status === 413) return 'zu_gross';
  return typeof f?.code === 'string' && /^[a-z_]{1,40}$/.test(f.code) ? f.code : 'fehler';
}

/** Ein Befund des Backends als gelesenes Dokument — nur die Felder, die das Antwort-Schema kennt;
 *  `null`, wenn der Befund unbrauchbar ist (dann gilt das Lesen als gescheitert). */
export function gelesenAus(befund: Readonly<Record<string, unknown>>, ohneName = 'Dokument'): GelesenesDokument | null {
  const b = (befund['befund'] ?? {}) as Record<string, unknown>;
  const ganz = (v: unknown) => (typeof v === 'number' && Number.isInteger(v) && v >= 0 ? v : null);
  const upload = befund['upload_id'];
  const format = befund['format'];
  if (typeof upload !== 'string' || typeof format !== 'string' || !FORMATE.has(format)) return null;
  const vorschau = Array.isArray(befund['ueberschriften_vorschau']) ? befund['ueberschriften_vorschau'] : [];
  return {
    upload_id: upload,
    name: Array.from(einZeiler(String(befund['name'] ?? '')) || ohneName).slice(0, 200).join(''),
    format,
    befund: {
      seiten: ganz(b['seiten']),
      woerter: ganz(b['woerter']) ?? 0,
      abschnitte: Math.min(ganz(b['abschnitte']) ?? 0, 400),
      gliederung_art: GLIEDERUNG.has(String(b['gliederung_art'])) ? String(b['gliederung_art']) : 'teile',
      warnungen: (Array.isArray(b['warnungen']) ? b['warnungen'] : []).filter((w): w is string => WARNUNGEN.has(String(w))).slice(0, 4),
    },
    vorschau: vorschau.filter((v): v is string => typeof v === 'string').map(einZeiler).filter(Boolean).slice(0, MAX_VORSCHAU),
  };
}

/** Die Antwort `aktion: "dokument"` aus Erfassung und gelesenen Dokumenten. TG-3e: `dokument` ist
 *  das erste, `dokumente` kommt nur bei mehreren dazu — mit einem bleibt die Antwort wie vorher. */
export function dokumenteAntwort<T>(e: Erfassung<T>, gelesen: readonly GelesenesDokument[],
  dateiOhneName?: string): UploadAntwort | null {
  if (!gelesen.length) return null;
  return {
    ...antwortDaten(e, 'dokument', dateiOhneName),
    dokument: gelesen[0],
    ...(gelesen.length > 1 ? { dokumente: [...gelesen] } : {}),
  };
}

/** Die Antwort aus einem Befund (vor TG-3e der einzige Weg) — `null` mit unbrauchbarem Befund. */
export function dokumentAntwort<T>(e: Erfassung<T>, befund: Readonly<Record<string, unknown>>,
  ohneName = 'Dokument'): UploadAntwort | null {
  const dok = gelesenAus(befund, ohneName);
  return dok ? dokumenteAntwort(e, [dok]) : null;
}

/** Wie viele Abschnitte die gelesenen Dokumente zusammen haben. */
export function abschnitteZusammen(a: UploadAntwort): number {
  return (a.dokumente ?? (a.dokument ? [a.dokument] : [])).reduce((n, d) => n + d.befund.abschnitte, 0);
}
