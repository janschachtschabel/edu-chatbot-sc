// @vitest-environment jsdom
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalPatternPanelsComponent } from './eval-pattern-panels.component';

const NBSP = ' ';

const GOLD_MUSTER: Record<string, unknown> = {
  judged_turns: 41,
  pattern_match_score_distribution: { 0: 0, 1: 3, 2: 38 },
  engine_pattern_judge_ok_rate: 0.927,
  llm_engine_match_rate: 1,
  llm_hint_present_count: 39,
  tool_compliance_rate: 0.85,
  tool_compliance_total: 20,
  persona_correct_rate: null,
  persona_total_judged: 0,
  intent_correct_rate: null,
  intent_total_judged: 0,
  persona_confusion: {},
  intent_confusion: {},
  pattern_confusion_llm_vs_engine: { M04: { M04: 11, M05: 1 }, M06: { M06: 10 } },
  tool_compliance_per_pattern: { M06: { ok: 10, total: 10 }, M10: { ok: 0, total: 3 } },
};

@Component({
  selector: 'studio-panels-host',
  imports: [EvalPatternPanelsComponent],
  template: '<studio-eval-pattern-panels [metrics]="metrics()" />',
})
class HostComponent {
  readonly metrics = signal<Record<string, unknown>>(GOLD_MUSTER);
}

let f: ComponentFixture<HostComponent>;

async function mount(locale = 'de'): Promise<HTMLElement> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  f = TestBed.createComponent(HostComponent);
  await f.whenStable();
  return f.nativeElement as HTMLElement;
}

const kpi = (el: HTMLElement, name: string): string =>
  Array.from(el.querySelectorAll('.pp-kpis > div'))
    .find((d) => d.querySelector('dt')?.textContent?.trim() === name)
    ?.querySelector('dd')?.textContent?.trim() ?? '';

describe('EvalPatternPanelsComponent (ST-7d)', () => {
  it('liegt zugeklappt unter „Muster-Tafeln"', async () => {
    const el = await mount();
    const aufklapper = el.querySelector('details.pp')!;
    expect(aufklapper.querySelector('summary')?.textContent).toContain('Muster-Tafeln');
    expect((aufklapper as HTMLDetailsElement).open).toBe(false);
  });

  it('nennt jede Kennzahl mit ihrer Basis, Ungemessenes als solches', async () => {
    const el = await mount();
    expect(kpi(el, 'Muster-Trefferquote'))
      .toBe(`100${NBSP}% (41 Züge) · davon voll passend: 93${NBSP}%`);
    expect(kpi(el, 'Hinweis = Endwahl')).toBe(`100${NBSP}% (39 Züge)`);
    expect(kpi(el, 'Werkzeugtreue')).toBe(`85${NBSP}% (20 Züge)`);
    expect(kpi(el, 'Persona-Trefferquote')).toBe('nicht gemessen');
  });

  it('zeigt nur Konfusionsmatrizen, in denen etwas gezählt wurde', async () => {
    const el = await mount();
    const tafeln = el.querySelectorAll('table.pp-matrix');
    expect(tafeln).toHaveLength(1);
    expect(tafeln[0].querySelector('caption')?.textContent).toContain('LLM-Hinweis');
    const erste = tafeln[0].querySelectorAll('tbody tr')[0].querySelectorAll('td');
    expect(Array.from(erste).map((td) => td.textContent?.trim())).toEqual(['11', '1', '0']);
    expect(erste[0].classList).toContain('pp-hit');
    expect(erste[1].classList).toContain('pp-miss');
    expect(erste[2].classList).toContain('pp-zero');
  });

  it('nennt die Werkzeugtreue je Muster, die schwächsten nicht versteckt', async () => {
    const el = await mount();
    const zeilen = Array.from(el.querySelectorAll('table.pp-tools tbody tr'))
      .map((tr) => Array.from(tr.children).map((zelle) => zelle.textContent?.trim()).join(' | '));
    expect(zeilen).toEqual([`M06 | 10 / 10 | 100${NBSP}%`, `M10 | 0 / 3 | 0${NBSP}%`]);
  });

  it('spricht Englisch', async () => {
    const el = await mount('en');
    expect(el.querySelector('summary')?.textContent).toContain('Pattern panels');
    expect(kpi(el, 'Persona hit rate')).toBe('not measured');
    expect(el.textContent).not.toMatch(/[äöüß]/);
  });
});
