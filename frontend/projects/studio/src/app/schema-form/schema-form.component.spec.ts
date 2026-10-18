// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { ChoicesApi } from '../core/choices-api.service';
import type { FieldProblem } from '../core/field-problems';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
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
  // ST-1: vorn steht die Katalog-Beschriftung, klein dahinter der Rohschlüssel
  // — ein Feld ist über beides zu finden.
  const label = Array.from(el.querySelectorAll('label')).find(
    (l) =>
      l.textContent?.trim().startsWith(labelText)
      || l.querySelector('.sf-key')?.textContent?.trim() === labelText,
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

  it('zeigt einen Wahrheitswert als Schalter — das native Kästchen mit der Rolle „switch"', () => {
    // ST-2b: das Kästchen bleibt, damit Leertaste, Fokus und der angesagte
    // Zustand vom Browser kommen; `role="switch"` lässt es „an/aus" heißen.
    const check = inputFor(h.el, 'enabled');
    expect(check.type).toBe('checkbox');
    expect(check.getAttribute('role')).toBe('switch');
    expect(check.classList).toContain('sf-switch');
  });

  it('zeigt die Grenzen eines Zahlfelds und setzt sie als min/max (ST-2c)', async () => {
    const mitGrenzen: JsonSchema = {
      type: 'object',
      properties: { prozent: { type: 'integer', minimum: 70, maximum: 100 } },
    };
    const g = await mount(mitGrenzen, { prozent: 85 });
    const feld = inputFor(g.el, 'prozent');
    expect([feld.getAttribute('min'), feld.getAttribute('max')]).toEqual(['70', '100']);
    const beschreibung = (feld.getAttribute('aria-describedby') ?? '')
      .split(' ')
      .map((id) => byId(g.el, id)?.textContent?.trim());
    expect(beschreibung).toContain('Erlaubt: 70 bis 100');
  });

  it('zeigt einen vom Code festgesetzten Schalter gesperrt als „fest aktiv" (ST-6)', async () => {
    // Das Sicherheitsprotokoll setzt der Lader fest auf an; ein bedienbarer
    // Schalter stellte sich wirkungslos auf „aus" — auch ein gespeichertes
    // `false` zeigt deshalb, was WIRKT.
    const fest: JsonSchema = {
      type: 'object',
      properties: { safety: { type: 'boolean', 'x-fixed': true } },
    };
    const g = await mount(fest, { safety: false });
    const schalter = inputFor(g.el, 'safety');
    expect(schalter.disabled).toBe(true);
    expect(schalter.checked).toBe(true);
    expect(g.el.textContent).toContain('fest aktiv');
    schalter.click();
    await g.fixture.whenStable();
    expect(g.emitted).toEqual([]);
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
  /** Der Name der Liste — seit ST-1 aus dem Katalog („Start-Chips"), nicht mehr
   *  der Rohschlüssel. Einträge und Knöpfe heißen danach. */
  let liste: string;
  beforeEach(async () => {
    h = await mount(WELCOME, { welcome: { quick_replies: ['a', 'b'] } });
    liste = TestBed.inject(StudioLanguageService).t('feld.WelcomeBlock.quick_replies.label');
  });

  it('renders one control per entry', () => {
    expect(inputFor(h.el, `${liste} 1`).value).toBe('a');
    expect(inputFor(h.el, `${liste} 2`).value).toBe('b');
  });

  it('appends the blank value of the item type', async () => {
    buttonWithLabel(h.el, `Eintrag zu ${liste} hinzufügen`).click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ welcome: { quick_replies: ['a', 'b', ''] } });
  });

  it('removes an entry and shifts the rest down', async () => {
    buttonWithLabel(h.el, `Eintrag 1 aus ${liste} entfernen`).click();
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

  // Seit ST-3 ist eine Map von Objekten ein Liste│Editor: die Knöpfe heißen
  // „Neu" und „Löschen", die Wirkung ist dieselbe.
  it('adds an entry under a free placeholder key', async () => {
    const h = await mount(RAG, {});
    // the root of a map area has no key; its buttons must still be named
    buttonWithLabel(h.el, 'Neu in Einträge').click();
    await h.fixture.whenStable();
    expect(Object.keys(h.emitted.at(-1) ?? {})).toEqual(['neuer_eintrag']);
  });

  it('removes an entry', async () => {
    const h = await mount(RAG, { FAQ: { mode: 'always' } });
    buttonWithLabel(h.el, 'Löschen: FAQ').click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({});
  });
});

describe('SchemaFormComponent — Maps einfacher Werte als Tabelle (Paket 15)', () => {
  // Nutzer-Rundgang 2026-10-17 („Anzeige“): je Eintrag „Schlüssel“, darunter ein Feld mit
  // demselben Namen, darunter „Entfernen“ — drei Ebenen für ein Paar.
  const SCHEMA: JsonSchema = {
    type: 'object',
    properties: {
      per_pattern: { type: 'object', additionalProperties: { type: 'boolean' } },
    },
  };
  const zeilen = (el: HTMLElement) => Array.from(el.querySelectorAll('table.sf-map tbody tr'));

  it('zeigt Schlüssel und Wert je Zeile in einer Tabelle', async () => {
    const h = await mount(SCHEMA, { per_pattern: { M09: true, M10: false } });
    const kopf = Array.from(h.el.querySelectorAll('table.sf-map thead th'))
      .map((th) => th.textContent?.trim());
    expect(kopf.slice(0, 2)).toEqual(['Schlüssel', 'Wert']);
    expect(zeilen(h.el)).toHaveLength(2);
    const [erste] = zeilen(h.el);
    expect(erste.querySelector<HTMLInputElement>('input[type="text"]')?.value).toBe('M09');
    expect(erste.querySelector<HTMLInputElement>('input[type="checkbox"]')?.checked).toBe(true);
  });

  it('ändert einen Wert, benennt einen Schlüssel um und entfernt eine Zeile', async () => {
    const h = await mount(SCHEMA, { per_pattern: { M09: true, M10: false } });
    const box = zeilen(h.el)[0].querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    box.checked = false;
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ per_pattern: { M09: false, M10: false } });

    const schluessel = zeilen(h.el)[1].querySelector<HTMLInputElement>('input[type="text"]')!;
    schluessel.value = 'M11';
    schluessel.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    // Review-Runde 2 (R2-12): Wert bleibt, Reihenfolge bleibt, der alte Schlüssel ist weg.
    // (Die Hülle reicht den Wert nicht zurück — jede Änderung geht vom Ausgangsdokument aus.)
    const umbenannt = (h.emitted.at(-1) as { per_pattern: Record<string, boolean> }).per_pattern;
    expect(umbenannt).toEqual({ M09: true, M11: false });
    expect(Object.keys(umbenannt)).toEqual(['M09', 'M11']);

    zeilen(h.el)[0].querySelector<HTMLButtonElement>('button')!.click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ per_pattern: { M10: false } });
  });

  it('zeigt auch Textflächen je Schlüssel als Tabelle (Begrüßung je Seitentyp)', async () => {
    const texte: JsonSchema = {
      type: 'object',
      properties: {
        greetings: {
          type: 'object',
          additionalProperties: { type: 'string', 'x-widget': 'textarea' } as JsonSchema,
        },
      },
    };
    const h = await mount(texte, { greetings: { collection: 'Hallo {title}' } });
    expect(zeilen(h.el)[0].querySelector('textarea')?.value).toBe('Hallo {title}');
  });

  it('gibt Schlüssel- und Wertfeld je Zeile einen zugänglichen Namen', async () => {
    const h = await mount(SCHEMA, { per_pattern: { M09: true } });
    const [zeile] = zeilen(h.el);
    const schluessel = zeile.querySelector<HTMLInputElement>('input[type="text"]')!;
    const wert = zeile.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    expect(h.el.querySelector(`label[for="${schluessel.id}"]`)?.textContent).toContain('M09');
    expect(h.el.querySelector(`label[for="${wert.id}"]`)?.textContent).toContain('M09');
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
    // `-json-err`, not `-err`: that one names the server's problem with the
    // field — the parse error has its own region since Paket 4 (S1).
    expect(described).toContain(`${box.id}-json-err`);
    expect(byId(h.el, `${box.id}-json-err`)?.textContent).toContain('JSON');
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

  it('die Fehlerzeile einer einfachen Karte steht leer bereit (Paket 4, S1)', async () => {
    // Karten mit einfachen Werten benennt das Feld selbst um, nicht die Liste.
    const LABELS: JsonSchema = {
      type: 'object',
      properties: { labels: { type: 'object', additionalProperties: { type: 'string' } } },
    };
    const h = await mount(LABELS, { labels: { FAQ: 'a', OER: 'b' } });
    const key = inputFor(h.el, 'Schlüssel');
    const region = byId(h.el, `${key.id}-err`);
    expect(region?.getAttribute('aria-live')).toBe('polite');
    expect(region!.textContent).toBe(''); // ganz leer, sonst greift `:empty` nicht

    key.value = 'OER';
    key.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();

    expect(byId(h.el, `${key.id}-err`)).toBe(region);
    expect(region!.textContent).toContain('ist schon vergeben');
  });

  // Paket 6: die Map-Regeln stehen in `map-entries.ts`. Die Rücksetz-Prüfung
  // oben läuft über die RAG-Karte — seit ST-3 eine Objekt-Liste, nicht dieser Zweig.
  describe('einfache Karte (Map-Zweig des Feldes)', () => {
    const LABELS: JsonSchema = {
      type: 'object',
      properties: { labels: { type: 'object', additionalProperties: { type: 'string' } } },
    };

    it('setzt den alten Schlüssel zurück, wenn der neue vergeben ist', async () => {
      const h = await mount(LABELS, { labels: { FAQ: 'a', OER: 'b' } });
      const key = inputFor(h.el, 'Schlüssel');
      key.value = 'OER';
      key.dispatchEvent(new Event('change'));
      await h.fixture.whenStable();

      expect(h.emitted).toHaveLength(0);
      expect(key.value).toBe('FAQ');
      expect(key.getAttribute('aria-invalid')).toBe('true');
    });

    it('benennt einen Schlüssel um und behält Wert und Reihenfolge', async () => {
      const h = await mount(LABELS, { labels: { FAQ: 'a', OER: 'b' } });
      const key = inputFor(h.el, 'Schlüssel');
      key.value = 'Fragen';
      key.dispatchEvent(new Event('change'));
      await h.fixture.whenStable();

      expect(h.emitted.at(-1)).toEqual({ labels: { Fragen: 'a', OER: 'b' } });
      expect(Object.keys((h.emitted.at(-1) as { labels: object }).labels)).toEqual(['Fragen', 'OER']);
    });
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
    // Paket 15: der Block heißt einmal — in der Zusammenfassung, nicht noch als Legende darunter.
    expect(legenden).not.toContain('block_a');
    const koepfe = Array.from(h.el.querySelectorAll('details.sf-section > summary'))
      .map((s) => s.textContent?.trim());
    expect(koepfe).toContain('block_a');
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
    // Seit ST-2g Chips: drei Chips, EIN Eingabefeld — an der einen Liste.
    expect(h.el.querySelectorAll('.sf-chip')).toHaveLength(3);
    const felder = h.el.querySelectorAll<HTMLInputElement>('input.sf-input[type="text"]');
    expect(felder).toHaveLength(1);
    expect(byId(h.el, felder[0].getAttribute('list')!)?.tagName).toBe('DATALIST');
    expect(h.el.querySelectorAll('datalist')).toHaveLength(1);
  });
});

