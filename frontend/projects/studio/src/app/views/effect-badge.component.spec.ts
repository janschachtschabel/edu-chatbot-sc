// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { type AreaEffects, EffectsApi } from '../core/effects-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EffectBadgeComponent } from './effect-badge.component';

const ZUORDNUNG: AreaEffects = {
  engine: 'pattern',
  areas: {
    beide: { pattern: 'voll', agent: 'teilweise' },
    muster: { pattern: 'voll', agent: 'keine' },
    nirgends: { pattern: 'keine', agent: 'keine' },
    krise: { pattern: 'voll', agent: 'krise' },
    engine: { pattern: 'teilweise', agent: 'teilweise' },
  },
  fields: {
    engine: { agent_rolle: { pattern: 'keine', agent: 'voll' }, agent: { pattern: 'keine', agent: 'voll' } },
    sicherheit: { crisis_message: { pattern: 'keine', agent: 'extern' } },
  },
};

async function text(
  area: string, effects: AreaEffects | null = ZUORDNUNG, felder?: string[],
): Promise<string> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()), provideHttpClientTesting()],
  });
  TestBed.inject(EffectsApi).effects.set(effects);
  const fixture = TestBed.createComponent(EffectBadgeComponent);
  fixture.componentRef.setInput('area', area);
  if (felder) fixture.componentRef.setInput('felder', felder);
  await fixture.whenStable();
  return ((fixture.nativeElement as HTMLElement).textContent ?? '').replace(/\s+/g, ' ').trim();
}

describe('EffectBadgeComponent (ST-5)', () => {
  it('nennt beide Maschinen, die teilweise mit Zusatz', async () => {
    expect(await text('beide')).toBe('Wirkt in: Muster-Maschine · Agent-Schleife (teilweise)');
  });

  it('nennt nur die Maschine, in der der Bereich wirkt', async () => {
    expect(await text('muster')).toBe('Wirkt in: Muster-Maschine');
  });

  it('nennt die Krisen-Züge, die auch unter der Agent-Schleife der Muster-Weg beantwortet', async () => {
    expect(await text('krise')).toBe(
      'Wirkt in: Muster-Maschine · Agent-Schleife (nur Krisen-Züge)');
  });

  it('sagt es, wenn ein Bereich derzeit nirgends wirkt', async () => {
    expect(await text('nirgends')).toBe('Wirkt derzeit in keiner Maschine');
  });

  it('schweigt ohne Zuordnung — lieber kein Hinweis als ein geratener', async () => {
    expect(await text('unbekannt')).toBe('');
    expect(await text('beide', null)).toBe('');
  });
});

describe('EffectBadgeComponent — Feld-Ausschnitt (Rundgang 3)', () => {
  it('nennt die Wirkung der gezeigten Felder, nicht die des Bereichs', async () => {
    expect(await text('engine', ZUORDNUNG, ['agent_rolle', 'agent'])).toBe('Wirkt in: Agent-Schleife');
  });

  it('nennt „nur externer Auftrag“ für die Stufe extern', async () => {
    const z: AreaEffects = { ...ZUORDNUNG, areas: { ...ZUORDNUNG.areas,
      sicherheit: { pattern: 'keine', agent: 'voll' } } };
    expect(await text('sicherheit', z, ['crisis_message'])).toBe(
      'Wirkt in: Agent-Schleife (nur externer Auftrag /api/agent)');
  });
});
