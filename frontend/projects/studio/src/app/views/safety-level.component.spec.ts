// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { SafetyLevelComponent } from './safety-level.component';

const DOC = {
  security_level: 'standard',
  presets: {
    off: { moderation: 'never' },
    regex: { moderation: 'never' },
    standard: { moderation: 'smart' },
    strict: { moderation: 'always' },
    paranoid: { moderation: 'always' },
  },
  extra_crisis_terms: ['ein ungepinnter Nachbar'],
};

async function mount(
  doc: Record<string, unknown> = DOC,
  locale: 'de' | 'en' = 'de',
): Promise<{
  fixture: ComponentFixture<SafetyLevelComponent>;
  el: HTMLElement;
  emitted: Record<string, unknown>[];
}> {
  // jsdom meldet `navigator.language === 'en-US'`; ohne diese Festlegung stünde
  // die Oberfläche in den deutschen Erwartungen unten auf Englisch.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(SafetyLevelComponent);
  const emitted: Record<string, unknown>[] = [];
  fixture.componentRef.setInput('doc', doc);
  fixture.componentInstance.docChange.subscribe((next) => emitted.push(next));
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, emitted };
}

function radios(el: HTMLElement): HTMLInputElement[] {
  return Array.from(el.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
}

describe('SafetyLevelComponent', () => {
  it('offers the five levels as ONE radio group', async () => {
    // A group of buttons has no selected state a screen reader can report and
    // no arrow-key navigation; radios give both without any ARIA of our own.
    const { el } = await mount();
    const names = new Set(radios(el).map((r) => r.name));
    expect(names.size).toBe(1);
    expect(radios(el).map((r) => r.value)).toEqual([
      'off', 'regex', 'standard', 'strict', 'paranoid',
    ]);
  });

  it('shows the level the document actually carries', async () => {
    const { el } = await mount({ ...DOC, security_level: 'strict' });
    expect(radios(el).find((r) => r.checked)?.value).toBe('strict');
  });

  it('treats the historical "basic" as "standard", like the safety service does', async () => {
    const { el } = await mount({ ...DOC, security_level: 'basic' });
    expect(radios(el).find((r) => r.checked)?.value).toBe('standard');
  });

  it('emits the WHOLE document with only the level changed', async () => {
    // Emitting `{security_level}` alone would delete presets and every key
    // beside them the moment the section saves.
    const { el, emitted } = await mount();
    const strict = radios(el).find((r) => r.value === 'strict');
    strict!.checked = true;
    strict!.dispatchEvent(new Event('change'));

    expect(emitted).toHaveLength(1);
    expect(emitted[0]).toEqual({ ...DOC, security_level: 'strict' });
  });

  it('does not save by itself — the section that owns the document does', async () => {
    const { el, emitted } = await mount();
    radios(el).find((r) => r.value === 'off')!.dispatchEvent(new Event('change'));
    // the only effect is the emitted document; no request, no status of its own
    expect(emitted).toHaveLength(1);
    expect(el.querySelector('button')).toBeNull();
  });

  it('says so when a level has no preset in this document', async () => {
    // Picking it does not fail — the safety service falls back to the legacy
    // escalation block — but nothing on screen would have said so.
    const { el } = await mount({ security_level: 'standard', presets: { standard: {} } });
    const missing = el.querySelectorAll('.sl-missing');
    expect(missing.length).toBe(4);
    expect(el.textContent).toContain('Kein Preset in dieser Datei hinterlegt');
  });

  it('lists a preset the document defines beyond the known five', async () => {
    const { el } = await mount({
      security_level: 'hausintern',
      presets: { ...DOC.presets, hausintern: { moderation: 'always' } },
    });
    const values = radios(el).map((r) => r.value);
    expect(values).toContain('hausintern');
    expect(radios(el).find((r) => r.checked)?.value).toBe('hausintern');
    // Der Name bleibt der Schlüssel aus der Datei; beschrieben wird er als das,
    // was er ist — und diese Beschreibung ist ein Satz, also übersetzt.
    expect(el.textContent).toContain('Eigenes Preset aus dieser Datei.');
  });

  it('beschriftet Legende und Beschreibungen in der aktiven Sprache', async () => {
    const { el } = await mount(DOC, 'en');
    expect(el.textContent).toContain('Safety level');
    expect(el.textContent).toContain('Regex + OpenAI moderation');
    expect(el.textContent).not.toContain('Empfohlen');
    // Die Namen der Stufen sind die Schlüssel aus der Datei und bleiben stehen.
    expect(radios(el).map((r) => r.value)).toEqual([
      'off', 'regex', 'standard', 'strict', 'paranoid',
    ]);
  });

  it('sagt auch auf Englisch, dass eine Stufe kein Preset hat', async () => {
    const { el } = await mount({ security_level: 'standard', presets: { standard: {} } }, 'en');
    expect(el.textContent).toContain('No preset in this file');
    expect(el.textContent).not.toContain('hinterlegt');
  });

  it('survives a document that has no presets block at all', async () => {
    const { el } = await mount({ security_level: 'regex' });
    expect(radios(el)).toHaveLength(5);
    expect(radios(el).find((r) => r.checked)?.value).toBe('regex');
  });
});
