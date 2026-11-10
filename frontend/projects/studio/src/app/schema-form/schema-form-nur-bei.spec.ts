// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { FieldProblem } from '../core/field-problems';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AREA_SCHEMAS } from './area-schemas.fixture';
import { JsonValueComponent } from './json-value.component';
import type { JsonSchema } from './json-schema';
import { SchemaFormComponent } from './schema-form.component';
import { rootField } from './schema-to-fields';

/**
 * Paket K2c-2: ein Feld mit `x-nur-bei` gilt nur, wenn das Nachbarfeld einen der Werte trägt — ein
 * Ablaufschritt zeigt so nur die Felder seines Typs. Ausgeblendet wird nur, was leer ist: ein
 * gesetzter Wert an einem Feld, das beim aktuellen Typ nicht wirkt, bleibt sichtbar und trägt den
 * Hinweis (sonst verschwände er still und bliebe trotzdem gespeichert).
 */
const SCHEMA: JsonSchema = {
  type: 'object',
  properties: { schritt: { $ref: '#/$defs/Schritt' } },
  $defs: {
    Schritt: {
      type: 'object',
      title: 'Schritt',
      properties: {
        typ: { type: 'string', 'x-choices': ['nachricht', 'auftrag'] },
        flow: {
          anyOf: [{ type: 'string', 'x-catalog': 'ablauf_flows' }, { type: 'null' }],
          'x-nur-bei': { feld: 'typ', werte: ['auftrag'] },
        },
        text: {
          anyOf: [{ type: 'string' }, { type: 'null' }],
          'x-nur-bei': { feld: 'typ', werte: ['auftrag', 'nachricht'] },
        },
      },
    },
  },
};

interface Harness {
  fixture: ComponentFixture<SchemaFormComponent>;
  el: HTMLElement;
  emitted: Record<string, unknown>[];
}

async function mount(value: Record<string, unknown>, schema: JsonSchema = SCHEMA,
  problems: readonly FieldProblem[] = []): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(SchemaFormComponent);
  const emitted: Record<string, unknown>[] = [];
  fixture.componentRef.setInput('schema', schema);
  fixture.componentRef.setInput('value', value);
  fixture.componentRef.setInput('problems', problems);
  fixture.componentInstance.valueChange.subscribe((next) => emitted.push(next));
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, emitted };
}

/** Wie der Bereichseditor: was das Formular meldet, kommt als neuer Wert zurück. */
async function zurueck(h: Harness): Promise<void> {
  h.fixture.componentRef.setInput('value', h.emitted[h.emitted.length - 1]);
  await h.fixture.whenStable();
}

const feld = (el: HTMLElement, key: string) => el.querySelector<HTMLElement>(`[id="sf-schritt.${key}"]`);

describe('schemaToFields — x-nur-bei (K2c-2)', () => {
  it('liest die Auszeichnung an der Eigenschaft', () => {
    const wurzel = rootField(SCHEMA);
    const schritt = wurzel.children!.find((c) => c.key === 'schritt')!;
    const flow = schritt.children!.find((c) => c.key === 'flow')!;
    expect(flow.nurBei).toEqual({ feld: 'typ', werte: ['auftrag'] });
    expect(schritt.children!.find((c) => c.key === 'typ')!.nurBei).toBeUndefined();
  });
});

