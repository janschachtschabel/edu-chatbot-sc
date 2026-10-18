// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { type AreaEffects, EffectsApi } from './effects-api.service';
import { ANSICHT_STORAGE_KEY, StudioAnsicht } from './studio-ansicht.service';

/**
 * Der Arbeitsbereich des Studios (Paket 14, A1): Agent oder Muster — es gibt keine Ansicht
 * „beide“ mehr. Startwert ist die Vorgabe-Maschine des Servers, eine Wahl wird je Browser gemerkt.
 */
const EFFECTS: AreaEffects = { engine: 'pattern', areas: {} };

describe('StudioAnsicht (Paket 14, A1)', () => {
  let effects: EffectsApi;

  function dienst(): StudioAnsicht {
    return TestBed.inject(StudioAnsicht);
  }

  beforeEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    effects = TestBed.inject(EffectsApi);
  });

  afterEach(() => vi.restoreAllMocks());

  it('startet ohne Wahl und ohne Wirkungen beim Agent — der Vorgabe im Betrieb', () => {
    expect(dienst().ansicht()).toBe('agent');
  });

  it('startet ohne Wahl bei der Vorgabe-Maschine des Servers', () => {
    effects.effects.set(EFFECTS);
    expect(dienst().ansicht()).toBe('pattern');
  });

  it('eine gemerkte Wahl geht vor der Vorgabe', () => {
    localStorage.setItem(ANSICHT_STORAGE_KEY, 'agent');
    effects.effects.set(EFFECTS);
    expect(dienst().ansicht()).toBe('agent');
  });

  it('ein gemerktes „beide“ aus Paket 13 zählt als keine Wahl', () => {
    localStorage.setItem(ANSICHT_STORAGE_KEY, 'beide');
    effects.effects.set(EFFECTS);
    expect(dienst().ansicht()).toBe('pattern');
  });

  it('merkt eine Wahl', () => {
    const a = dienst();
    a.waehle('pattern');
    expect(a.ansicht()).toBe('pattern');
    expect(localStorage.getItem(ANSICHT_STORAGE_KEY)).toBe('pattern');
  });

  it('ein gesperrter Speicher hält weder Lesen noch Wählen auf', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('gesperrt');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('gesperrt');
    });
    const a = dienst();
    expect(a.ansicht()).toBe('agent');
    a.waehle('pattern');
    expect(a.ansicht()).toBe('pattern');
  });

  it('zeigt: ohne Kennzeichnung immer, sonst nur im passenden Arbeitsbereich', () => {
    const a = dienst();
    a.waehle('pattern');
    expect(a.zeigt(undefined)).toBe(true);
    expect(a.zeigt(['pattern'])).toBe(true);
    expect(a.zeigt(['agent'])).toBe(false);
  });

  it('ein gescheitertes Nachladen der Wirkungen kippt den Arbeitsbereich nicht (Review #1)', () => {
    const a = dienst();
    effects.effects.set(EFFECTS);
    expect(a.ansicht()).toBe('pattern');
    effects.effects.set(null);
    expect(a.ansicht()).toBe('pattern');
  });

  it('ermittle wartet ohne Wahl auf die Vorgabe des Servers (Review #1)', async () => {
    const http = TestBed.inject(HttpTestingController);
    const start = dienst().ermittle();
    http.expectOne('/studio/api/config/effects').flush(EFFECTS);
    expect(await start).toBe('pattern');
  });

  it('ermittle fragt mit Wahl oder geladenen Wirkungen nicht nach', async () => {
    const http = TestBed.inject(HttpTestingController);
    localStorage.setItem(ANSICHT_STORAGE_KEY, 'agent');
    expect(await dienst().ermittle()).toBe('agent');
    http.expectNone('/studio/api/config/effects');
  });

  it('maschine ist die Maschine des Arbeitsbereichs (Filter für Analyse und Evaluation)', () => {
    const a = dienst();
    a.waehle('pattern');
    expect(a.maschine()).toBe('pattern');
  });
});
