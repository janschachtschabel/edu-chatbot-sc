// @vitest-environment jsdom
import { ApplicationRef, provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ResultGroupsContext } from '@boerdi/ui/grouping/result-grouping';
import { DE } from '@boerdi/ui/i18n/de';
import { createTranslator } from '@boerdi/ui/i18n/dictionary';

import { MODUL_HOST, type ModulHost, type TrefferUmgebung } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { UiTrefferliste, type UiTrefferlisteDaten } from './ui-trefferliste.component';

const KONTEXT_DER_SHELL: ResultGroupsContext = {
  withBsid: (u) => u ?? '',
  externalLinkWarning: () => '',
  isTrustedHost: () => false,
  t: createTranslator(DE, DE),
};

function host(umgebung: Partial<TrefferUmgebung> = {}) {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), markdown: vi.fn(), link: vi.fn(),
    treffer: vi.fn(() => ({ kontext: KONTEXT_DER_SHELL, kacheln: false, beschaeftigt: false, ...umgebung })),
    aktion: vi.fn(),
  };
}

async function render(daten: UiTrefferlisteDaten, h = host(), anzeigeRegeln: Record<string, unknown> | null = null) {
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: h as unknown as ModulHost }],
  });
  const f = TestBed.createComponent(UiTrefferliste);
  f.componentRef.setInput('daten', daten);
  const kontext: ModulKontext = {
    blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln,
  };
  f.componentRef.setInput('kontext', kontext);
  await f.whenStable();
  return { el: f.nativeElement as HTMLElement, h };
}

afterEach(() => TestBed.resetTestingModule());

describe('UiTrefferliste (Textlink-Boxen)', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const { el } = await render(beispiel.daten as UiTrefferlisteDaten);
      expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
      expect(el.querySelector('boerdi-search-cta')).not.toBeNull();
    });
  }

  it('zeigt Sammlungen und Materialien wie die bisherigen Boxen', async () => {
    const { el } = await render(manifest.beispiele[0].daten as UiTrefferlisteDaten);
    const text = el.textContent ?? '';
    expect(text).toContain('Sammlung Optik');
    expect(text).toContain('Video: Licht und Schatten');
  });

  it('bei Typ-Fokus nur der Such-Absprung, keine Treffer-Boxen', async () => {
    const { el } = await render(manifest.beispiele[1].daten as UiTrefferlisteDaten);
    expect(el.querySelectorAll('.result-group__item').length).toBe(0);
    expect(el.querySelector('boerdi-search-cta')).not.toBeNull();
  });


  it('während ein Zug läuft, ist „Inhalt anzeigen“ gesperrt', async () => {
    const daten: UiTrefferlisteDaten = {
      karten: [{ node_id: 'm1', title: 'Arbeitsblatt', node_type: 'content', url: 'https://wirlernenonline.de/m1' }],
      such_metas: [], seiten: null, typ_fokus: '',
    };
    const { el } = await render(daten, host({ beschaeftigt: true }));
    expect((el.querySelector('button.result-group__item-btn') as HTMLButtonElement).disabled).toBe(true);
  });

  it('die Gruppen-Grenzen kommen aus den Anzeige-Regeln', async () => {
    const karten = [1, 2, 3].map((i) => ({
      node_id: `m${i}`, title: `Material ${i}`, node_type: 'content', url: `https://wirlernenonline.de/m${i}`,
    }));
    const { el } = await render({ karten, such_metas: [], seiten: null, typ_fokus: '' }, host(),
      { groups: { materialien_max: 2 } });
    expect(el.querySelectorAll('a.result-group__item').length).toBe(2);
  });

  it('„Inhalt anzeigen“ läuft über die Host-Aktion volltext', async () => {
    const daten: UiTrefferlisteDaten = {
      karten: [{ node_id: 'm1', title: 'Arbeitsblatt', node_type: 'content', url: 'https://wirlernenonline.de/m1' }],
      such_metas: [], seiten: null, typ_fokus: '',
    };
    const { el, h } = await render(daten);
    const knopf = [...el.querySelectorAll('button')].find((b) => /Inhalt/i.test(b.textContent ?? '') || /Inhalt/i.test(b.getAttribute('aria-label') ?? ''));
    expect(knopf).toBeTruthy();
    knopf!.click();
    expect(h.aktion).toHaveBeenCalledWith('volltext', { nodeId: 'm1', title: 'Arbeitsblatt' });
  });
});

