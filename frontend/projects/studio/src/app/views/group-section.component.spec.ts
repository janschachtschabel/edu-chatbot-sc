// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { AREA_SCHEMAS } from '../schema-form/area-schemas.fixture';
import type { CuratedSection } from './curated-views';
import { GroupSectionComponent } from './group-section.component';

const PATTERNS: CuratedSection = {
  area: '03-patterns',
  kind: 'group',
  label: 'Gesprächsmuster',
  hint: 'Ein Dokument je Muster.',
};

/** Dieselbe Gruppe, aber mit ALTs Reiter-Gliederung (A7). */
const PATTERNS_TABS: CuratedSection = { ...PATTERNS, feature: 'pattern-tabs' };

const ELEMENTS = {
  patterns: [
    { id: 'M01', label: 'Orientierung', file: '03-patterns/m01-orientierung.md' },
    { id: 'M02', label: 'Suche', file: '03-patterns/m02-suche.md' },
  ],
  personas: [{ id: 'lehrkraft', label: 'Lehrkraft', file: '04-personas/lehrkraft.md' }],
};

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<GroupSectionComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(section: CuratedSection = PATTERNS): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(GroupSectionComponent);
  fixture.componentRef.setInput('section', section);
  fixture.componentRef.setInput('open', true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne('/studio/api/config/elements').flush(ELEMENTS);
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

/** Answer the schema+data pair for one document of the group. */
function answerDoc(http: HttpTestingController, key: string, data: Record<string, unknown>): void {
  http.expectOne(`/studio/api/config/schema/${key}`).flush(AREA_SCHEMAS['03-patterns']);
  http.expectOne(`/studio/api/config/data/${key}`).flush({ area: key, data, type: 'md' });
}

describe('GroupSectionComponent', () => {
  it('lists the documents of its group with their labels', async () => {
    const { el } = await mount();
    const options = Array.from(el.querySelectorAll('.gs-entry')).map((b) => b.textContent?.trim());
    expect(options).toEqual(['M01 — Orientierung', 'M02 — Suche']);
  });

  it('reads the other group from the same response', async () => {
    const { el } = await mount({
      area: '04-personas', kind: 'group', label: 'Personas', hint: 'Zielgruppen.',
    });
    const options = Array.from(el.querySelectorAll('.gs-entry')).map((b) => b.textContent?.trim());
    expect(options).toEqual(['lehrkraft — Lehrkraft']);
  });

  it('loads a document when it is picked, addressed by its own key', async () => {
    const { el, http, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[1].click();
    await fixture.whenStable();

    answerDoc(http, '03-patterns/m02-suche', { frontmatter: { id: 'M02' }, body: '# Suche' });
    await tick();
    await fixture.whenStable();
    expect(fixture.componentInstance.editor.doc()).toEqual({
      frontmatter: { id: 'M02' }, body: '# Suche',
    });
  });

  it('refuses to switch documents with unsaved changes', async () => {
    // Switching would silently drop them — the list is not a discard control.
    const { el, http, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[0].click();
    await fixture.whenStable();
    answerDoc(http, '03-patterns/m01-orientierung', { frontmatter: {}, body: 'alt' });
    await tick();
    await fixture.whenStable();

    fixture.componentInstance.editor.setDoc({ frontmatter: {}, body: 'neu' });
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[1].click();
    await fixture.whenStable();

    http.verify(); // no load for M02
    expect(fixture.componentInstance.selected()).toBe('03-patterns/m01-orientierung');
    expect(el.textContent).toContain('speichern oder verwerfen');
  });

  it('saves the WHOLE document of the selected entry', async () => {
    const { el, http, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[0].click();
    await fixture.whenStable();
    answerDoc(http, '03-patterns/m01-orientierung', {
      frontmatter: { id: 'M01' }, body: 'alt', eigener_schluessel: 1,
    });
    await tick();
    await fixture.whenStable();

    fixture.componentInstance.editor.setDoc({
      frontmatter: { id: 'M01' }, body: 'neu', eigener_schluessel: 1,
    });
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.gs-save')?.click();
    await fixture.whenStable();

    const req = http.expectOne('/studio/api/config/data/03-patterns/m01-orientierung');
    expect(req.request.body).toEqual({
      data: { frontmatter: { id: 'M01' }, body: 'neu', eigener_schluessel: 1 },
    });
  });

  it('creates a new document under a key derived from the name', async () => {
    const { el, http, fixture } = await mount();
    const input = el.querySelector<HTMLInputElement>('.gs-new-name');
    input!.value = 'M03 Kuratieren';
    input!.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.gs-new-go')?.click();
    await fixture.whenStable();

    const req = http.expectOne('/studio/api/config/file');
    expect(req.request.method).toBe('PUT');
    expect(req.request.body.path).toBe('03-patterns/m03-kuratieren.md');
    expect(req.request.body.content).toContain('label: "M03 Kuratieren"');
    req.flush({ status: 'saved' });
    await fixture.whenStable();
    // the list is re-read so the new entry appears
    http.expectOne('/studio/api/config/elements').flush(ELEMENTS);
  });

  it('quotes the name, so a colon or a newline cannot rewrite the frontmatter', async () => {
    // `label: Kuratieren: schnell` is not valid YAML (the store answers 400),
    // and a name containing a newline would add keys of its own.
    const { el, http, fixture } = await mount();
    const input = el.querySelector<HTMLInputElement>('.gs-new-name');
    input!.value = 'Kuratieren: schnell';
    input!.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.gs-new-go')?.click();
    await fixture.whenStable();

    const req = http.expectOne('/studio/api/config/file');
    expect(req.request.body.content).toContain('label: "Kuratieren: schnell"');
    req.flush({ status: 'saved' });
    await fixture.whenStable();
    http.expectOne('/studio/api/config/elements').flush(ELEMENTS);
  });

  it('refuses to create while the open document has unsaved changes', async () => {
    // Creating switches the selection, which would drop those edits without
    // a word — the same trap as switching entries.
    const { el, http, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[0].click();
    await fixture.whenStable();
    answerDoc(http, '03-patterns/m01-orientierung', { frontmatter: {}, body: 'alt' });
    await tick();
    await fixture.whenStable();
    fixture.componentInstance.editor.setDoc({ frontmatter: {}, body: 'neu' });

    const input = el.querySelector<HTMLInputElement>('.gs-new-name');
    input!.value = 'M03 Kuratieren';
    input!.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.gs-new-go')?.click();
    await fixture.whenStable();

    http.verify(); // nothing written, nothing switched
    expect(fixture.componentInstance.selected()).toBe('03-patterns/m01-orientierung');
    expect(fixture.componentInstance.editor.doc()).toEqual({ frontmatter: {}, body: 'neu' });
  });

  it('clears a refusal notice once something actually happens', async () => {
    // The live region kept announcing "please save first" long after the save.
    const { el, http, fixture } = await mount();
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[0].click();
    await fixture.whenStable();
    answerDoc(http, '03-patterns/m01-orientierung', { frontmatter: {}, body: 'alt' });
    await tick();
    await fixture.whenStable();

    fixture.componentInstance.editor.setDoc({ frontmatter: {}, body: 'neu' });
    el.querySelectorAll<HTMLButtonElement>('.gs-entry')[1].click(); // refused
    await fixture.whenStable();
    expect(fixture.componentInstance.notice()).not.toBe('');

    el.querySelector<HTMLButtonElement>('.gs-save')?.click();
    await fixture.whenStable();
    http.expectOne('/studio/api/config/data/03-patterns/m01-orientierung')
      .flush({
        area: '03-patterns/m01-orientierung',
        data: { frontmatter: {}, body: 'neu' },
        type: 'md',
      });
    await tick();
    await fixture.whenStable();

    expect(fixture.componentInstance.notice()).toBe('');
    expect(el.querySelector('.cs-status')?.textContent?.trim()).toBe('Gespeichert.');
  });

  it('refuses a name that would overwrite an existing document', async () => {
    const { el, http, fixture } = await mount();
    const input = el.querySelector<HTMLInputElement>('.gs-new-name');
    input!.value = 'm01 orientierung';
    input!.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.gs-new-go')?.click();
    await fixture.whenStable();

    http.verify(); // no PUT — an existing pattern would have been replaced
    expect(el.textContent).toContain('gibt es schon');
  });
});

// ── A7: Reiter im Pattern-Formular ──────────────────────────────────

/**
 * Beschriftungen der sichtbaren Felder — der Reiter-Schnitt in einem Wort.
 * Skalare stehen in `<label>`, Listen/Gruppen in `<legend>`
 * (`schema-field.component.html`); beides zählt als sichtbares Feld.
 */
function fieldLabels(el: HTMLElement): string[] {
  return Array.from(el.querySelectorAll('label, legend'))
    .map((l) => l.textContent?.trim().split(/\s+/)[0] ?? '')
    .filter(Boolean);
}

async function mountWithDoc(section: CuratedSection): Promise<Harness> {
  const h = await mount(section);
  h.el.querySelectorAll<HTMLButtonElement>('.gs-entry')[0].click();
  await h.fixture.whenStable();
  answerDoc(h.http, '03-patterns/m01-orientierung', {
    frontmatter: { id: 'M01', label: 'Orientierung', tools: [] }, body: '# Text',
  });
  await tick();
  await h.fixture.whenStable();
  return h;
}

describe('GroupSectionComponent mit Feld-Reitern', () => {
  it('teilt das Pattern-Formular in ALTs fünf Reiter', async () => {
    const { el } = await mountWithDoc(PATTERNS_TABS);
    const tabs = Array.from(el.querySelectorAll('[role="tab"]')).map((t) => t.textContent?.trim());
    expect(tabs).toEqual([
      'Identität', 'Antwort-Form', 'Tools & Wissen', 'Slots & Degradation', 'Anweisungen',
    ]);
  });

  it('zeigt nur die Felder des offenen Reiters', async () => {
    const { el, fixture } = await mountWithDoc(PATTERNS_TABS);
    expect(fieldLabels(el)).toContain('label');
    expect(fieldLabels(el)).not.toContain('tools');

    const tools = Array.from(el.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
      .find((t) => t.textContent?.includes('Tools'))!;
    tools.click();
    await fixture.whenStable();

    expect(fieldLabels(el)).toContain('tools');
    expect(fieldLabels(el)).not.toContain('label');
  });

  it('verbindet Reiter und Feldbereich, wie die Reiterleiste es zusagt', async () => {
    // `#tab-x` steuert `#panel-x` (tab-bar.component.ts) — sonst zeigt die
    // Zusage ins Leere und ein Screenreader findet den Bereich nicht.
    const { el } = await mountWithDoc(PATTERNS_TABS);
    const tab = el.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')!;
    const panel = el.querySelector<HTMLElement>('[role="tabpanel"]')!;
    expect(panel.id).toBe(tab.getAttribute('aria-controls'));
    expect(panel.getAttribute('aria-labelledby')).toBe(tab.id);
  });

  it('nennt bei einem Feldfehler den Reiter, in dem er steckt', async () => {
    // Ohne den Reiter-Namen suchte man ein gesperrtes Speichern in fünf Reitern.
    // Geprüft wird die Meldung selbst, nicht die Seite: „Tools & Wissen" steht
    // ohnehin in der Reiterleiste — eine Zusicherung auf `el.textContent` wäre
    // immer erfüllt (beim Rot-Grün-Nachweis aufgefallen).
    const { el, fixture } = await mountWithDoc(PATTERNS_TABS);
    fixture.componentInstance.editor.setFieldErrors(['frontmatter.tools']);
    await fixture.whenStable();

    const blocked = Array.from(el.querySelectorAll('[role="alert"]'))
      .map((p) => p.textContent ?? '')
      .find((text) => text.includes('Nicht speicherbar'));
    expect(blocked).toContain('frontmatter.tools');
    expect(blocked).toContain('Reiter „Tools & Wissen"');
  });

  it('lässt ein Formular ohne das Merkmal ungeteilt', async () => {
    const { el } = await mountWithDoc(PATTERNS);
    expect(el.querySelector('[role="tablist"]')).toBeNull();
    expect(fieldLabels(el)).toEqual(expect.arrayContaining(['label', 'tools']));
  });
});
