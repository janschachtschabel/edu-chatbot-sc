// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { ChoicesApi } from '../core/choices-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AREA_SCHEMAS } from './area-schemas.fixture';
import type { JsonSchema } from './json-schema';
import { SchemaFormComponent } from './schema-form.component';

interface Harness {
  fixture: ComponentFixture<SchemaFormComponent>;
  el: HTMLElement;
  /** Documents emitted by valueChange, in order. */
  emitted: Record<string, unknown>[];
}

/** `[id="…"]` rather than `#${CSS.escape(id)}`: the CSS global is absent here,
 * and map-entry ids contain user-supplied key text. */
function byId(el: HTMLElement, id: string): HTMLElement | null {
  return el.querySelector(`[id="${id.replace(/"/g, '\\"')}"]`);
}

async function mount(schema: JsonSchema, value: Record<string, unknown>): Promise<Harness> {
  // several tests mount a second form to compare a variant
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
  // Zusagen unten brauchen deshalb die oberste Sprachquelle.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(SchemaFormComponent);
  const emitted: Record<string, unknown>[] = [];
  fixture.componentRef.setInput('schema', schema);
  fixture.componentRef.setInput('value', value);
  fixture.componentInstance.valueChange.subscribe((next) => emitted.push(next));
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, emitted };
}

function inputFor(el: HTMLElement, labelText: string): HTMLInputElement {
  const label = Array.from(el.querySelectorAll('label')).find((l) =>
    l.textContent?.trim().startsWith(labelText),
  );
  if (!label) throw new Error(`no label starting with "${labelText}"`);
  const control = byId(el, label.htmlFor);
  if (!control) throw new Error(`label "${labelText}" points at missing #${label.htmlFor}`);
  return control as HTMLInputElement;
}

function type(control: HTMLInputElement | HTMLTextAreaElement, text: string): void {
  control.value = text;
  control.dispatchEvent(new Event('input'));
}

function buttonWithLabel(el: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(el.querySelectorAll('button')).find(
    (b) => b.getAttribute('aria-label') === label,
  );
  if (!found) throw new Error(`no button labelled "${label}"`);
  return found;
}

const WELCOME = AREA_SCHEMAS['01-base/welcome-config'];

describe('SchemaFormComponent — scalars', () => {
  const schema: JsonSchema = {
    type: 'object',
    properties: {
      greeting: { type: 'string' },
      max: { type: 'integer' },
      enabled: { type: 'boolean' },
    },
    required: ['greeting'],
  };

  let h: Harness;
  beforeEach(async () => {
    h = await mount(schema, { greeting: 'Moin', max: 3, enabled: true });
  });

  it('gives every control a label that points at it', () => {
    for (const label of Array.from(h.el.querySelectorAll('label'))) {
      expect(label.htmlFor, `label "${label.textContent}" has no for=`).toBeTruthy();
      expect(byId(h.el, label.htmlFor)).not.toBeNull();
    }
  });

  it('shows current values', () => {
    expect(inputFor(h.el, 'greeting').value).toBe('Moin');
    expect(inputFor(h.el, 'max').value).toBe('3');
    expect(inputFor(h.el, 'enabled').checked).toBe(true);
  });

  it('emits the edited document on input', async () => {
    type(inputFor(h.el, 'greeting'), 'Servus');
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ greeting: 'Servus', max: 3, enabled: true });
  });

  it('emits a number, not a string, from a numeric field', async () => {
    type(inputFor(h.el, 'max'), '7');
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)?.['max']).toBe(7);
  });

  it('emits null for a cleared numeric field rather than a silent 0', async () => {
    type(inputFor(h.el, 'max'), '');
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)?.['max']).toBeNull();
  });

  it('toggles a checkbox', async () => {
    const check = inputFor(h.el, 'enabled');
    check.checked = false;
    check.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)?.['enabled']).toBe(false);
  });

  it('marks a required field in words, not by colour', () => {
    const label = Array.from(h.el.querySelectorAll('label')).find((l) =>
      l.textContent?.includes('greeting'),
    );
    expect(label?.textContent).toContain('Pflichtfeld');
    expect(inputFor(h.el, 'greeting').getAttribute('aria-required')).toBe('true');
  });

  it('does not mark an optional field as required', () => {
    expect(inputFor(h.el, 'max').getAttribute('aria-required')).toBeNull();
  });
});

