// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { RagApi } from './rag-api.service';

function setup(): { api: RagApi; http: HttpTestingController } {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  return { api: TestBed.inject(RagApi), http: TestBed.inject(HttpTestingController) };
}

describe('RagApi', () => {
  let api: RagApi;
  let http: HttpTestingController;

  beforeEach(() => ({ api, http } = setup()));

  it('caches the area list in a signal the whole page can read', async () => {
    expect(api.areas()).toEqual([]);
    const done = api.refreshAreas();
    http.expectOne('/studio/api/rag/areas').flush([{ area: 'wlo', chunks: 12, documents: 3 }]);
    await done;
    expect(api.areas()).toEqual([{ area: 'wlo', chunks: 12, documents: 3 }]);
  });

  it('reports a failed area load instead of showing an empty knowledge base', async () => {
    // An empty list and "the request failed" look identical to the reader,
    // and only one of them means "nothing is ingested yet".
    const done = api.refreshAreas();
    http.expectOne('/studio/api/rag/areas').flush('nope', { status: 500, statusText: 'Server Error' });
    await done;
    expect(api.areasError()).not.toBe('');
    expect(api.areas()).toEqual([]);
  });

  it('escapes an area name in the path, so a slash cannot address another route', () => {
    void api.documents('a/b');
    http.expectOne('/studio/api/rag/area/a%2Fb');
  });

  it('identifies a document by BOTH title and source', () => {
    // The backend groups on the pair; sending only the title would delete a
    // same-titled document from a different source.
    void api.document('wlo', 'Titel', 'https://x/y');
    const req = http.expectOne((r) => r.url === '/studio/api/rag/area/wlo/doc');
    expect(req.request.params.get('title')).toBe('Titel');
    expect(req.request.params.get('source')).toBe('https://x/y');
  });

  it('deletes one document without touching its area', () => {
    void api.deleteDocument('wlo', 'Titel', 'q.pdf');
    const req = http.expectOne((r) => r.url === '/studio/api/rag/area/wlo/doc');
    expect(req.request.method).toBe('DELETE');
    expect(req.request.params.get('title')).toBe('Titel');
  });

  it('sends an uploaded file as multipart, with area and title alongside', () => {
    const file = new File(['x'], 'k.pdf', { type: 'application/pdf' });
    void api.ingestFile('wlo', 'Kunde', file);
    const req = http.expectOne('/studio/api/rag/ingest/file');
    const body = req.request.body as FormData;
    expect(body.get('area')).toBe('wlo');
    expect(body.get('title')).toBe('Kunde');
    expect(body.get('file')).toBe(file);
    // Angular must set the multipart boundary itself — a Content-Type we
    // guessed here would be missing it and the upload would arrive empty.
    expect(req.request.headers.get('Content-Type')).toBeNull();
  });

  it('sends url and text ingests as form fields, not JSON', () => {
    void api.ingestUrl('wlo', '', 'https://example.org');
    expect((http.expectOne('/studio/api/rag/ingest/url').request.body as FormData).get('url'))
      .toBe('https://example.org');

    void api.ingestText('wlo', 'Notiz', 'Inhalt');
    expect((http.expectOne('/studio/api/rag/ingest/text').request.body as FormData).get('content'))
      .toBe('Inhalt');
  });
});
