// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { Messbedingungen } from '../core/eval-auswertung';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalMessbedingungenComponent } from './eval-messbedingungen.component';

/**
 * Messbedingungen eines Laufs (Paket 13, F2): womit er maß — und, beim Aufklappen, was sich
 * gegenüber dem vorigen Lauf derselben Maschine änderte (Wechselmarken der Trends).
 */
const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

const MB: Messbedingungen = {
  maschine: 'agent',
  weg: { anbieter: 'openai', modell: 'gpt-6-luna', api: 'responses', reasoning_effort: 'low' },
  judge_weg: { anbieter: 'openai', modell: 'gpt-6-luna', api: 'responses' },
  app: { version: '0.4', commit: 'abc1234' },
  konfiguration: { hash: 'k0nf1g' },
  gold_flows: { hash: 'g0ld', ids: ['A', 'B'] },
  master_skill: { enabled: true, sha256: 'abcdef1234567890' },
};

describe('EvalMessbedingungenComponent (Paket 13, F2)', () => {
  let fixture: ComponentFixture<EvalMessbedingungenComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    fixture = TestBed.createComponent(EvalMessbedingungenComponent);
    fixture.componentRef.setInput('mb', MB);
    fixture.componentRef.setInput('fassung', 'f4ssung');
    fixture.componentRef.setInput('runId', 'r2');
    fixture.componentRef.setInput('engine', 'agent');
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
    http = TestBed.inject(HttpTestingController);
  });

  async function aufklappen(): Promise<void> {
    const details = el.querySelector('details')!;
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await fixture.whenStable();
  }

  it('nennt Maschine, Weg, Judge samt Fassung und die Stände', () => {
    const text = el.textContent ?? '';
    expect(text).toContain('Agent-Schleife');
    expect(text).toContain('openai · gpt-6-luna · responses · reasoning_effort=low');
    expect(text).toContain('f4ssung');
    for (const stand of ['0.4', 'abc1234', 'k0nf1g', 'g0ld', 'abcdef123456']) {
      expect(text).toContain(stand);
    }
  });

  it('fragt erst beim Aufklappen nach Änderungen — und nur einmal', async () => {
    http.expectNone((r) => r.url.endsWith('/eval/trends'));
    await aufklappen();
    const req = http.expectOne((r) => r.url.endsWith('/eval/trends'));
    expect(req.request.params.get('engine')).toBe('agent');
    req.flush({ runs: [{ id: 'r1' }, { id: 'r2' }], v2: { wechsel: [
      { run_id: 'r2', created_at: 'x', felder: ['modell', 'konfiguration'], prompts: ['agent.kopf'] },
    ] } });
    await tick();
    await fixture.whenStable();
    const liste = el.querySelector('.emb-wechsel')!.textContent ?? '';
    expect(liste).toContain('Chat-Modell');
    expect(liste).toContain('Konfiguration');
    expect(liste).toContain('agent.kopf');

    await aufklappen();
    http.expectNone((r) => r.url.endsWith('/eval/trends'));
  });

  it('sagt, wenn sich nichts änderte', async () => {
    await aufklappen();
    http.expectOne((r) => r.url.endsWith('/eval/trends')).flush({ runs: [{ id: 'r1' }, { id: 'r2' }], v2: { wechsel: [] } });
    await tick();
    await fixture.whenStable();
    expect(el.querySelector('.emb-wechsel')?.textContent)
      .toContain('Keine Änderung gegenüber dem vorigen Lauf');
  });

  it('sagt ehrlich, wenn der vorige Lauf außerhalb des Verlaufs liegt oder es keinen gibt', async () => {
    await aufklappen();
    http.expectOne((r) => r.url.endsWith('/eval/trends')).flush({ runs: [], v2: { wechsel: [] } });
    await tick();
    await fixture.whenStable();
    expect(el.querySelector('.emb-wechsel')?.textContent).toContain('außerhalb');
  });
});
