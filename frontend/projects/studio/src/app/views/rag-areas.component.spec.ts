// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { RagAreasComponent } from './rag-areas.component';

const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const AREAS = [
  { area: 'wlo', chunks: 12, documents: 3 },
  { area: 'recht', chunks: 4, documents: 1 },
];

interface Harness {
  fixture: ComponentFixture<RagAreasComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(open = true): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(RagAreasComponent);
  fixture.componentRef.setInput('section', {
    panel: 'rag-areas', label: 'Wissensbereiche', hint: 'Was der Bot nachschlagen kann.',
  });
  fixture.componentRef.setInput('open', open);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

async function withAreas(areas: unknown[] = AREAS): Promise<Harness> {
  const harness = await mount();
  harness.http.expectOne('/studio/api/rag/areas').flush(areas);
  await tick();
  await harness.fixture.whenStable();
  return harness;
}

describe('RagAreasComponent', () => {
  it('lists every area with its chunk and document counts', async () => {
    const { el } = await withAreas();
    const rows = Array.from(el.querySelectorAll('.ra-row')).map((r) => r.textContent);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toContain('wlo');
    expect(rows[0]).toContain('12');
    expect(rows[0]).toContain('3');
  });

  it('does not fetch before the panel is opened', async () => {
    const { http } = await mount(false);
    http.verify(); // nine collapsed panels must not fire nine requests on arrival
  });

  it('says what an empty knowledge base means and how to fill it', async () => {
    const { el } = await withAreas([]);
    expect(el.textContent).toContain('Noch keine Wissensbereiche');
    expect(el.textContent).toContain('Dokumente hinzufügen');
  });

  it('shows a failed load as an error, not as an empty knowledge base', async () => {
    const { el, fixture, http } = await mount();
    http.expectOne('/studio/api/rag/areas').flush('x', { status: 500, statusText: 'Error' });
    await tick();
    await fixture.whenStable();
    expect(el.querySelector('[role="alert"]')?.textContent).toBeTruthy();
    expect(el.textContent).not.toContain('Noch keine Wissensbereiche');
  });

  it('loads the documents of the area that was chosen', async () => {
    const { el, fixture, http } = await withAreas();
    el.querySelectorAll<HTMLButtonElement>('.ra-open')[1].click();
    await fixture.whenStable();
    http.expectOne('/studio/api/rag/area/recht').flush([]);
  });

  it('asks before deleting an area, and does nothing when the ask is cancelled', async () => {
    // A knowledge area is many ingested documents; there is no undo.
    const { el, fixture, http } = await withAreas();
    el.querySelectorAll<HTMLButtonElement>('.ra-del')[0].click();
    await fixture.whenStable();
    expect(el.textContent).toContain('Wirklich löschen');

    el.querySelector<HTMLButtonElement>('.ra-del-no')?.click();
    await fixture.whenStable();
    http.verify(); // cancelled means no request at all
    expect(el.textContent).not.toContain('Wirklich löschen');
  });

  it('deletes the confirmed area and re-reads the list', async () => {
    const { el, fixture, http } = await withAreas();
    el.querySelectorAll<HTMLButtonElement>('.ra-del')[0].click();
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.ra-del-yes')?.click();
    await fixture.whenStable();

    const req = http.expectOne('/studio/api/rag/area/wlo');
    expect(req.request.method).toBe('DELETE');
    req.flush({ status: 'deleted' });
    await tick();
    await fixture.whenStable();
    http.expectOne('/studio/api/rag/areas').flush([AREAS[1]]);
  });

  it('confirms only the area that was asked about', async () => {
    // One shared "confirm" flag would arm every row at once.
    const { el, fixture } = await withAreas();
    el.querySelectorAll<HTMLButtonElement>('.ra-del')[1].click();
    await fixture.whenStable();
    expect(el.querySelectorAll('.ra-del-yes')).toHaveLength(1);
    expect(el.querySelectorAll('.ra-row')[1].textContent).toContain('Wirklich löschen');
  });

/**
 * B6: the confirmation appears under the button that armed it and the focus does
 * not move, so without a live region a screen reader learns nothing before the
 * second click. `role="alert"` carries the QUESTION only — a container that also
 * held the buttons would re-announce the whole thing every time a button label
 * flips to "Wird gelöscht …" (the trap A3 documented for the cost paragraph).
 */
  it('announces the confirmation question', async () => {
    const { el, fixture } = await withAreas();
    el.querySelectorAll<HTMLButtonElement>('.ra-del')[0].click();
    await fixture.whenStable();
    const alert = el.querySelector('.ra-confirm [role="alert"]');
    expect(alert?.textContent).toContain('Wirklich löschen?');
    expect(alert?.querySelector('button')).toBeNull();
  });
});
