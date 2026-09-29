// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { EffectsApi } from './effects-api.service';

const ANTWORT = {
  engine: 'agent',
  areas: { '03-patterns': { pattern: 'voll', agent: 'keine' } },
};

describe('EffectsApi (ST-5)', () => {
  let api: EffectsApi;
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
    api = TestBed.inject(EffectsApi);
    http = TestBed.inject(HttpTestingController);
  });

  it('liest die Zuordnung und die Vorgabe-Maschine', async () => {
    expect(api.effects()).toBeNull();
    const done = api.refresh();
    http.expectOne('/studio/api/config/effects').flush(ANTWORT);
    await done;
    expect(api.effects()).toEqual(ANTWORT);
  });

  it('zeigt nach einem Fehlschlag lieber keine Hinweise als veraltete', async () => {
    const erste = api.refresh();
    http.expectOne('/studio/api/config/effects').flush(ANTWORT);
    await erste;
    const zweite = api.refresh();
    http.expectOne('/studio/api/config/effects')
      .flush('weg', { status: 500, statusText: 'Server Error' });
    await expect(zweite).resolves.toBeUndefined();
    expect(api.effects()).toBeNull();
  });
});