describe('SchemaFormComponent — Felder je Typ (K2c-2)', () => {
  it('zeigt nur die Felder des gewählten Typs', async () => {
    const { el } = await mount({ schritt: { typ: 'nachricht' } });
    expect(feld(el, 'flow')).toBeNull();
    expect(feld(el, 'text')).not.toBeNull();
  });

  it('ein anderer Typ blendet seine Felder ein', async () => {
    const { el } = await mount({ schritt: { typ: 'auftrag' } });
    expect(feld(el, 'flow')).not.toBeNull();
    expect(feld(el, 'text')).not.toBeNull();
  });

  it('ein gesetzter Wert an einem Feld, das nicht wirkt, bleibt sichtbar und trägt den Hinweis', async () => {
    const { el } = await mount({ schritt: { typ: 'nachricht', flow: 'wlo/volltext' } });
    const eingabe = feld(el, 'flow') as HTMLInputElement;
    expect(eingabe).not.toBeNull();
    expect(eingabe.value).toBe('wlo/volltext');
    // Re-Review K2c-2, Befund 4: die Beschreibung ist der Satz, nicht der Knopf daneben.
    const hinweis = el.querySelector('.sf-nur-bei span[id]');
    // Befund 6: die Beschriftungen aus dem Katalog („Flow“, „Art“), nicht die Rohschlüssel.
    expect(hinweis?.textContent).toContain('„Flow“ wirkt beim gewählten Wert von „Art“ nicht');
    // Der Hinweis gehört zum Feld: ein Screenreader liest ihn mit.
    expect(eingabe.closest('.sf-nur-bei-feld')?.querySelector('.sf-nur-bei span[id]')).toBe(hinweis);
    expect(eingabe.getAttribute('aria-describedby')?.split(' ')).toContain(hinweis!.id);
  });

  it('ohne gesetzten Typ bleibt alles sichtbar', async () => {
    const { el } = await mount({ schritt: {} });
    expect(feld(el, 'flow')).not.toBeNull();
  });

  // Review K2c-2, Befund 1: wer einen Restwert leert, tippt gerade darin — das Feld bleibt stehen.
  it('ein geleerter Restwert bleibt sichtbar, bis der Typ wechselt', async () => {
    const h = await mount({ schritt: { typ: 'nachricht', flow: 'wlo/volltext' } });
    h.fixture.componentRef.setInput('value', { schritt: { typ: 'nachricht', flow: '' } });
    await h.fixture.whenStable();
    expect(feld(h.el, 'flow')).not.toBeNull();
    h.fixture.componentRef.setInput('value', { schritt: { typ: 'auftrag', flow: '' } });
    await h.fixture.whenStable();
    h.fixture.componentRef.setInput('value', { schritt: { typ: 'nachricht', flow: '' } });
    await h.fixture.whenStable();
    expect(feld(h.el, 'flow')).toBeNull();
  });

  // Befund 1/4: „Wert entfernen“ nimmt den Schlüssel heraus, auch eine Gruppe.
  it('„Wert entfernen“ nimmt den Restwert heraus und blendet das Feld aus', async () => {
    const h = await mount({ schritt: { typ: 'nachricht', flow: 'wlo/volltext' } });
    const knopf = h.el.querySelector<HTMLButtonElement>('.sf-nur-bei-weg')!;
    expect(knopf.textContent?.trim()).toBe('Wert entfernen');
    knopf.click();
    expect(h.emitted.at(-1)).toEqual({ schritt: { typ: 'nachricht' } });
    await zurueck(h);
    expect(feld(h.el, 'flow')).toBeNull();
  });

  // Befund 2: eine Meldung an einem leeren, ausgeblendeten Feld stünde sonst nirgends.
  it('ein leeres Feld mit Meldung bleibt sichtbar', async () => {
    const h = await mount({ schritt: { typ: 'nachricht', flow: '' } }, SCHEMA,
      [{ path: ['schritt', 'flow'], type: 'string_type', msg: 'kaputt', ctx: {} }]);
    expect(feld(h.el, 'flow')).not.toBeNull();
  });

  // Re-Review K2c-2, Befund 2: blendet der Typ ein Feld aus, gehen die Meldungen darunter mit.
  it('das Ausblenden durch den Typ nimmt die Meldungen des Felds zurück', async () => {
    const h = await mount({ schritt: { typ: 'auftrag', flow: '' } });
    const fehler: (readonly string[])[] = [];
    h.fixture.componentInstance.errorsChange.subscribe((f) => fehler.push(f));
    h.fixture.componentInstance.apply({ kind: 'field-error', path: ['schritt', 'flow', 'x'],
                                        message: 'Kein gültiges JSON' });
    expect(fehler.at(-1)).toEqual(['schritt.flow.x']);
    h.fixture.componentRef.setInput('value', { schritt: { typ: 'nachricht', flow: '' } });
    await h.fixture.whenStable();
    expect(feld(h.el, 'flow')).toBeNull();
    expect(fehler.at(-1)).toEqual([]);
  });

  // Re-Review K2c-2, Befund 1: eine Instanz zeigt nacheinander mehrere Schritte — nichts wandert mit.
  it('der klebende Zustand eines Schritts geht nicht auf den nächsten über', async () => {
    const schritt = (id: string, mehr: Record<string, unknown> = {}) =>
      ({ id, typ: 'nachricht', text: { de: id }, ...mehr });
    // AS-0: ein Dokument je Ablauf — der Ablauf ist die Wurzel.
    const wert = (flow: unknown) => ({ id: 'lesen', titel: { de: 'Lesen' }, schritte: [
      schritt('erster', { flow }), schritt('zweiter')] });
    const h = await mount(wert('wlo/volltext'), AREA_SCHEMAS['06-ablaeufe']);
    h.fixture.componentRef.setInput('value', wert(''));
    await h.fixture.whenStable();
    expect(h.el.querySelector('[id="sf-schritte.0.flow"]')).not.toBeNull();
    const zweiter = [...h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')]
      .find((b) => b.querySelector('.ol-title')?.textContent?.trim() === 'zweiter')!;
    zweiter.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('[id^="sf-schritte.1.text"]')).not.toBeNull();
    expect(h.el.querySelector('[id="sf-schritte.1.flow"]')).toBeNull();
    expect(h.el.querySelector('.sf-nur-bei')).toBeNull();
  });

  // Re-Review K2c-2, älterer Befund P1: zeigt die Instanz danach einen anderen Schritt, verwirft die
  // Box ihren Entwurf — die Rücknahme gilt dem Pfad, an dem die Meldung stand, nicht dem neuen.
  it('eine JSON-Meldung wird für ihren eigenen Pfad zurückgenommen', async () => {
    // Seit K2c-3 ist `daten` eine Tabelle; ihre JSON-Zeile meldet sich wie die JSON-Box.
    const schritt = (id: string) => ({ id, typ: 'modul', modul: 'ui_upload', daten: { n: 1 } });
    const wert = { id: 'lesen', titel: { de: 'Lesen' }, schritte: [
      schritt('erster'), schritt('zweiter')] };
    const h = await mount(wert, AREA_SCHEMAS['06-ablaeufe']);
    const fehler: (readonly string[])[] = [];
    h.fixture.componentInstance.errorsChange.subscribe((f) => fehler.push(f));
    const box = h.el.querySelector<HTMLTextAreaElement>(
      '[id="sf-schritte.0.daten"] textarea.tw-wert')!;
    box.value = '{ kaputt';
    box.dispatchEvent(new Event('input'));
    box.dispatchEvent(new Event('change'));      // gelesen wird beim Verlassen
    await h.fixture.whenStable();
    expect(fehler.at(-1)).toEqual(['schritte.0.daten']);
    const zweiter = [...h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')]
      .find((b) => b.querySelector('.ol-title')?.textContent?.trim() === 'zweiter')!;
    zweiter.click();
    await h.fixture.whenStable();
    expect(fehler.at(-1)).toEqual([]);
  });

  // Befund 7: das echte Schema eines Ablaufschritts, Typ im Formular gewechselt.
  it('im echten Ablaufschema wechselt der Typ die Felder, ohne etwas zu schreiben', async () => {
    const wert = { id: 'lesen', titel: { de: 'Lesen' }, schritte: [
      { id: 'hallo', typ: 'nachricht', text: { de: 'Hallo' } }] };
    const h = await mount(wert, AREA_SCHEMAS['06-ablaeufe']);
    expect(h.emitted).toEqual([]);
    const id = (k: string) => `sf-schritte.0.${k}`;
    // Eine Map (`text`) trägt keine eigene Kennung, nur `…text-desc`, `…text-key-0` — also der Anfang.
    const da = (k: string) => h.el.querySelector(`[id^="${id(k)}"]`) !== null;
    expect(da('text')).toBe(true);
    expect(da('flow') || da('werkzeug') || da('agent')).toBe(false);
    const typ = h.el.querySelector<HTMLSelectElement>(`[id="${id('typ')}"]`)!;
    typ.value = 'auftrag';
    typ.dispatchEvent(new Event('change'));
    await zurueck(h);
    expect(da('flow') && da('schreibt') && da('warten')).toBe(true);
    expect(da('werkzeug') || da('modul')).toBe(false);
  });
});

// Re-Review K2c-2, Befund 2: der Abbau einer Box nimmt ihre Meldung NICHT zurück — ein Reiterwechsel
// muss die Speichersperre behalten (A7, `feld-reiter.ts`). Das Ausblenden durch den Typ nimmt sie
// zurück (Test oben).
describe('JsonValueComponent — Meldung beim Abbau (K2c-2)', () => {
  it('bleibt stehen, wenn die Box verschwindet', () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(JsonValueComponent);
    fixture.componentRef.setInput('fieldId', 'sf-x');
    fixture.componentRef.setInput('value', {});
    const gemeldet: string[] = [];
    fixture.componentInstance.errorChange.subscribe((m) => gemeldet.push(m));
    fixture.componentInstance.error.set('Kein gültiges JSON');
    fixture.destroy();
    expect(gemeldet).toEqual([]);
  });
});

