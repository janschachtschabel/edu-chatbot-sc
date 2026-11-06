// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import type { AblageSchritt } from '@boerdi/ui-module';

import { clearAccessBlock, writeAccessBlock } from '../session/mcp-access';
import { ablageSenden } from './ablage-transport';

/**
 * Paket U3-3b (T6): die drei Schritte der Ablage im persönlichen Bereich an `/api/ui/ablage/*` — als
 * XHR (Fortschritt beim Hochladen), mit dem Zugangsblock; Fehler tragen Status und Code aus `detail`.
 */
class Xhr {
  static letzte: Xhr;
  url = '';
  kopf: Record<string, string> = {};
  rumpf: FormData | string | null = null;
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
  open(_methode: string, url: string): void { this.url = url; }
  setRequestHeader(name: string, wert: string): void { this.kopf[name] = wert; }
  send(rumpf: FormData | string): void { this.rumpf = rumpf; }
  abort(): void { this.abgebrochen = true; this.onabort?.(); }
  antworte(status: number, rumpf: unknown): void {
    this.status = status;
    this.responseText = JSON.stringify(rumpf);
    this.onload?.();
  }
}

function senden(schritt: AblageSchritt, signal?: AbortSignal) {
  return ablageSenden({
    basis: 'https://boerdi.example/api', sessionId: 'bb-1', blockId: 'b0000001', schritt, signal,
    xhrFabrik: () => new Xhr() as unknown as XMLHttpRequest,
  });
}

afterEach(() => clearAccessBlock());

describe('ablageSenden', () => {
  it('vorbereiten geht als JSON mit Zugangsblock', async () => {
    writeAccessBlock('wlo2.block');
    const lauf = senden({
      schritt: 'vorbereiten', ordner: 'Physik 7',
      eintraege: [{ titel: 'Mechanik', sha256: 'a'.repeat(64), groesse: 5, art: 'pdf' }],
    });
    const x = Xhr.letzte;
    expect(x.url).toBe('https://boerdi.example/api/ui/ablage/vorbereiten');
    expect(x.kopf['WLO-Access-Block']).toBe('wlo2.block');
    expect(x.kopf['Content-Type']).toBe('application/json');
    expect(JSON.parse(x.rumpf as string)).toEqual({
      session_id: 'bb-1', block_id: 'b0000001', ordner: 'Physik 7',
      eintraege: [{ titel: 'Mechanik', sha256: 'a'.repeat(64), groesse: 5, art: 'pdf' }],
    });
    x.antworte(200, { batch_token: 'tok-1234567890', layout: 'ordner', eintraege: [] });
    await expect(lauf).resolves.toMatchObject({ batch_token: 'tok-1234567890' });
  });

  it('eine Datei geht als multipart und meldet den Fortschritt', async () => {
    const fortschritt: number[] = [];
    const datei = new File(['%PDF-'], 'Mechanik.pdf', { type: 'application/pdf' });
    const lauf = senden({ schritt: 'datei', batchToken: 'tok-1234567890', index: 3, datei,
      onFortschritt: (a) => fortschritt.push(a) });
    const x = Xhr.letzte;
    expect(x.url).toBe('https://boerdi.example/api/ui/ablage/datei');
    const rumpf = x.rumpf as FormData;
    expect([rumpf.get('session_id'), rumpf.get('block_id'), rumpf.get('batch_token'), rumpf.get('index')])
      .toEqual(['bb-1', 'b0000001', 'tok-1234567890', '3']);
    expect((rumpf.get('datei') as File).name).toBe('Mechanik.pdf');
    expect(x.kopf['Content-Type']).toBeUndefined();     // die Grenze setzt der Browser
    x.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 4 });
    x.antworte(200, { index: 3, stand: 'stored', node_id: 'n-3', link: null });
    await expect(lauf).resolves.toMatchObject({ stand: 'stored' });
    expect(fortschritt).toEqual([0.25]);
  });

  it('abschluss nennt nur den Schlüssel', async () => {
    const lauf = senden({ schritt: 'abschluss', batchToken: 'tok-1234567890' });
    expect(Xhr.letzte.url).toBe('https://boerdi.example/api/ui/ablage/abschluss');
    expect(JSON.parse(Xhr.letzte.rumpf as string)).toEqual({
      session_id: 'bb-1', block_id: 'b0000001', batch_token: 'tok-1234567890' });
    Xhr.letzte.antworte(200, { stand: 'stored', bereits: false });
    await expect(lauf).resolves.toEqual({ stand: 'stored', bereits: false });
  });

  it('ein Fehler trägt Status und Code; eine Antwort ohne Objekt ist „fehler“', async () => {
    const abgewiesen = senden({ schritt: 'abschluss', batchToken: 'tok-1234567890' });
    Xhr.letzte.antworte(403, { detail: 'nur_angemeldet' });
    await expect(abgewiesen).rejects.toMatchObject({ status: 403, code: 'nur_angemeldet' });
    const leer = senden({ schritt: 'abschluss', batchToken: 'tok-1234567890' });
    Xhr.letzte.antworte(200, ['x']);
    await expect(leer).rejects.toMatchObject({ code: 'fehler' });
  });

  it('ein Abbruch von außen bricht ab', async () => {
    const steuerung = new AbortController();
    const lauf = senden({ schritt: 'abschluss', batchToken: 'tok-1234567890' }, steuerung.signal);
    steuerung.abort();
    expect(Xhr.letzte.abgebrochen).toBe(true);
    await expect(lauf).rejects.toMatchObject({ name: 'AbortError' });
  });
});
