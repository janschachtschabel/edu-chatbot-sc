// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { WidgetElementLoader } from '../core/widget-element-loader';
import { WidgetPreviewComponent } from './widget-preview.component';

interface Harness {
  fixture: ComponentFixture<WidgetPreviewComponent>;
  el: HTMLElement;
  load: ReturnType<typeof vi.fn>;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(load: () => Promise<void>): Promise<Harness> {
  const spy = vi.fn(load);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      { provide: WidgetElementLoader, useValue: { load: spy } },
    ],
  });
  const fixture = TestBed.createComponent(WidgetPreviewComponent);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, load: spy };
  await settle(h);
  return h;
}

const widget = (h: Harness): Element | null => h.el.querySelector('boerdi-chat');

function button(h: Harness, label: string): HTMLButtonElement {
  const match = Array.from(h.el.querySelectorAll('button'))
    .find((b) => (b.textContent ?? '').includes(label));
  if (!match) throw new Error(`Kein Knopf mit „${label}“: ${h.el.textContent}`);
  return match as HTMLButtonElement;
}

describe('WidgetPreviewComponent', () => {
  it('lädt das Element von selbst und zeigt bis dahin einen Fortschritt', async () => {
    let release!: () => void;
    const h = await mount(() => new Promise<void>((resolve) => { release = resolve; }));

    expect(h.load).toHaveBeenCalledTimes(1);
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain('wird geladen');
    expect(widget(h)).toBeNull();

    release();
    await settle(h);
    expect(widget(h)).not.toBeNull();
  });

  it('meldet einen gescheiterten Ladevorgang und lässt ihn wiederholen', async () => {
    // Ein Chunk kann fehlschlagen (Deploy während offener Sitzung, Netz weg).
    // Ohne Meldung bliebe eine leere Seite stehen, die wie „kein Widget" aussieht.
    let fail = true;
    const h = await mount(() => (fail ? Promise.reject(new Error('chunk')) : Promise.resolve()));

    const alert = h.el.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('konnte nicht geladen werden');
    expect(widget(h)).toBeNull();

    fail = false;
    button(h, 'Erneut versuchen').click();
    await settle(h);
    expect(h.load).toHaveBeenCalledTimes(2);
    expect(widget(h)).not.toBeNull();
    expect(h.el.querySelector('[role="alert"]')).toBeNull();
  });

  it('bettet das Element mit den Attributen ein, die im Studio gelten', async () => {
    const h = await mount(() => Promise.resolve());
    const el = widget(h)!;

    // Ohne diese beiden Abweichungen vom Default würde die Vorschau den
    // Studio-DOM als Besucher-Seite verschicken und eine Sitzung im
    // Studio-Browser festhalten.
    expect(el.getAttribute('auto-context')).toBe('false');
    expect(el.getAttribute('persist-session')).toBe('false');
    expect(el.getAttribute('initial-state')).toBe('expanded');
    expect(el.getAttribute('api-url')).toBe(window.location.origin);
    expect(el.getAttribute('page-context')).toBeNull();
  });

  it('übernimmt den Seitenkontext erst beim Absenden, nicht beim Tippen', async () => {
    const h = await mount(() => Promise.resolve());

    const select = h.el.querySelector('select') as HTMLSelectElement;
    select.value = 'topic';
    select.dispatchEvent(new Event('change'));
    await settle(h);

    const input = h.el.querySelector('input[type="text"]') as HTMLInputElement;
    input.value = 'eiszeit';
    input.dispatchEvent(new Event('input'));
    await settle(h);
    // Jeder Tastendruck würde sonst eine neue Sitzung starten.
    expect(widget(h)!.getAttribute('page-context')).toBeNull();

    (h.el.querySelector('form') as HTMLFormElement)
      .dispatchEvent(new Event('submit', { cancelable: true }));
    await settle(h);
    expect(JSON.parse(widget(h)!.getAttribute('page-context') ?? '{}')).toEqual({
      page_kind: 'topic',
      topic_page_slug: 'eiszeit',
      detection_source: 'studio:vorschau',
    });
  });

  it('erzeugt das Element neu, statt es weiterlaufen zu lassen', async () => {
    // Der Konfigurations-Boot (Begrüßung, Quick-Replies, Lotse) läuft EINMAL
    // beim Verbinden. Ein Neustart ohne neues Element zeigte den alten Stand.
    const h = await mount(() => Promise.resolve());
    const before = widget(h);

    button(h, 'Vorschau neu starten').click();
    await settle(h);

    expect(widget(h)).not.toBeNull();
    expect(widget(h)).not.toBe(before);
  });

  it('zeigt das Wertfeld nur bei Seitentypen, die einen Wert brauchen', async () => {
    const h = await mount(() => Promise.resolve());
    expect(h.el.querySelector('input[type="text"]')).toBeNull();

    const select = h.el.querySelector('select') as HTMLSelectElement;
    select.value = 'collection';
    select.dispatchEvent(new Event('change'));
    await settle(h);

    const input = h.el.querySelector('input[type="text"]') as HTMLInputElement;
    expect(input).not.toBeNull();
    expect(h.el.querySelector(`label[for="${input.id}"]`)?.textContent)
      .toContain('Sammlungs-ID');
  });

  it('behält den eingegebenen Wert beim Wechsel des Seitentyps', async () => {
    // Sammlung und Inhaltsseite meinen dieselbe UUID in anderer Bedeutung
    // (page_context.py:6-7) — Leeren hieße bei jedem Wechsel neu einfügen.
    const h = await mount(() => Promise.resolve());
    const select = h.el.querySelector('select') as HTMLSelectElement;

    select.value = 'collection';
    select.dispatchEvent(new Event('change'));
    await settle(h);
    const input = h.el.querySelector('input[type="text"]') as HTMLInputElement;
    input.value = 'abc-123';
    input.dispatchEvent(new Event('input'));
    await settle(h);

    select.value = 'content';
    select.dispatchEvent(new Event('change'));
    await settle(h);
    expect((h.el.querySelector('input[type="text"]') as HTMLInputElement).value).toBe('abc-123');
  });
});