describe('SchemaFormComponent — the preservation guarantee', () => {
  it('keeps document keys no field renders', async () => {
    // the reason the form edits the document instead of rebuilding it: 357
    // real config paths are not pinned by their area model
    const h = await mount(WELCOME, {
      welcome: { greeting: 'Moin', haus_intern: 'bleibt' },
      notiz: 'bleibt auch',
    });
    type(inputFor(h.el, 'greeting'), 'Servus');
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({
      welcome: { greeting: 'Servus', haus_intern: 'bleibt' },
      notiz: 'bleibt auch',
    });
  });

  it('says so when the document carries top-level keys it does not show', async () => {
    const h = await mount(WELCOME, { welcome: {}, notiz: 'x', intern: 'y' });
    expect(h.el.textContent).toContain('notiz, intern');
    expect(h.el.textContent).toContain('Rohtext');
  });

  it('names NESTED unmapped keys too — that is where the real ones sit', async () => {
    // a top-level-only note would have read as exhaustive while hiding
    // `welcome.haus_intern`, exactly the shape of the 357 measured paths
    const h = await mount(WELCOME, { welcome: { greeting: 'Moin', haus_intern: 'x' } });
    expect(h.el.textContent).toContain('welcome.haus_intern');
  });

  it('phrases the singular case as German rather than as a template', async () => {
    const h = await mount(WELCOME, { welcome: {}, notiz: 'x' });
    expect(h.el.textContent).toContain('ändern lässt er sich');
  });

  it('stays quiet when every key is rendered', async () => {
    const h = await mount(WELCOME, { welcome: {} });
    expect(h.el.querySelector('.sf-note')).toBeNull();
  });
});

describe('SchemaFormComponent — lists', () => {
  let h: Harness;
  beforeEach(async () => {
    h = await mount(WELCOME, { welcome: { quick_replies: ['a', 'b'] } });
  });

  it('renders one control per entry', () => {
    expect(inputFor(h.el, 'quick_replies 1').value).toBe('a');
    expect(inputFor(h.el, 'quick_replies 2').value).toBe('b');
  });

  it('appends the blank value of the item type', async () => {
    buttonWithLabel(h.el, 'Eintrag zu quick_replies hinzufügen').click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ welcome: { quick_replies: ['a', 'b', ''] } });
  });

  it('removes an entry and shifts the rest down', async () => {
    buttonWithLabel(h.el, 'Eintrag 1 aus quick_replies entfernen').click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ welcome: { quick_replies: ['b'] } });
  });

  it('offers an empty state instead of a bare heading', async () => {
    const empty = await mount(WELCOME, { welcome: { quick_replies: [] } });
    expect(empty.el.textContent).toContain('Noch keine Einträge.');
  });
});

describe('SchemaFormComponent — maps', () => {
  const RAG = AREA_SCHEMAS['05-knowledge/rag-config'];

  it('renders one row per entry with an editable key', async () => {
    const h = await mount(RAG, { FAQ: { mode: 'always' } });
    expect(inputFor(h.el, 'Schlüssel').value).toBe('FAQ');
    expect(inputFor(h.el, 'mode').value).toBe('always');
  });

  it('renames a key on change, keeping its value', async () => {
    const h = await mount(RAG, { FAQ: { mode: 'always' }, OER: { mode: 'nie' } });
    const key = inputFor(h.el, 'Schlüssel');
    key.value = 'Fragen';
    key.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ Fragen: { mode: 'always' }, OER: { mode: 'nie' } });
  });

  it('adds an entry under a free placeholder key', async () => {
    const h = await mount(RAG, {});
    // the root of a map area has no key; its buttons must still be named
    buttonWithLabel(h.el, 'Eintrag zu Einträge hinzufügen').click();
    await h.fixture.whenStable();
    expect(Object.keys(h.emitted.at(-1) ?? {})).toEqual(['neuer_eintrag']);
  });

  it('removes an entry', async () => {
    const h = await mount(RAG, { FAQ: { mode: 'always' } });
    buttonWithLabel(h.el, 'Eintrag FAQ entfernen').click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({});
  });
});

