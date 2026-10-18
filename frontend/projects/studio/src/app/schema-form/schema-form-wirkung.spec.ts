// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';

import { type AreaEffects, EffectsApi } from '../core/effects-api.service';
import { ANSICHT_STORAGE_KEY } from '../core/studio-ansicht.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import type { JsonSchema } from './json-schema';
import { SchemaFormComponent } from './schema-form.component';

/**
 * Rundgang 3: Felder, die im offenen Arbeitsbereich nicht wirken, tragen eine Plakette — der
 * Nutzer will sie sehen (nicht ausblenden), aber wissen, dass sie dort nichts tun.
 */
const SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    muster_skills: { type: 'boolean', default: false },
    crisis_message: { type: 'string', default: '' },
    mode: { type: 'string', default: 'agent' },
  },
};

const EFFECTS: AreaEffects = {
  engine: 'agent',
  areas: { '01-base/engine': { pattern: 'teilweise', agent: 'teilweise' } },
  fields: {
    '01-base/engine': {
      muster_skills: { pattern: 'voll', agent: 'keine' },
      crisis_message: { pattern: 'keine', agent: 'extern' },
    },
  },
};

async function mount(ansicht: 'agent' | 'pattern', area: string | null = '01-base/engine') {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  localStorage.setItem(ANSICHT_STORAGE_KEY, ansicht);
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()),
      provideHttpClientTesting()],
  });
  TestBed.inject(EffectsApi).effects.set(EFFECTS);
  const fixture = TestBed.createComponent(SchemaFormComponent);
  fixture.componentRef.setInput('schema', SCHEMA);
  fixture.componentRef.setInput('value', { muster_skills: true, crisis_message: 'x', mode: 'agent' });
  if (area) fixture.componentRef.setInput('area', area);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

const zeile = (el: HTMLElement, id: string) =>
  el.querySelector(`[id="${id}"]`)!.closest('.sf-row')!.textContent ?? '';

describe('SchemaFormComponent — Wirkung je Feld (Rundgang 3)', () => {
  afterEach(() => localStorage.removeItem(ANSICHT_STORAGE_KEY));

  it('kennzeichnet im Agent-Arbeitsbereich Felder ohne Agent-Wirkung', async () => {
    const el = await mount('agent');
    expect(zeile(el, 'sf-muster_skills')).toContain('wirkt nur im Muster-Modus');
    expect(zeile(el, 'sf-crisis_message')).toContain('nur externer Auftrag');
    expect(zeile(el, 'sf-mode')).not.toContain('wirkt nur');
  });

  it('schweigt im Muster-Arbeitsbereich bei Muster-Feldern', async () => {
    const el = await mount('pattern');
    expect(zeile(el, 'sf-muster_skills')).not.toContain('wirkt nur');
  });

  it('schweigt ohne Bereich (etwa in Einzelformularen ohne Zuordnung)', async () => {
    const el = await mount('agent', null);
    expect(zeile(el, 'sf-muster_skills')).not.toContain('wirkt nur');
  });
});
