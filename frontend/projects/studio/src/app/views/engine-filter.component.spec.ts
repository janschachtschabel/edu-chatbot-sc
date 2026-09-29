// @vitest-environment jsdom
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { EngineFilter } from '../core/eval-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EngineFilterComponent } from './engine-filter.component';

@Component({
  selector: 'studio-engine-filter-host',
  imports: [EngineFilterComponent],
  template: `<studio-engine-filter inputId="x-engine" [value]="value()"
                                   (valueChange)="value.set($event)" />`,
})
class HostComponent {
  readonly value = signal<EngineFilter>('');
}

async function mount(locale = 'de'): Promise<ComponentFixture<HostComponent>> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(HostComponent);
  await fixture.whenStable();
  return fixture;
}

const select = (f: ComponentFixture<HostComponent>): HTMLSelectElement =>
  (f.nativeElement as HTMLElement).querySelector<HTMLSelectElement>('#x-engine')!;

describe('EngineFilterComponent (ST-7a)', () => {
  it('bietet alle Maschinen, die Muster-Maschine und die Agent-Schleife an', async () => {
    const f = await mount();
    const auswahl = select(f);
    expect(auswahl.labels?.[0]?.textContent).toContain('Maschine');
    expect([...auswahl.options].map((o) => [o.value, o.textContent?.trim()])).toEqual([
      ['', 'alle Maschinen'], ['pattern', 'Muster-Maschine'], ['agent', 'Agent-Schleife'],
    ]);
    expect(auswahl.value).toBe('');
  });

  it('meldet die Wahl und zeigt sie an', async () => {
    const f = await mount();
    select(f).value = 'agent';
    select(f).dispatchEvent(new Event('change'));
    await f.whenStable();

    expect(f.componentInstance.value()).toBe('agent');
    expect(select(f).value).toBe('agent');
  });

  it('spricht Englisch', async () => {
    const f = await mount('en');
    expect(select(f).labels?.[0]?.textContent).toContain('Engine');
    expect(select(f).options[0].textContent?.trim()).toBe('all engines');
  });
});
