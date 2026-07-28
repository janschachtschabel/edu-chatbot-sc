import { describe, expect, it } from 'vitest';

import { STUDIO_VIEWS } from '../studio-views';
import {
  LAYER_CARDS, OPS_CARDS, type ElementCounts, elementCounts, viewOf,
} from './overview-cards';

const COUNTS: ElementCounts = {
  patterns: 16, personas: 6, intents: 8, states: 3, entities: 5, signals: 17,
};

describe('overview cards', () => {
  it('has the six architecture layers and the six operations cards', () => {
    expect(LAYER_CARDS.map((c) => c.num)).toEqual([1, 2, 3, 4, 5, 6]);
    // Five from ALT plus "Sicherung" (9-6), which ALT reached from a header
    // button and from its quick-access row — this page has cards instead.
    expect(OPS_CARDS).toHaveLength(6);
    expect(OPS_CARDS.map((c) => c.slug)).toContain('sicherung');
  });

  it('points every card at a view that exists', () => {
    // The whole reason routes and nav are derived from STUDIO_VIEWS: a card
    // linking to a slug nobody serves is a dead end on the studio's front page.
    const slugs = new Set(STUDIO_VIEWS.map((v) => v.slug));
    for (const card of [...LAYER_CARDS, ...OPS_CARDS]) {
      expect(slugs, `card -> ${card.slug}`).toContain(card.slug);
    }
  });

  it('takes label and description from the view registry, not from a copy', () => {
    const view = viewOf('analyse');
    expect(view.label).toBe('Analyse');
    expect(view.desc).toBe('Pattern-/Intent-Verteilung, Diagnose');
  });
});

describe('layer figures', () => {
  const layer = (num: number) => LAYER_CARDS.find((c) => c.num === num)!;

  it('counts the live elements once they have arrived', () => {
    expect(layer(3).primary(COUNTS)).toBe('16 Patterns');
    expect(layer(4).primary(COUNTS)).toBe('6 Personas · 8 Intents');
    expect(layer(4).tags(COUNTS)).toContain('3 States');
    expect(layer(4).tags(COUNTS)).toContain('17 Signale');
  });

  it('claims no figure while the counts are still missing', () => {
    // ALT filled the gap with `?? 16`, `?? 6`, `?? 8`, `?? 3`, `?? 5`, `?? 17`
    // (HomeOverview.tsx:128-133), so the first paint stated six counts nobody
    // had measured — and they stayed if the request failed.
    expect(layer(3).primary(null)).toBe('');
    expect(layer(4).primary(null)).toBe('');
    expect(layer(4).tags(null)).toEqual(['Turn-Count', 'Tonalitäts-Modifier']);
  });

  it('keeps the figures a layer does not read from the backend', () => {
    // The 18 material types are not in /config/elements, so they cannot be
    // measured here; the number is checked into the card with its source.
    expect(layer(5).primary(null)).toBe('18 Material-Typen');
    expect(layer(1).primary(null)).toBe('Persona · Guardrails · Safety · Policy');
  });
});

describe('elementCounts', () => {
  it('reads the six list lengths out of the elements payload', () => {
    expect(elementCounts({
      patterns: [{ id: 'M01' }, { id: 'M02' }], personas: [{ id: 'P-LEH' }],
      intents: [], states: [], entities: [], signals: [{ id: 's' }],
    })).toEqual({
      patterns: 2, personas: 1, intents: 0, states: 0, entities: 0, signals: 1,
    });
  });

  it('is null without a payload, so the cards stay silent', () => {
    expect(elementCounts(null)).toBeNull();
    expect(elementCounts(undefined)).toBeNull();
  });
});
