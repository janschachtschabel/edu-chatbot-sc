// @vitest-environment jsdom
/**
 * Ordner-Bereiche als Liste│Editor (Paket 6, S1 — ST-3d): Zähler, Suche,
 * Duplizieren und Löschen für Muster und Personas.
 *
 * Anders als die Einträge EINES Dokuments (`object-list`) sind das Dokumente:
 * Duplizieren und Löschen gehen sofort zum Server, deshalb fragt Löschen nach —
 * und sagt, ob das Dokument zur Werksfassung gehört (dann bleibt es gelöscht, bis es unter
 * Sicherung → „Werk und eigene Fassung“ wiederhergestellt wird — Paket 12).
 */
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AREA_SCHEMAS } from '../schema-form/area-schemas.fixture';
import type { CuratedSection } from './curated-views';
import { GroupSectionComponent } from './group-section.component';

const PATTERNS: CuratedSection = {
  area: '03-patterns',
  kind: 'group',
  labelKey: 'curated.patterns.patterns.label',
  hintKey: 'curated.patterns.patterns.hint',
};

const ELEMENTS = {
  patterns: [
    { id: 'M01', label: 'Orientierung', file: '03-patterns/m01-orientierung.md' },
    { id: 'M02', label: 'Suche', file: '03-patterns/m02-suche.md' },
  ],
  personas: [],
};

const M01 = '03-patterns/m01-orientierung';
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<GroupSectionComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

async function mount(section: CuratedSection = PATTERNS): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(GroupSectionComponent);
  fixture.componentRef.setInput('section', section);
  fixture.componentRef.setInput('open', true);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
  await fixture.whenStable();
  h.http.expectOne('/studio/api/config/elements').flush(ELEMENTS);
  await settle(h);
  return h;
}

/** M01 wählen und sein Dokument liefern. */
async function waehleM01(h: Harness, frontmatter: Record<string, unknown> = { id: 'M01' }): Promise<void> {
  h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')[0].click();
  await h.fixture.whenStable();
  h.http.expectOne(`/studio/api/config/schema/${M01}`).flush(AREA_SCHEMAS['03-patterns']);
  h.http.expectOne(`/studio/api/config/data/${M01}`).flush({
    area: M01, data: { frontmatter, body: '# Text' }, type: 'md', version: 4,
  });
  await settle(h);
  h.http.match('/studio/api/config/choices').forEach((req) => req.flush({}));
  h.http.match('/studio/api/config/data/05-knowledge/rag-config').forEach((req) => req.flush({
    area: '05-knowledge/rag-config', type: 'yaml',
    data: { WLO: { mode: 'always' }, Projekt: { mode: 'on-demand' } },
  }));
  await settle(h);
}

function knopf(h: Harness, text: string): HTMLButtonElement | undefined {
  return [...h.el.querySelectorAll<HTMLButtonElement>('button')]
    .find((b) => b.textContent?.trim() === text);
}

async function suche(h: Harness, text: string): Promise<void> {
  const feld = h.el.querySelector<HTMLInputElement>('input[type="search"]')!;
  feld.value = text;
  feld.dispatchEvent(new Event('input'));
  await h.fixture.whenStable();
}

function titel(h: Harness): string[] {
  return [...h.el.querySelectorAll('.ol-entry .ol-title')].map((s) => s.textContent!.trim());
}

