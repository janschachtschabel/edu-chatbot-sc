// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import type { JsonSchema } from './json-schema';
import { SchemaFormComponent } from './schema-form.component';

/**
 * Vorgaben im Formular (Paket 15, A3): Ein Schlüssel, der im Dokument fehlt, zeigt die
 * Schema-Vorgabe — den Wert, den der Server nimmt — als „Vorgabe“ gekennzeichnet. Vorher
 * stand ein fehlender Schalter mit Vorgabe „an“ als aus da (RAG für den Agenten), und eine
 * fehlende Liste als leer (Schutzregeln): wer eine Regel ergänzte, ersetzte die vier still.
 */
const SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    agent: { type: 'boolean', default: true },
    max: { type: 'integer', default: 5 },
    host: { type: 'string', default: '' },
    regeln: { type: 'array', items: { type: 'string' }, default: ['R-05', 'R-08'] },
    rolle: { $ref: '#/$defs/Rolle', default: { text: 'Du hilfst.', stufe: 2 } },
  },
  $defs: {
    Rolle: {
      type: 'object',
      title: 'Rolle',
      properties: {
        text: { type: 'string', default: 'Du hilfst.' },
        stufe: { type: 'integer', default: 2 },
      },
    },
  },
};

interface Harness {
  fixture: ComponentFixture<SchemaFormComponent>;
  el: HTMLElement;
  emitted: Record<string, unknown>[];
}

async function mount(value: Record<string, unknown>, schema: JsonSchema = SCHEMA): Promise<Harness> {
  TestBed.resetTestingModule();
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

const byId = <T extends HTMLElement>(el: HTMLElement, id: string) =>
  el.querySelector<T>(`[id="${id}"]`)!;
const zeileVon = (el: HTMLElement, id: string) => byId(el, id).closest('.sf-row')!;

describe('SchemaFormComponent — Vorgaben (Paket 15, A3)', () => {
  it('zeigt einen fehlenden Schalter und eine fehlende Zahl mit ihrer Vorgabe', async () => {
    const { el, emitted } = await mount({});
    expect(byId<HTMLInputElement>(el, 'sf-agent').checked).toBe(true);
    expect(byId<HTMLInputElement>(el, 'sf-max').value).toBe('5');
    expect(zeileVon(el, 'sf-agent').textContent).toContain('Vorgabe');
    // Nur anzeigen, nicht schreiben: ohne Änderung bleibt das Dokument, wie es ist.
    expect(emitted).toEqual([]);
  });

  it('ein gespeicherter Wert trägt keine Vorgabe-Marke', async () => {
    const { el } = await mount({ agent: true });
    expect(zeileVon(el, 'sf-agent').textContent).not.toContain('Vorgabe');
  });

  it('eine Änderung schreibt den Wert', async () => {
    const { el, fixture, emitted } = await mount({});
    const schalter = byId<HTMLInputElement>(el, 'sf-agent');
    schalter.checked = false;
    schalter.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ agent: false });
  });

  it('„Auf Vorgabe zurück“ entfernt einen abweichenden Wert wieder', async () => {
    const { el, fixture, emitted } = await mount({ max: 9 });
    const zurueck = zeileVon(el, 'sf-max').querySelector<HTMLButtonElement>('.sf-zurueck')!;
    expect(zurueck.textContent?.trim()).toBe('Auf Vorgabe zurück');
    zurueck.click();
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({});
  });

  it('zeigt eine fehlende Liste mit ihrer Vorgabe; Ergänzen behält die Vorgabe-Einträge', async () => {
    const { el, fixture, emitted } = await mount({});
    expect(byId<HTMLInputElement>(el, 'sf-regeln.0').value).toBe('R-05');
    expect(byId<HTMLInputElement>(el, 'sf-regeln.1').value).toBe('R-08');
    Array.from(el.querySelectorAll<HTMLButtonElement>('.sf-add'))
      .find((b) => b.getAttribute('aria-label')?.includes('regeln'))!.click();
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ regeln: ['R-05', 'R-08', ''] });
  });

  it('Entfernen aus einer Vorgabe-Liste schreibt den Rest', async () => {
    const { el, fixture, emitted } = await mount({});
    Array.from(el.querySelectorAll<HTMLButtonElement>('.sf-remove'))[0].click();
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ regeln: ['R-08'] });
  });

  it('eine Änderung in einer fehlenden Gruppe schreibt nur das Feld, wenn die Gruppe den Kindern folgt', async () => {
    // Review Paket 15, #3: sonst fröre ein Schalter alle Geschwister auf ihrer heutigen Vorgabe ein.
    const { el, fixture, emitted } = await mount({});
    expect(byId<HTMLInputElement>(el, 'sf-rolle.text').value).toBe('Du hilfst.');
    const text = byId<HTMLInputElement>(el, 'sf-rolle.text');
    text.value = 'Du hilfst freundlich.';
    text.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ rolle: { text: 'Du hilfst freundlich.' } });
  });

  it('eine Gruppe mit eigener Vorgabe (Fabrik) wird beim ersten Ändern ganz geschrieben', async () => {
    // Die Gruppen-Vorgabe weicht von den Kindern ab: ohne sie fiele `stufe` auf 2 statt 4.
    const { el, fixture, emitted } = await mount({}, {
      ...SCHEMA,
      properties: { ...SCHEMA.properties,
        rolle: { $ref: '#/$defs/Rolle', default: { text: 'Du hilfst.', stufe: 4 } } },
    });
    const text = byId<HTMLInputElement>(el, 'sf-rolle.text');
    text.value = 'Neu';
    text.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ rolle: { text: 'Neu', stufe: 4 } });
  });

  it('schweigt bei leerer Vorgabe und bei Schaltern — sonst stünde der Knopf unter jedem Feld', async () => {
    // Browser-Abnahme Paket 15: jede ausgefüllte Adresse trug „Auf Vorgabe zurück“ (Vorgabe '').
    const { el } = await mount({ host: 'https://wlo.example', agent: false });
    expect(zeileVon(el, 'sf-host').querySelector('.sf-zurueck')).toBeNull();
    expect(zeileVon(el, 'sf-agent').querySelector('.sf-zurueck')).toBeNull();
    const leer = await mount({});
    expect(zeileVon(leer.el, 'sf-host').textContent).not.toContain('Vorgabe');
  });
});

