// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { routes } from '../app.routes';
import { BackupComponent } from './backup.component';

const BASE = '/studio/api/config';

interface Harness {
  fixture: ComponentFixture<BackupComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(BackupComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  // The two children load on their own; the hull reads nothing.
  http.expectOne(`${BASE}/factory`).flush({ exists: false });
  http.expectOne(`${BASE}/snapshots`).flush([]);
  await settle(h);
  return h;
}

const text = (h: Harness): string => h.el.textContent ?? '';

function button(h: Harness, label: string): HTMLButtonElement {
  const match = Array.from(h.el.querySelectorAll('button'))
    .find((b) => (b.textContent ?? '').trim().startsWith(label));
  if (!match) throw new Error(`Kein Knopf "${label}" — vorhanden: ${
    Array.from(h.el.querySelectorAll('button')).map((b) => b.textContent?.trim()).join(' | ')}`);
  return match;
}

async function click(h: Harness, label: string): Promise<void> {
  button(h, label).click();
  await settle(h);
}

describe('BackupComponent', () => {
  beforeEach(() => {
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() });
  });

  it('hängt an der Route `sicherung`', async () => {
    // A finished view nobody can reach is not built (the 9-5c lesson).
    const children = routes.find((r) => r.path === '')!.children!;
    const route = children.find((r) => r.path === 'sicherung')!;
    const loaded = await (route.loadComponent as () => Promise<unknown>)();
    expect(loaded).toBe(BackupComponent);
  });

  it('zeigt beide Werkzeuge auf einer Seite', async () => {
    const h = await mount();
    expect(h.el.querySelector('studio-snapshots-panel')).toBeTruthy();
    expect(h.el.querySelector('studio-factory-panel')).toBeTruthy();
  });

  it('sagt, was in einem Backup steckt und was nicht', async () => {
    const h = await mount();
    // Config areas only — the Postgres dump is deferred to P10. Without this
    // sentence an operator would reasonably read "Backup" as "everything".
    expect(text(h)).toContain('Konfigurationsbereiche');
    expect(text(h)).toMatch(/keine Sessions|ohne Sessions/);
  });

  it('lädt das Backup als Datei statt die Seite zu verlassen', async () => {
    const h = await mount();
    await click(h, 'Backup herunterladen');
    const req = h.http.expectOne(`${BASE}/backup`);
    expect(req.request.responseType).toBe('blob');
    req.flush(new Blob(['PK']));
    await settle(h);
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it('spielt eine ZIP erst nach Rückfrage ein', async () => {
    const h = await mount();
    expect(button(h, 'Backup einspielen').disabled).toBe(true);

    const file = new File(['PK'], 'boerdi-config-backup.zip');
    h.fixture.componentInstance.onFile({ target: { files: [file] } } as unknown as Event);
    await settle(h);

    await click(h, 'Backup einspielen');
    h.http.expectNone(`${BASE}/restore`);
    // The confirmation names the file — the chosen name itself is shown by the
    // native file input, which jsdom does not render.
    expect(text(h)).toContain('boerdi-config-backup.zip');

    await click(h, 'Ja, einspielen');
    const req = h.http.expectOne(`${BASE}/restore`);
    expect((req.request.body as FormData).get('file')).toBe(file);
    req.flush({ status: 'restored', areas: 35 });
    await settle(h);
    expect(text(h)).toContain('35');
    // The chosen file STAYS chosen. Clearing the signal alone would leave the
    // native picker showing a file name next to a button that refuses to use
    // it, and clearing the input element too needs a DOM reach-around for no
    // gain — re-applying the same ZIP writes the same areas.
    expect(button(h, 'Backup einspielen').disabled).toBe(false);
  });

  it('zeigt den Satz des Backends, wenn die ZIP abgelehnt wird', async () => {
    const h = await mount();
    h.fixture.componentInstance.onFile(
      { target: { files: [new File(['x'], 'kaputt.zip')] } } as unknown as Event);
    await settle(h);
    await click(h, 'Backup einspielen');
    await click(h, 'Ja, einspielen');
    h.http.expectOne(`${BASE}/restore`).flush(
      { detail: 'Keine gültige ZIP-Datei.' }, { status: 413, statusText: 'Payload Too Large' });
    await settle(h);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Keine gültige ZIP-Datei.');
  });
});
