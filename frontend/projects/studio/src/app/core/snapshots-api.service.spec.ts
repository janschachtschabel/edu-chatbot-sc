import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { SnapshotsApi } from './snapshots-api.service';
import { StudioApiError } from './studio-api-error';

const BASE = '/studio/api/config';

function setup(): { api: SnapshotsApi; http: HttpTestingController } {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  return { api: TestBed.inject(SnapshotsApi), http: TestBed.inject(HttpTestingController) };
}

describe('SnapshotsApi', () => {
  let api: SnapshotsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    ({ api, http } = setup());
  });

  it('legt einen Snapshot mit Label im Body an', () => {
    void api.create('vor dem Umbau');
    const req = http.expectOne(`${BASE}/snapshots`);
    expect(req.request.method).toBe('POST');
    // The endpoint takes a `SnapshotCreate` model, not a query parameter as ALT
    // did (`?label=…`) — a label with `&` in it would have been truncated there.
    expect(req.request.body).toEqual({ label: 'vor dem Umbau' });
    req.flush({ id: 'snap-1', label: 'vor dem Umbau' });
  });

  it('kodiert die Snapshot-ID in jedem Pfad, der sie trägt', () => {
    void api.restore('snap /1');
    http.expectOne(`${BASE}/snapshots/snap%20%2F1/restore`).flush({ status: 'restored', areas: 3 });
    void api.remove('snap /1');
    http.expectOne(`${BASE}/snapshots/snap%20%2F1`).flush({ status: 'deleted', id: 'snap /1' });
  });

  it('holt die vier Werksstand-Wege unter /config/factory', () => {
    void api.factory();
    expect(http.expectOne(`${BASE}/factory`).request.method).toBe('GET');
    void api.saveFactory();
    expect(http.expectOne(`${BASE}/factory/save`).request.method).toBe('POST');
    void api.restoreFactory();
    expect(http.expectOne(`${BASE}/factory/restore`).request.method).toBe('POST');
    void api.downloadFactory();
    expect(http.expectOne(`${BASE}/factory/download`).request.responseType).toBe('blob');
    http.verify();
  });

  it('lädt das Voll-Backup als Blob statt per Seitenwechsel', async () => {
    const pending = api.backup();
    const req = http.expectOne(`${BASE}/backup`);
    expect(req.request.responseType).toBe('blob');
    req.flush(new Blob(['PK']));
    await expect(pending).resolves.toBeInstanceOf(Blob);
  });

  it('nennt bei einem gescheiterten Download den Satz des Backends', async () => {
    // ALT navigated the whole studio to the download URL, so a 404 replaced the
    // page with raw JSON. Here the error must arrive as a sentence — and with
    // `responseType: 'blob'` the body is a Blob, not a parsed object.
    const pending = api.downloadFactory();
    http.expectOne(`${BASE}/factory/download`).flush(
      new Blob([JSON.stringify({ detail: 'Kein Factory-Stand gesetzt' })]),
      { status: 404, statusText: 'Not Found' },
    );

    await expect(pending).rejects.toMatchObject({ detail: 'Kein Factory-Stand gesetzt' });
  });

  it('schickt eine hochgeladene ZIP als multipart im Feld `file`', () => {
    void api.restoreBackup(new File(['PK'], 'backup.zip'));
    const req = http.expectOne(`${BASE}/restore`);
    expect(req.request.method).toBe('POST');
    const body = req.request.body as FormData;
    // `file` is FastAPI's parameter name (`async def restore_backup(file: UploadFile)`);
    // any other field name is a 422 the user cannot act on.
    expect((body.get('file') as File).name).toBe('backup.zip');
    req.flush({ status: 'restored', areas: 35 });
  });

  it('lädt einen Werksstand als eigene Datei hoch', () => {
    void api.uploadFactory(new File(['PK'], 'factory.zip'));
    const req = http.expectOne(`${BASE}/factory/upload`);
    expect((req.request.body as FormData).get('file')).toBeInstanceOf(File);
    req.flush({ status: 'saved', id: 'factory' });
  });

  it('meldet ein totes Backend als solches, nicht als Unbekanntes', async () => {
    const pending = api.list();
    http.expectOne(`${BASE}/snapshots`).error(new ProgressEvent('error'), { status: 0 });
    await expect(pending).rejects.toBeInstanceOf(StudioApiError);
  });
});
