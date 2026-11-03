// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DomSanitizer } from '@angular/platform-browser';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { UiInhaltsrahmen, type UiInhaltsrahmenDaten } from './ui-inhaltsrahmen.component';

function host(): ModulHost & { [k: string]: ReturnType<typeof vi.fn> } {
  return {
    herunterladen: vi.fn(),
    drucken: vi.fn(),
    markdown: vi.fn((text: string) =>
      TestBed.inject(DomSanitizer).bypassSecurityTrustHtml(`<p class="md">${text}</p>`)),
  } as never;
}

async function render(daten: UiInhaltsrahmenDaten, mehr: Partial<ModulKontext> = {}) {
  const h = host();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: h }],
  });
  const f = TestBed.createComponent(UiInhaltsrahmen);
  f.componentRef.setInput('daten', daten);
  f.componentRef.setInput('kontext', {
    blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null, ...mehr,
  });
  await f.whenStable();
  return { el: f.nativeElement as HTMLElement, h };
}

afterEach(() => TestBed.resetTestingModule());

describe('UiInhaltsrahmen', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const daten = beispiel.daten as UiInhaltsrahmenDaten;
      const { el, h } = await render(daten);
      expect(el.querySelector('.inline-document__title')?.textContent?.trim()).toBe(daten.titel);
      expect(h['markdown']).toHaveBeenCalledWith(daten.markdown);
      expect(el.querySelector('.inline-document__body .md')).not.toBeNull();
    });
  }

  it('Drucken gibt Titel und Markdown an den Host', async () => {
    const { el, h } = await render({ titel: 'Plan', art: 'stundenplanung', markdown: '## A' });
    (el.querySelector('button[data-aktion="drucken"]') as HTMLButtonElement).click();
    expect(h['drucken']).toHaveBeenCalledWith('Plan', '## A');
  });

  it('Herunterladen bietet die Markdown-Datei an', async () => {
    const { el, h } = await render({ titel: 'Mein Plan', art: 'stundenplanung', markdown: 'Text' });
    (el.querySelector('button[data-aktion="herunterladen"]') as HTMLButtonElement).click();
    expect(h['herunterladen']).toHaveBeenCalledWith('mein-plan.md', 'text/markdown;charset=utf-8', '# Mein Plan\n\nText\n');
  });

  it('beide Knöpfe tragen einen sprechenden Namen in der Sprache des Widgets', async () => {
    const de = await render({ titel: 'P', art: 'lernpfad', markdown: 'x' });
    const namenDe = [...de.el.querySelectorAll('button')].map((b) => b.getAttribute('aria-label'));
    expect(namenDe).toEqual(['Als PDF drucken / speichern', 'Als Markdown herunterladen']);
    TestBed.resetTestingModule();
    const en = await render({ titel: 'P', art: 'lernpfad', markdown: 'x' }, { sprache: 'en' });
    const namenEn = [...en.el.querySelectorAll('button')].map((b) => b.getAttribute('aria-label'));
    expect(namenEn).toEqual(['Print / save as PDF', 'Download as Markdown']);
  });

  it('ohne Titel steht die Bezeichnung der Art', async () => {
    const { el } = await render({ titel: '', art: 'lernpfad', markdown: 'x' });
    expect(el.querySelector('.inline-document__title')?.textContent?.trim()).toBe('Lernpfad');
  });

  it('übernimmt die Schriftgröße aus dem Kontext', async () => {
    const { el } = await render({ titel: 'P', art: 'lernpfad', markdown: 'x' }, { schriftSkala: 0.7 });
    const box = el.querySelector('.inline-document') as HTMLElement;
    expect(box.style.getPropertyValue('--inline-doc-scale')).toBe('0.7');
  });

  it('Symbole sind für Vorleser verborgen (aria-hidden, Review U1 gesamt)', async () => {
    const { el } = await render(manifest.beispiele[0].daten as UiInhaltsrahmenDaten);
    const symbole = [...el.querySelectorAll('.bb-icon')];
    expect(symbole.length).toBeGreaterThan(0);
    expect(symbole.filter((s) => s.getAttribute('aria-hidden') !== 'true')).toEqual([]);
  });
});
