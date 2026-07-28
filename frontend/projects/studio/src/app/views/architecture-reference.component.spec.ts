// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { ArchitectureReferenceComponent } from './architecture-reference.component';
import { HOST_ATTRIBUTES, HOST_EVENTS, HOST_OUTPUTS } from './widget-contract-data';
import { provideRouter } from '@angular/router';

/**
 * The hull composes four section components; two of them need providers of
 * their own (the catalogue reads `/config/data/…`, the knowledge section links
 * to the Sicherung view). Both are flushed here so the hull's own assertions
 * never depend on a pending request.
 */
function mount(): HTMLElement {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(ArchitectureReferenceComponent);
  fixture.detectChanges();
  TestBed.inject(HttpTestingController)
    .expectOne('/studio/api/config/data/05-canvas/material-types')
    .flush({ area: '05-canvas/material-types', type: 'yaml', data: { material_types: [] } });
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('ArchitectureReferenceComponent', () => {
  it('uses native disclosures, so every section is keyboard-operable', () => {
    // ALT hand-rolled `useState(open)` + a toggle button per section
    // (InfoView.tsx:22-38). `<details>` is expandable for assistive technology
    // and findable by in-page search without any of that.
    const el = mount();
    const sections = el.querySelectorAll('details');
    expect(sections.length).toBeGreaterThanOrEqual(8);
    for (const section of Array.from(sections)) {
      expect(section.querySelector(':scope > summary')).toBeTruthy();
    }
  });

  it('opens on the pipeline and leaves the rest closed', () => {
    const el = mount();
    const open = Array.from(el.querySelectorAll('details')).filter((d) => d.open);
    expect(open).toHaveLength(1);
    expect(open[0].textContent).toContain('Verarbeitungs-Pipeline');
  });

  it('documents every host attribute the element accepts', () => {
    // This table is a specification, not decoration: an attribute missing here is
    // how `data-position` (8-5) and `inline-result-grouping` (8-7) stayed dead
    // long enough to ship. ALT's table listed 17 of the 18.
    const el = mount();
    const rows = el.querySelectorAll('.ar-table code');
    const documented = Array.from(rows).map((c) => c.textContent?.trim());
    for (const { attr } of HOST_ATTRIBUTES) {
      expect(documented, `Attribut ${attr}`).toContain(attr);
    }
    expect(HOST_ATTRIBUTES).toHaveLength(18);
    expect(HOST_ATTRIBUTES.map((a) => a.attr)).toContain('inline-result-grouping');
  });

  it('names each attribute group once instead of on every row', () => {
    const el = mount();
    const groups = Array.from(el.querySelectorAll('.ar-group'))
      .map((c) => c.textContent?.trim()).filter((label) => label !== '');
    expect(groups).toEqual(['Basis', 'Session', 'Kontext', 'Anzeige', 'Integration']);
  });

  it('lists the four window events and the four Angular outputs', () => {
    const el = mount();
    const text = el.textContent ?? '';
    for (const event of HOST_EVENTS) expect(text).toContain(event.name);
    // ALT claimed a fifth output, `(pageAction)`, which its own widget never
    // declared (widget.component.ts:119-146) — page-action is a window event.
    expect(HOST_OUTPUTS).toHaveLength(4);
    expect(HOST_OUTPUTS).not.toContain('pageAction');
    expect(text).toContain('badboerdi:page-action');
    expect(text).toContain('nur als window-Event');
  });

  it('describes the self-ID override as it works in NEU', () => {
    // ALT's row cited the routing rule `lookup_persona_self_id__*` two sections
    // after saying that engine was removed. NEU has `persona_overrides` in
    // classify-overrides.yaml, rendered into the classifier prompt.
    const el = mount();
    const text = el.textContent ?? '';
    expect(text).toContain('persona_overrides');
    expect(text).toContain('classify-overrides.yaml');
  });

  it('keeps wide tables inside their own scroll box', () => {
    // SC 1.4.10: the page itself must never scroll sideways at 320px.
    const el = mount();
    for (const table of Array.from(el.querySelectorAll('.ar-table'))) {
      const boxed = table.closest('.ar-scroll') !== null
        || table.classList.contains('ar-table--fields');
      expect(boxed, table.querySelector('th')?.textContent ?? '?').toBe(true);
    }
  });

  it('sends the reader to the Übersicht tab for the live counts', () => {
    // The figures live in one place; repeating them here is what went stale in
    // ALT's "Anzahl" column.
    expect(mount().textContent).toContain('stehen im Tab „Übersicht“');
  });
});
