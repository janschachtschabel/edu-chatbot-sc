/**
 * „Hier im Chat“ (Plan 2026-11-17, Paket U4) — Regeln ohne DOM. Löst „Lesen lassen“ ab (U3-2c,
 * TG-3e): statt nur Strukturdokumente liest der Chat jetzt jede lesbare Datei der Auswahl, je Datei
 * ein `POST /api/ui/dokumente` mit `rolle` (`inhalt` | `struktur`, über `host.hochladen`). Das
 * Backend antwortet mit Befund, Rolle und bei Inhalten kurzen Angaben — nie mit dem Text; die
 * Antwort an den Chat trägt davon nur die `upload_id` (Teile rechnet der Server selbst).
 *
 * Antwort: `aktion: "bereitgestellt"` mit `ort: "chat"` und `dateien: [{i, rolle, upload_id}]`;
 * „Nur Namen senden“ mit `ort: "namen"` ohne Dateien.
 */
import type { AblageRolle } from '../_vertrag/modul-host';
import { antwortDaten, type UploadAntwort } from './upload-antwort';
import type { Erfassung } from './upload-erfassen';

/** Wie das Antwort-Schema (`dateien[].upload_id`): eine UUID v4. */
const UPLOAD_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
/** Codes, bei denen ein neuer Versuch helfen kann (Netz, Last, Frist) — nicht die Grenzen der Sitzung. */
const WIEDERHOLBAR = new Set(['netz', 'zu_langsam', 'ausgelastet', 'gedrosselt', 'laeuft_schon', 'pruefung_fehlt', 'fehler']);

export interface GeleseneDatei {
  readonly i: number;
  readonly rolle: AblageRolle;
  readonly upload_id: string;
}

/** Welche Datei gerade dran ist — `nr` ab 1, `von` alle lesbaren, dazu ihr Name. */
export interface ChatStelle {
  readonly nr: number;
  readonly von: number;
  readonly name: string;
}

/** Wo „Hier im Chat“ steht: senden (mit Anteil), lesen (Backend), Fehler einer Datei (mit dem, was
 *  schon gelesen ist), beendet (`halt`: an der Sitzungsgrenze bei `stelle` oder angehalten — Review der
 *  Oberfläche, 1 und 2) oder fertig (Antwort gebaut, wartet, wenn gerade ein Zug läuft). */
export type ChatLauf =
  | { readonly phase: 'sendet'; readonly anteil: number; readonly stelle: ChatStelle }
  | { readonly phase: 'liest'; readonly stelle: ChatStelle }
  | { readonly phase: 'fehler'; readonly code: string; readonly stelle: ChatStelle; readonly bisher: readonly GeleseneDatei[] }
  | {
    /** `code`: `grenze_anzahl` oder `ort_nicht_erlaubt` — jede weitere Datei scheiterte ebenso. */
    readonly phase: 'halt'; readonly grund: 'grenze'; readonly code: string; readonly stelle: ChatStelle;
    readonly bisher: readonly GeleseneDatei[];
  }
  | { readonly phase: 'halt'; readonly grund: 'angehalten'; readonly bisher: readonly GeleseneDatei[] }
  | { readonly phase: 'fertig'; readonly antwort: UploadAntwort };

export function wiederholbar(code: string): boolean {
  return WIEDERHOLBAR.has(code);
}

/** Der Code eines abgelehnten Hochladens (`status`/`code` aus dem Transport). Der eigene Code des
 *  Backends geht vor; 429 ohne Code heißt gedrosselt, 413 ohne Code ist die Rumpf-Grenze des Pfads
 *  (antwortet vor dem Endpunkt, Review U3-2, 8). */
export function codeVon(fehler: unknown): string {
  const f = fehler as { status?: unknown; code?: unknown } | null;
  const code = typeof f?.code === 'string' && /^[a-z_]{1,40}$/.test(f.code) ? f.code : null;
  if (code && code !== 'fehler') return code;
  if (f?.status === 429) return 'gedrosselt';
  if (f?.status === 413) return 'zu_gross';
  return code ?? 'fehler';
}

/** Die `upload_id` aus dem Befund des Backends — `null`, wenn er unbrauchbar ist (dann gilt das
 *  Lesen als gescheitert). */
export function gelesenAus(befund: Readonly<Record<string, unknown>>): string | null {
  const id = befund['upload_id'];
  return typeof id === 'string' && UPLOAD_ID.test(id) ? id : null;
}

export function chatAntwort<T>(e: Erfassung<T>, gelesen: readonly GeleseneDatei[], dateiOhneName?: string): UploadAntwort {
  return {
    ...antwortDaten(e, 'bereitgestellt', dateiOhneName), ort: 'chat',
    dateien: gelesen.map(({ i, rolle, upload_id }) => ({ i, rolle, upload_id })),
  };
}

export function namenAntwort<T>(e: Erfassung<T>, dateiOhneName?: string): UploadAntwort {
  return { ...antwortDaten(e, 'bereitgestellt', dateiOhneName), ort: 'namen' };
}
