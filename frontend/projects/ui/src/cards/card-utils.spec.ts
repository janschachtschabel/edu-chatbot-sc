import { describe, it, expect } from 'vitest';
import { WloCard } from './card-types';
import { isThemenseite, isSammlung, isInhalt } from './card-utils';

/**
 * Golden-Master der Drei-Wege-Klassifikation (Themenseite / Sammlung /
 * Inhalt) über alle relevanten ``node_type``-Fälle. Verhalten ist strikt
 * an die (historisch korrekte) chat.component-Referenz gebunden; siehe
 * Regression 2026-06-02 (topic_page → Material-Box). Die identische
 * Matrix läuft in chat.component.spec.ts gegen die Delegatoren.
 */

type TopicPages = WloCard['topic_pages'];

/** Nur die für die Klassifikation relevanten Felder. */
function card(node_type: string, topic_pages?: TopicPages): WloCard {
  return { node_type, topic_pages } as unknown as WloCard;
}

const TP: TopicPages = [
  { url: 'https://x', target_group: 'a', label: 'L', variant_id: 'v1' },
];

/** [Beschreibung, Card, [Themenseite, Sammlung, Inhalt]] */
const CASES: [string, WloCard, [boolean, boolean, boolean]][] = [
  ['topic_page ohne Varianten',       card('topic_page'),            [true,  false, false]],
  ['topic_page mit Varianten',        card('topic_page', TP),        [true,  false, false]],
  ['topic_page mit leerem Array',     card('topic_page', []),        [true,  false, false]],
  ['collection mit Varianten (alt)',  card('collection', TP),        [true,  false, false]],
  ['collection ohne topic_pages',     card('collection'),            [false, true,  false]],
  ['collection mit leerem Array',     card('collection', []),        [false, true,  false]],
  ['content',                         card('content'),               [false, false, true ]],
  ['material',                        card('material', TP),          [false, false, true ]],
  ['leerer node_type',                card(''),                      [false, false, true ]],
];

describe('card-utils Drei-Wege-Klassifikation', () => {
  for (const [name, c, [ts, sa, ih]] of CASES) {
    it(`${name}: [Themenseite=${ts}, Sammlung=${sa}, Inhalt=${ih}]`, () => {
      expect(isThemenseite(c)).toBe(ts);
      expect(isSammlung(c)).toBe(sa);
      expect(isInhalt(c)).toBe(ih);
    });
  }

  it('klassifiziert jede Card in genau eine Kategorie (disjunkt + vollständig)', () => {
    for (const [name, c] of CASES) {
      const hits = [isThemenseite(c), isSammlung(c), isInhalt(c)].filter(Boolean).length;
      expect(hits, name).toBe(1);
    }
  });
});