// ── U1-c2b: Kacheln ───────────────────────────────────────────────────────
function karten(n: number, typ = 'content') {
  return Array.from({ length: n }, (_, i) => ({
    node_id: `k${i}`, title: `Karte ${i}`, node_type: typ, url: `https://wirlernenonline.de/k${i}`,
  }));
}

describe('UiTrefferliste (Kacheln)', () => {
  it('zeigt im Kachel-Modus die Kachelliste statt der Boxen', async () => {
    const { el } = await render(manifest.beispiele[0].daten as UiTrefferlisteDaten, host({ kacheln: true }));
    expect(el.querySelector('boerdi-card-list')).not.toBeNull();
    expect(el.querySelector('boerdi-result-groups')).toBeNull();
    expect(el.querySelectorAll('.wlo-card-wrapper').length).toBe(2);
  });

  it('„mehr anzeigen“ deckt fünf weitere Karten auf — im Modul, ohne die Nachricht', async () => {
    const { el, h } = await render({ karten: karten(12), such_metas: [], seiten: null, typ_fokus: '' },
      host({ kacheln: true }));
    expect(el.querySelectorAll('.wlo-card-wrapper').length).toBe(5);
    const mehr = [...el.querySelectorAll('.pagination-bar button')][0] as HTMLButtonElement;
    mehr.click();
    await TestBed.inject(ApplicationRef).whenStable();
    expect(el.querySelectorAll('.wlo-card-wrapper').length).toBe(10);
    expect(h.aktion).not.toHaveBeenCalled();
  });

  it('anfangs eine Seite der Sammlung sichtbar (page_size wie bisher)', async () => {
    const seiten = { total_count: 20, skip_count: 0, page_size: 10, has_more: true, collection_id: 'c1', collection_title: 'M' };
    const { el } = await render({ karten: karten(12), such_metas: [], seiten, typ_fokus: '' }, host({ kacheln: true }));
    expect(el.querySelectorAll('.wlo-card-wrapper').length).toBe(10);
  });

  it('„mehr laden“ bittet den Host mit der Block-Kennung', async () => {
    const seiten = { total_count: 12, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe' };
    const { el, h } = await render({ karten: karten(5), such_metas: [], seiten, typ_fokus: '' }, host({ kacheln: true }));
    (el.querySelector('.pagination-bar button') as HTMLButtonElement).click();
    expect(h.aktion).toHaveBeenCalledWith('mehrLaden', { blockId: 'b1' });
  });

  it('kommen neue Karten (nach „mehr laden“), stehen alle sichtbar da', async () => {
    const seiten = { total_count: 12, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe' };
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: host({ kacheln: true }) as unknown as ModulHost }],
    });
    const f = TestBed.createComponent(UiTrefferliste);
    f.componentRef.setInput('daten', { karten: karten(5), such_metas: [], seiten, typ_fokus: '' });
    f.componentRef.setInput('kontext', {
      blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
    });
    await f.whenStable();
    f.componentRef.setInput('daten', { karten: karten(10), such_metas: [], seiten: { ...seiten, has_more: false }, typ_fokus: '' });
    await f.whenStable();
    expect((f.nativeElement as HTMLElement).querySelectorAll('.wlo-card-wrapper').length).toBe(10);
  });

  it('Sammlung öffnen und Lernpfad laufen über Host-Aktionen', async () => {
    const { el, h } = await render({ karten: karten(1, 'collection'), such_metas: [], seiten: null, typ_fokus: '' },
      host({ kacheln: true }));
    const knoepfe = [...el.querySelectorAll('.wlo-card-wrapper button')] as HTMLButtonElement[];
    knoepfe.forEach((k) => k.click());
    const namen = h.aktion.mock.calls.map((c: unknown[]) => c[0]);
    expect(namen).toContain('sammlung');
    expect(namen).toContain('lernpfad');
    expect(h.aktion).toHaveBeenCalledWith('sammlung', { nodeId: 'k0', title: 'Karte 0' });
  });
});