describe('Ordner-Bereiche als Liste│Editor (ST-3d)', () => {
  it('zählt die Dokumente und sucht in Name und Kennung', async () => {
    const h = await mount();
    expect(h.el.querySelector('.ol-count')?.textContent).toContain('2 Einträge');
    await suche(h, 'such');
    expect(titel(h)).toEqual(['Suche']);
    expect(h.el.querySelector('.ol-count')?.textContent).toContain('1 von 2');
    await suche(h, 'm01');
    expect(titel(h)).toEqual(['Orientierung']);
  });

  it('dupliziert das gewählte Dokument mit freier Kennung und öffnet die Kopie', async () => {
    const h = await mount();
    await waehleM01(h);
    knopf(h, 'Duplizieren')!.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne('/studio/api/config/documents');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      group: '03-patterns', id: 'M01_kopie', label: 'Orientierung (Kopie)', source: M01,
    });
    req.flush({ status: 'created', key: '03-patterns/m01_kopie', version: 1 });
    await settle(h);
    h.http.expectOne('/studio/api/config/elements').flush({
      ...ELEMENTS,
      patterns: [...ELEMENTS.patterns,
        { id: 'M01_kopie', label: 'Orientierung (Kopie)', file: '03-patterns/m01_kopie.md' }],
    });
    await settle(h);
    h.http.expectOne('/studio/api/config/schema/03-patterns/m01_kopie').flush(AREA_SCHEMAS['03-patterns']);
    h.http.expectOne('/studio/api/config/data/03-patterns/m01_kopie').flush({
      area: '03-patterns/m01_kopie', data: { frontmatter: { id: 'M01_kopie' }, body: '' },
      type: 'md', version: 1,
    });
    await settle(h);
    expect(h.fixture.componentInstance.selected()).toBe('03-patterns/m01_kopie');
  });

  it('nimmt für die Kopie die nächste freie Kennung, ohne Rücksicht auf Groß/Klein', async () => {
    const h = await mount();
    h.http.verify();
    // Neu laden mit einer schon vorhandenen Kopie
    void h.fixture.componentInstance.docs.load();
    h.http.expectOne('/studio/api/config/elements').flush({
      ...ELEMENTS,
      patterns: [...ELEMENTS.patterns,
        { id: 'm01_KOPIE', label: 'Alt', file: '03-patterns/m01_kopie.md' }],
    });
    await settle(h);
    await waehleM01(h);
    knopf(h, 'Duplizieren')!.click();
    await h.fixture.whenStable();
    expect(h.http.expectOne('/studio/api/config/documents').request.body.id).toBe('M01_kopie_2');
  });

  it('dupliziert nicht, solange das Dokument ungespeicherte Änderungen hat', async () => {
    // Die Kopie entstünde aus dem gespeicherten Stand — die Änderungen fehlten ihr.
    const h = await mount();
    await waehleM01(h);
    h.fixture.componentInstance.editor.setDoc({ frontmatter: { id: 'M01' }, body: 'neu' });
    await h.fixture.whenStable();
    knopf(h, 'Duplizieren')!.click();
    await h.fixture.whenStable();
    h.http.verify();
    expect(h.el.textContent).toContain('speichern oder verwerfen');
  });

  it('löscht erst nach der Rückfrage und sagt, wo ein Werksdokument zurückkommt', async () => {
    const h = await mount();
    await waehleM01(h);
    knopf(h, 'Löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/seed').flush({
      available: true, area_count: 2, neu: [], gleich: [M01], abweichend: [], nur_in_db: [],
    });
    await settle(h);

    const rueckfrage = h.el.querySelector('.gs-confirm');
    expect(rueckfrage?.getAttribute('role')).toBe('alert');
    expect(rueckfrage?.textContent).toContain('„Orientierung“');
    expect(rueckfrage?.textContent).toContain('Werk und eigene Fassung');
    h.http.verify(); // noch nichts gelöscht

    knopf(h, 'Abbrechen')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.gs-confirm')).toBeNull();

    knopf(h, 'Löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/seed').flush({
      available: true, area_count: 2, neu: [], gleich: [M01], abweichend: [], nur_in_db: [],
    });
    await settle(h);
    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    const loeschen = h.http.expectOne((r) => r.url === '/studio/api/config/file');
    expect(loeschen.request.method).toBe('DELETE');
    // Nur der geladene Stand (Review Paket 6) — sonst 409 wie beim Speichern.
    expect(loeschen.request.params.get('expected_version')).toBe('4');
    expect(loeschen.request.params.get('path')).toBe(`${M01}.md`);
    loeschen.flush({ status: 'deleted', path: `${M01}.md` });
    await settle(h);
    h.http.expectOne('/studio/api/config/elements').flush({ ...ELEMENTS, patterns: [ELEMENTS.patterns[1]] });
    await settle(h);

    expect(h.fixture.componentInstance.selected()).toBe('');
    expect(h.fixture.componentInstance.dirty()).toBe(false);
    expect(titel(h)).toEqual(['Suche']);
    expect(h.el.querySelector('.cs-status')?.textContent).toContain('gelöscht');
  });

  it('sagt bei einem eigenen Dokument, dass es danach weg ist', async () => {
    const h = await mount();
    await waehleM01(h);
    knopf(h, 'Löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/seed').flush({
      available: true, area_count: 1, neu: [], gleich: [], abweichend: [], nur_in_db: [M01],
    });
    await settle(h);
    expect(h.el.querySelector('.gs-confirm')?.textContent).toContain('nur in dieser Anlage');
  });

  it('nennt einen Fehler beim Löschen und lässt die Liste stehen', async () => {
    const h = await mount();
    await waehleM01(h);
    knopf(h, 'Löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/seed').flush({ available: false });
    await settle(h);
    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/config/file')
      .flush({ detail: 'gehört zur festen Konfiguration' }, { status: 400, statusText: 'Bad Request' });
    await settle(h);
    h.http.verify(); // kein neues Laden der Liste
    expect(titel(h)).toEqual(['Orientierung', 'Suche']);
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain('festen Konfiguration');
  });

  it('benennt Duplizieren und Löschen mit dem Dokument, um das es geht', async () => {
    const h = await mount();
    expect(knopf(h, 'Duplizieren')).toBeUndefined(); // ohne Wahl nichts zu duplizieren
    await waehleM01(h);
    expect(knopf(h, 'Duplizieren')?.getAttribute('aria-label')).toBe('Duplizieren: Orientierung');
    expect(knopf(h, 'Löschen')?.getAttribute('aria-label')).toBe('Löschen: Orientierung');
  });

  it('nennt im Muster-Formular die Wissensbereiche, die tatsächlich wirken (S4)', async () => {
    const h = await mount();
    await waehleM01(h, { id: 'M01', sources: ['mcp', 'rag'] });
    expect(h.el.querySelector('.gs-effective')?.textContent)
      .toContain('es wirken die Bereiche des Katalogs: WLO und Projekt');

    h.fixture.componentInstance.editor.setDoc({ frontmatter: { id: 'M01', sources: ['mcp'] }, body: '' });
    await h.fixture.whenStable();
    expect(h.el.querySelector('.gs-effective')?.textContent)
      .toContain('„rag“ steht nicht unter den Quellen');
  });

  it('zeigt den Wissensbereiche-Satz mit Feld-Reitern nur unter „Tools & Wissen“', async () => {
    const h = await mount({ ...PATTERNS, feature: 'pattern-tabs' });
    await waehleM01(h, { id: 'M01', sources: ['mcp', 'rag'] });
    expect(h.el.querySelector('.gs-effective')?.textContent ?? '').toBe('');

    h.el.querySelector<HTMLButtonElement>('#tab-pf-tools')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.gs-effective')?.textContent).toContain('WLO und Projekt');
  });

  it('hält die Region für den Satz bereit, bevor er erscheint (F-M6)', async () => {
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')[0].click();
    await h.fixture.whenStable();
    h.http.expectOne(`/studio/api/config/schema/${M01}`).flush(AREA_SCHEMAS['03-patterns']);
    h.http.expectOne(`/studio/api/config/data/${M01}`).flush({
      area: M01, data: { frontmatter: { id: 'M01', sources: ['rag'] }, body: '' }, type: 'md', version: 4,
    });
    await settle(h);
    const region = h.el.querySelector('.gs-effective');
    expect(region?.getAttribute('aria-live')).toBe('polite');
    expect(region?.textContent).toBe('');

    h.http.match('/studio/api/config/choices').forEach((req) => req.flush({}));
    h.http.expectOne('/studio/api/config/data/05-knowledge/rag-config').flush({
      area: '05-knowledge/rag-config', type: 'yaml', data: { WLO: { mode: 'always' } },
    });
    await settle(h);
    expect(h.el.querySelector('.gs-effective')).toBe(region);
    expect(region?.textContent).toContain('WLO');
  });
});

