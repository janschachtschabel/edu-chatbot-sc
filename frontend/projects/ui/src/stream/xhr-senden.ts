/**
 * Ein POST als `XMLHttpRequest` für die Wege der Module ohne Zug (U3-2c Dokument, U3-3b Ablage) —
 * aus `dokument-transport.ts` gelöst, damit beide denselben Weg nehmen.
 *
 * XHR statt `fetch`: nur sie meldet den Fortschritt des Hochladens. Der Zugangsblock reist wie bei
 * jedem Zug mit (`accessBlockHeaders`). Ein Fehler trägt `status` und `code` — den Code aus `detail`
 * (`bild`, `zu_gross`, `nur_angemeldet` …), nie einen Text des Servers. `netz` (keine Verbindung),
 * `zu_langsam` (Frist) und `fehler` (nicht lesbar) setzt der Transport selbst; ein Abbruch von außen
 * lehnt mit einem `AbortError` ab.
 */
import { accessBlockHeaders } from '../session/mcp-access';

export interface TransportFehler extends Error {
  readonly status: number;
  readonly code: string;
}

export interface SendenOptionen {
  readonly url: string;
  /** `FormData` (multipart) oder ein Objekt, das als JSON geht. */
  readonly rumpf: FormData | Record<string, unknown>;
  /** Anteil 0…1 des gesendeten Rumpfs. */
  readonly onFortschritt?: (anteil: number) => void;
  readonly signal?: AbortSignal;
  readonly fristMs: number;
  /** Für Tests. */
  readonly xhrFabrik?: () => XMLHttpRequest;
}

export function transportFehler(status: number, code: string): TransportFehler {
  return Object.assign(new Error(`Transport: ${status} ${code}`), { status, code });
}

function codeAus(text: string): string {
  try {
    const detail = (JSON.parse(text) as { detail?: unknown })?.detail;
    return typeof detail === 'string' && /^[a-z_]{1,40}$/.test(detail) ? detail : 'fehler';
  } catch {
    return 'fehler';
  }
}

function abgebrochen(): DOMException {
  return new DOMException('Senden abgebrochen', 'AbortError');
}

/** Sendet und löst mit dem gelesenen JSON der Antwort auf (200); sonst lehnt es mit Status und Code ab. */
export function xhrSenden(o: SendenOptionen): Promise<unknown> {
  return new Promise<unknown>((erfuellt, abgelehnt) => {
    // Schon abgebrochen: ein `abort()` vor `send()` feuert kein Ereignis (Review U3-2, 13).
    if (o.signal?.aborted) return abgelehnt(abgebrochen());
    const xhr = (o.xhrFabrik ?? (() => new XMLHttpRequest()))();
    const abbrechen = () => xhr.abort();
    const ende = () => o.signal?.removeEventListener('abort', abbrechen);
    xhr.open('POST', o.url);
    for (const [name, wert] of Object.entries(accessBlockHeaders())) xhr.setRequestHeader(name, wert);
    xhr.timeout = o.fristMs;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) o.onFortschritt?.(Math.min(1, e.loaded / e.total));
    };
    xhr.onload = () => {
      ende();
      if (xhr.status !== 200) return abgelehnt(transportFehler(xhr.status, codeAus(xhr.responseText)));
      try {
        return erfuellt(JSON.parse(xhr.responseText));
      } catch {
        return abgelehnt(transportFehler(xhr.status, 'fehler'));
      }
    };
    xhr.onerror = () => { ende(); abgelehnt(transportFehler(0, 'netz')); };
    xhr.ontimeout = () => { ende(); abgelehnt(transportFehler(0, 'zu_langsam')); };
    xhr.onabort = () => { ende(); abgelehnt(abgebrochen()); };
    o.signal?.addEventListener('abort', abbrechen, { once: true });
    if (o.rumpf instanceof FormData) {
      xhr.send(o.rumpf);
    } else {
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify(o.rumpf));
    }
  });
}
