// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import type { JsonSchema } from './json-schema';
import { ObjectListComponent } from './object-list.component';
import type { FormEdit } from './schema-field.component';
import { rootField, type SchemaField } from './schema-to-fields';

const FLOW: JsonSchema = {
  type: 'object', title: 'Flow',
  properties: { id: { type: 'string' }, title: { type: 'string' }, note: { type: 'string' } },
};
const LISTE: JsonSchema = {
  type: 'object', properties: { flows: { type: 'array', items: { $ref: '#/$defs/Flow' } } },
  $defs: { Flow: FLOW },
};
const KARTE: JsonSchema = {
  type: 'object',
  properties: { rules: { type: 'object', additionalProperties: { $ref: '#/$defs/Flow' } } },
  $defs: { Flow: FLOW },
};

const FLOWS = [
  { id: 'GV-1', title: 'Erster Flow' },
  { id: 'GV-2', title: 'Zweiter Flow' },
  { id: 'GV-3' },
];

interface Harness {
  fixture: ComponentFixture<ObjectListComponent>;
  el: HTMLElement;
  emitted: FormEdit[];
}

function feld(schema: JsonSchema): SchemaField {
  return rootField(schema).children![0];
}

async function mount(schema: JsonSchema, value: unknown, problems = new Map<string, string>()):
  Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(ObjectListComponent);
  const field = feld(schema);
  fixture.componentRef.setInput('field', field);
  fixture.componentRef.setInput('path', [field.key]);
  fixture.componentRef.setInput('value', value);
  fixture.componentRef.setInput('label', 'Gold-Flows');
  fixture.componentRef.setInput('idPrefix', 'test');
  fixture.componentRef.setInput('problems', problems);
  const emitted: FormEdit[] = [];
  fixture.componentInstance.edit.subscribe((edit) => emitted.push(edit));
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, emitted };
}

const titel = (h: Harness): string[] =>
  [...h.el.querySelectorAll('.ol-entry .ol-title')].map((s) => s.textContent!.trim());

function knopf(h: Harness, text: string): HTMLButtonElement {
  const found = [...h.el.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!found) throw new Error(`kein Knopf „${text}"`);
  return found;
}

/** Den Wert neu setzen, wie ihn das Formular nach einer Änderung hereinreicht. */
async function neuerWert(h: Harness, value: unknown): Promise<void> {
  h.fixture.componentRef.setInput('value', value);
  await h.fixture.whenStable();
}

const editorWert = (h: Harness, feldName: string): string =>
  (h.el.querySelector<HTMLInputElement>(`.ol-editor input[id$="${feldName}"]`)?.value) ?? '';

describe('ObjectListComponent — Liste│Editor (ST-3)', () => {
  it('zeigt je Eintrag seinen Titel und die Zahl', async () => {
    const h = await mount(LISTE, FLOWS);
    expect(titel(h)).toEqual(['Erster Flow', 'Zweiter Flow', 'GV-3']);
    expect(h.el.querySelector('.ol-count')?.textContent).toContain('3 Einträge');
  });

  it('öffnet den ersten Eintrag im Editor und wechselt per Klick', async () => {
    const h = await mount(LISTE, FLOWS);
    expect(editorWert(h, 'title')).toBe('Erster Flow');
    const zweiter = [...h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')][1];
    zweiter.click();
    await h.fixture.whenStable();
    expect(editorWert(h, 'title')).toBe('Zweiter Flow');
    expect(zweiter.getAttribute('aria-current')).toBe('true');
  });

  it('filtert nach dem Suchtext und sagt, wie viele übrig sind', async () => {
    const h = await mount(LISTE, FLOWS);
    const suche = h.el.querySelector<HTMLInputElement>('input[type="search"]')!;
    suche.value = 'zwei';
    suche.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    expect(titel(h)).toEqual(['Zweiter Flow']);
    expect(h.el.querySelector('.ol-count')?.textContent).toContain('1 von 3');
  });

  it('reicht Änderungen im Editor mit dem Pfad des Eintrags weiter', async () => {
    const h = await mount(LISTE, FLOWS);
    [...h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')][1].click();
    await h.fixture.whenStable();
    const feld = h.el.querySelector<HTMLInputElement>('.ol-editor input[id$="title"]')!;
    feld.value = 'Neu betitelt';
    feld.dispatchEvent(new Event('input'));
    expect(h.emitted.at(-1)).toEqual({ kind: 'set', path: ['flows', 1, 'title'], value: 'Neu betitelt' });
  });

  it('legt einen neuen Eintrag an und wählt ihn', async () => {
    const h = await mount(LISTE, FLOWS);
    knopf(h, 'Neu').click();
    const edit = h.emitted.at(-1) as { kind: string; path: unknown; value: unknown[] };
    expect(edit.kind).toBe('set');
    expect(edit.path).toEqual(['flows']);
    expect(edit.value).toHaveLength(4);
    await neuerWert(h, edit.value);
    expect(h.el.querySelectorAll('.ol-entry')[3].getAttribute('aria-current')).toBe('true');
  });

  it('dupliziert den gewählten Eintrag direkt dahinter und wählt die Kopie', async () => {
    const h = await mount(LISTE, FLOWS);
    knopf(h, 'Duplizieren').click();
    const edit = h.emitted.at(-1) as { value: unknown[] };
    expect(edit.value).toEqual([FLOWS[0], FLOWS[0], FLOWS[1], FLOWS[2]]);
    await neuerWert(h, edit.value);
    expect(h.el.querySelectorAll('.ol-entry')[1].getAttribute('aria-current')).toBe('true');
  });

  it('löscht den gewählten Eintrag — eine Formular-Änderung, Verwerfen holt ihn zurück', async () => {
    const h = await mount(LISTE, FLOWS);
    [...h.el.querySelectorAll<HTMLButtonElement>('.ol-entry')][2].click();
    await h.fixture.whenStable();
    knopf(h, 'Löschen').click();
    expect(h.emitted.at(-1)).toEqual({ kind: 'remove', path: ['flows', 2] });
  });

  it('markiert Einträge, an denen der Server etwas abgewiesen hat', async () => {
    const h = await mount(LISTE, FLOWS, new Map([['flows.2.id', 'Dieses Feld muss ausgefüllt sein.']]));
    const dritter = h.el.querySelectorAll('.ol-entry')[2];
    expect(dritter.textContent).toContain('⚠');
    expect(dritter.textContent).toContain('enthält einen Fehler');
  });

  it('zeigt eine Map mit ihren Schlüsseln und benennt im Editor um', async () => {
    const h = await mount(KARTE, { alpha: { title: 'A' }, beta: { title: 'B' } });
    expect(titel(h)).toEqual(['alpha', 'beta']);
    const schluessel = h.el.querySelector<HTMLInputElement>('.ol-editor .ol-key')!;
    schluessel.value = 'gamma';
    schluessel.dispatchEvent(new Event('change'));
    expect(h.emitted.at(-1)).toEqual({ kind: 'rename', path: ['rules'], from: 'alpha', to: 'gamma' });
  });

  it('dupliziert einen Map-Eintrag unter einem freien Schlüssel', async () => {
    const h = await mount(KARTE, { alpha: { title: 'A' } });
    knopf(h, 'Duplizieren').click();
    expect(h.emitted.at(-1)).toEqual({ kind: 'set', path: ['rules', 'alpha_kopie'], value: { title: 'A' } });
  });
});
