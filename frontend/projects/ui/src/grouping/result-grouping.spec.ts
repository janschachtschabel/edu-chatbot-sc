import { describe, expect, it } from 'vitest';

import { WloCard } from '../cards/card-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatMessage, QueryMetaEntry } from './message-types';
import {
  cardTooltip,
  _dedupTake,
  displayContent,
  _groupLimit,
  GroupingContext,
  groupedCollectionCards,
  groupedContentCards,
  groupedContentCardsCount,
  groupedSearchTerm,
  groupedSearchUrl,
  groupedTopicCards,
  groupedWebLinks,
  hasGroupedResults,
  isTourMessage,
  itemTooltip,
  searchCtaTooltip,
} from './result-grouping';

/**
 * Charakterisierung der Result-Grouping-Logik — Verbatim-Port des ALT
 * `chat/result-grouping.utils.ts` (dort keine eigene Spec; integrativ über
 * chat.component.spec.ts gedeckt, die erst mit der Chat-Shell portiert wird).
 * Erwartete Werte aus dem ALT-Quelltext abgeleitet. Die 5-Box-Renderer (8-2h)
 * bauen auf diesen Funktionen auf, daher hier vor dem Konsum gepinnt.
 */
function msg(fields: Partial<ChatMessage>): ChatMessage {
  return fields as unknown as ChatMessage;
}
function card(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}
function meta(fields: Partial<QueryMetaEntry>): QueryMetaEntry {
  return fields as unknown as QueryMetaEntry;
}

/** Deutscher Übersetzer: die Funktionen hier bauen ihre Labels bislang selbst
 *  (das räumt C1-b3 ab); der Kontext trägt ihn schon, damit es EINEN Weg gibt. */
const t = createTranslator(DE, DE);
/** Trusted-Host: keine Extern-Warnung, withBsid identisch. */
const ctx: GroupingContext = { withBsid: (u) => u ?? '', externalLinkWarning: () => '', t };
/** Untrusted-Host: Extern-Warnung für jede URL. */
const ctxWarn: GroupingContext = {
  withBsid: (u) => u ?? '',
  externalLinkWarning: (u) => (u ? 'Achtung! Externe URL.' : ''),
  t,
};

describe('_dedupTake', () => {
  it('dedupt per node_id ODER normalisiertem Titel, Reihenfolge bleibt', () => {
    const cards = [
      card({ node_id: 'a', title: 'Winkel' }),
      card({ node_id: 'a', title: 'Andere' }), // dup node_id
      card({ node_id: 'b', title: '  winkel ' }), // dup Titel (normalisiert)
      card({ node_id: 'c', title: 'Dritte' }),
    ];
    expect(_dedupTake(cards, 10).map((c) => c.node_id)).toEqual(['a', 'c']);
  });

  it('bricht bei Limit ab', () => {
    const cards = [
      card({ node_id: 'a', title: '1' }),
      card({ node_id: 'b', title: '2' }),
      card({ node_id: 'c', title: '3' }),
    ];
    expect(_dedupTake(cards, 2).map((c) => c.node_id)).toEqual(['a', 'b']);
  });
});

describe('_groupLimit', () => {
  it('liest displayRules.groups[key] (Zahl/String), sonst Fallback', () => {
    const m = msg({ displayRules: { groups: { themenseiten_max: 5, sammlungen_max: '4' } } });
    expect(_groupLimit(m, 'themenseiten_max')).toBe(5);
    expect(_groupLimit(m, 'sammlungen_max')).toBe(4);
    expect(_groupLimit(m, 'materialien_max')).toBe(3); // Default-Fallback
    expect(_groupLimit(m, 'materialien_max', 7)).toBe(7); // eigener Fallback
    expect(_groupLimit(msg({}), 'x')).toBe(3); // keine displayRules
  });
});

