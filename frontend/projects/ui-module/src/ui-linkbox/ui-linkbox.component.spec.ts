// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DE } from '@boerdi/ui/i18n/de';
import { EN } from '@boerdi/ui/i18n/en';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { UiLinkbox, type UiLinkboxDaten } from './ui-linkbox.component';

/** Host-Attrappe: hängt eine Sitzungs-Kennung an und warnt bei fremden Seiten. */
function host(): ModulHost {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), markdown: vi.fn(),
    link: vi.fn((url: string) => url.includes('wirlernenonline.de')
      ? { href: `${url}?bsid=s1`, hinweis: '' }
      : { href: url, hinweis: 'Externe Seite' }),
  } as unknown as ModulHost;
}

async function render(daten: UiLinkboxDaten, sprache: 'de' | 'en' = 'de') {
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: host() }],
  });
  const f = TestBed.createComponent(UiLinkbox);
  f.componentRef.setInput('daten', daten);
  const kontext: ModulKontext = { blockId: 'b1', sprache, nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
  f.componentRef.setInput('kontext', kontext);
  await f.whenStable();
  return f.nativeElement as HTMLElement;
}

afterEach(() => TestBed.resetTestingModule());

describe('UiLinkbox', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const daten = beispiel.daten as UiLinkboxDaten;
      const el = await render(daten);
      expect(el.querySelectorAll('a.result-group__item').length).toBe(daten.links.length);
    });
  }

  it('sieht aus wie die bisherige Box: Rahmen, Überschrift, Einträge', async () => {
    const el = await render({ links: [{ titel: 'WLO', url: 'https://wirlernenonline.de/' }] });
    expect(el.querySelector('.result-groups .result-group.result-group--web')).not.toBeNull();
    expect(el.querySelector('.result-group__heading')?.textContent?.trim()).toBe('Webseiten-Inhalte');
    expect(el.querySelector('.result-group__item-title')?.textContent).toBe('WLO');
  });

  it('Adresse und Hinweis kommen vom Host (Sitzungs-Kennung, fremde Seiten)', async () => {
    const el = await render({ links: [
      { titel: 'WLO', url: 'https://wirlernenonline.de/' },
      { titel: '', url: 'https://example.org/x' },
    ] });
    const [wlo, fremd] = [...el.querySelectorAll('a')] as HTMLAnchorElement[];
    expect(wlo.getAttribute('href')).toBe('https://wirlernenonline.de/?bsid=s1');
    expect(wlo.getAttribute('title')).toBe('WLO (Webseite)');
    expect(fremd.getAttribute('title')).toBe('Webseite — Externe Seite');
    for (const a of [wlo, fremd]) {
      expect(a.getAttribute('target')).toBe('_blank');
      expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    }
  });

  it('ein Link ohne Titel trägt sichtbar „Webseite“', async () => {
    const el = await render({ links: [{ titel: '', url: 'https://example.org/x' }] });
    expect(el.querySelector('.result-group__item-title')?.textContent).toBe('Webseite');
  });

  it('die Texte gleichen denen der bisherigen Box (Shell-Wörterbuch)', async () => {
    for (const [sprache, buch] of [['de', DE], ['en', EN]] as const) {
      TestBed.resetTestingModule();
      const el = await render({ links: [
        { titel: 'T', url: 'https://wirlernenonline.de/' }, { titel: '', url: 'https://wirlernenonline.de/2' },
      ] }, sprache);
      expect(el.querySelector('.result-group__heading')?.textContent?.trim()).toBe(buch['groups.web']);
      const [mit, ohne] = [...el.querySelectorAll('a')];
      expect(mit.getAttribute('title')).toBe(buch['groups.webItem'].replace('{title}', 'T'));
      expect(ohne.getAttribute('title')).toBe(buch['groups.webItemUntitled']);
    }
  });

  it('spricht Englisch, wenn das Widget es tut', async () => {
    const el = await render({ links: [{ titel: '', url: 'https://example.org/x' }] }, 'en');
    expect(el.querySelector('.result-group__heading')?.textContent?.trim()).toBe('Web page contents');
    expect(el.querySelector('a')?.getAttribute('title')).toBe('Web page — Externe Seite');
  });
});
