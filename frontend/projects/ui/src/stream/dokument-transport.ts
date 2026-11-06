/**
 * Ein Dokument aus dem Auswahlfeld `ui_upload` an `POST /api/ui/dokumente` (Paket U3-2c).
 *
 * Als `XMLHttpRequest` (`xhr-senden.ts`), nicht `fetch`: nur sie meldet den Fortschritt des
 * Hochladens. Der Zugangsblock reist wie bei jedem Zug mit, damit das Backend weiß, ob eine
 * angemeldete Person lädt (`dokument_ohne_anmeldung`). Kein Zug, keine KI: das Backend liest das
 * Dokument, legt es an der Sitzung ab und gibt nur den Befund zurück, nie den Text.
 *
 * Ein Fehler trägt `status` und `code` — den Code aus `detail` (`bild`, `zu_gross`, `kein_text` …),
 * ohne Text des Servers; das Modul zeigt je Code einen eigenen Satz. `netz` (keine Verbindung),
 * `zu_langsam` (Frist) und `fehler` (nicht lesbar) setzt der Transport selbst.
 */
import { type TransportFehler, transportFehler, xhrSenden } from './xhr-senden';

/** Was das Backend über ein gelesenes Dokument zurückgibt. */
export interface DokumentBefund {
  readonly upload_id: string;
  readonly name: string;
  readonly format: string;
  readonly befund: Record<string, unknown>;
  readonly ueberschriften_vorschau: readonly string[];
}

export type DokumentFehler = TransportFehler;

export interface HochladenOptionen {
  readonly url: string;
  readonly sessionId: string;
  readonly blockId: string;
  readonly datei: File;
  /** Anteil 0…1 des gesendeten Rumpfs; danach liest das Backend (ohne eigene Meldung). */
  readonly onFortschritt?: (anteil: number) => void;
  readonly signal?: AbortSignal;
  /** Über der Frist des Backends (60 s Umwandlung) plus Hochladen. */
  readonly fristMs?: number;
  /** Für Tests. */
  readonly xhrFabrik?: () => XMLHttpRequest;
}

const FRIST_MS = 120_000;

function istBefund(d: unknown): d is DokumentBefund {
  const b = d as Partial<DokumentBefund> | null;
  return typeof b?.upload_id === 'string' && typeof b.name === 'string' && typeof b.format === 'string'
    && !!b.befund && typeof b.befund === 'object' && Array.isArray(b.ueberschriften_vorschau);
}

export async function dokumentHochladen(o: HochladenOptionen): Promise<DokumentBefund> {
  const rumpf = new FormData();
  rumpf.append('session_id', o.sessionId);
  rumpf.append('block_id', o.blockId);
  rumpf.append('datei', o.datei, o.datei.name);
  const antwort = await xhrSenden({
    url: o.url, rumpf, onFortschritt: o.onFortschritt, signal: o.signal,
    fristMs: o.fristMs ?? FRIST_MS, xhrFabrik: o.xhrFabrik,
  });
  if (!istBefund(antwort)) throw transportFehler(200, 'fehler');
  return antwort;
}
