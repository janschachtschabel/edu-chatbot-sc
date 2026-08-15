import { describe, it, expect } from 'vitest';
import { WloCard } from './card-types';
import { isThemenseite, isSammlung, isInhalt, getCardCollectionUrl } from './card-utils';

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

/**
 * Die Klassifikation bleibt disjunkt (oben) — der Sammlungen-KASTEN zeigt
 * seit 15.08.2026 trotzdem auch Themenseiten-Karten, weil eine Sammlung mit
 * kuratierter Themenseite immer noch eine Sammlung ist. Dafür braucht dieser
 * Kasten ein eigenes Ziel: `link` zeigt bei solchen Karten auf die
 * Themenseite, `collection_link` auf die Sammlung.
 */
describe('getCardCollectionUrl', () => {
  const mit = {
    node_type: 'topic_page',
    link: 'https://wirlernenonline.de/themenseite/optik',
    collection_link: 'https://redaktion.openeduhub.net/edu-sharing/components/collections?id=opt1',
  } as unknown as WloCard;

  it('nimmt collection_link, wo es gesetzt ist', () => {
    expect(getCardCollectionUrl(mit)).toBe(
      'https://redaktion.openeduhub.net/edu-sharing/components/collections?id=opt1',
    );
  });

  it('fällt ohne collection_link auf den Hauptlink zurück', () => {
    // Reine Sammlungen: `link` IST schon der Browse-Link. Und alte
    // Antworten aus dem Sitzungs-Verlauf tragen das Feld noch nicht —
    // dort darf der Kasten nicht ins Leere zeigen.
    const ohne = { node_type: 'collection', link: 'https://repo/collections?id=c1' } as unknown as WloCard;
    expect(getCardCollectionUrl(ohne)).toBe('https://repo/collections?id=c1');
  });

  // Die zweite Darstellung einer Themenseite: `node_type: 'collection'` MIT
  // Varianten. Genau die entsteht, wenn Sammlungs- und Themenseitensuche
  // dieselbe node_id liefern — `_build_cards` führt sie zusammen und setzt
  // dabei `node_type = 'collection'` (build.py). Solche Karten tragen KEIN
  // `collection_link`; ihr `link` ist bereits der Browse-Link. Ohne diesen
  // Fall zeigte der Sammlungen-Kasten auf die Themenseite — der Fehler, den
  // dieser Umbau beheben soll, nur in der anderen Darstellung.
  it('nimmt bei node_type collection MIT Varianten den Browse-Link, nicht die Themenseite', () => {
    const zusammengefuehrt = {
      node_type: 'collection',
      link: 'https://repo/edu-sharing/components/collections?id=opt1',
      topic_pages: [{ url: 'https://wirlernenonline.de/themenseite/optik' }],
    } as unknown as WloCard;
    expect(getCardCollectionUrl(zusammengefuehrt)).toBe(
      'https://repo/edu-sharing/components/collections?id=opt1',
    );
  });
});
