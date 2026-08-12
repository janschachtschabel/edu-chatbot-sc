import { describe, it, expect } from 'vitest';
import { ICONS } from '../icons/icons';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { WloCard } from './card-types';
import { getCardIcon, getCardPrimaryUrl, getContentTypeLabel } from './card-utils';

/** Deutscher Übersetzer — pinnt den bisherigen Wortlaut über den Katalog. */
const t = createTranslator(DE, DE);

/**
 * Charakterisierung der Render-Helfer (Link/Icon/Label) — in ALT über die
 * große chat.component.spec.ts gepinnt (Integration), die erst mit dem Tile
 * (8-2f) portiert wird. Hier vorgezogen, weil der Tile diese drei Funktionen
 * direkt konsumiert und der geklickte Primary-Link + die Box-Zuordnung
 * user-sichtbar sind. Verhalten aus ALT `services/card-utils.ts` abgeleitet.
 */

function makeCard(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}

const TP = [{ url: 'https://themenseite.example/x', target_group: 'a', label: 'L', variant_id: 'v1' }];

describe('getCardPrimaryUrl: Fallback-Kette', () => {
  it('Themenseiten-Card: topic_pages[0].url schlägt link', () => {
    const c = makeCard({ topic_pages: TP, link: 'https://link.example', node_type: 'topic_page' });
    expect(getCardPrimaryUrl(c)).toBe('https://themenseite.example/x');
  });

  it('ohne topic_pages: link bevorzugt', () => {
    const c = makeCard({
      topic_pages: [], link: 'https://link.example',
      guide_url: 'https://guide.example', wlo_url: 'https://wlo.example', url: 'https://ext.example',
    });
    expect(getCardPrimaryUrl(c)).toBe('https://link.example');
  });

  it('ohne link: guide_url → wlo_url → url in dieser Reihenfolge', () => {
    expect(getCardPrimaryUrl(makeCard({ guide_url: 'https://g', wlo_url: 'https://w', url: 'https://u' }))).toBe('https://g');
    expect(getCardPrimaryUrl(makeCard({ wlo_url: 'https://w', url: 'https://u' }))).toBe('https://w');
    expect(getCardPrimaryUrl(makeCard({ url: 'https://u' }))).toBe('https://u');
  });

  it('keine URL / null / undefined → "#"', () => {
    expect(getCardPrimaryUrl(makeCard({ node_type: 'content' }))).toBe('#');
    expect(getCardPrimaryUrl(null)).toBe('#');
    expect(getCardPrimaryUrl(undefined)).toBe('#');
  });
});

describe('getContentTypeLabel', () => {
  it('Themenseite und Sammlung feste Labels', () => {
    expect(getContentTypeLabel(makeCard({ node_type: 'topic_page' }), t)).toBe('Themenseite');
    expect(getContentTypeLabel(makeCard({ node_type: 'collection' }), t)).toBe('Sammlung');
  });

  it('Einzelinhalt: erster learning_resource_type, "Sammlung"/"collection" herausgefiltert', () => {
    expect(getContentTypeLabel(makeCard({ node_type: 'content', learning_resource_types: ['Video'] }), t)).toBe('Video');
    expect(getContentTypeLabel(makeCard({ node_type: 'content', learning_resource_types: ['Sammlung', 'Arbeitsblatt'] }), t)).toBe('Arbeitsblatt');
    expect(getContentTypeLabel(makeCard({ node_type: 'content', learning_resource_types: [] }), t)).toBe('Inhalt');
  });

  it('nimmt die festen Labels aus dem Übersetzer (C1-b3)', () => {
    const en = createTranslator(
      { 'contentType.topicPage': 'Topic page', 'contentType.collection': 'Collection', 'contentType.fallback': 'Content' },
      DE,
    );
    expect(getContentTypeLabel(makeCard({ node_type: 'topic_page' }), en)).toBe('Topic page');
    expect(getContentTypeLabel(makeCard({ node_type: 'collection' }), en)).toBe('Collection');
    expect(getContentTypeLabel(makeCard({ node_type: 'content', learning_resource_types: [] }), en)).toBe('Content');
  });

  it('der Backend-Typ bleibt unübersetzt — er ist Inhalt, kein Oberflächentext', () => {
    const en = createTranslator({ Video: 'Movie' }, DE);
    expect(getContentTypeLabel(makeCard({ node_type: 'content', learning_resource_types: ['Video'] }), en)).toBe('Video');
  });
});

describe('getCardIcon: Typ → Material-Symbol', () => {
  it('Themenseite/Sammlung eigene Icons', () => {
    expect(getCardIcon(makeCard({ node_type: 'topic_page' }))).toBe(ICONS.topic);
    expect(getCardIcon(makeCard({ node_type: 'collection' }))).toBe(ICONS.auto_stories);
  });

  it('Inhaltstyp-Mapping (Video) + Fallback menu_book', () => {
    expect(getCardIcon(makeCard({ node_type: 'content', learning_resource_types: ['Erklärvideo'] }))).toBe(ICONS.play_circle);
    expect(getCardIcon(makeCard({ node_type: 'content', learning_resource_types: [] }))).toBe(ICONS.menu_book);
  });
});