describe('SchemaFormComponent — Chips aus Katalogen (ST-2g)', () => {
  const WERKZEUGE: JsonSchema = {
    type: 'object',
    properties: { tools: { type: 'array', items: { type: 'string', 'x-catalog': 'tools' } } },
  };

  function neu(el: HTMLElement): HTMLInputElement {
    return el.querySelector<HTMLInputElement>('.sf-chip-add input')!;
  }

  it('zeigt jeden Wert als Chip mit eigenem Entfernen-Knopf', async () => {
    const h = await mount(WERKZEUGE, { tools: ['search_wlo_content', 'get_skill'] });
    const chips = Array.from(h.el.querySelectorAll('.sf-chip'));
    expect(chips.map((c) => c.querySelector('.sf-chip-text')?.textContent?.trim()))
      .toEqual(['search_wlo_content', 'get_skill']);
    const knopf = chips[1].querySelector('button')!;
    expect(knopf.getAttribute('aria-label')).toContain('get_skill');
    knopf.click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ tools: ['search_wlo_content'] });
  });

  it('hängt einen Wert an — per Knopf und per Eingabetaste — und leert das Feld', async () => {
    const h = await mount(WERKZEUGE, { tools: ['a'] });
    const feld = neu(h.el);
    feld.value = ' b ';
    h.el.querySelector<HTMLButtonElement>('.sf-chip-add button')!.click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ tools: ['a', 'b'] });
    expect(feld.value).toBe('');
    feld.value = 'c';
    feld.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ tools: ['a', 'c'] });
  });

  it('nimmt einen Wert nicht doppelt auf und sagt warum', async () => {
    const h = await mount(WERKZEUGE, { tools: ['a'] });
    const vorher = h.emitted.length;
    neu(h.el).value = 'a';
    h.el.querySelector<HTMLButtonElement>('.sf-chip-add button')!.click();
    await h.fixture.whenStable();
    expect(h.emitted.length).toBe(vorher);
    expect(h.el.querySelector('.sf-chip-add .sf-error')?.textContent).toContain('„a“');
  });

  it('die Fehlerzeile steht leer bereit, bevor sie etwas meldet (Paket 4, S1)', async () => {
    // Eine Live-Region, die erst mit ihrem Text entsteht, sagen Screenreader
    // oft nicht an (Audit 2026-09-29, F-M6).
    const h = await mount(WERKZEUGE, { tools: ['a'] });
    const region = h.el.querySelector<HTMLElement>('.sf-chip-add .sf-error[aria-live="polite"]');
    expect(region).not.toBeNull();
    expect(region!.textContent).toBe(''); // ganz leer, sonst greift `:empty` nicht
    neu(h.el).value = 'a';
    h.el.querySelector<HTMLButtonElement>('.sf-chip-add button')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.sf-chip-add .sf-error[aria-live="polite"]')).toBe(region);
    expect(region!.textContent).toContain('„a“');
  });
});