describe('SchemaFormComponent — free-form (raw) fields', () => {
  const POLICY = AREA_SCHEMAS['01-base/policy'];
  const doc = { rules: [{ id: 'r1', match: { persona: 'lehrkraft' }, effect: {} }] };

  function jsonBoxes(el: HTMLElement): HTMLTextAreaElement[] {
    return Array.from(el.querySelectorAll<HTMLTextAreaElement>('textarea.sf-json'));
  }

  it('renders `dict[str, Any]` config as editable JSON, not as a dead end', async () => {
    const h = await mount(POLICY, doc);
    const texts = jsonBoxes(h.el).map((box) => box.value);
    expect(texts).toContain(JSON.stringify({ persona: 'lehrkraft' }, null, 2));
  });

  it('commits parsed JSON on change', async () => {
    const h = await mount(POLICY, doc);
    const box = jsonBoxes(h.el)[0];
    box.value = '{"persona": "lernende"}';
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({
      rules: [{ id: 'r1', match: { persona: 'lernende' }, effect: {} }],
    });
  });

  it('reports invalid JSON and emits nothing', async () => {
    const h = await mount(POLICY, doc);
    const box = jsonBoxes(h.el)[0];
    box.value = '{nope';
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted).toHaveLength(0);
    expect(h.el.textContent).toContain('Kein gültiges JSON');
    expect(box.getAttribute('aria-invalid')).toBe('true');
    // the typed text stays: discarding it would be worse than the error
    expect(box.value).toBe('{nope');
  });

  it('keeps the error tied to the field it belongs to', async () => {
    const h = await mount(POLICY, doc);
    const box = jsonBoxes(h.el)[0];
    box.value = '{nope';
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    const described = box.getAttribute('aria-describedby') ?? '';
    expect(described).toContain(`${box.id}-err`);
    expect(byId(h.el, `${box.id}-err`)).not.toBeNull();
  });
});

describe('SchemaFormComponent — a stored value that does not fit the schema', () => {
  it('shows a conflicting value as JSON instead of an empty group', async () => {
    // `welcome` is an object in the schema. As an array, every keystroke into
    // the rendered group would be written to `arr[NaN]`, dropped by
    // JSON.stringify, and the dirty check would stay false — a silent no-op.
    const h = await mount(WELCOME, { welcome: [] });
    expect(h.el.textContent).toContain('das Bereichsmodell erwartet hier ein Objekt');
    expect(h.el.querySelector('textarea.sf-json')).not.toBeNull();
  });

  it('keeps the conflicting value editable, and a repair reaches the document', async () => {
    const h = await mount(WELCOME, { welcome: 'oops' });
    const box = h.el.querySelector<HTMLTextAreaElement>('textarea.sf-json')!;
    box.value = '{"greeting": "Moin"}';
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ welcome: { greeting: 'Moin' } });
  });

  it('does not cry conflict over a missing value', async () => {
    const h = await mount(WELCOME, {});
    expect(h.el.textContent).not.toContain('Bereichsmodell erwartet');
  });
});

describe('SchemaFormComponent — refused map renames', () => {
  const RAG = AREA_SCHEMAS['05-knowledge/rag-config'];

  async function renameFirstKey(h: Harness, to: string): Promise<HTMLInputElement> {
    const key = inputFor(h.el, 'Schlüssel');
    key.value = to;
    key.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    return key;
  }

  it('puts the field back and says why when the name is taken', async () => {
    const h = await mount(RAG, { FAQ: { mode: 'a' }, OER: { mode: 'b' } });
    const key = await renameFirstKey(h, 'OER');
    expect(h.emitted).toHaveLength(0);
    // without restoring the input, two rows would claim the same key while the
    // document still had the old one
    expect(key.value).toBe('FAQ');
    expect(h.el.textContent).toContain('ist schon vergeben');
    expect(key.getAttribute('aria-invalid')).toBe('true');
  });

  it('refuses an empty key rather than doing nothing at all', async () => {
    const h = await mount(RAG, { FAQ: { mode: 'a' } });
    const key = await renameFirstKey(h, '   ');
    expect(h.emitted).toHaveLength(0);
    expect(key.value).toBe('FAQ');
    expect(h.el.textContent).toContain('darf nicht leer sein');
  });
});