describe('SchemaFormComponent — Zurücksetzen (Review Paket 15, #4)', () => {
  it('räumt Entwurf und Fehler eines JSON-Felds, auch wenn sein Wert gleich bleibt', async () => {
    // Das Feld zeigt die Vorgabe `{}` — nach „Verwerfen“ wieder dieselbe, das Feld sah keinen
    // neuen Wert, und der ungültige Entwurf samt Fehler blieb stehen.
    const { el, fixture } = await mount({}, {
      type: 'object', properties: { effect: { type: 'object', default: {} } },
    });
    const feld = byId<HTMLTextAreaElement>(el, 'sf-effect');
    feld.value = '{kaputt';
    feld.dispatchEvent(new Event('input'));
    feld.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(el.querySelector('.sf-error')?.textContent?.trim()).not.toBe('');

    fixture.componentRef.setInput('epoche', 1);
    await fixture.whenStable();
    expect(el.querySelector('.sf-error')?.textContent?.trim()).toBe('');
    expect(byId<HTMLTextAreaElement>(el, 'sf-effect').value).toBe('{}');
  });
});

/** Review-Runde 2 (R2-1, R2-8, R2-9): eine Gruppe fehlt im Dokument, ihre Vorgabe folgt den
 *  Kindern — darunter eine Liste und eine Map mit eigener Vorgabe. */
const GRUPPE: JsonSchema = {
  type: 'object',
  properties: {
    rolle: {
      $ref: '#/$defs/Rolle',
      default: { text: 'Du hilfst.', regeln: ['R-05', 'R-08'], stufen: { a: 1, b: 2 } },
    },
  },
  $defs: {
    Rolle: {
      type: 'object',
      title: 'Rolle',
      properties: {
        text: { type: 'string', default: 'Du hilfst.' },
        regeln: { type: 'array', items: { type: 'string' }, default: ['R-05', 'R-08'] },
        stufen: { type: 'object', additionalProperties: { type: 'integer' },
          default: { a: 1, b: 2 } },
      },
    },
  },
};

describe('SchemaFormComponent — Vorgaben unter einer fehlenden Gruppe (Review-Runde 2)', () => {
  it('Entfernen aus einer Vorgabe-Liste in der Gruppe schreibt den Rest', async () => {
    const { el, fixture, emitted } = await mount({}, GRUPPE);
    Array.from(el.querySelectorAll<HTMLButtonElement>('.sf-remove'))
      .find((b) => b.getAttribute('aria-label')?.includes('regeln'))!.click();
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ rolle: { regeln: ['R-08'] } });
  });

  it('eine Änderung in einer Vorgabe-Map der Gruppe behält die Geschwister', async () => {
    const { el, fixture, emitted } = await mount({}, GRUPPE);
    const wert = el.querySelector<HTMLInputElement>('[id="sf-rolle.stufen-wert-0"]')!;
    wert.value = '5';
    wert.dispatchEvent(new Event('input'));
    wert.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ rolle: { stufen: { a: 5, b: 2 } } });
  });

  it('zeigt die Plakette „Vorgabe“ auch an Kindern und Listen einer fehlenden Gruppe', async () => {
    const { el } = await mount({}, GRUPPE);
    expect(zeileVon(el, 'sf-rolle.text').textContent).toContain('Vorgabe');
    const liste = Array.from(el.querySelectorAll('legend'))
      .find((l) => l.textContent?.includes('regeln'))!;
    expect(liste.textContent).toContain('Vorgabe');
  });

  it('im Ausschnitt zählen die vollen Kinder: nur das geänderte Feld wird geschrieben', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    const emitted: Record<string, unknown>[] = [];
    fixture.componentRef.setInput('schema', GRUPPE);
    fixture.componentRef.setInput('value', {});
    fixture.componentRef.setInput('visiblePaths', ['rolle.text']);
    fixture.componentInstance.valueChange.subscribe((next) => emitted.push(next));
    await fixture.whenStable();
    const text = byId<HTMLInputElement>(fixture.nativeElement as HTMLElement, 'sf-rolle.text');
    text.value = 'Neu';
    text.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(emitted.at(-1)).toEqual({ rolle: { text: 'Neu' } });
  });
});
