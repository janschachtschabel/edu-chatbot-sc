import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import { STUDIO_VIEWS } from '../studio-views';
import {
  LAYER_CARDS, OPS_CARDS, type ElementCounts, elementCounts, figureText, viewOf, visibleTags,
} from './overview-cards';

const COUNTS: ElementCounts = {
  patterns: 16, personas: 6, intents: 8, states: 3, entities: 5, signals: 17,
};

function translator(locale: 'de' | 'en'): I18n['t'] {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  return (key, params) => i18n.t(key, params);
}

const de = translator('de');

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
    // Seit C1-d2 sind es Katalog-Schlüssel; der Wortlaut hängt an der Sprache
    // und ist in `i18n/views-i18n.spec.ts` festgehalten.
    const view = viewOf('analyse');
    expect(view.labelKey).toBe('view.analyse.label');
    expect(view.descKey).toBe('view.analyse.desc');
  });

  it('nennt nur Katalog-Schlüssel, die es in beiden Sprachen gibt', () => {
    // C1-d4a. Ein Tippfehler im Schlüssel bliebe sonst unsichtbar, bis jemand
    // die Startseite öffnet und den Schlüssel als Überschrift liest.
    const keys = LAYER_CARDS.flatMap((card) => [
      card.headlineKey, card.primary.key, ...card.tags.map((tag) => tag.key),
    ]);
    expect(keys.filter((key) => !(key in STUDIO_DE)), 'fehlt auf Deutsch').toEqual([]);
    expect(keys.filter((key) => !(key in STUDIO_EN)), 'fehlt auf Englisch').toEqual([]);
  });

  it('meldet je Text genau die Zählungen an, die er als Platzhalter führt', () => {
    // Eine Karte, die `{states}` schreibt aber `states` nicht anmeldet, zeigte
    // den Platzhalter roh; eine, die zu viel anmeldet, verschwände ohne Not,
    // solange die Zahlen noch nicht da sind.
    for (const card of LAYER_CARDS) {
      for (const figure of [card.primary, ...card.tags]) {
        const genannt = [...STUDIO_DE[figure.key].matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
        expect([...figure.counts].sort(), figure.key).toEqual(genannt.sort());
      }
    }
  });
});

describe('layer figures', () => {
  const layer = (num: number) => LAYER_CARDS.find((c) => c.num === num)!;
  const primary = (num: number, counts: ElementCounts | null, t = de) =>
    figureText(layer(num).primary, counts, t);

  it('counts the live elements once they have arrived', () => {
    expect(primary(3, COUNTS)).toBe('16 Patterns');
    expect(primary(4, COUNTS)).toBe('6 Personas · 8 Intents');
    expect(visibleTags(layer(4), COUNTS, de)).toContain('3 States');
    expect(visibleTags(layer(4), COUNTS, de)).toContain('17 Signale');
  });

  it('claims no figure while the counts are still missing', () => {
    // ALT filled the gap with `?? 16`, `?? 6`, `?? 8`, `?? 3`, `?? 5`, `?? 17`
    // (HomeOverview.tsx:128-133), so the first paint stated six counts nobody
    // had measured — and they stayed if the request failed.
    expect(primary(3, null)).toBe('');
    expect(primary(4, null)).toBe('');
    expect(visibleTags(layer(4), null, de)).toEqual(['Turn-Count', 'Tonalitäts-Modifier']);
  });

  it('keeps the figures a layer does not read from the backend', () => {
    // The 18 material types are not in /config/elements, so they cannot be
    // measured here; the number is checked into the card with its source.
    expect(primary(5, null)).toBe('18 Material-Typen');
    expect(primary(1, null)).toBe('Persona · Guardrails · Safety · Policy');
  });

  it('setzt die Zahl dorthin, wo die jeweilige Sprache sie erwartet', () => {
    // Bis C1-d4a stand `${counts.patterns} Patterns` im Code — die deutsche
    // Wortstellung, fest verdrahtet. Der Platzhalter gibt sie der Sprache
    // zurück; dass beide sie hier gleich setzen, ist ein Befund, keine Annahme.
    const en = translator('en');
    expect(primary(3, COUNTS, en)).toBe('16 patterns');
    expect(figureText(layer(6).primary, null, en)).toBe('RAG + MCP tools');
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
