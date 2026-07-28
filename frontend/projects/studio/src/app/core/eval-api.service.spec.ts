import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { EvalApi } from './eval-api.service';

const BASE = '/studio/api/eval';

describe('EvalApi', () => {
  let api: EvalApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(EvalApi);
    http = TestBed.inject(HttpTestingController);
  });

  it('unwraps the run list', async () => {
    const promise = api.runs();
    const req = http.expectOne((r) => r.url === `${BASE}/runs`);
    expect(req.request.params.get('limit')).toBe('50');
    req.flush({ runs: [{ id: 'r1' }] });
    expect((await promise).map((r) => r.id)).toEqual(['r1']);
  });

  it('survives a run list without the wrapper key', async () => {
    // Every list endpoint in this studio is defensive about the envelope: a 200
    // with an unexpected body must not throw inside a template.
    const promise = api.runs();
    http.expectOne((r) => r.url === `${BASE}/runs`).flush({});
    expect(await promise).toEqual([]);
  });

  it('unwraps the gold flows', async () => {
    const promise = api.goldFlows();
    http.expectOne((r) => r.url === `${BASE}/gold-flows`)
      .flush({ flows: [{ id: 'f1', name: 'Suche' }], count: 1 });
    expect((await promise).map((f) => f.id)).toEqual(['f1']);
  });

  it('asks for an estimate with the whole form, as a body', async () => {
    void api.estimate({
      mode: 'both', persona_ids: ['P01'], intent_ids: [],
      scenarios_per_combo: 2, turns_per_conv: 3,
    });
    const req = http.expectOne((r) => r.url === `${BASE}/estimate`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      mode: 'both', persona_ids: ['P01'], intent_ids: [],
      scenarios_per_combo: 2, turns_per_conv: 3,
    });
    req.flush({ est_usd: 1.2 });
  });

  it('starts a generative run with the config slug included', async () => {
    void api.startRun({
      mode: 'scenarios', persona_ids: [], intent_ids: ['I02'],
      scenarios_per_combo: 1, turns_per_conv: 3, config_slug: 'wlo/v1',
    });
    const req = http.expectOne((r) => r.url === `${BASE}/runs` && r.method === 'POST');
    expect(req.request.body.config_slug).toBe('wlo/v1');
    req.flush({ run_id: 'r9' });
  });

  it('starts a golden run', async () => {
    void api.startGoldenRun({ flow_ids: ['f1'], judge: false, config_slug: '' });
    const req = http.expectOne((r) => r.url === `${BASE}/runs/golden`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ flow_ids: ['f1'], judge: false, config_slug: '' });
    req.flush({ run_id: 'g1' });
  });

  it('reads one run and deletes one run', async () => {
    void api.run('r1');
    http.expectOne((r) => r.url === `${BASE}/runs/r1` && r.method === 'GET').flush({ id: 'r1' });

    void api.deleteRun('r1');
    http.expectOne((r) => r.url === `${BASE}/runs/r1` && r.method === 'DELETE')
      .flush({ deleted: 'r1' });
  });

  it('confirms a bulk delete only when nothing narrows it', async () => {
    // The endpoint refuses an unrestricted wipe without `confirm=true`; a status
    // or mode filter counts as a restriction. Mirrored so the flag is sent
    // exactly when it is required — same rule as the quality-log clear.
    void api.deleteRuns({});
    expect(http.expectOne((r) => r.url === `${BASE}/runs` && r.method === 'DELETE')
      .request.params.get('confirm')).toBe('true');
    http.verify();

    void api.deleteRuns({ status: 'failed' });
    const narrowed = http.expectOne((r) => r.url === `${BASE}/runs` && r.method === 'DELETE');
    expect(narrowed.request.params.get('status')).toBe('failed');
    expect(narrowed.request.params.has('confirm')).toBe(false);
    narrowed.flush({ deleted: 2 });
  });

  it('passes the mode filter through under its own name', async () => {
    void api.deleteRuns({ mode: 'golden' });
    const req = http.expectOne((r) => r.url === `${BASE}/runs` && r.method === 'DELETE');
    expect(req.request.params.get('mode')).toBe('golden');
    expect(req.request.params.has('status')).toBe(false);
    req.flush({ deleted: 1 });
  });

  it('clears the quality logs the eval runs wrote', async () => {
    void api.clearEvalQualityLogs();
    const req = http.expectOne((r) => r.url === `${BASE}/quality-logs`);
    expect(req.request.method).toBe('DELETE');
    req.flush({ deleted: 12 });
  });

  it('reads the trends with an explicit window', async () => {
    void api.trends();
    expect(http.expectOne((r) => r.url === `${BASE}/trends`).request.params.get('limit'))
      .toBe('20');
  });

  it('scopes the pattern usage and drops an empty "since"', async () => {
    void api.patternUsage('eval', '');
    const req = http.expectOne((r) => r.url === `${BASE}/analytics/pattern-usage`);
    expect(req.request.params.get('scope')).toBe('eval');
    expect(req.request.params.has('since')).toBe(false);
    req.flush({ triples: [], by_pattern: [], by_intent: [], total: 0, scope: 'eval' });
  });

  it('reads the personas and intents that a run can be scoped to', async () => {
    void api.config();
    http.expectOne((r) => r.url === `${BASE}/config`)
      .flush({ personas: [{ id: 'P01' }], intents: [{ id: 'I02' }] });
  });
});
