// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { OverviewApi, type HealthInfo } from '../core/overview-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EinbettungHerkuenfteComponent } from './einbettung-herkuenfte.component';

/** Plan 2026-11-07 (R4): die Einbettung sichtbar machen, damit sie am MCP-Server gleich steht. */
async function mount(health: () => Promise<HealthInfo>): Promise<HTMLElement> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: OverviewApi, useValue: { health } }],
  });
  const fixture = TestBed.createComponent(EinbettungHerkuenfteComponent);
  fixture.componentRef.setInput('backendHerkunft', 'https://boerdi.example');
  await new Promise((r) => setTimeout(r, 0));
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('EinbettungHerkuenfteComponent', () => {
  it('zeigt die Liste und die Werte für den MCP-Server', async () => {
    const el = await mount(async () => ({ einbettung: {
      offen: false, herkuenfte: ['https://wirlernenonline.de', 'https://redaktion.example'],
      muster: null } }));
    expect(el.querySelectorAll('li')).toHaveLength(2);
    expect(el.textContent).toContain(
      'TICKET_ALLOWED_ORIGINS=https://wirlernenonline.de,https://redaktion.example');
    expect(el.textContent).toContain('WIDGET_OAUTH_ORIGINS=https://boerdi.example');
    expect(el.textContent).not.toContain('Offen: jede Seite');
  });

  it('warnt bei offener Einbettung und nennt die übersteuerte Liste', async () => {
    const el = await mount(async () => ({ einbettung: {
      offen: true, herkuenfte: ['https://a.example'], muster: '^chrome-extension://.*$' } }));
    expect(el.textContent).toContain('Offen: jede Seite');
    expect(el.textContent).toContain('übersteuert');
    expect(el.textContent).toContain('^chrome-extension://.*$');
  });

  it('übernimmt nur, was der MCP-Server als Herkunft annimmt', async () => {
    const el = await mount(async () => ({ einbettung: {
      offen: false, herkuenfte: ['*', 'chatbot.example.org', 'https://wlo.example/pfad/',
        'https://wlo.example'], muster: null } }));
    expect(el.textContent).toContain('TICKET_ALLOWED_ORIGINS=https://wlo.example');
    expect(el.textContent).not.toContain('TICKET_ALLOWED_ORIGINS=*');
    expect(el.textContent).toContain('Nicht übernommen');
    expect(el.textContent).toContain('chatbot.example.org');
  });

  it('verträgt doppelte Einträge', async () => {
    const el = await mount(async () => ({ einbettung: {
      offen: false, herkuenfte: ['https://a.example', 'https://a.example'], muster: null } }));
    expect(el.querySelectorAll('li')).toHaveLength(2);
    expect(el.textContent).toContain('TICKET_ALLOWED_ORIGINS=https://a.example');
    expect(el.textContent).not.toContain('https://a.example,https://a.example');
  });

  it('nennt keine Zeile, wenn nichts Brauchbares in der Liste steht', async () => {
    const el = await mount(async () => ({ einbettung: { offen: false, herkuenfte: ['*'], muster: null } }));
    expect(el.textContent).not.toContain('TICKET_ALLOWED_ORIGINS');
    expect(el.textContent).toContain('Nicht übernommen');
  });

  it('sagt, wenn keine Seite eingetragen ist', async () => {
    const el = await mount(async () => ({ einbettung: { offen: true, herkuenfte: [], muster: null } }));
    expect(el.textContent).toContain('Keine Seite eingetragen.');
    expect(el.textContent).not.toContain('TICKET_ALLOWED_ORIGINS');
  });

  it('meldet einen Lesefehler mit Wiederholen-Knopf', async () => {
    const el = await mount(async () => { throw new Error('weg'); });
    expect(el.querySelector('[role="alert"]')).not.toBeNull();
    expect(el.querySelector('button')).not.toBeNull();
  });
});
