// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import { clearAccessBlock, writeAccessBlock } from '../session/mcp-access';
import { dokumentHochladen, type DokumentFehler } from './dokument-transport';

/**
 * Paket U3-2c: ein Dokument aus `ui_upload` an `POST /api/ui/dokumente` — als XHR, weil nur sie den
 * Fortschritt des Hochladens meldet. Der Zugangsblock reist wie bei jedem Zug mit; ein Fehler trägt
 * Status und Code aus `detail` (nie einen Text des Servers).
 */
class Xhr {
  static letzte: Xhr;
  methode = '';
  url = '';
  kopf: Record<string, string> = {};
  rumpf: FormData | null = null;
  status = 0;
  responseText = '';
  timeout = 0;
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  abgebrochen = false;

  constructor() { Xhr.letzte = this; }
  open(methode: string, url: string): void { this.methode = methode; this.url = url; }
  setRequestHeader(name: string, wert: string): void { this.kopf[name] = wert; }
  send(rumpf: FormData): void { this.rumpf = rumpf; }
  abort(): void { this.abgebrochen = true; this.onabort?.(); }
  antworte(status: number, rumpf: unknown): void {
    this.status = status;
    this.responseText = JSON.stringify(rumpf);
    this.onload?.();
  }
}

const BEFUND = { upload_id: '11111111-2222-4333-8444-555555555555', name: 'Lehrplan.pdf', format: 'pdf',
  befund: { seiten: 3, woerter: 900, abschnitte: 5, gliederung_art: 'ueberschriften', warnungen: [] },
  ueberschriften_vorschau: ['Mechanik'] };

function laden(mehr: Partial<Parameters<typeof dokumentHochladen>[0]> = {}) {
  const datei = new File(['%PDF-1.4'], 'Lehrplan.pdf', { type: 'application/pdf' });
  return dokumentHochladen({
    url: 'https://boerdi.example/api/ui/dokumente', sessionId: 'bb-1', blockId: 'b0000001', datei,
    xhrFabrik: () => new Xhr() as unknown as XMLHttpRequest, ...mehr,
  });
}

afterEach(() => clearAccessBlock());

describe('dokumentHochladen', () => {
  it('schickt Sitzung, Block und Datei mit Zugangsblock und meldet den Fortschritt', async () => {
    writeAccessBlock('wlo2.block');
    const fortschritt: number[] = [];
    const lauf = laden({ onFortschritt: (a) => fortschritt.push(a) });
    const x = Xhr.letzte;
    expect(x.methode).toBe('POST');
    expect(x.url).toBe('https://boerdi.example/api/ui/dokumente');
    expect(x.kopf['WLO-Access-Block']).toBe('wlo2.block');
    expect(x.rumpf?.get('session_id')).toBe('bb-1');
    expect(x.rumpf?.get('block_id')).toBe('b0000001');
    expect((x.rumpf?.get('datei') as File).name).toBe('Lehrplan.pdf');
    x.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
    x.upload.onprogress?.({ lengthComputable: false, loaded: 0, total: 0 });
    x.antworte(200, BEFUND);
    await expect(lauf).resolves.toEqual(BEFUND);
    expect(fortschritt).toEqual([0.5]);
  });

  it('ohne Anmeldung keine Zugangs-Kopfzeile', () => {
    void laden().catch(() => undefined);
    expect(Xhr.letzte.kopf['WLO-Access-Block']).toBeUndefined();
  });

  it('ein Fehler trägt Status und Code aus detail', async () => {
    const lauf = laden();
    Xhr.letzte.antworte(415, { detail: 'bild' });
    await expect(lauf).rejects.toMatchObject({ status: 415, code: 'bild' } satisfies Partial<DokumentFehler>);
  });

  it('ein Fehler ohne lesbaren Code wird „fehler“', async () => {
    const lauf = laden();
    Xhr.letzte.status = 502;
    Xhr.letzte.responseText = '<html>Bad Gateway</html>';
    Xhr.letzte.onload?.();
    await expect(lauf).rejects.toMatchObject({ status: 502, code: 'fehler' });
  });

  it('Netz, Frist und eine Antwort ohne Kennung sind Fehler', async () => {
    const netz = laden();
    Xhr.letzte.onerror?.();
    await expect(netz).rejects.toMatchObject({ status: 0, code: 'netz' });
    const frist = laden({ fristMs: 5 });
    expect(Xhr.letzte.timeout).toBe(5);
    Xhr.letzte.ontimeout?.();
    await expect(frist).rejects.toMatchObject({ code: 'zu_langsam' });
    const leer = laden();
    Xhr.letzte.antworte(200, { name: 'x' });
    await expect(leer).rejects.toMatchObject({ code: 'fehler' });
  });

  it('ein Abbruch von außen bricht die Anfrage ab', async () => {
    const steuerung = new AbortController();
    const lauf = laden({ signal: steuerung.signal });
    steuerung.abort();
    expect(Xhr.letzte.abgebrochen).toBe(true);
    await expect(lauf).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('Review 13: schon abgebrochen — sofort AbortError, keine Anfrage', async () => {
    const steuerung = new AbortController();
    steuerung.abort();
    const vorher = Xhr.letzte;
    await expect(laden({ signal: steuerung.signal })).rejects.toMatchObject({ name: 'AbortError' });
    expect(Xhr.letzte).toBe(vorher);
  });
});
