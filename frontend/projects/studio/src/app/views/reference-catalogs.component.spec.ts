// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { ReferenceCatalogsComponent } from './reference-catalogs.component';
import type { SignalElement } from './reference-catalogs';

const MATERIALS = '/studio/api/config/data/05-canvas/material-types';

interface Harness {
  fixture: ComponentFixture<ReferenceCatalogsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const SIGNALS: readonly SignalElement[] = [
  {
    id: 'effizient',
    modulations: {
      dimension: 'D1-Zeit', label: 'Effizient', tone: 'sachlich', length: 'kurz',
      skip_intro: true,
    },
  },
  {
    id: 'vertrauend',
    modulations: { dimension: 'D3-Haltung', label: 'Vertrauend', tone: 'empfehlend', length: 'mittel' },
  },
];

const MATERIAL_DOC = {
  area: '05-canvas/material-types',
  type: 'yaml',
  data: {
    material_types: [
      { id: 'auto', label: 'Automatisch', emoji: '🤖', category: 'didaktisch' },
      { id: 'vokabelliste', label: 'Vokabelliste', emoji: '🗣️', category: 'didaktisch' },
      { id: 'bericht', label: 'Bericht', emoji: '📊', category: 'analytisch' },
    ],
  },
};

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(
  signals: readonly SignalElement[] = SIGNALS,
  doc: Record<string, unknown> | null = MATERIAL_DOC,
): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(ReferenceCatalogsComponent);
  fixture.componentRef.setInput('signals', signals);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne(MATERIALS);
  if (doc === null) {
    req.flush({ detail: 'Bereich unbekannt.' }, { status: 404, statusText: 'Not Found' });
  } else {
    req.flush(doc);
  }
  await settle(h);
  return h;
}

const text = (h: Harness): string => h.el.textContent ?? '';

describe('ReferenceCatalogsComponent', () => {
  it('zeigt die Signal-Modulationen so, wie die Konfiguration sie führt', async () => {
    const h = await mount();
    // ALT tippte diese Tabelle ab und lag bei vier Zeilen daneben — u.a. genau
    // bei diesen beiden (`effizient` als "mittel", `vertrauend` als "keine
    // Overrides"). Hier kommt jede Zeile aus `/config/elements`.
    expect(text(h)).toContain('D1 — Zeit');
    expect(text(h)).toContain('effizient');
    expect(text(h)).toContain('kurz');
    expect(text(h)).toContain('ohne Einleitung');
    expect(text(h)).toContain('vertrauend');
    expect(text(h)).toContain('empfehlend');
  });

  it('sagt, dass die Signale noch fehlen, statt eine leere Tabelle zu zeigen', async () => {
    const h = await mount([]);
    expect(text(h)).toContain('Konfiguration');
    expect(h.el.querySelectorAll('table')).toHaveLength(1); // nur die Material-Tabelle
  });

  it('holt die Material-Typen und zählt Einträge und Typen getrennt', async () => {
    const h = await mount();
    expect(text(h)).toContain('Vokabelliste');
    expect(text(h)).toContain('Bericht');
    // 3 Einträge, davon ist `auto` der Selektor ⇒ 2 Typen. ALTs Kopie hatte
    // „Didaktisch (13)" über zwölf echten Typen stehen.
    expect(text(h)).toMatch(/3 Einträge/);
    expect(text(h)).toMatch(/2 Typen/);
  });

  it('zeigt den Satz des Backends, wenn die Material-Typen nicht laden', async () => {
    const h = await mount(SIGNALS, null);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Bereich unbekannt.');
  });
});