describe('grouped*Cards', () => {
  const m = msg({
    cards: [
      card({ node_type: 'topic_page', node_id: 't1', title: 'TP1' }),
      card({ node_type: 'collection', node_id: 'c1', title: 'Sammlung1' }),
      card({ node_type: 'content', node_id: 'm1', title: 'Mat1' }),
      card({ node_type: 'content', node_id: 'm2', title: 'Mat2' }),
    ],
  });

  it('trennt nach Klassifikation', () => {
    expect(groupedTopicCards(m).map((c) => c.node_id)).toEqual(['t1']);
    expect(groupedCollectionCards(m).map((c) => c.node_id)).toEqual(['c1']);
    expect(groupedContentCards(m).map((c) => c.node_id)).toEqual(['m1', 'm2']);
    expect(groupedContentCardsCount(m)).toBe(2);
  });

  it('ohne cards → leer', () => {
    expect(groupedTopicCards(msg({}))).toEqual([]);
    expect(groupedContentCardsCount(msg({}))).toBe(0);
  });

  it('n-Parameter überschreibt das displayRules-Limit', () => {
    const lim = msg({
      cards: [
        card({ node_type: 'topic_page', node_id: 'a', title: 'A' }),
        card({ node_type: 'topic_page', node_id: 'b', title: 'B' }),
      ],
      displayRules: { groups: { themenseiten_max: 1 } },
    });
    expect(groupedTopicCards(lim).map((c) => c.node_id)).toEqual(['a']);
    expect(groupedTopicCards(lim, 2).map((c) => c.node_id)).toEqual(['a', 'b']);
  });
});

describe('groupedSearchUrl / groupedSearchTerm', () => {
  it('Tool-Priorität content > collections > topic_pages > erste', () => {
    const m = msg({
      queryMetas: [
        meta({ tool_name: 'search_wlo_topic_pages', search_url: 'https://tp' }),
        meta({ tool_name: 'search_wlo_content', search_url: 'https://content' }),
      ],
    });
    expect(groupedSearchUrl(m, ctx)).toBe('https://content');
  });

  it('keine metas → ""', () => {
    expect(groupedSearchUrl(msg({}), ctx)).toBe('');
  });

  it('Fallback komponiert URL aus repository_url + search_term', () => {
    const m = msg({
      queryMetas: [
        meta({
          tool_name: 'search_wlo_collections',
          search_url: '',
          search_term: 'Klima wandel',
          repository_url: 'https://repo.example/',
        }),
      ],
    });
    expect(groupedSearchUrl(m, ctx)).toBe(
      'https://repo.example/edu-sharing/components/search?query=Klima%20wandel',
    );
  });

  it('term ohne repository_url → "" (kein WP-Redirect)', () => {
    const m = msg({ queryMetas: [meta({ tool_name: 'x', search_term: 'y' })] });
    expect(groupedSearchUrl(m, ctx)).toBe('');
  });

  it('groupedSearchTerm: erster nicht-leerer, getrimmt', () => {
    const m = msg({
      queryMetas: [meta({ search_term: '  ' }), meta({ search_term: ' Mathe ' })],
    });
    expect(groupedSearchTerm(m)).toBe('Mathe');
    expect(groupedSearchTerm(msg({}))).toBe('');
  });
});

describe('groupedWebLinks', () => {
  it('type-focus via debug-Marker → []', () => {
    const m = msg({ debug: { _type_focus: true }, webLinks: [{ title: 'X', url: 'https://x' }] });
    expect(groupedWebLinks(m, ctx)).toEqual([]);
  });

  it('type-focus via content-Pattern → []', () => {
    const m = msg({
      content: 'Für Videos schau in die Suche unten',
      webLinks: [{ title: 'X', url: 'https://x' }],
    });
    expect(groupedWebLinks(m, ctx)).toEqual([]);
  });

  it('strukturiertes webLinks-Feld bevorzugt, Limit 3', () => {
    const m = msg({
      webLinks: [
        { title: 'A', url: 'https://a' },
        { title: 'B', url: 'https://b' },
        { title: 'C', url: 'https://c' },
        { title: 'D', url: 'https://d' },
      ],
    });
    expect(groupedWebLinks(m, ctx)).toEqual([
      { title: 'A', url: 'https://a' },
      { title: 'B', url: 'https://b' },
      { title: 'C', url: 'https://c' },
    ]);
  });

  it('debug._web_links-Fallback (filtert kaputte Einträge)', () => {
    const m = msg({ debug: { _web_links: [{ title: 'W', url: 'https://w' }, { bad: 1 }] } });
    expect(groupedWebLinks(m, ctx)).toEqual([{ title: 'W', url: 'https://w' }]);
  });

  it('Regex-Fallback auf content, Card-URLs ausgeschlossen', () => {
    const m = msg({
      content: 'Siehe [Eins](https://one.example) und [Zwei](https://two.example).',
      cards: [card({ link: 'https://one.example' })],
    });
    expect(groupedWebLinks(m, ctx)).toEqual([{ title: 'Zwei', url: 'https://two.example' }]);
  });
});

