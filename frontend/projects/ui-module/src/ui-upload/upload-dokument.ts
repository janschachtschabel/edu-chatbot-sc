/**
 * Ein Strukturdokument im Chat lesen lassen (Paket U3-2c, Plan §16.6) — Regeln ohne DOM.
 *
 * Das Modul lädt das markierte Strukturdokument über den Host hoch (`host.hochladen`, Fähigkeit
 * `hochladen`); das Backend liest es und gibt nur den Befund zurück. Daraus entsteht die Antwort
 * `aktion: "dokument"` mit dem Ziel der Person. Die Ziele sind eine Liste (Plan O-26): heute nur
 * „Themenbaum aus dem Dokument“, später etwa „Inhalte erschließen“ oder „als Gesprächsgrundlage“.
 *
 * Erlaubt ist das nur, wenn das System es im Block erlaubt (`schalter.dokument_im_chat` — Studio und
 * Anmeldung) und ein Strukturdokument markiert ist; welche Dateiarten gehen, regelt schon die Rolle
 * (`kannStrukturSein`).
 */
import { antwortDaten, einZeiler, type UploadAntwort } from './upload-antwort';
import type { ErfassteDatei, Erfassung } from './upload-erfassen';

export type DokumentZiel = 'themenbaum';
export const DOKUMENT_ZIELE: readonly DokumentZiel[] = ['themenbaum'];

const MAX_VORSCHAU = 8;
const GLIEDERUNG = new Set(['ueberschriften', 'nummeriert', 'teile']);
const WARNUNGEN = new Set(['bilder_entfernt', 'wenig_text', 'keine_gliederung', 'gekuerzt']);
const FORMATE = new Set(['pdf', 'docx', 'txt', 'md']);
/** Codes, bei denen ein neuer Versuch helfen kann (Netz, Last, Frist). */
const WIEDERHOLBAR = new Set(['netz', 'zu_langsam', 'ausgelastet', 'gedrosselt', 'laeuft_schon', 'pruefung_fehlt', 'fehler']);

/** Wo das Lesen steht: senden (mit Anteil), lesen (Backend), fertig (Befund, Antwort noch nicht
 *  gesendet, weil gerade ein Zug lief) oder Fehler (mit Code). */
export type DokumentLauf =
  | { readonly phase: 'sendet'; readonly ziel: DokumentZiel; readonly anteil: number }
  | { readonly phase: 'liest'; readonly ziel: DokumentZiel }
  | { readonly phase: 'fertig'; readonly ziel: DokumentZiel; readonly antwort: UploadAntwort }
  | { readonly phase: 'fehler'; readonly ziel: DokumentZiel; readonly code: string };

export function strukturDatei<T>(e: Erfassung<T>): ErfassteDatei<T> | null {
  return e.dateien.find((d) => d.rolle === 'struktur') ?? null;
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

/** Die Antwort `aktion: "dokument"` aus Erfassung und Befund des Backends — nur die Felder, die das
 *  Antwort-Schema kennt; `null`, wenn der Befund unbrauchbar ist (dann gilt das Lesen als gescheitert). */
export function dokumentAntwort<T>(e: Erfassung<T>, befund: Readonly<Record<string, unknown>>, ziel: DokumentZiel,
  ohneName = 'Dokument'): UploadAntwort | null {
  const b = (befund['befund'] ?? {}) as Record<string, unknown>;
  const ganz = (v: unknown) => (typeof v === 'number' && Number.isInteger(v) && v >= 0 ? v : null);
  const upload = befund['upload_id'];
  const format = befund['format'];
  if (typeof upload !== 'string' || typeof format !== 'string' || !FORMATE.has(format)) return null;
  const vorschau = Array.isArray(befund['ueberschriften_vorschau']) ? befund['ueberschriften_vorschau'] : [];
  return {
    ...antwortDaten(e, 'dokument'),
    dokument: {
      upload_id: upload,
      name: Array.from(einZeiler(String(befund['name'] ?? '')) || ohneName).slice(0, 200).join(''),
      format,
      ziel,
      befund: {
        seiten: ganz(b['seiten']),
        woerter: ganz(b['woerter']) ?? 0,
        abschnitte: Math.min(ganz(b['abschnitte']) ?? 0, 400),
        gliederung_art: GLIEDERUNG.has(String(b['gliederung_art'])) ? String(b['gliederung_art']) : 'teile',
        warnungen: (Array.isArray(b['warnungen']) ? b['warnungen'] : []).filter((w): w is string => WARNUNGEN.has(String(w))).slice(0, 4),
      },
      vorschau: vorschau.filter((v): v is string => typeof v === 'string').map(einZeiler).filter(Boolean).slice(0, MAX_VORSCHAU),
    },
  };
}
