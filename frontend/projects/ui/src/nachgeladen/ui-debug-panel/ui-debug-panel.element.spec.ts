// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import { DebugInfo, UiInfo } from '../../grouping/message-types';
import { createTranslator } from '../../i18n/dictionary';
import { DE } from '../../i18n/de';
import { EN } from '../../i18n/en';
import { definiere, ELEMENT, UiDebugPanelElement } from './ui-debug-panel.element';

/**
 * Charakterisierung des Debug-Panel-Renderers — visueller Port des ALT Diagnose-Panels
 * (`chat.component.html:422-607`). Seit Paket BU-3 ein nachgeladenes, rahmenloses Element (nur
 * Redaktion und Entwicklung sehen es); dieselben Fälle wie zuvor an der Komponente, gelesen aus dem
 * Shadow Root. Pro Sektion am gerenderten DOM gepinnt, weil das Risiko ein STILL falsch gemapptes
 * Feld ist (undefined statt Wert).
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


let offen: UiDebugPanelElement[] = [];

/** Wie zuvor `render(debug, show, ui, katalog)` — gibt ein Objekt mit `querySelector(All)` und dem
 *  sichtbaren `textContent` des Panels zurück (der Shadow Root trägt zusätzlich das Stilblatt). */
async function render(
  debug: DebugInfo | null, show = true, ui: UiInfo | null = null, katalog = DE,
) {
  definiere();
  const el = document.createElement(ELEMENT) as UiDebugPanelElement;
  el.uebersetzen = createTranslator(katalog, DE);
  el.debug = debug;
  el.ui = ui;
  el.show = show;
  document.body.appendChild(el);
  offen.push(el);
  const wurzel = el.shadowRoot as ShadowRoot;
  return {
    el,
    querySelector: (s: string) => wurzel.querySelector(s),
    querySelectorAll: (s: string) => wurzel.querySelectorAll(s),
    get textContent() { return wurzel.querySelector('.debug-panel')?.textContent ?? ''; },
  };
}

afterEach(() => {
  offen.forEach((e) => e.remove());
  offen = [];
});

