// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { BApiBetrieb } from '../core/overview-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { BApiBetriebComponent } from './b-api-betrieb.component';

/** Plan 2026-11-19 (N1): die Betriebsart der b-api, wie diese Backend-Kopie sie zuletzt sah. */
async function mount(info: BApiBetrieb | null, sprache = 'de'): Promise<HTMLElement> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, sprache);
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(BApiBetriebComponent);
  fixture.componentRef.setInput('info', info);
  fixture.componentRef.setInput('bezugMs', Date.parse('2026-11-19T10:05:00Z'));
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

const AM = '2026-11-19T10:00:00+00:00';

function info(teil: Partial<BApiBetrieb>): BApiBetrieb {
  return { modus: 'auto', zuletzt: 'delegation', zuletzt_am: AM, abgewiesen: 0, warnungen: [],
    ...teil };
}

describe('BApiBetriebComponent', () => {
  it('nennt die Delegation hinter dem Proxy mit Zeit und Modus', async () => {
    const el = await mount(info({}));
    const text = el.textContent ?? '';
    expect(text).toContain('Betriebsart erkannt: hinter dem b-api-Proxy (Delegation)');
    expect(text).toContain('vor 5 Minuten');
    expect(text).toContain('auto');
    expect(el.querySelector('[role="status"]')).toBeNull();
  });

  it('sagt, dass die Angabe nur diese Backend-Kopie betrifft', async () => {
    expect((await mount(info({}))).textContent).toContain('(diese Backend-Kopie)');
    expect((await mount(info({}), 'en')).textContent).toContain('(this backend instance)');
  });

  it('nennt den Direktbetrieb', async () => {
    const el = await mount(info({ zuletzt: 'direkt' }));
    expect(el.textContent).toContain('direkt (B_API_KEY)');
  });

  it('nennt unter forward die Abweisungen und warnt', async () => {
    const el = await mount(info({ modus: 'forward', zuletzt: null, zuletzt_am: null,
      abgewiesen: 3, warnungen: ['forward_ohne_token'] }));
    expect(el.textContent).toContain('noch keine Nutzeranfrage');
    expect(el.textContent).toContain('abgewiesen: 3');
    const warnung = el.querySelector('[role="status"]')?.textContent ?? '';
    expect(warnung).toContain('forward gesetzt, aber kein Token gesehen');
  });

  it('nennt ohne forward keine Abweisungen', async () => {
    expect((await mount(info({}))).textContent).not.toContain('abgewiesen');
  });

  it('weist auf den fehlenden Zugangsblock hin und nennt den anonymen Normalfall', async () => {
    const el = await mount(info({ warnungen: ['zugangsblock_fehlt'] }));
    const warnung = el.querySelector('[role="status"]')?.textContent ?? '';
    expect(warnung).toContain('Zugangsblock fehlt hinter dem Proxy');
    expect(warnung).toContain('allowedRequestHeaders');
    expect(warnung).toContain('anonym');
  });

  it('spricht Englisch', async () => {
    const el = await mount(info({ zuletzt: 'schluessel', modus: 'forward', abgewiesen: 1 }), 'en');
    expect(el.textContent).toContain('Mode detected: behind the b-api proxy (forwarded key)');
    expect(el.textContent).toContain('rejected: 1');
  });

  it('zeigt nichts ohne Angabe (älteres Backend)', async () => {
    const el = await mount(null);
    expect(el.textContent?.trim()).toBe('');
  });
});
