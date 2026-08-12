// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';

interface Harness {
  fixture: ComponentFixture<AsyncStateComponent>;
  el: HTMLElement;
  set: (inputs: Record<string, unknown>) => Promise<void>;
}

async function mount(
  inputs: Record<string, unknown> = {},
  locale: 'de' | 'en' = 'de',
): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'`; ohne die oberste Quelle
  // stünde dieser Streifen hier auf Englisch (C1-c-Fund).
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(AsyncStateComponent);
  const set = async (next: Record<string, unknown>): Promise<void> => {
    for (const [key, value] of Object.entries(next)) fixture.componentRef.setInput(key, value);
    await fixture.whenStable();
  };
  await set({ label: 'Sessions', ...inputs });
  return { fixture, el: fixture.nativeElement as HTMLElement, set };
}

describe('AsyncStateComponent', () => {
  it('renders nothing at all once the data is there', async () => {
    const { el } = await mount();
    expect(el.textContent?.trim()).toBe('');
  });

  it('announces loading as busy', async () => {
    const { el } = await mount({ loading: true });
    const busy = el.querySelector('[aria-busy="true"]');
    expect(busy?.textContent).toContain('Sessions');
  });

  // ── Der Satz gehört dem Katalog, nicht der Aufrufstelle (C1-d3a) ──────
  //
  // Vorher stand hier `{{ label() }} werden geladen …`: das Subjekt kam aus
  // einer anderen Datei, das Verb aus dieser. Das war schon einsprachig falsch
  // (sechs der 21 Aufrufe übergeben einen Singular) und zweisprachig gar nicht
  // zu machen — die Wortstellung ist Teil der Übersetzung.
  it('baut den Lade-Satz nicht aus Bruchstücken zusammen', async () => {
    const einzahl = await mount({ loading: true, label: 'Lauf' });
    expect(einzahl.el.textContent).toContain('Lade Lauf …');
    const mehrzahl = await mount({ loading: true, label: 'Sessions' });
    expect(mehrzahl.el.textContent).toContain('Lade Sessions …');
  });

  it('übersetzt seine eigenen Texte mit', async () => {
    const { el } = await mount({ loading: true, label: 'Sessions' }, 'en');
    expect(el.textContent).toContain('Loading Sessions …');
  });

  it('nennt dem Screenreader, WAS der Knopf erneut lädt', async () => {
    // Mehrere Streifen auf einer Seite tragen denselben sichtbaren Text; ohne
    // das Ziel im zugänglichen Namen sind ihre Knöpfe nicht unterscheidbar.
    const { el } = await mount({ error: 'kaputt', label: 'Snapshots' });
    const knopf = el.querySelector<HTMLButtonElement>('.as-retry');
    expect(knopf?.textContent?.trim()).toBe('Erneut versuchen');
    expect(knopf?.getAttribute('aria-label')).toBe('Erneut versuchen — Snapshots');
  });

  it('shows a failure as an alert with a way out', async () => {
    const { el } = await mount({ error: 'Backend nicht erreichbar.' });
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('Backend nicht erreichbar.');
    expect(el.querySelector('.as-retry')).not.toBeNull();
  });

  it('asks for a retry instead of retrying by itself', async () => {
    const { el, fixture } = await mount({ error: 'kaputt' });
    let retries = 0;
    fixture.componentInstance.retry.subscribe(() => { retries += 1; });
    el.querySelector<HTMLButtonElement>('.as-retry')?.click();
    expect(retries).toBe(1);
  });

  it('says what an empty list means, in the caller’s words', async () => {
    const { el } = await mount({
      empty: true, emptyText: 'Noch keine Sessions — das Widget legt sie an.',
    });
    expect(el.textContent).toContain('das Widget legt sie an');
  });

  it('prefers loading over a stale error, so a retry looks like it started', async () => {
    // Leaving the old alert up during the retry reads as "it failed again".
    const { el } = await mount({ error: 'kaputt' });
    const { set } = await mount({ error: 'kaputt', loading: true });
    expect(el.querySelector('[role="alert"]')).not.toBeNull();
    await set({});
    expect(document.querySelector('[role="alert"]')).toBeNull();
  });

  it('prefers an error over emptiness — a failed load is not an empty list', async () => {
    const { el } = await mount({ error: 'kaputt', empty: true, emptyText: 'Nichts da.' });
    expect(el.querySelector('[role="alert"]')).not.toBeNull();
    expect(el.textContent).not.toContain('Nichts da.');
  });
});
