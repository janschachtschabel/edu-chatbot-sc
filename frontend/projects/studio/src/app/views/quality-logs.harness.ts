/**
 * Shared setup for the two log-panel specs.
 *
 * Test-only module, not a suite. The panel has one harness but two reasons to
 * change — reading (filters, list, detail) and mutating (delete, bulk clear) —
 * so the tests live in two files and the scaffolding in one.
 */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { QualityLogsComponent } from './quality-logs.component';
import type { LogFilters, QualityScope } from '../core/quality-api.service';

export const LOGS_URL = '/studio/api/quality/logs';
export const CLEAR_URL = '/studio/api/quality/logs/clear';

export function log(id: number, over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id,
    session_id: `sess-${id}`,
    pattern_id: 'M04',
    intent_id: 'I02',
    created_at: '2026-07-24T10:00:00Z',
    persona_id: 'P01',
    state_id: 'S3',
    turn_type: 'answer',
    turn_count: 2,
    final_confidence: 0.81,
    pattern_label: 'M04 (Fakten-Bulletin)',
    signals: ['hint'],
    entities: { thema: 'Bruchrechnen' },
    tools_called: ['search_wlo_all'],
    degradation: 0,
    missing_slots: [],
    response_length: 431,
    cards_count: 3,
    message: 'Was ist Bruchrechnen?',
    ...over,
  };
}

export const PAGE = { count: 2, logs: [log(1), log(2, { degradation: 1, pattern_id: 'M15' })] };

@Component({
  selector: 'studio-logs-host',
  imports: [QualityLogsComponent],
  template: `<studio-quality-logs
    [scope]="scope()"
    [filters]="filters()"
    (filtersChange)="filters.set($event)"
  />`,
})
export class HostComponent {
  readonly scope = signal<QualityScope>('all');
  readonly filters = signal<LogFilters>({});
}

export interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

export async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

/** A fixture with no answer flushed yet — for asserting on the first request. */
export async function bare(): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  return h;
}

export async function mount(page: object = PAGE): Promise<Harness> {
  const h = await bare();
  h.http.expectOne((r) => r.url === LOGS_URL).flush(page);
  await settle(h);
  return h;
}

export const rows = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>('.ql-row'));

export function type(h: Harness, id: string, value: string): void {
  const input = h.el.querySelector<HTMLInputElement>(id)!;
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

export async function submit(h: Harness): Promise<void> {
  h.el.querySelector('form')!.dispatchEvent(new Event('submit'));
  await h.fixture.whenStable();
}
