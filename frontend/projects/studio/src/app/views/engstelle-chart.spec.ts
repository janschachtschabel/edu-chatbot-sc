import { describe, expect, it } from 'vitest';

import { engstelle } from './engstelle-chart';

const ART = {
  n: 4, ok: 4, p50_s: 6, p95_s: 9,
  zeiten_ms: { llm: 4000, werkzeuge: 1000, vorabsuche: 0, rerank: 2000, rag: 0, safety: 0, rest: 1000 },
  anteile: { llm: 0.5, werkzeuge: 0.125, vorabsuche: 0, rerank: 0.25, rag: 0, safety: 0, rest: 0.125 },
};

describe('engstelle (Paket 16, D4)', () => {
  it('nimmt die Stufe mit der höchsten Parallelität und je Art die Teile in fester Folge', () => {
    const e = engstelle([
      { concurrency: 1, by_kind: { suche: { ...ART, anteile: { llm: 1 } } } },
      { concurrency: 4, by_kind: { suche: ART } },
    ]);
    expect(e?.concurrency).toBe(4);
    const suche = e!.arten[0];
    expect(suche.kind).toBe('suche');
    expect(suche.teile.map((t) => t.kategorie)).toEqual(['llm', 'werkzeuge', 'rerank', 'rest']);
    expect(suche.groesste).toBe('llm');
    expect(suche.teile[2]).toEqual({ kategorie: 'rerank', anteil: 0.25, ms: 2000 });
  });

  it('lässt Arten ohne Aufteilung weg — und ohne jede Aufteilung gibt es keine Engstelle', () => {
    expect(engstelle([{ concurrency: 2, by_kind: { suche: { n: 1, ok: 1, p50_s: 1, p95_s: 1 } } }]))
      .toBeNull();
    expect(engstelle([])).toBeNull();
  });
});
