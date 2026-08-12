// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { RagDocumentsComponent } from './rag-documents.component';

const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const DOCS = [
  { title: 'Leitfaden', source: 'leitfaden.pdf', chunks: 7, preview: 'Erste Zeilen …' },
  { title: 'Leitfaden', source: 'https://x/y', chunks: 2, preview: 'Web-Fassung …' },
];

interface Harness {
  fixture: ComponentFixture<RagDocumentsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(docs: unknown[] = DOCS): Promise<Harness> {
  TestBed.resetTestingModule();
  // Siehe rag-ingest.component.spec.ts — jsdom meldet `en-US`.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(RagDocumentsComponent);
  fixture.componentRef.setInput('area', 'wlo');
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne('/studio/api/rag/area/wlo').flush(docs);
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

describe('RagDocumentsComponent', () => {
  it('lists the documents of its area with source and chunk count', async () => {
    const { el } = await mount();
    const rows = el.querySelectorAll('.rd-row');
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('Leitfaden');
    expect(rows[0].textContent).toContain('leitfaden.pdf');
    expect(rows[0].textContent).toContain('7');
  });

  it('reloads when it is pointed at another area', async () => {
    const { fixture, http } = await mount();
    fixture.componentRef.setInput('area', 'recht');
    await fixture.whenStable();
    http.expectOne('/studio/api/rag/area/recht').flush([]);
  });

  it('says an area is empty rather than showing nothing', async () => {
    const { el } = await mount([]);
    expect(el.textContent).toContain('keine Dokumente');
  });

  it('deletes exactly the (title, source) pair of the chosen row', async () => {
    // Both rows are titled "Leitfaden" — deleting by title would take both.
    const { el, fixture, http } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.rd-del')[1].click();
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.rd-del-yes')?.click();
    await fixture.whenStable();

    const req = http.expectOne((r) => r.url === '/studio/api/rag/area/wlo/doc');
    expect(req.request.method).toBe('DELETE');
    expect(req.request.params.get('title')).toBe('Leitfaden');
    expect(req.request.params.get('source')).toBe('https://x/y');
  });

  it('tells the page a document is gone, so the area counts stop lying', async () => {
    const { el, fixture, http } = await mount();
    const changes: unknown[] = [];
    fixture.componentInstance.changed.subscribe(() => changes.push(1));

    el.querySelectorAll<HTMLButtonElement>('.rd-del')[0].click();
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.rd-del-yes')?.click();
    await fixture.whenStable();
    http.expectOne((r) => r.url === '/studio/api/rag/area/wlo/doc').flush({ status: 'deleted' });
    await tick();
    await fixture.whenStable();

    http.expectOne('/studio/api/rag/area/wlo').flush([DOCS[1]]);
    await tick();
    expect(changes).toHaveLength(1);
  });

  it('loads the full text on request — the preview is 200 characters', async () => {
    const { el, fixture, http } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.rd-show')[0].click();
    await fixture.whenStable();

    const req = http.expectOne((r) => r.url === '/studio/api/rag/area/wlo/doc');
    expect(req.request.method).toBe('GET');
    req.flush({
      area: 'wlo', title: 'Leitfaden', source: 'leitfaden.pdf',
      chunk_count: 2, total_chars: 40,
      chunks: [{ index: 0, content: 'Abschnitt eins', created_at: '' },
               { index: 1, content: 'Abschnitt zwei', created_at: '' }],
    });
    await tick();
    await fixture.whenStable();

    const chunks = Array.from(el.querySelectorAll('.rd-chunk-body')).map((c) => c.textContent);
    expect(chunks).toEqual(['Abschnitt eins', 'Abschnitt zwei']);
  });

  it('shows a failed document load in place, keeping the list usable', async () => {
    const { el, fixture, http } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.rd-show')[0].click();
    await fixture.whenStable();
    http.expectOne((r) => r.url === '/studio/api/rag/area/wlo/doc')
      .flush('x', { status: 500, statusText: 'Error' });
    await tick();
    await fixture.whenStable();

    expect(el.querySelector('[role="alert"]')?.textContent).toBeTruthy();
    expect(el.querySelectorAll('.rd-row')).toHaveLength(2);
  });

/**
 * B6: the confirmation appears under the button that armed it and the focus does
 * not move, so without a live region a screen reader learns nothing before the
 * second click. `role="alert"` carries the QUESTION only — a container that also
 * held the buttons would re-announce the whole thing every time a button label
 * flips to "Wird gelöscht …" (the trap A3 documented for the cost paragraph).
 */
  it('announces the confirmation question', async () => {
    const { el, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.rd-del')[0].click();
    await fixture.whenStable();
    const alert = el.querySelector('.rd-confirm [role="alert"]');
    expect(alert?.textContent).toContain('Wirklich löschen?');
    expect(alert?.querySelector('button')).toBeNull();
  });

  it('gibt jedem Knopf einen zugänglichen Namen, der sein Dokument nennt', async () => {
    // Beide Zeilen heissen „Leitfaden" und tragen dieselben sichtbaren
    // Beschriftungen — ohne das Ziel im Namen sind ihre Knöpfe für einen
    // Screenreader nicht unterscheidbar. Bis C1-d3c stand es in einem
    // `sr`-Bruchstück, das sich nicht übersetzen liess (C1-d3a).
    const { el, fixture } = await mount();
    expect(el.querySelector('.rd-row .sr')).toBeNull();
    expect(el.querySelectorAll<HTMLButtonElement>('.rd-show')[0].getAttribute('aria-label'))
      .toBe('Volltext anzeigen — Leitfaden');
    expect(el.querySelectorAll<HTMLButtonElement>('.rd-del')[0].getAttribute('aria-label'))
      .toBe('Löschen — Leitfaden');

    // Aufgeklappt benennt derselbe Knopf die andere Richtung.
    el.querySelectorAll<HTMLButtonElement>('.rd-show')[0].click();
    await fixture.whenStable();
    expect(el.querySelectorAll<HTMLButtonElement>('.rd-show')[0].getAttribute('aria-label'))
      .toBe('Volltext ausblenden — Leitfaden');
  });
});