describe('SchemaFormComponent — Textfläche (Fliesstext)', () => {
  // Seit ST-2f entscheidet der Hinweis des Modells, nicht der Name.
  const MIT_STRUKTUR: JsonSchema = {
    type: 'object',
    properties: {
      structure: { type: 'string', 'x-widget': 'textarea' },
      label: { type: 'string' },
    },
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

  it('hält die Zeilenumbrüche einer Kernregel über eine Bearbeitung (SF-2)', async () => {
    // Ein einzeiliges Feld entfernt Umbrüche aus seinem Wert, und die erste
    // Eingabe schrieb den geplätteten Text ins Dokument zurück. Gegen das
    // ECHTE Musterschema: dort stand `core_rule` in einem `input`.
    const kernregel = 'Erst fragen.\nDann suchen.';
    const h = await mount(AREA_SCHEMAS['03-patterns'], {
      frontmatter: { id: 'M99', core_rule: kernregel },
      body: '',
    });
    const feld = inputFor(h.el, 'core_rule');
    type(feld, `${feld.value} Dann zeigen.`);
    await h.fixture.whenStable();
    const doc = h.emitted.at(-1) as { frontmatter: Record<string, unknown> };
    expect(doc.frontmatter['core_rule']).toBe(`${kernregel} Dann zeigen.`);
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

describe('SchemaFormComponent — Schieberegler mit Bedeutung (ST-2h)', () => {
  const TON = AREA_SCHEMAS['01-base/tone-modifiers'];

  async function ton(bias: number | null): Promise<Harness> {
    return mount(TON, { default_modifier: { length_bias: bias } });
  }

  function regler(el: HTMLElement): HTMLInputElement {
    return el.querySelector<HTMLInputElement>('input[type="range"][id$="length_bias"]')!;
  }

  it('zeigt einen Regler mit den Grenzen und dem Schritt aus dem Schema', async () => {
    const h = await ton(0);
    const r = regler(h.el);
    expect([r.min, r.max, r.step]).toEqual(['-0.3', '0.3', '0.05']);
  });

  it('sagt, was der Wert bewirkt — sichtbar und als aria-valuetext', async () => {
    const t = TestBed.inject(StudioLanguageService).t;
    const laenger = t('feld.ToneModifier.length_bias.zone.ueber');
    const h = await ton(0.2);
    expect(regler(h.el).getAttribute('aria-valuetext')).toContain(laenger);
    expect(h.el.textContent).toContain(laenger);
    const g = await ton(0.15); // die Schwelle selbst verschiebt noch nicht
    expect(regler(g.el).getAttribute('aria-valuetext'))
      .toContain(t('feld.ToneModifier.length_bias.zone.mitte'));
  });

  it('schreibt beim Ziehen eine Zahl', async () => {
    const h = await ton(0);
    const r = regler(h.el);
    r.value = '-0.2';
    r.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    const doc = h.emitted.at(-1)?.['default_modifier'] as Record<string, unknown>;
    expect(doc['length_bias']).toBe(-0.2);
  });
});

describe('SchemaFormComponent — Tour-Chip als Radio je Zeile (ST-2i)', () => {
  const chips = ['Hallo', 'Web-Tour starten', 'Suche'];

  async function welcome(tour: string): Promise<Harness> {
    return mount(WELCOME, { welcome: { quick_replies: [...chips], tour_reply: tour } });
  }

  function radios(el: HTMLElement): HTMLInputElement[] {
    return Array.from(el.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
      .filter((r) => r.name.includes('quick_replies') && !r.name.includes('_en'));
  }

  it('setzt je Chip ein Radio und eins für „ohne" — das zum Tour-Chip ist gewählt', async () => {
    const h = await welcome('Web-Tour starten');
    const r = radios(h.el);
    expect(r).toHaveLength(chips.length + 1);
    expect(r.map((x) => x.checked)).toEqual([false, true, false, false]);
    // der Text der Zeile gehört in den zugänglichen Namen, sonst hieße jedes
    // Radio gleich
    expect(r[0].getAttribute('aria-label')).toContain('Hallo');
  });

  it('schreibt den gewählten Chip in den Tour-Chip', async () => {
    const h = await welcome('');
    radios(h.el)[2].click();
    await h.fixture.whenStable();
    expect((h.emitted.at(-1)?.['welcome'] as Record<string, unknown>)['tour_reply']).toBe('Suche');
  });

  it('„ohne" leert den Tour-Chip', async () => {
    const h = await welcome('Suche');
    radios(h.el).at(-1)!.click();
    await h.fixture.whenStable();
    expect((h.emitted.at(-1)?.['welcome'] as Record<string, unknown>)['tour_reply']).toBe('');
  });

  it('nimmt den Tour-Chip mit, wenn sein Text geändert wird', async () => {
    const h = await welcome('Suche');
    const liste = TestBed.inject(StudioLanguageService).t('feld.WelcomeBlock.quick_replies.label');
    type(inputFor(h.el, `${liste} 3`), 'Suchen');
    await h.fixture.whenStable();
    const doc = h.emitted.at(-1)?.['welcome'] as Record<string, unknown>;
    expect(doc['quick_replies']).toEqual(['Hallo', 'Web-Tour starten', 'Suchen']);
    expect(doc['tour_reply']).toBe('Suchen');
  });

  it('räumt den Tour-Chip, wenn seine Zeile gelöscht wird', async () => {
    const h = await welcome('Suche');
    const liste = TestBed.inject(StudioLanguageService).t('feld.WelcomeBlock.quick_replies.label');
    buttonWithLabel(h.el, `Eintrag 3 aus ${liste} entfernen`).click();
    await h.fixture.whenStable();
    const doc = h.emitted.at(-1)?.['welcome'] as Record<string, unknown>;
    expect(doc['quick_replies']).toEqual(['Hallo', 'Web-Tour starten']);
    expect(doc['tour_reply']).toBe('');
  });
});

describe('SchemaFormComponent — Tour-Chip nur noch an den Startchips (Paket 15)', () => {
  // Nutzer-Rundgang 2026-10-17: das Feld „Tour-Chip“ unter Grundwerte zeigte denselben Wert
  // wie die Radios an den Startchips — zwei Stellen für eine Einstellung.
  it('zeigt das Ziel des Radios nicht noch einmal als eigenes Feld', async () => {
    const h = await mount(WELCOME, { welcome: { quick_replies: ['Hallo'], tour_reply: 'Hallo' } });
    expect(h.el.querySelector('[id$="welcome.tour_reply"]')).toBeNull();
    expect(h.el.querySelector('[id$="welcome.tour_reply_en"]')).toBeNull();
  });

  it('warnt, wenn der gespeicherte Tour-Chip zu keinem Startchip passt', async () => {
    const h = await mount(WELCOME, { welcome: { quick_replies: ['Hallo'], tour_reply: 'Tour!' } });
    const warnung = h.el.querySelector('.sf-marker-warnung');
    expect(warnung?.getAttribute('role')).toBe('note');
    expect(warnung?.textContent).toContain('Tour!');
  });

  it('schweigt, wenn er passt oder leer ist', async () => {
    for (const tour of ['Hallo', '']) {
      const h = await mount(WELCOME, { welcome: { quick_replies: ['Hallo'], tour_reply: tour } });
      expect(h.el.querySelector('.sf-marker-warnung')).toBeNull();
    }
  });
});

describe('SchemaFormComponent — Prüffehler am Feld (ST-2e)', () => {
  const SCHEMA: JsonSchema = {
    type: 'object',
    properties: {
      prozent: { type: 'integer', minimum: 70, maximum: 100 },
      gruppe: { type: 'object', properties: { x: { type: 'string' } } },
    },
  };

  async function mitFehlern(problems: FieldProblem[]): Promise<Harness> {
    const h = await mount(SCHEMA, { prozent: 10, gruppe: { x: 'a' } });
    h.fixture.componentRef.setInput('problems', problems);
    await h.fixture.whenStable();
    return h;
  }

  function beschreibung(el: HTMLElement, control: Element): (string | undefined)[] {
    return (control.getAttribute('aria-describedby') ?? '')
      .split(' ')
      .map((id) => byId(el, id)?.textContent?.trim());
  }

  it('hängt die Meldung an ihr Feld und markiert es als ungültig', async () => {
    const h = await mitFehlern([
      { path: ['prozent'], type: 'greater_than_equal', msg: 'm', ctx: { ge: 70 } },
    ]);
    const feld = inputFor(h.el, 'prozent');
    expect(feld.getAttribute('aria-invalid')).toBe('true');
    expect(beschreibung(h.el, feld).some((t) => t?.includes('Mindestens 70.'))).toBe(true);
  });

  it('hängt die Meldung einer Gruppe unter ihre Überschrift', async () => {
    const h = await mitFehlern([{ path: ['gruppe'], type: 'dict_type', msg: 'm', ctx: {} }]);
    // nicht der erste Rahmen: das ist die Wurzel des Formulars
    const gruppe = Array.from(h.el.querySelectorAll('fieldset.sf-group')).find(
      (f) => f.querySelector(':scope > legend')?.textContent?.includes('gruppe'),
    )!;
    expect(beschreibung(h.el, gruppe).some((t) => t?.includes('Einträge mit Schlüsseln'))).toBe(true);
  });

  it('nennt eine Meldung ohne eigenes Feld über dem Formular', async () => {
    const h = await mitFehlern([{ path: ['gibt_es_nicht'], type: 'missing', msg: 'm', ctx: {} }]);
    expect(h.el.textContent).toContain('gibt_es_nicht: Dieses Feld muss ausgefüllt sein.');
  });

  it('markiert ohne Meldung nichts', async () => {
    const h = await mitFehlern([]);
    expect(inputFor(h.el, 'prozent').getAttribute('aria-invalid')).toBeNull();
  });
});

describe('SchemaFormComponent — Feldtexte aus dem Katalog (ST-1)', () => {
  // Das echte Modell der vier Schichtdokumente — sein Schema trägt die
  // Modellnamen, aus denen die Katalog-Schlüssel entstehen.
  const LAYER_DOC = AREA_SCHEMAS['01-base/base-persona'];

  function labelOf(el: HTMLElement, control: Element): HTMLLabelElement {
    const label = el.querySelector<HTMLLabelElement>(`label[for="${control.id}"]`);
    if (!label) throw new Error(`kein <label for="${control.id}">`);
    return label;
  }

  it('beschriftet ein Feld mit dem Katalogtext und nennt den Schlüssel klein dahinter', async () => {
    const h = await mount(LAYER_DOC, { frontmatter: { version: '4.0.0' }, body: 'x' });
    const t = TestBed.inject(StudioLanguageService).t;
    const control = h.el.querySelector('[id$="frontmatter.version"]')!;
    const label = labelOf(h.el, control);
    expect(label.textContent).toContain(t('feld.LayerDocFrontmatter.version.label'));
    expect(label.querySelector('.sf-key')?.textContent?.trim()).toBe('version');
  });

  it('hängt den Hilfetext an das Feld — sichtbar und für Screenreader verknüpft', async () => {
    const h = await mount(LAYER_DOC, { frontmatter: {}, body: 'x' });
    const t = TestBed.inject(StudioLanguageService).t;
    const control = h.el.querySelector('[id$="frontmatter.priority"]')!;
    const describedBy = control.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(byId(h.el, describedBy!)?.textContent?.trim())
      .toBe(t('feld.LayerDocFrontmatter.priority.hint'));
  });

  it('beschriftet auch Gruppen aus dem Katalog', async () => {
    const h = await mount(LAYER_DOC, { frontmatter: {}, body: 'x' });
    const t = TestBed.inject(StudioLanguageService).t;
    // Seit Paket 15 als Überschrift des Abschnitts (die Legende darunter entfällt) — und als
    // zugänglicher Name der Gruppe.
    const koepfe = Array.from(h.el.querySelectorAll('details.sf-section > summary'))
      .map((s) => s.textContent ?? '');
    expect(koepfe.some((k) => k.includes(t('feld.LayerDocArea.frontmatter.label')))).toBe(true);
    expect(h.el.querySelector('fieldset[aria-label]')?.getAttribute('aria-label'))
      .toContain(t('feld.LayerDocArea.frontmatter.label'));
  });

  it('überschreibt Abschnitte mit der Katalog-Beschriftung, den Schlüssel klein dahinter', async () => {
    const h = await mount(AREA_SCHEMAS['01-base/welcome-config'], { welcome: {} });
    const t = TestBed.inject(StudioLanguageService).t;
    const kopf = Array.from(h.el.querySelectorAll('details.sf-section > summary')).find(
      (s) => s.querySelector('.sf-key')?.textContent?.trim() === 'greeting',
    );
    expect(kopf?.textContent).toContain(t('feld.WelcomeBlock.greeting.label'));
  });

  it('lässt die Hülle der Abschnitte ohne Überschrift — sonst stünde sie über jedem', async () => {
    const h = await mount(AREA_SCHEMAS['01-base/welcome-config'], { welcome: {} });
    const t = TestBed.inject(StudioLanguageService).t;
    const legenden = Array.from(h.el.querySelectorAll('legend')).map((l) => l.textContent?.trim());
    expect(legenden).not.toContain(t('feld.WelcomeArea.welcome.label'));
  });

  it('nennt die Optionen einer Auswahl im Klartext, den Wert dahinter (ST-2d)', async () => {
    const h = await mount(AREA_SCHEMAS['01-base/engine'], { mode: 'pattern' });
    const t = TestBed.inject(StudioLanguageService).t;
    const auswahl = h.el.querySelector<HTMLSelectElement>('select[id$="-mode"]')!;
    const texte = Array.from(auswahl.options).map((o) => o.textContent?.trim());
    expect(texte).toContain(`${t('feld.EngineArea.mode.wahl.pattern')} (pattern)`);
    // der gespeicherte Wert bleibt der Rohwert — nur die Anzeige ist Klartext
    expect(auswahl.value).toBe('pattern');
  });

  it('bleibt ohne Katalogtext beim Rohschlüssel — ohne ihn doppelt zu nennen', async () => {
    const schema: JsonSchema = {
      title: 'OhneTexteModell', type: 'object', properties: { notiz: { type: 'string' } },
    };
    const h = await mount(schema, { notiz: '' });
    const label = labelOf(h.el, h.el.querySelector('[id$="notiz"]')!);
    expect(label.textContent?.trim()).toBe('notiz');
    expect(label.querySelector('.sf-key')).toBeNull();
  });
});

describe('SchemaFormComponent — Liste│Editor für Objekte (ST-3)', () => {
  const OBJEKT: JsonSchema = {
    type: 'object', title: 'Regel',
    properties: { id: { type: 'string' }, label: { type: 'string' } },
  };
  const SCHEMA: JsonSchema = {
    type: 'object',
    properties: {
      regeln: { type: 'array', items: { $ref: '#/$defs/Regel' } },
      karte: { type: 'object', additionalProperties: { $ref: '#/$defs/Regel' } },
      woerter: { type: 'array', items: { type: 'string' } },
    },
    $defs: { Regel: OBJEKT },
  };

  it('zeigt Listen und Maps von Objekten als Liste│Editor, Text-Listen wie bisher', async () => {
    const h = await mount(SCHEMA, {
      regeln: [{ id: 'r1', label: 'Erste' }, { id: 'r2', label: 'Zweite' }],
      karte: { a: { label: 'A' } },
      woerter: ['eins', 'zwei'],
    });
    const listen = h.el.querySelectorAll('studio-object-list');
    expect(listen).toHaveLength(2);
    expect([...listen[0].querySelectorAll('.ol-title')].map((s) => s.textContent?.trim()))
      .toEqual(['Erste', 'Zweite']);
    // nur der gewählte Eintrag steht im Editor, nicht beide untereinander
    expect(listen[0].querySelectorAll('.ol-editor input[id$="label"]')).toHaveLength(1);
    // Text-Listen behalten ihre Zeilen
    expect(h.el.querySelectorAll('.sf-entries')).toHaveLength(1);
  });
});


describe('SchemaFormComponent — Vorgabe oder leer (Paket 4c, B2)', () => {
  // „Nie gesetzt“ (es gilt die Vorgabe) und „leer“ (ausdrücklich keine) sahen
  // gleich aus: „Noch keine Einträge.“ Wer den letzten Wissensbereich eines
  // Musters entfernte, schaltete das Erben ab, ohne es zu sehen (Paket 4, C6).
  const BEREICHE: JsonSchema = {
    type: 'object',
    properties: {
      rag_areas: {
        anyOf: [{ type: 'array', items: { type: 'string', 'x-catalog': 'rag_areas' } },
                { type: 'null' }],
        default: null,
        'x-vorgabe': true,
      },
    },
  };
  const zustand = (el: HTMLElement): HTMLElement | null =>
    el.querySelector<HTMLElement>('.sf-vorgabe [role="status"]');
  const knopf = (el: HTMLElement): HTMLButtonElement =>
    el.querySelector<HTMLButtonElement>('.sf-vorgabe button')!;

  it('sagt „nicht gesetzt“, solange die Vorgabe gilt — und nicht „keine Einträge“', async () => {
    const h = await mount(BEREICHE, { rag_areas: null });
    expect(zustand(h.el)?.textContent).toContain('Nicht gesetzt');
    expect(h.el.textContent).not.toContain('Noch keine Einträge');
    expect(h.el.querySelector('.sf-count')).toBeNull(); // „(0)“ stünde neben „es gilt die Vorgabe“
    expect(knopf(h.el).getAttribute('aria-disabled')).toBe('true');
  });

  it('zeigt die geleerte Liste als leer und bietet die Vorgabe an', async () => {
    const h = await mount(BEREICHE, { rag_areas: [] });
    expect(zustand(h.el)?.textContent).toBe(''); // leer bereit, für die nächste Ansage
    expect(h.el.textContent).toContain('Noch keine Einträge');
    expect(h.el.querySelector('.sf-count')?.textContent).toBe('(0)');
    expect(knopf(h.el).getAttribute('aria-disabled')).toBe('false');
    expect(knopf(h.el).getAttribute('aria-label')).toContain('rag_areas');
  });

  it('stellt die Vorgabe wieder her — und tut nichts, solange sie schon gilt', async () => {
    const h = await mount(BEREICHE, { rag_areas: ['a'] });
    knopf(h.el).click();
    await h.fixture.whenStable();
    // Review 4c: Der Schlüssel fällt weg, statt `null` zu werden. Fehlend liest
    // die Laufzeit als Vorgabe; `sources: null` legte die Musterwahl lahm.
    expect(h.emitted.at(-1)).toEqual({});

    const g = await mount(BEREICHE, { rag_areas: null });
    knopf(g.el).click();
    await g.fixture.whenStable();
    expect(g.emitted).toEqual([]);
  });

  it('bleibt in derselben Region — von gesetzt über leer zurück zur Vorgabe', async () => {
    // Review 4c: Angesagt wird das Zurücksetzen nur, weil die Region bleibt;
    // eine Region, die mit ihrem Text entsteht, sagen Screenreader oft nicht an.
    const h = await mount(BEREICHE, { rag_areas: ['a'] });
    const region = zustand(h.el);
    expect(region?.textContent).toBe('');
    h.el.querySelector<HTMLButtonElement>('.sf-chip-remove')!.click();
    await h.fixture.whenStable();
    expect(h.emitted.at(-1)).toEqual({ rag_areas: [] });
    h.fixture.componentRef.setInput('value', h.emitted.at(-1));
    await h.fixture.whenStable();
    expect(h.el.textContent).toContain('Noch keine Einträge');
    expect(knopf(h.el).getAttribute('aria-disabled')).toBe('false');

    knopf(h.el).click();
    await h.fixture.whenStable();
    h.fixture.componentRef.setInput('value', h.emitted.at(-1));
    await h.fixture.whenStable();
    expect(zustand(h.el)).toBe(region);
    expect(region!.textContent).toContain('Nicht gesetzt');
    expect(knopf(h.el).getAttribute('aria-disabled')).toBe('true');
  });

  it('zeigt nichts davon an Listen ohne den Hinweis', async () => {
    const OHNE: JsonSchema = {
      type: 'object',
      properties: {
        tools: { anyOf: [{ type: 'array', items: { type: 'string' } }, { type: 'null' }], default: null },
      },
    };
    const h = await mount(OHNE, { tools: null });
    expect(h.el.querySelector('.sf-vorgabe')).toBeNull();
    expect(h.el.textContent).toContain('Noch keine Einträge');
  });
});

describe('SchemaFormComponent — Prüffehler in Map-Tabelle und Marker-Ziel (Review-Runde 2)', () => {
  it('hängt die Meldung an den Wert einer Map-Tabelle', async () => {
    const schema: JsonSchema = {
      type: 'object',
      properties: { stufen: { type: 'object', additionalProperties: { type: 'integer' } } },
    };
    const h = await mount(schema, { stufen: { a: 10 } });
    h.fixture.componentRef.setInput('problems', [
      { path: ['stufen', 'a'], type: 'greater_than_equal', msg: 'm', ctx: { ge: 70 } },
    ]);
    await h.fixture.whenStable();
    const feld = byId(h.el, 'sf-stufen-wert-0')!;
    expect(feld.getAttribute('aria-invalid')).toBe('true');
    const ids = (feld.getAttribute('aria-describedby') ?? '').split(' ');
    expect(ids.map((id) => byId(h.el, id)?.textContent ?? '').join(' ')).toContain('Mindestens 70.');
  });

  it('zeigt eine Meldung zum ausgeblendeten Marker-Ziel an der Liste', async () => {
    const h = await mount(WELCOME, { welcome: { quick_replies: ['Hallo'], tour_reply: 'Hallo' } });
    h.fixture.componentRef.setInput('problems', [
      { path: ['welcome', 'tour_reply'], type: 'string_too_long', msg: 'm', ctx: { max_length: 3 } },
    ]);
    await h.fixture.whenStable();
    const liste = Array.from(h.el.querySelectorAll('fieldset.sf-group')).find(
      (f) => f.querySelector(':scope > legend')?.textContent?.includes('quick_replies'))!;
    expect(liste.querySelector('.sf-error')?.textContent).toContain('Tour-Chip:');
    // Review PR #18: die Radios des Markers verweisen auf die Meldung.
    const radio = liste.querySelector<HTMLInputElement>('.sf-marker input')!;
    const ids = (radio.getAttribute('aria-describedby') ?? '').split(' ');
    expect(ids.map((id) => byId(h.el, id)?.textContent ?? '').join(' ')).toContain('Tour-Chip:');
  });
});