describe('ui-debug-panel (Element)', () => {
  it('rendert nichts bei show=false', async () => {
    const host = await render(makeDebug(), false);
    expect(host.querySelector('.debug-panel')).toBeNull();
  });

  it('rendert nichts bei debug=null und ui=null', async () => {
    const host = await render(null, true);
    expect(host.querySelector('.debug-panel')).toBeNull();
  });

  // Paket 18C/D, Phase 4: ohne Freigabe kommt kein Debug-Block — das Panel zeigt, was `ui`
  // trägt, und sagt, wo die Diagnose steht.
  it('ohne debug: Zusammenfassung aus ui und Hinweis aufs Studio', async () => {
    const host = await render(null, true, {
      pattern: 'M06', intent: 'I03', state: 'S3', tools_called: ['search_wlo_content'],
    });
    expect(host.querySelector('.debug-panel')).not.toBeNull();
    const text = host.textContent!;
    expect(text).toContain('steht im Studio');
    expect(text).toContain('Muster');
    expect(text).toContain('M06');
    expect(text).toContain('I03');
    expect(text).toContain('S3');
    expect(text).toContain('search_wlo_content');
    expect(host.querySelectorAll('.debug-section-title').length).toBe(0);
  });

  it('ohne debug: Hinweis und Beschriftungen auf Englisch, wenn Englisch eingestellt ist', async () => {
    const host = await render(null, true, { pattern: 'M06', tools_called: [] }, EN);
    expect(host.textContent).toContain('in the Studio');
    expect(host.textContent).toContain('Tools');
    expect(host.textContent).not.toContain('Werkzeuge');
  });

  it('mit debug bleibt das volle Panel, ohne Hinweis', async () => {
    const host = await render(makeDebug(), true, { pattern: 'M06' });
    expect(host.querySelectorAll('.debug-section-title').length).toBe(6);
    expect(host.textContent).not.toContain('steht im Studio');
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

  // Paket BU-1 (Bündel kleiner): die vier Angular-Pipes sind durch Methoden ersetzt — diese
  // Tests halten die Ausgabe der Pipes fest (Reihenfolge, Stellen, Kürzung, JSON-Form).
  describe('Formate ohne Pipes (BU-1)', () => {
    it('Scores nach Schlüssel sortiert, auf 2 Stellen gerundet und aufgefüllt', async () => {
      const host = await render(makeDebug({ phase2_scores: { M09: 0.4, M06: 0.825, M10: 1234.5 } }));
      const texte = [...host.querySelectorAll('.debug-score')].map((e) => e.textContent?.trim());
      expect(texte).toEqual(['M06=0.83', 'M09=0.40', 'M10=1,234.50']);
    });

    it('Confidence mit 2 Stellen, auch bei 0', async () => {
      expect((await render(makeDebug({ confidence: 0.8 }))).textContent).toContain('Confidence: 0.80');
      expect((await render(makeDebug({ confidence: 0 }))).textContent).toContain('Confidence: 0.00');
      // Review BU-2, NIT 7: was auf Null rundet, trägt wie bei DecimalPipe kein Minus
      expect((await render(makeDebug({ confidence: -0.001 }))).textContent).toContain('Confidence: 0.00');
    });

    it('Entities als eingerücktes JSON', async () => {
      const host = await render(makeDebug({ entities: { fach: 'Physik', n: 2 } }));
      expect(host.querySelector('code')?.textContent).toBe(JSON.stringify({ fach: 'Physik', n: 2 }, null, 2));
    });

    it('Reasoning und Core-Rule gekürzt mit Auslassungszeichen', async () => {
      const host = await render(makeDebug({
        pattern_reasoning: 'r'.repeat(170),
        phase3_modulations: { core_rule: 'c'.repeat(130) },
      }));
      const text = host.textContent ?? '';
      expect(text).toContain(`${'r'.repeat(160)}…`);
      expect(text).not.toContain('r'.repeat(161));
      expect(text).toContain(`${'c'.repeat(120)}…`);
      expect(text).not.toContain('c'.repeat(121));
    });

    it('Cache-Anteil ohne Nachkommastellen, Phasen nach Schlüssel sortiert', async () => {
      const host = await render(makeDebug({
        token_usage: {
          calls: 2, prompt_tokens: 3, completion_tokens: 1, cached_tokens: 2,
          per_phase: {
            tool_loop: { prompt: 3, completion: 1, cached: 1, calls: 1 },
            classify: { prompt: 0, completion: 0, cached: 0, calls: 1 },
          },
        },
      }));
      const text = host.textContent ?? '';
      expect(text).toContain('(67% cache)');
      const phasen = [...host.querySelectorAll('.debug-sub')].map((e) => e.textContent?.replace(/\s+/g, ' ').trim());
      expect(phasen).toEqual(['· classify: prompt=0, cached=0', '· tool_loop: prompt=3, cached=1 (33%)']);
    });
  });
});

describe('ui-debug-panel (Element) — Paket BU-3', () => {
  it('ein zweites Laden des Bündels definiert nicht noch einmal (Element-Vertrag)', () => {
    definiere();
    expect(() => definiere()).not.toThrow();
    expect(customElements.get(ELEMENT)).toBe(UiDebugPanelElement);
  });

  it('jede Zuweisung zeichnet neu: aus wird an, ein neuer Block ersetzt den alten', async () => {
    const host = await render(makeDebug({ pattern: 'M01' }), false);
    expect(host.querySelector('.debug-panel')).toBeNull();
    host.el.show = true;
    expect(host.textContent).toContain('M01');
    host.el.debug = makeDebug({ pattern: 'M09' });
    expect(host.textContent).toContain('M09');
    expect(host.textContent).not.toContain('M01');
  });

  it('Fremdtext bleibt Text (kein HTML aus dem Debug-Block)', async () => {
    const host = await render(makeDebug({ pattern: '<img src=x onerror=alert(1)>' }));
    expect(host.querySelector('img')).toBeNull();
    expect(host.textContent).toContain('<img src=x onerror=alert(1)>');
  });
});

describe('ui-debug-panel (Element) — Review BU-3', () => {
  it('Befund 1: fehlende Werte bleiben leer wie im alten Template — nie „undefined“ oder „null“', async () => {
    const host = await render(makeDebug({
      phase3_modulations: { detail_level: null, tie_breaker: { applied: true } },
      state_transition: { prev: '', next: undefined, plausible: true, reason: '', expected_next_likely: [] },
      safety: { risk_level: undefined } as never,
      outcomes: [{ tool: 'suche' } as never],
      context: {} as never,
      trace: [{ step: 'zeit' } as never],
      token_usage: { calls: 1, per_phase: { classify: {} as never } },
    } as never));
    const text = host.textContent;
    expect(text).toContain('Ton=, Formalität=, Länge=, Detail=');
    expect(text).toContain('Typ=, Format=, Follow-up=, Kacheln=, Max=');
    expect(text).not.toMatch(/undefined|null/);
  });

  it('Befund 4: ein neuer Block lässt die Box stehen (Scroll-Lage bleibt)', async () => {
    const host = await render(makeDebug({ pattern: 'M01' }));
    const box = host.querySelector('.debug-panel') as HTMLElement;
    box.scrollTop = 40;
    host.el.setze({ debug: makeDebug({ pattern: 'M02' }), ui: null, show: true, uebersetzen: host.el.uebersetzen });
    expect(host.querySelector('.debug-panel')).toBe(box);
    expect(host.textContent).toContain('M02');
  });

  it('Befund 6: ein kaputter Block zeigt nichts Falsches und wirft nicht', async () => {
    const host = await render(makeDebug({ pattern: 'M01' }));
    expect(() => { host.el.debug = makeDebug({ outcomes: [null as never] }); }).not.toThrow();
    expect(host.textContent).not.toContain('M01');
  });

  it('Befund 7: die Balken eines parallelen Trace tragen ihren title; der Studio-Hinweis ist eine Notiz', async () => {
    const host = await render(makeDebug({ trace: [{ step: 't', label: 'Tools', duration_ms: 200, data: {
      parallel: true, tasks: [{ name: 'a', label: 'Suche', started_at_ms: 50, duration_ms: 100 }] } }] }));
    expect((host.querySelector('.debug-parallel-task') as HTMLElement).title)
      .toBe('Suche — Start +50ms · Dauer 100ms');
    const ohne = await render(null, true, { pattern: 'M05', tools_called: [] } as never);
    expect(ohne.querySelector('[role="note"]')?.textContent).toContain('Studio');
  });

  it('Kleinigkeit 8: ohne Gesamtdauer keine Balken-Maße (wie zuvor NaN, das der Browser verwarf)', async () => {
    const host = await render(makeDebug({ trace: [{ step: 't', label: 'Tools', data: {
      parallel: true, tasks: [{ name: 'a', label: 'Suche', started_at_ms: 50, duration_ms: 100 }] } } as never] }));
    const balken = host.querySelector('.debug-parallel-task') as HTMLElement;
    expect([balken.style.marginLeft, balken.style.width]).toEqual(['', '']);
  });
});
