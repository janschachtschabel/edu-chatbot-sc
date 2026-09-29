import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { Translate } from '../i18n/studio-language.service';
import { readTokens, readTrace, stopReasonLabel } from './agent-trace';

const übersetzer = (locale: 'de' | 'en'): Translate => {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  return (key, params) => i18n.t(key, params);
};

/** Zwei Runden und das Ende, wie `agent_trace.spur` sie schreibt, dazu die
 *  Skill-Zeile aus `turn_persist` (AG-5). */
const SPUR: readonly unknown[] = [
  {
    step: 'agent_round', label: 'Runde 1: search_wlo_content', duration_ms: 1200,
    data: {
      runde: 1, dauer_ms: 1200, prompt_tokens: 3000, cached_tokens: 2800, completion_tokens: 40,
      werkzeuge: [{ name: 'search_wlo_content', argumente: ['maxItems', 'query'] }],
    },
  },
  {
    step: 'agent_round', label: 'Runde 2: ohne Werkzeug', duration_ms: 2300,
    data: {
      runde: 2, dauer_ms: 2300, prompt_tokens: 3500, cached_tokens: 3000,
      completion_tokens: 210, werkzeuge: [],
    },
  },
  {
    step: 'agent_stop', label: 'Ende: text', duration_ms: 3500,
    data: { stop_reason: 'text', runden: 2 },
  },
  { step: 'skill', label: 'Quiz erstellen', data: { node_id: 'abc-1', titel: 'Quiz erstellen' } },
];

describe('readTrace (ST-8a)', () => {
  it('liest je Runde die Werkzeuge mit Argument-Namen, Dauer und Token', () => {
    expect(readTrace(SPUR).rounds).toEqual([
      {
        round: 1, durationMs: 1200, promptTokens: 3000, cachedTokens: 2800,
        completionTokens: 40, tools: [{ name: 'search_wlo_content', args: ['maxItems', 'query'] }],
      },
      {
        round: 2, durationMs: 2300, promptTokens: 3500, cachedTokens: 3000,
        completionTokens: 210, tools: [],
      },
    ]);
  });

  it('liest das Ende mit Grund, Rundenzahl und Gesamtdauer', () => {
    expect(readTrace(SPUR).stop).toEqual({ reason: 'text', rounds: 2, durationMs: 3500 });
  });

  it('nennt die geholte Anleitung mit Titel und Knoten', () => {
    expect(readTrace(SPUR).skills).toEqual([{ title: 'Quiz erstellen', nodeId: 'abc-1' }]);
  });

  it('nennt eine Anleitung ohne Titel bei ihrem Knoten', () => {
    const { skills } = readTrace([
      { step: 'skill', label: 'abc-2', data: { node_id: 'abc-2', titel: '' } },
    ]);
    expect(skills).toEqual([{ title: 'abc-2', nodeId: 'abc-2' }]);
  });

  it('gibt für einen Zug ohne Spur leere Teile zurück', () => {
    const leer = { rounds: [], stop: null, skills: [] };
    expect(readTrace([])).toEqual(leer);
    expect(readTrace(undefined)).toEqual(leer);
    expect(readTrace({ step: 'agent_round' })).toEqual(leer);
  });

  // Der Debug-Block ist gespeichertes JSON, auch aus älteren Ständen: eine Zeile
  // ohne `data`, ein Text statt einer Zahl oder eine fremde Stufe darf die
  // Ansicht nicht umwerfen — und keine Zahl erfinden.
  it('übersteht unvollständige und fremde Zeilen', () => {
    const { rounds, stop, skills } = readTrace([
      { step: 'agent_round', label: 'Runde ?' },
      { step: 'agent_round', data: { runde: 'zwei', dauer_ms: 'lang', werkzeuge: 'x' } },
      { step: 'agent_round', data: { werkzeuge: [{ name: 7 }, null, { name: 'get_skill' }] } },
      { step: 'agent_round', data: { runde: 4, prompt_tokens: -5, completion_tokens: Number.NaN } },
      { step: 'classify', label: 'fremd', data: {} },
      'kaputt',
      null,
      { step: 'skill', data: {} },
      { step: 'agent_stop', data: {} },
    ]);
    expect(rounds.map((r) => r.round)).toEqual([1, 2, 3, 4]);
    expect(rounds[1]).toMatchObject({ durationMs: 0, promptTokens: 0, tools: [] });
    expect(rounds[2].tools).toEqual([{ name: 'get_skill', args: [] }]);
    expect(rounds[3]).toMatchObject({ promptTokens: 0, completionTokens: 0 });
    expect(stop).toEqual({ reason: '', rounds: 4, durationMs: 0 });
    expect(skills).toEqual([]);
  });
});

describe('readTokens (ST-8a)', () => {
  it('liest Eingabe, davon gecacht, und Ausgabe des Zugs', () => {
    expect(readTokens({
      prompt_tokens: 6500, cached_tokens: 5800, completion_tokens: 250, calls: 2,
    })).toEqual({ prompt: 6500, cached: 5800, completion: 250 });
  });

  it('setzt einen fehlenden Cache-Wert auf null Token', () => {
    expect(readTokens({ prompt_tokens: 900, completion_tokens: 80 }))
      .toEqual({ prompt: 900, cached: 0, completion: 80 });
  });

  it('gibt nichts zurück, wo der Zug nichts gebucht hat', () => {
    expect(readTokens({})).toBeNull();
    expect(readTokens(undefined)).toBeNull();
    expect(readTokens('viel')).toBeNull();
    expect(readTokens({ prompt_tokens: 0, completion_tokens: 0 })).toBeNull();
  });
});

describe('stopReasonLabel (ST-8a)', () => {
  // Die Ende-Gründe von `agent_loop` und der Schutz-Stopp des Auftrags-Endpunkts.
  const GRUENDE = [
    'text', 'submit', 'deadline', 'token_budget', 'max_iterations',
    'no_progress', 'empty', 'error', 'safety',
  ];

  it('übersetzt jeden bekannten Grund in beiden Sprachen', () => {
    const de = übersetzer('de');
    const en = übersetzer('en');
    for (const grund of GRUENDE) {
      expect(stopReasonLabel(grund, de)).not.toContain('trace.stop');
      expect(stopReasonLabel(grund, en)).not.toContain('trace.stop');
      expect(stopReasonLabel(grund, de)).not.toBe(stopReasonLabel(grund, en));
    }
    expect(stopReasonLabel('deadline', de)).toBe('Frist erreicht');
    expect(stopReasonLabel('deadline', en)).toBe('Deadline reached');
  });

  it('zeigt einen fremden Grund roh — auch einen Namen vom Objekt-Prototyp', () => {
    const de = übersetzer('de');
    expect(stopReasonLabel('warp', de)).toBe('warp');
    expect(stopReasonLabel('toString', de)).toBe('toString');
  });
});
