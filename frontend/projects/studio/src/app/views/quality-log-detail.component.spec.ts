// @vitest-environment jsdom
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { QualityLogDetailComponent } from './quality-log-detail.component';
import type { QualityLog } from '../core/quality-api.service';

const TURN: QualityLog = {
  id: 7,
  session_id: 'sess-7',
  pattern_id: 'M04',
  intent_id: 'I02 (Wissen)',
  created_at: '2026-07-24T10:00:00Z',
  persona_id: 'P01',
  state_id: 'S3',
  turn_type: 'answer',
  turn_count: 2,
  final_confidence: 0.812,
  pattern_label: 'M04 (Fakten-Bulletin)',
  signals: ['hint', 'entity'],
  entities: { thema: 'Bruchrechnen', stufe: '', fach: null },
  tools_called: ['search_wlo_all'],
  degradation: 0,
  missing_slots: [],
  response_length: 4312,
  cards_count: 3,
  message: 'Was ist Bruchrechnen?',
};

@Component({
  selector: 'studio-detail-host',
  imports: [QualityLogDetailComponent],
  template: '<studio-quality-log-detail [log]="log()" (dismiss)="closed = true" />',
})
class HostComponent {
  readonly log = signal<QualityLog>(TURN);
  closed = false;
}

async function mount(log: QualityLog = TURN) {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(HostComponent);
  fixture.componentInstance.log.set(log);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

describe('QualityLogDetailComponent', () => {
  it('shows the classification of the turn in German units', async () => {
    const h = await mount();
    const text = h.el.textContent!;
    expect(text).toContain('P01');
    expect(text).toContain('S3');
    expect(text).toContain('0,81'); // decimal comma, cut at two places
    expect(text).toContain('4.312'); // thousands grouped the German way
  });

  it('leaves out the two figures that cannot vary', async () => {
    // `phase2_winner_score` is 1.0 and `phase2_score_gap` is 0.0 on every row
    // since Welle E v4 — ALT showed both in this block as if they were measured.
    const h = await mount();
    expect(h.el.textContent).not.toContain('Score-Gap');
    expect(h.el.textContent).not.toContain('Winner');
  });

  it('drops entities whose value is empty instead of printing a blank row', async () => {
    const h = await mount();
    const keys = Array.from(h.el.querySelectorAll('.qd-entities th')).map((t) => t.textContent);
    expect(keys).toEqual(['thema']);
  });

  it('says so when nothing was extracted', async () => {
    const h = await mount({ ...TURN, entities: {} });
    expect(h.el.querySelector('.qd-entities')).toBeNull();
    expect(h.el.textContent).toContain('Keine Entities erkannt');
  });

  it('states a degradation in words and names the missing slots', async () => {
    const h = await mount({ ...TURN, degradation: 1, missing_slots: ['stufe', 'fach'] });
    const line = h.el.querySelector('.qd-degradation')!;
    expect(line.textContent).toContain('Degradation');
    expect(line.textContent).toContain('stufe, fach');
    expect(line.classList.contains('qd-degradation--on')).toBe(true);
  });

  it('says a clean turn was clean rather than showing nothing', async () => {
    const h = await mount();
    expect(h.el.querySelector('.qd-degradation')!.textContent).toContain('Keine Degradation');
  });

  it('can be dismissed', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.qd-close')!.click();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.closed).toBe(true);
  });

  it('survives a turn with no message and no label', async () => {
    const h = await mount({ ...TURN, message: '', pattern_label: '', turn_type: '' });
    expect(h.el.textContent).toContain('(leere Nachricht)');
    expect(h.el.textContent).toContain('Pattern ohne Label');
  });
});
