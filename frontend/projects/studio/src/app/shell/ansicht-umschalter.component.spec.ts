// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { StudioAnsicht } from '../core/studio-ansicht.service';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
import { AnsichtUmschalterComponent } from './ansicht-umschalter.component';

/**
 * Der Umschalter im Kopf (Paket 13 E2, Paket 14): echte Radios in einem Fieldset — Gruppenname,
 * Pfeiltasten und Auswahlzustand kommen von der Plattform. Zwei Arbeitsbereiche, keine
 * Ansicht „beide“; ein Wechsel auf einer Seite des alten Bereichs führt zur neuen Startseite.
 */
@Component({ template: '' })
class LeerComponent {}

describe('AnsichtUmschalterComponent', () => {
  let fixture: ComponentFixture<AnsichtUmschalterComponent>;
  let el: HTMLElement;
  let ansicht: StudioAnsicht;

  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(),
        provideRouter([
          ...['patterns', 'uebersicht', 'agent-uebersicht', 'begruessung']
            .map((path) => ({ path, component: LeerComponent })),
          // Eine Agent-Seite mit ungespeicherter Änderung, deren Rückfrage abgebrochen wird.
          { path: 'agent-rolle', component: LeerComponent, canDeactivate: [() => false] },
        ]),
      ],
    });
    ansicht = TestBed.inject(StudioAnsicht);
    ansicht.waehle('agent');
    fixture = TestBed.createComponent(AnsichtUmschalterComponent);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  function radios(): HTMLInputElement[] {
    return [...el.querySelectorAll<HTMLInputElement>('input[type="radio"]')];
  }

  async function waehle(index: number): Promise<void> {
    const radio = radios()[index];
    radio.checked = true;
    radio.dispatchEvent(new Event('change'));
    await fixture.whenStable();
  }

  it('ist eine benannte Gruppe aus zwei Radios', () => {
    expect(el.querySelector('fieldset legend')?.textContent?.trim()).toBe('Arbeitsbereich');
    expect(radios().map((r) => r.closest('label')?.textContent?.trim())).toEqual(['Agent', 'Muster']);
    expect(new Set(radios().map((r) => r.name)).size).toBe(1);
  });

  it('markiert den aktuellen Arbeitsbereich', () => {
    expect(radios().map((r) => r.checked)).toEqual([true, false]);
  });

  it('eine Wahl stellt den Arbeitsbereich um', async () => {
    await waehle(1);
    expect(ansicht.ansicht()).toBe('pattern');
    expect(radios().map((r) => r.checked)).toEqual([false, true]);
  });

  it('führt von einer Seite des alten Arbeitsbereichs zur neuen Startseite', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/agent-uebersicht');
    await waehle(1);
    await fixture.whenStable();
    expect(router.url).toBe('/uebersicht');
  });

  it('bleibt beim alten Arbeitsbereich, wenn das Verlassen abgebrochen wird (Review #7)', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/agent-rolle');
    await waehle(1);
    await fixture.whenStable();
    expect(router.url).toBe('/agent-rolle');
    expect(ansicht.ansicht()).toBe('agent');
    expect(radios().map((r) => r.checked)).toEqual([true, false]);
  });

  it('bleibt auf einer gemeinsamen Seite stehen', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/begruessung');
    await waehle(1);
    await fixture.whenStable();
    expect(router.url).toBe('/begruessung');
  });

  it('sagt, was der Umschalter tut', () => {
    expect(el.querySelector('fieldset')?.getAttribute('title'))
      .toBe('Zeigt die Seiten des gewählten Betriebsmodus und die gemeinsamen.');
  });

  it('spricht Englisch, wenn das Studio es tut', async () => {
    TestBed.inject(StudioLanguageService).toggle();
    await fixture.whenStable();
    expect(el.querySelector('legend')?.textContent?.trim()).toBe('Workspace');
    expect(radios()[1].closest('label')?.textContent?.trim()).toBe('Patterns');
  });
});