describe('displayContent', () => {
  it('inline-result-grouping aus → raw unverändert', () => {
    const m = msg({
      content: '- [A](https://a.example)',
      webLinks: [{ title: 'A', url: 'https://a.example' }],
    });
    expect(displayContent(m, false, ctx)).toBe('- [A](https://a.example)');
  });

  it('strippt promoted Bullet-Links, behält Inline-Links im Satz', () => {
    const m = msg({
      content:
        'Einleitung mit [Inline](https://a.example) Link.\n- [A](https://a.example)\n- [B](https://b.example)\nSchluss.',
      webLinks: [
        { title: 'A', url: 'https://a.example' },
        { title: 'B', url: 'https://b.example' },
      ],
    });
    expect(displayContent(m, true, ctx)).toBe(
      'Einleitung mit [Inline](https://a.example) Link.\nSchluss.',
    );
  });
});

describe('Tooltips', () => {
  it('itemTooltip: Label + Extern-Warnung, null wenn beides leer', () => {
    expect(itemTooltip('Titel', 'https://x', ctxWarn)).toBe('Titel — Achtung! Externe URL.');
    expect(itemTooltip('Titel', 'https://x', ctx)).toBe('Titel');
    expect(itemTooltip('', null, ctx)).toBeNull();
    expect(itemTooltip(null, 'https://x', ctxWarn)).toBe('Achtung! Externe URL.');
  });

  it('cardTooltip: "Titel (Typ)" + Warnung, null-Card → null', () => {
    const c = card({ node_type: 'content', title: 'Photo', learning_resource_types: ['Video'] });
    expect(cardTooltip(c, 'https://x', ctxWarn)).toBe('Photo (Video) — Achtung! Externe URL.');
    expect(cardTooltip(null, 'https://x', ctx)).toBeNull();
  });

  it('searchCtaTooltip: Basis-Text mit Term', () => {
    const m = msg({
      queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s', search_term: 'Mathe' })],
    });
    expect(searchCtaTooltip(m, ctx)).toBe('Alle Treffer in der Suche anzeigen zu „Mathe"');
  });

  it('searchCtaTooltip ohne Term: der Satz ohne Zusatz', () => {
    const m = msg({ queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s' })] });
    expect(searchCtaTooltip(m, ctx)).toBe('Alle Treffer in der Suche anzeigen');
  });

  it('searchCtaTooltip nimmt beide Sätze aus dem Übersetzer (C1-b3)', () => {
    // Zwei ganze Sätze statt Präfix+Suffix: eine andere Sprache stellt den Term
    // womöglich vorne oder in anderer Fügung — Zusammenkleben ginge dort schief.
    const en = createTranslator(
      {
        'groups.ctaTooltip.all': 'Show all search results',
        'groups.ctaTooltip.withTerm': 'Show all results for “{term}”',
      },
      DE,
    );
    const ctxEn: GroupingContext = { ...ctx, t: en };
    const mitTerm = msg({
      queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s', search_term: 'Mathe' })],
    });
    const ohneTerm = msg({ queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s' })] });
    expect(searchCtaTooltip(mitTerm, ctxEn)).toBe('Show all results for “Mathe”');
    expect(searchCtaTooltip(ohneTerm, ctxEn)).toBe('Show all search results');
  });
});

describe('isTourMessage / hasGroupedResults', () => {
  it('isTourMessage: debug.pattern TOUR:*', () => {
    expect(isTourMessage(msg({ debug: { pattern: 'TOUR:step1' } }))).toBe(true);
    expect(isTourMessage(msg({ debug: { pattern: 'M06' } }))).toBe(false);
    expect(isTourMessage(msg({}))).toBe(false);
  });

  it('hasGroupedResults: Tour unterdrückt alles', () => {
    const m = msg({
      debug: { pattern: 'TOUR:x' },
      cards: [card({ node_type: 'topic_page', node_id: 'a', title: 'A' })],
    });
    expect(hasGroupedResults(m, ctx)).toBe(false);
  });

  it('hasGroupedResults: Themenseiten-Karten → true, leer → false', () => {
    const withTopic = msg({ cards: [card({ node_type: 'topic_page', node_id: 'a', title: 'A' })] });
    expect(hasGroupedResults(withTopic, ctx)).toBe(true);
    expect(hasGroupedResults(msg({}), ctx)).toBe(false);
  });

  it('hasGroupedResults: nur Search-CTA (type-focus) zählt als sichtbar', () => {
    const m = msg({
      queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s', search_term: 'x' })],
    });
    expect(hasGroupedResults(m, ctx)).toBe(true);
  });
});
