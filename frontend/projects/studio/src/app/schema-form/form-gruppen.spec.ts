import { describe, expect, it } from 'vitest';

import { gruppenSections } from './form-sections';
import type { JsonSchema } from './json-schema';
import { rootField, type SchemaField } from './schema-to-fields';

/**
 * Rundgang 3: Feldgruppen — benannte Abschnitte in fester Reihenfolge, EIN Editor je Bereich
 * (kein 409). Tour in Laufzeit-Reihenfolge, Kontext-Aktionen nach DE/EN getrennt.
 */
const HUELLE: JsonSchema = {
  type: 'object',
  properties: {
    tour: {
      type: 'object',
      properties: {
        enabled: { type: 'boolean' },
        intro: { type: 'string' },
        intro_en: { type: 'string' },
        base_host: { type: 'string' },
        neu: { type: 'string' },
      },
    },
  },
};

const blattSchluessel = (feld: SchemaField): string[] =>
  (feld.children ?? []).map((c) => c.key);

describe('gruppenSections', () => {
  it('ordnet Felder in benannte Abschnitte in der Reihenfolge der Gruppen', () => {
    const sections = gruppenSections(rootField(HUELLE), [
      { id: 'texte', labelKey: 'g.texte', felder: ['tour.intro', 'tour.intro_en'] },
      { id: 'start', labelKey: 'g.start', felder: ['tour.enabled'] },
    ]);
    expect(sections.map((s) => s.labelKey)).toEqual(['g.texte', 'g.start', 'schemaForm.weitere']);
    // Eine einzelne Hülle wird aufgelöst: die Felder stehen ohne doppelte Legende darunter.
    expect(sections[0].basePath).toEqual(['tour']);
    expect(sections[0].field.ohneLegende).toBe(true);
    expect(blattSchluessel(sections[0].field)).toEqual(['intro', 'intro_en']);
  });

  it('sammelt nicht genannte Felder in „Weitere Einstellungen“ — nichts geht verloren', () => {
    const sections = gruppenSections(rootField(HUELLE), [
      { id: 'texte', labelKey: 'g.texte', felder: ['tour.intro', 'tour.intro_en'] },
    ]);
    const rest = sections.at(-1)!;
    expect(rest.labelKey).toBe('schemaForm.weitere');
    expect(blattSchluessel(rest.field)).toEqual(['enabled', 'base_host', 'neu']);
  });

  it('findet ein nicht genanntes Feld auch in einem teilweise genannten Block (Review A-3)', () => {
    const zwei: JsonSchema = { type: 'object', properties: {
      a: { type: 'object', properties: { x: { type: 'string' }, y: { type: 'string' } } },
      b: { type: 'object', properties: { z: { type: 'string' } } },
    } };
    const sections = gruppenSections(rootField(zwei), [
      { id: 'eins', labelKey: 'g.eins', felder: ['a.x', 'b.z'] },
    ]);
    const rest = sections.at(-1)!;
    expect(rest.id).toBe('grp-rest');
    expect(rest.paths).toEqual(['a.y']);
    expect(blattSchluessel(rest.field)).toEqual(['a']);
    expect(blattSchluessel(rest.field.children![0])).toEqual(['y']);
    // Der Teil-Ausschnitt behält seinen Namen für Screenreader, ohne sichtbare Legende.
    expect(rest.field.children![0].ohneLegende).toBe(true);
    expect(rest.field.children![0].label).toBeTruthy();
  });

  it('lässt „Weitere Einstellungen“ weg, wenn alle Felder genannt sind', () => {
    const sections = gruppenSections(rootField(HUELLE), [
      { id: 'a', labelKey: 'g.a', felder: ['tour.enabled', 'tour.intro', 'tour.intro_en'] },
      { id: 'b', labelKey: 'g.b', felder: ['tour.base_host', 'tour.neu'] },
    ]);
    expect(sections.map((s) => s.id)).toEqual(['grp-a', 'grp-b']);
  });
});

describe('SchemaFormComponent — Feldgruppen (Rundgang 3)', () => {
  it('zeigt die Gruppen als benannte Abschnitte und schreibt ein Dokument', async () => {
    const { provideZonelessChangeDetection } = await import('@angular/core');
    const { TestBed } = await import('@angular/core/testing');
    const { SchemaFormComponent } = await import('./schema-form.component');
    const { STUDIO_LOCALE_STORAGE_KEY } = await import('../i18n/studio-language.service');
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    const emitted: Record<string, unknown>[] = [];
    fixture.componentRef.setInput('schema', HUELLE);
    fixture.componentRef.setInput('value', { tour: { enabled: true, intro: 'Hallo' } });
    fixture.componentRef.setInput('gruppen', [
      { id: 'texte', labelKey: 'curated.fuehrung.gruppe.texte', felder: ['tour.intro', 'tour.intro_en'] },
    ]);
    fixture.componentInstance.valueChange.subscribe((v) => emitted.push(v));
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const koepfe = Array.from(el.querySelectorAll('.sf-section-head')).map((h) => h.textContent?.trim());
    expect(koepfe).toEqual(['Texte', 'Weitere Einstellungen']);
    const intro = el.querySelector<HTMLInputElement>('[id="sf-tour.intro"]')!;
    intro.value = 'Moin';
    intro.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ tour: { enabled: true, intro: 'Moin' } });
  });
});

describe('Feldgruppen der kuratierten Seiten (Rundgang 3)', () => {
  it('nennen jedes Feld ihres Bereichs genau einmal — keins doppelt, keins im Rest', async () => {
    const { CURATED_VIEWS, isAreaSection } = await import('../views/curated-views');
    const { AREA_SCHEMAS } = await import('./area-schemas.fixture');
    const mitGruppen = CURATED_VIEWS.flatMap((v) => v.sections.filter(isAreaSection)
      .filter((s) => s.gruppen?.length).map((s) => ({ seite: v.slug, s })));
    expect(mitGruppen.map((x) => `${x.seite}:${x.s.area}`)).toEqual(expect.arrayContaining([
      'fuehrung:01-base/website-tour', 'kontext-aktionen:01-base/context-actions',
      'agent-rolle:01-base/engine']));
    for (const { seite, s } of mitGruppen) {
      const felder = s.gruppen!.flatMap((g) => g.felder);
      expect(new Set(felder).size, `${seite}: doppelt`).toBe(felder.length);
      // Mit Feld-Ausschnitt gliedern die Gruppen nur die gezeigten Felder.
      const { pickFields } = await import('./pick-fields');
      const wurzel = rootField(AREA_SCHEMAS[s.area]);
      const sections = gruppenSections(
        s.felder ? pickFields(wurzel, new Set(s.felder)) : wurzel, s.gruppen!);
      expect(sections.some((x) => x.id === 'grp-rest'), `${seite}: Rest`).toBe(false);
    }
  });
});
