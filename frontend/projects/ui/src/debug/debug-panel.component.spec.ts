import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { DebugInfo } from '../grouping/message-types';
import { DebugPanelComponent } from './debug-panel.component';

/**
 * Charakterisierung des Debug-Panel-Renderers — visueller Port des ALT
 * Diagnose-Panels (`chat.component.html:422-607`). In ALT nur integrativ
 * gedeckt; hier pro Sektion am gerenderten DOM gepinnt, weil das Risiko ein
 * STILL falsch gemapptes Feld ist (undefined statt Wert): Gate (show/debug),
 * Kern-Felder der 6 Phasen-Gruppen, State-Übergang-Warnung, Safety-Zeile,
 * Outcomes, Trace linear + parallel (Task-Bars mit Offset/Breite),
 * Phase-2-Scores.
 */
function makeDebug(over: Partial<DebugInfo> = {}): DebugInfo {
  return {
    persona: 'schueler',
    intent: 'suche',
    state: 'exploring',
    turn_type: 'normal',
    signals: [],
    pattern: 'M06',
    entities: {},
    tools_called: [],
    phase1_eliminated: [],
    phase2_scores: {},
    phase3_modulations: {},
    ...over,
  };
}

async function render(debug: DebugInfo | null, show = true): Promise<HTMLElement> {
  const fixture = TestBed.createComponent(DebugPanelComponent);
  fixture.componentRef.setInput('debug', debug);
  fixture.componentRef.setInput('show', show);
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('DebugPanelComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DebugPanelComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('rendert nichts bei show=false', async () => {
    const host = await render(makeDebug(), false);
    expect(host.querySelector('.debug-panel')).toBeNull();
  });

  it('rendert nichts bei debug=null', async () => {
    const host = await render(null, true);
    expect(host.querySelector('.debug-panel')).toBeNull();
  });

  it('rendert das Panel mit den Kern-Feldern der 6 Phasen-Gruppen', async () => {
    const host = await render(
      makeDebug({
        state: 'exploring',
        turn_type: 'normal',
        persona: 'lehrer',
        intent: 'material_suche',
        signals: ['neugier', 'zeitdruck'],
        pattern: 'M06',
        tools_called: ['search_wlo_content', 'get_rag'],
      }),
    );
    expect(host.querySelector('.debug-panel')).not.toBeNull();
    expect(host.querySelectorAll('.debug-section-title').length).toBe(6);
    const text = host.textContent!;
    expect(text).toContain('exploring');
    expect(text).toContain('lehrer');
    expect(text).toContain('material_suche');
    expect(text).toContain('neugier, zeitdruck'); // signals.join(', ')
    expect(text).toContain('M06');
    expect(text).toContain('search_wlo_content, get_rag'); // tools_called.join(', ')
  });

  it('State-Übergang implausibel → Warn-Markierung + erwartete Folge-States', async () => {
    const host = await render(
      makeDebug({
        state_transition: {
          prev: 'greeting',
          next: 'canvas',
          plausible: false,
          reason: '',
          expected_next_likely: ['exploring', 'searching'],
        },
      }),
    );
    expect(host.querySelector('.debug-warn')).not.toBeNull();
    const text = host.textContent!;
    expect(text).toContain('greeting → canvas');
    expect(text).toContain('implausibel');
    expect(text).toContain('exploring, searching');
  });

  it('Safety-Zeile zeigt Risk-Level, Stages, Eskalation und flagged Categories', async () => {
    const host = await render(
      makeDebug({
        safety: {
          risk_level: 'high',
          blocked_tools: [],
          enforced_pattern: '',
          reasons: [],
          stages_run: ['regex', 'moderation'],
          flagged_categories: ['self-harm'],
          escalated: true,
        },
      }),
    );
    const text = host.textContent!;
    expect(text).toContain('Risk=high');
    expect(text).toContain('regex→moderation'); // stages_run.join('→')
    expect(text).toContain('escalated');
    expect(text).toContain('self-harm');
  });

  it('Outcomes → je Tool eine debug-sub-Zeile mit Status/Count/Latenz/Fehler', async () => {
    const host = await render(
      makeDebug({
        outcomes: [
          { tool: 'search_wlo_content', status: 'success', item_count: 5, error: '', latency_ms: 120 },
          { tool: 'get_rag', status: 'error', item_count: 0, error: 'timeout', latency_ms: 900 },
        ],
      }),
    );
    const text = host.textContent!;
    expect(text).toContain('search_wlo_content → success (5 items, 120ms)');
    expect(text).toContain('get_rag → error (0 items, 900ms)');
    expect(text).toContain('– timeout');
    expect(host.querySelectorAll('.debug-sub').length).toBeGreaterThanOrEqual(2);
  });

  it('Trace linear → "[step] label – ms"', async () => {
    const host = await render(
      makeDebug({ trace: [{ step: 'classify', label: 'Klassifikation', duration_ms: 42, data: {} }] }),
    );
    expect(host.textContent).toContain('[classify] Klassifikation – 42ms');
    expect(host.querySelector('.debug-parallel-stack')).toBeNull();
  });

  it('Trace parallel → Header + Task-Bars mit relativem Offset/Breite', async () => {
    const host = await render(
      makeDebug({
        trace: [
          {
            step: 'tools',
            label: 'Tool-Loop',
            duration_ms: 200,
            data: {
              parallel: true,
              tasks: [
                { name: 'a', label: 'Suche', started_at_ms: 0, duration_ms: 100 },
                { name: 'b', label: 'RAG', started_at_ms: 100, duration_ms: 100 },
              ],
            },
          },
        ],
      }),
    );
    expect(host.querySelector('.debug-parallel-stack')).not.toBeNull();
    const tasks = host.querySelectorAll('.debug-parallel-task');
    expect(tasks.length).toBe(2);
    expect(host.textContent).toContain('Tool-Loop');
    // Zweiter Task: Offset = 100/200*100 = 50%, Breite = max(50,2) = 50%.
    expect((tasks[1] as HTMLElement).style.marginLeft).toBe('50%');
    expect((tasks[1] as HTMLElement).style.width).toBe('50%');
  });

  it('Phase-2-Scores → je Score ein debug-score-Span mit 2 Nachkommastellen', async () => {
    const host = await render(makeDebug({ phase2_scores: { M06: 0.82, M09: 0.41 } }));
    const scores = host.querySelectorAll('.debug-score');
    expect(scores.length).toBe(2);
    expect(host.textContent).toContain('M06=0.82');
    expect(host.textContent).toContain('M09=0.41');
  });
});