describe('SchemaFormComponent — unparseable fields are reported upwards', () => {
  const POLICY = AREA_SCHEMAS['01-base/policy'];

  it('announces which fields cannot be parsed, and withdraws it on repair', async () => {
    TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); die deutschen
  // Zusagen unten brauchen deshalb die oberste Sprachquelle.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    const errors: readonly string[][] = [];
    fixture.componentRef.setInput('schema', POLICY);
    fixture.componentRef.setInput('value', { rules: [{ id: 'r1', match: {} }] });
    fixture.componentInstance.errorsChange.subscribe((next) =>
      (errors as string[][]).push([...next]),
    );
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const box = el.querySelector<HTMLTextAreaElement>('textarea.sf-json')!;
    box.value = '{kaputt';
    box.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(errors.at(-1)).toEqual(['rules.0.match']);
    box.value = '{"persona": "lehrkraft"}';
    box.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(errors.at(-1)).toEqual([]);
  });

  it('treats an emptied JSON field as null, not as the string ""', async () => {
    const h = await mount(POLICY, { rules: [{ id: 'r1', match: { a: 1 } }] });
    const box = h.el.querySelector<HTMLTextAreaElement>('textarea.sf-json')!;
    box.value = '   ';
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ rules: [{ id: 'r1', match: null }] });
  });
});

describe('SchemaFormComponent — every real area renders', () => {
  it.each(Object.keys(AREA_SCHEMAS))('mounts %s with an empty document', async (area) => {
    const h = await mount(AREA_SCHEMAS[area], {});
    expect(h.el.querySelector('studio-schema-field')).not.toBeNull();
  });
});

describe('SchemaFormComponent — aufklappbare Abschnitte (S5)', () => {
  const LANG: JsonSchema = {
    type: 'object',
    properties: {
      stufe: { type: 'string' },
      block_a: { type: 'object', properties: { x: { type: 'string' } } },
      block_b: { type: 'object', properties: { y: { type: 'string' } } },
    },
  };

  function sections(el: HTMLElement): HTMLDetailsElement[] {
    return Array.from(el.querySelectorAll<HTMLDetailsElement>('details.sf-section'));
  }

  it('gibt jedem Block einen Abschnitt und öffnet nur den ersten', async () => {
    const h = await mount(LANG, { stufe: 'standard', block_a: {}, block_b: {} });
    const auf = sections(h.el);
    expect(auf.map((d) => d.querySelector('summary')?.textContent?.trim())).toEqual([
      'Grundwerte', 'block_a', 'block_b',
    ]);
    expect(auf.map((d) => d.open)).toEqual([true, false, false]);
  });

  it('schreibt aus einem Abschnitt in dasselbe Dokument', async () => {
    // Die tragende Zusage: die Gliederung ist Anzeige, nicht Struktur —
    // gespeichert wird weiterhin das ganze Dokument.
    const h = await mount(LANG, { stufe: 'standard', block_a: { x: 'alt' }, block_b: {} });
    const feld = sections(h.el)[1].querySelector<HTMLInputElement>('input.sf-input')!;
    feld.value = 'neu';
    feld.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({
      stufe: 'standard', block_a: { x: 'neu' }, block_b: {},
    });
  });

  it('lässt ein kurzes Formular ungegliedert', async () => {
    const kurz: JsonSchema = { type: 'object', properties: { a: { type: 'string' } } };
    const h = await mount(kurz, { a: '1' });
    expect(sections(h.el)).toHaveLength(0);
    expect(h.el.querySelector('studio-schema-field')).not.toBeNull();
  });

  // Die MEISTEN Bereiche sehen so aus — 16 von 34 packen alles in einen Block.
  const HUELLE: JsonSchema = {
    type: 'object',
    properties: {
      display_rules: {
        type: 'object',
        properties: {
          block_a: { type: 'object', properties: { x: { type: 'string' } } },
          block_b: { type: 'object', properties: { y: { type: 'string' } } },
        },
      },
    },
  };

  it('nennt die Hülle nicht über jedem Abschnitt', async () => {
    const h = await mount(HUELLE, { display_rules: { block_a: {}, block_b: {} } });
    const legenden = Array.from(h.el.querySelectorAll('legend')).map((l) => l.textContent?.trim());
    expect(legenden).not.toContain('display_rules');
    expect(legenden).toContain('block_a');
  });

  it('schreibt aus einem Abschnitt hinter der Hülle in denselben Pfad', async () => {
    // Die Gliederung verschiebt die ANZEIGE, nicht das Dokument: ein Abschnitt
    // beginnt hinter der Hülle, sein Feld muss trotzdem unter ihr landen.
    const h = await mount(HUELLE, { display_rules: { block_a: { x: 'alt' }, block_b: {} } });
    const feld = sections(h.el)[0].querySelector<HTMLInputElement>('input.sf-input')!;
    type(feld, 'neu');
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ display_rules: { block_a: { x: 'neu' }, block_b: {} } });
  });
});

