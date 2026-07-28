// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { RagIngestComponent } from './rag-ingest.component';

const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<RagIngestComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(RagIngestComponent);
  fixture.componentRef.setInput('section', {
    panel: 'rag-ingest', label: 'Dokumente hinzufügen', hint: 'Datei, Webseite oder Text.',
  });
  fixture.componentRef.setInput('open', true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

/** Type into a field and let the view settle — "Einlesen" only enables then. */
async function type(h: Harness, selector: string, value: string): Promise<void> {
  const field = h.el.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector);
  if (!field) throw new Error(`no field: ${selector}`);
  field.value = value;
  field.dispatchEvent(new Event('input'));
  await h.fixture.whenStable();
}

async function submit(h: Harness): Promise<void> {
  h.el.querySelector<HTMLButtonElement>('.ri-go')?.click();
  await h.fixture.whenStable();
}

async function pickMode(h: Harness, value: string): Promise<void> {
  const radio = h.el.querySelector<HTMLInputElement>(`input[name$="-mode"][value="${value}"]`);
  if (!radio) throw new Error(`no mode: ${value}`);
  radio.checked = true;
  radio.dispatchEvent(new Event('change'));
  await h.fixture.whenStable();
}

describe('RagIngestComponent', () => {
  it('offers the three sources as a real radio group', async () => {
    // Native radios give arrow-key selection and aria-checked for free; ALT's
    // button row had to hand-roll both and rolled neither.
    const { el } = await mount();
    const values = Array.from(el.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
      .map((r) => r.value);
    expect(values).toEqual(['file', 'url', 'text']);
  });

  it('refuses to send before there is anything to send', async () => {
    const { el, http } = await mount();
    expect(el.querySelector<HTMLButtonElement>('.ri-go')?.disabled).toBe(true);
    http.verify();
  });

  it('names what is still missing instead of just greying the button out', async () => {
    const h = await mount();
    expect(h.el.querySelector('.ri-missing')?.textContent)
      .toContain('ein Wissensbereich und eine Datei');

    await type(h, '.ri-area', 'wlo');
    expect(h.el.querySelector('.ri-missing')?.textContent).toContain('eine Datei');
    expect(h.el.querySelector('.ri-missing')?.textContent).not.toContain('Wissensbereich');
  });

  it('uploads a chosen file into the named area', async () => {
    const h = await mount();
    await type(h, '.ri-area', 'recht');
    await type(h, '.ri-title', 'Schulgesetz');
    const file = new File(['x'], 'gesetz.pdf', { type: 'application/pdf' });
    h.fixture.componentInstance.onFile({ target: { files: [file] } } as unknown as Event);
    await h.fixture.whenStable();

    await submit(h);

    const body = h.http.expectOne('/studio/api/rag/ingest/file').request.body as FormData;
    expect(body.get('area')).toBe('recht');
    expect(body.get('title')).toBe('Schulgesetz');
    expect((body.get('file') as File).name).toBe('gesetz.pdf');
  });

  it('sends a URL when the URL source is chosen', async () => {
    const h = await mount();
    await pickMode(h, 'url');
    await type(h, '.ri-area', 'wlo');
    await type(h, '.ri-url', 'https://example.org/seite');
    await submit(h);

    const body = h.http.expectOne('/studio/api/rag/ingest/url').request.body as FormData;
    expect(body.get('url')).toBe('https://example.org/seite');
  });

  it('reports what was ingested, in chunks', async () => {
    const h = await mount();
    await pickMode(h, 'text');
    await type(h, '.ri-area', 'wlo');
    await type(h, '.ri-text', 'Ein Satz.');
    await submit(h);

    h.http.expectOne('/studio/api/rag/ingest/text')
      .flush({ status: 'ok', area: 'wlo', title: 'Notiz', chunks: 3 });
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.ri-result')?.textContent).toContain('3');
  });

  it('re-reads the area list after an ingest, so the counts above are current', async () => {
    const h = await mount();
    await pickMode(h, 'text');
    await type(h, '.ri-area', 'neu');
    await type(h, '.ri-text', 'Inhalt');
    await submit(h);
    h.http.expectOne('/studio/api/rag/ingest/text')
      .flush({ status: 'ok', area: 'neu', title: '', chunks: 1 });
    await tick();
    await h.fixture.whenStable();

    h.http.expectOne('/studio/api/rag/areas').flush([]);
  });

  it('keeps the entered text when the ingest fails', async () => {
    // Losing a pasted document to a 400 is the whole cost of the request.
    const h = await mount();
    await pickMode(h, 'text');
    await type(h, '.ri-area', 'wlo');
    await type(h, '.ri-text', 'Mühsam getippt');
    await submit(h);

    h.http.expectOne('/studio/api/rag/ingest/text')
      .flush({ detail: 'Fehler beim Konvertieren' }, { status: 400, statusText: 'Bad Request' });
    await tick();
    await h.fixture.whenStable();

    // The backend's sentence, not the transport envelope: `err.message` reads
    // "HTTP 400 /rag/ingest/text — …" and has no business on the page.
    expect(h.el.querySelector('[role="alert"]')?.textContent?.trim())
      .toBe('Fehler beim Konvertieren');
    expect(h.el.querySelector<HTMLTextAreaElement>('.ri-text')?.value).toBe('Mühsam getippt');
  });

  it('blocks a second send while the first is running', async () => {
    const h = await mount();
    await pickMode(h, 'text');
    await type(h, '.ri-area', 'wlo');
    await type(h, '.ri-text', 'Inhalt');
    await submit(h);

    expect(h.el.querySelector<HTMLButtonElement>('.ri-go')?.disabled).toBe(true);
    await submit(h);
    h.http.expectOne('/studio/api/rag/ingest/text'); // exactly one, not two
  });
});