describe('Lösch-Rückfrage gehört EINEM Dokument (Review Paket 6)', () => {
  async function fragLoeschen(h: Harness): Promise<void> {
    knopf(h, 'Löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/seed').flush({
      available: true, area_count: 2, neu: [], gleich: [M01], abweichend: [], nur_in_db: [],
    });
    await settle(h);
  }

  async function waehleM02(h: Harness): Promise<void> {
    h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')[1].click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/schema/03-patterns/m02-suche').flush(AREA_SCHEMAS['03-patterns']);
    h.http.expectOne('/studio/api/config/data/03-patterns/m02-suche').flush({
      area: '03-patterns/m02-suche', data: { frontmatter: { id: 'M02' }, body: '' }, type: 'md', version: 2,
    });
    await settle(h);
    h.http.match('/studio/api/config/choices').forEach((req) => req.flush({}));
    await settle(h);
  }

  it('sagt, wenn jemand das Dokument inzwischen gespeichert hat, statt es zu löschen', async () => {
    const h = await mount();
    await waehleM01(h);
    await fragLoeschen(h);
    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/config/file').flush(
      { detail: { message: 'x', version: 5, updated_by: 'studio', updated_at: null } },
      { status: 409, statusText: 'Conflict' });
    await settle(h);
    h.http.verify();
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain('inzwischen gespeichert');
    expect(h.fixture.componentInstance.selected()).toBe(M01);
  });

  it('schließt die Rückfrage, wenn Duplizieren ein anderes Dokument öffnet', async () => {
    // Sonst nannte die offene Rückfrage die Kopie, behielt den Hinweis zum
    // Auslieferungsstand des Originals, und „Ja, löschen“ traf die Kopie.
    const h = await mount();
    await waehleM01(h);
    await fragLoeschen(h);
    expect(h.el.querySelector('.gs-confirm')).not.toBeNull();

    knopf(h, 'Duplizieren')!.click();
    await h.fixture.whenStable();
    h.http.expectOne('/studio/api/config/documents')
      .flush({ status: 'created', key: '03-patterns/m01_kopie', version: 1 });
    await settle(h);
    h.http.expectOne('/studio/api/config/elements').flush({
      ...ELEMENTS,
      patterns: [...ELEMENTS.patterns,
        { id: 'M01_kopie', label: 'Orientierung (Kopie)', file: '03-patterns/m01_kopie.md' }],
    });
    await settle(h);
    h.http.expectOne('/studio/api/config/schema/03-patterns/m01_kopie').flush(AREA_SCHEMAS['03-patterns']);
    h.http.expectOne('/studio/api/config/data/03-patterns/m01_kopie').flush({
      area: '03-patterns/m01_kopie', data: { frontmatter: { id: 'M01_kopie' }, body: '' },
      type: 'md', version: 1,
    });
    await settle(h);

    expect(h.fixture.componentInstance.selected()).toBe('03-patterns/m01_kopie');
    expect(h.el.querySelector('.gs-confirm')).toBeNull();
    expect(knopf(h, 'Ja, löschen')).toBeUndefined();
  });

  it('zeigt einen Löschfehler nur beim Dokument, zu dem er gehört, und gibt den Fokus zurück', async () => {
    const h = await mount();
    await waehleM01(h);
    await fragLoeschen(h);
    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/config/file')
      .flush({ detail: 'gehört zur festen Konfiguration' }, { status: 400, statusText: 'Bad Request' });
    await settle(h);
    expect(h.el.textContent).toContain('festen Konfiguration');
    expect(document.activeElement).toBe(knopf(h, 'Löschen'));

    await waehleM02(h);
    expect(h.el.textContent).not.toContain('festen Konfiguration');
  });

  it('führt den Fokus in die Rückfrage, beim Abbrechen zurück und nach dem Löschen zur Liste', async () => {
    const h = await mount();
    await waehleM01(h);
    await fragLoeschen(h);
    expect(document.activeElement).toBe(knopf(h, 'Abbrechen'));

    knopf(h, 'Abbrechen')!.click();
    await settle(h);
    expect(document.activeElement).toBe(knopf(h, 'Löschen'));

    await fragLoeschen(h);
    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/config/file')
      .flush({ status: 'deleted', path: `${M01}.md` });
    await settle(h);
    h.http.expectOne('/studio/api/config/elements').flush({ ...ELEMENTS, patterns: [ELEMENTS.patterns[1]] });
    await settle(h);
    expect(document.activeElement?.id).toBe('gs-03-patterns-list');
  });

  it('lässt während des Löschens keinen Wechsel und kein Duplizieren zu', async () => {
    const h = await mount();
    await waehleM01(h);
    await fragLoeschen(h);
    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    const loeschen = h.http.expectOne((r) => r.url === '/studio/api/config/file');

    h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')[1].click();
    await h.fixture.whenStable();
    expect(h.http.match((r) => r.url.includes('m02-suche'))).toHaveLength(0);
    expect(h.fixture.componentInstance.selected()).toBe(M01);
    expect(knopf(h, 'Duplizieren')?.disabled).toBe(true);

    loeschen.flush({ status: 'deleted', path: `${M01}.md` });
    await settle(h);
    h.http.expectOne('/studio/api/config/elements').flush({ ...ELEMENTS, patterns: [ELEMENTS.patterns[1]] });
    await settle(h);
    expect(h.fixture.componentInstance.selected()).toBe('');
  });

  it('löscht ein Dokument mit offenen Änderungen erst nach dem Hinweis und verwirft sie', async () => {
    const h = await mount();
    await waehleM01(h);
    h.fixture.componentInstance.editor.setDoc({ frontmatter: { id: 'M01' }, body: 'neu' });
    await h.fixture.whenStable();
    await fragLoeschen(h);
    expect(h.el.querySelector('.gs-confirm')?.textContent).toContain('ungespeicherten Änderungen');

    knopf(h, 'Ja, löschen')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/config/file')
      .flush({ status: 'deleted', path: `${M01}.md` });
    await settle(h);
    h.http.expectOne('/studio/api/config/elements').flush({ ...ELEMENTS, patterns: [ELEMENTS.patterns[1]] });
    await settle(h);
    expect(h.fixture.componentInstance.dirty()).toBe(false);
    expect(h.fixture.componentInstance.selected()).toBe('');
  });
});