describe('SchemaFormComponent — Auswahlfeld (S3)', () => {
  const MIT_AUSWAHL: JsonSchema = {
    type: 'object',
    properties: { mode: { type: 'string', 'x-choices': ['off', 'smart', 'always'] } },
  };

  it('zeigt jede erlaubte Option plus eine leere', async () => {
    const h = await mount(MIT_AUSWAHL, { mode: 'smart' });
    const box = h.el.querySelector<HTMLSelectElement>('select.sf-select')!;
    expect(Array.from(box.options).map((o) => o.value)).toEqual(['', 'off', 'smart', 'always']);
    expect(box.value).toBe('smart');
  });

  it('meldet die Wahl als Dokument-Änderung', async () => {
    const h = await mount(MIT_AUSWAHL, { mode: 'smart' });
    const box = h.el.querySelector<HTMLSelectElement>('select.sf-select')!;
    box.value = 'always';
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ mode: 'always' });
  });

  it('führt einen Bestandswert ausserhalb der Liste weiter und weist ihn aus', async () => {
    // Sonst zeigte das Feld die erste Option an, obwohl etwas anderes
    // gespeichert ist — und der nächste Speichervorgang schriebe die Lüge fest.
    const h = await mount(MIT_AUSWAHL, { mode: 'aus-2024' });
    const box = h.el.querySelector<HTMLSelectElement>('select.sf-select')!;
    expect(box.value).toBe('aus-2024');
    const fremd = Array.from(box.options).find((o) => o.value === 'aus-2024')!;
    expect(fremd.textContent).toContain('aus-2024');
    expect(fremd.textContent?.trim()).not.toBe('aus-2024'); // trägt den Hinweis
    expect(h.emitted).toEqual([]); // nichts verändert, nur angezeigt
  });
});

describe('SchemaFormComponent — Vorschlagsliste (S3)', () => {
  const MIT_KATALOG: JsonSchema = {
    type: 'object',
    properties: { crisis_pattern: { type: 'string', 'x-catalog': 'patterns' } },
  };

  it('bleibt ein Textfeld und hängt eine datalist an', async () => {
    const h = await mount(MIT_KATALOG, { crisis_pattern: 'M01' });
    const feld = h.el.querySelector<HTMLInputElement>('input.sf-input[type="text"]')!;
    expect(feld.value).toBe('M01');
    const liste = feld.getAttribute('list');
    expect(liste).toBeTruthy();
    expect(byId(h.el, liste!)?.tagName).toBe('DATALIST');
  });

  it('lässt einen Namen zu, der noch in keinem Katalog steht', async () => {
    // Ein Muster entsteht durch Anlegen, ein RAG-Bereich durch Einlesen — wer
    // den Namen schon kennt, muss ihn tippen dürfen.
    const h = await mount(MIT_KATALOG, { crisis_pattern: '' });
    const feld = h.el.querySelector<HTMLInputElement>('input.sf-input[type="text"]')!;
    feld.value = 'M99';
    feld.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ crisis_pattern: 'M99' });
  });

  it('rendert eine Liste je Katalog, nicht je Feld', async () => {
    // Ein Muster nennt bis zu acht Werkzeuge; eine eigene Liste je Eintrag
    // hiesse achtmal denselben Katalog in die Seite zu schreiben.
    const listenFeld: JsonSchema = {
      type: 'object',
      properties: {
        tools: { type: 'array', items: { type: 'string', 'x-catalog': 'tools' } },
      },
    };
    const h = await mount(listenFeld, { tools: ['a', 'b', 'c'] });
    const felder = h.el.querySelectorAll<HTMLInputElement>('input.sf-input[type="text"]');
    expect(felder).toHaveLength(3);
    expect(new Set(Array.from(felder).map((f) => f.getAttribute('list'))).size).toBe(1);
    expect(h.el.querySelectorAll('datalist')).toHaveLength(1);
  });
});

