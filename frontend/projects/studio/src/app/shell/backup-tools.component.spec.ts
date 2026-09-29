// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { BackupToolsComponent } from './backup-tools.component';

const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));
const BASE = '/studio/api/config';

@Component({ standalone: true, template: '<p>Seite</p>' })
class StubViewComponent {}

interface Harness {
  fixture: ComponentFixture<BackupToolsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideRouter([
        { path: 'sicherung', component: StubViewComponent },
        { path: 'anderswo', component: StubViewComponent },
      ]),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(BackupToolsComponent);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
}

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

function button(h: Harness, text: string): HTMLButtonElement {
  const found = [...h.el.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!found) throw new Error(`kein Knopf „${text}"`);
  return found;
}

function link(h: Harness, text: string): HTMLAnchorElement {
  const found = [...h.el.querySelectorAll('a')].find((a) => a.textContent?.trim() === text);
  if (!found) throw new Error(`kein Link „${text}"`);
  return found;
}

describe('BackupToolsComponent (ST-9, Kopfzeile)', () => {
  beforeEach(() => {
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() });
  });

  it('bietet Snapshot, Backup und Einspielen als Gruppe „Sicherung" an', async () => {
    const h = await mount();
    const gruppe = h.el.querySelector('[role="group"]');
    expect(gruppe?.getAttribute('aria-label')).toBe('Sicherung');
    expect(button(h, 'Snapshot anlegen')).toBeTruthy();
    expect(button(h, 'Backup herunterladen')).toBeTruthy();
    // Einspielen ersetzt die ganze Konfiguration: Datei-Wahl und Rückfrage
    // stehen auf der Sicherungs-Seite, die Kopfzeile führt nur dorthin.
    expect(link(h, 'Backup einspielen …').getAttribute('href')).toBe('/sicherung#voll-backup');
  });

  it('legt einen Snapshot sofort an und führt zur Liste', async () => {
    const h = await mount();
    button(h, 'Snapshot anlegen').click();
    await settle(h);
    const req = h.http.expectOne(`${BASE}/snapshots`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ label: '' });
    req.flush({ id: 'snap-7', label: '' });
    await settle(h);

    expect(h.el.querySelector('[role="status"]')?.textContent).toContain('Snapshot „snap-7“ angelegt.');
    expect(link(h, 'Zu den Snapshots').getAttribute('href')).toBe('/sicherung#snapshots');
  });

  it('lädt das Backup als Datei', async () => {
    const h = await mount();
    button(h, 'Backup herunterladen').click();
    await settle(h);
    const req = h.http.expectOne(`${BASE}/backup`);
    expect(req.request.responseType).toBe('blob');
    req.flush(new Blob(['PK']));
    await settle(h);
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain('Backup heruntergeladen.');
  });

  it('sperrt beide Knöpfe, solange einer läuft', async () => {
    const h = await mount();
    button(h, 'Snapshot anlegen').click();
    await settle(h);
    expect(button(h, 'Wird angelegt …').disabled).toBe(true);
    expect(button(h, 'Backup herunterladen').disabled).toBe(true);
    h.http.expectOne(`${BASE}/snapshots`).flush({ id: 'snap-8', label: '' });
    await settle(h);
    expect(button(h, 'Snapshot anlegen').disabled).toBe(false);
  });

  it('meldet einen Fehlschlag als Alarm', async () => {
    const h = await mount();
    button(h, 'Snapshot anlegen').click();
    await settle(h);
    h.http.expectOne(`${BASE}/snapshots`)
      .flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle(h);
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain('⚠');
  });

  it('räumt die Meldung auf Zuruf weg — die Shell ruft das beim Seitenwechsel', async () => {
    // Die Kopfzeile bleibt über alle Seiten stehen — eine Meldung zur letzten
    // Aktion gehört nicht auf die nächste Seite. Den Wechsel meldet die Shell
    // (`onViewActivated`); das Frontend hält bewusst keine Router-Abos.
    const h = await mount();
    button(h, 'Snapshot anlegen').click();
    await settle(h);
    h.http.expectOne(`${BASE}/snapshots`).flush({ id: 'snap-9', label: '' });
    await settle(h);
    expect(h.el.querySelector('[role="status"]')).not.toBeNull();

    h.fixture.componentInstance.dismiss();
    await settle(h);
    expect(h.el.querySelector('[role="status"]')).toBeNull();
  });
});
