// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { SessionsApi } from './sessions-api.service';

describe('SessionsApi — Löschen und Wartung (ST-6)', () => {
  let api: SessionsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    api = TestBed.inject(SessionsApi);
    http = TestBed.inject(HttpTestingController);
  });

  it('sendet beim Löschen JEDEN Schalter, auch die ausgeschalteten', async () => {
    // Der Endpunkt setzt drei Schalter ohne Angabe auf „löschen" — ein
    // weggelassenes `false` wäre ein `true`.
    const done = api.purge({
      messages: true, memory: false, quality_logs: false, safety_logs: false, sessions: false,
    });
    const req = http.expectOne((r) => r.url === '/studio/api/sessions/purge');
    expect(req.request.method).toBe('POST');
    expect(req.request.params.get('messages')).toBe('true');
    expect(req.request.params.get('memory')).toBe('false');
    expect(req.request.params.get('quality_logs')).toBe('false');
    expect(req.request.params.get('safety_logs')).toBe('false');
    expect(req.request.params.get('sessions')).toBe('false');
    expect(req.request.params.get('confirm')).toBe('true');
    req.flush({ status: 'purged', deleted: { messages: 4 } });
    expect(await done).toEqual({ messages: 4 });
  });

  it('liest Größe und Schätzung der Datenbank', async () => {
    const done = api.dbStats();
    const stats = { size_bytes: 2048, live_tuples: 9, dead_tuples: 1, reclaimable_bytes: 204 };
    const req = http.expectOne('/studio/api/sessions/db-stats');
    expect(req.request.method).toBe('GET');
    req.flush(stats);
    expect(await done).toEqual(stats);
  });

  it('räumt auf und meldet die Größe vorher und nachher', async () => {
    const done = api.optimize();
    const req = http.expectOne('/studio/api/sessions/optimize');
    expect(req.request.method).toBe('POST');
    req.flush({ status: 'optimized', before_bytes: 10, after_bytes: 8, reclaimed_bytes: 2 });
    expect(await done).toEqual({
      status: 'optimized', before_bytes: 10, after_bytes: 8, reclaimed_bytes: 2,
    });
  });

  it('fragt die Liste ohne Parameter, solange alle Herkünfte gelten (ST-9)', () => {
    // Der Standardaufruf bleibt byte-gleich — ohne `scope` antwortet der Server
    // wie vor ST-9.
    void api.list();
    http.expectOne('/studio/api/sessions/').flush([]);
  });

  it('fragt mit `scope`, wenn eine Herkunft gewählt ist (ST-9)', () => {
    void api.list('production');
    const req = http.expectOne((r) => r.url === '/studio/api/sessions/');
    expect(req.request.params.get('scope')).toBe('production');
    req.flush([]);
  });

  it('liest die Fristen je Protokoll (Paket 8, A)', async () => {
    const done = api.retention();
    const req = http.expectOne('/studio/api/sessions/retention');
    expect(req.request.method).toBe('GET');
    const zeile = { bereich: 'safety_logs', tage: 90, faellig: 2, aeltester: null };
    req.flush({ fristen: [zeile] });
    expect(await done).toEqual([zeile]);
  });

  it('zieht die Bereinigung vor und meldet je Protokoll, was gelöscht wurde (Paket 8, A)', async () => {
    const done = api.runRetention();
    const req = http.expectOne('/studio/api/sessions/retention');
    expect(req.request.method).toBe('POST');
    req.flush({ status: 'done', deleted: { safety_logs: 2, quality_logs: 0 } });
    expect(await done).toEqual({ safety_logs: 2, quality_logs: 0 });
  });
});