describe('SchemaFormComponent — Textfläche (Fliesstext)', () => {
  const MIT_STRUKTUR: JsonSchema = {
    type: 'object',
    properties: { structure: { type: 'string' }, label: { type: 'string' } },
  };

  it('wächst mit dem Inhalt statt bei einer festen Höhe zu bleiben', async () => {
    // Nutzer 2026-08-13: „in einer fortlaufenden Zeile ist das als Mensch kaum
    // zu bearbeiten". Eine feste Höhe hiesse: für `structure` (bis 729 Zeichen)
    // zu klein, für ein leeres Feld unnötig hoch.
    const kurz = await mount(MIT_STRUKTUR, { structure: 'Kurz.', label: 'x' });
    const lang = await mount(MIT_STRUKTUR, { structure: 'W'.repeat(700), label: 'x' });
    const zeilen = (h: Awaited<ReturnType<typeof mount>>) =>
      Number(h.el.querySelector<HTMLTextAreaElement>('textarea.sf-multiline')!.rows);
    expect(zeilen(kurz)).toBeGreaterThanOrEqual(3);
    expect(zeilen(lang)).toBeGreaterThan(zeilen(kurz));
  });

  it('lässt kurze Felder einzeilig', async () => {
    const h = await mount(MIT_STRUKTUR, { structure: '', label: 'Automatisch' });
    const label = inputFor(h.el, 'label');
    expect(label.tagName).toBe('INPUT');
  });
});

describe('SchemaFormComponent — Sprung zum Element (S4)', () => {
  const MIT_KATALOG: JsonSchema = {
    type: 'object',
    properties: { crisis_pattern: { type: 'string', 'x-catalog': 'patterns' } },
  };
  const EINTRAG = { value: 'M06', label: 'Material-Suche', area: '03-patterns/m06-material' };
  // Kein `satisfies ChoicesApi`: der Dienst hat private Felder, die eine
  // Attrappe nicht nachbauen kann und nicht nachbauen soll.
  const attrappe: Pick<ChoicesApi, 'catalogs' | 'prime' | 'entries' | 'areaFor'> = {
    catalogs: signal({ patterns: [EINTRAG] }).asReadonly(),
    prime: () => Promise.resolve(),
    entries: () => [EINTRAG],
    areaFor: (_katalog, wert) => (wert === EINTRAG.value ? EINTRAG.area : ''),
  };

  it('adressiert den Bereich in Segmenten, nicht als ein %2F-Stück', async () => {
    // Wie in `areas.component.ts`: der Schlüssel trägt einen Schrägstrich. Als
    // EIN Segment übergeben landet er `%2F`-kodiert in der Adresse — im SPA
    // löst das noch auf, beim Neuladen entscheidet der Reverse-Proxy.
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([{ path: '**', children: [] }]),
        { provide: ChoicesApi, useValue: attrappe },
      ],
    });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    fixture.componentRef.setInput('schema', MIT_KATALOG);
    fixture.componentRef.setInput('value', { crisis_pattern: 'M06' });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const link = el.querySelector<HTMLAnchorElement>('a.sf-jump')!;
    expect(link.getAttribute('href')).toBe('/bereich/03-patterns/m06-material');
  });
});
