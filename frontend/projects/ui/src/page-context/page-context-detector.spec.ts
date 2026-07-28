import { describe, it, expect } from 'vitest';
import { _detectFromUrl } from './page-context-detector';

/**
 * URL-Klassifikation des Page-Context-Detectors. jsdom kann nicht navigieren
 * (siehe widget.component.spec.ts), daher wird die reine URL-Logik
 * ``_detectFromUrl(URL)`` direkt geprüft. Golden-Cases sind die realen
 * Staging-URLs aus der Nutzer-Anforderung (docs/plans/2026-07-10-…).
 */

const STAGING = 'https://repository.staging.openeduhub.net/edu-sharing';
const PROD = 'https://redaktion.openeduhub.net/edu-sharing';

function detect(url: string) {
  return _detectFromUrl(new URL(url));
}

describe('page-context-detector: Bestandsmuster (Regression)', () => {
  it('Einzelinhalt /components/render/<uuid> → content', () => {
    const r = detect(`${STAGING}/components/render/e4640668-f482-4c6a-9998-eec0c1bdde3e`);
    expect(r.node_id).toBe('e4640668-f482-4c6a-9998-eec0c1bdde3e');
    expect(r.page_kind).toBe('content');
  });

  it('Sammlung /components/collections?id=<uuid> → collection', () => {
    const r = detect(`${STAGING}/components/collections?id=94f22c9b-0d3a-4c1c-8987-4c8e83f3a92e&scope=TYPE_EDITORIAL`);
    expect(r.collection_id).toBe('94f22c9b-0d3a-4c1c-8987-4c8e83f3a92e');
    expect(r.page_kind).toBe('collection');
  });

  it('Themenseite-Slug /themenseite/<slug> → topic', () => {
    const r = detect(`${STAGING}/themenseite/klimawandel`);
    expect(r.topic_page_slug).toBe('klimawandel');
    expect(r.page_kind).toBe('topic');
  });

  it('Fachportal /fachportal/<subject> → subject', () => {
    const r = detect(`${STAGING}/fachportal/physik`);
    expect(r.subject_slug).toBe('physik');
    expect(r.page_kind).toBe('subject');
  });
});

describe('page-context-detector: T4 edu-sharing Themenseite /components/topic-pages', () => {
  it('topic-pages?collectionId=<uuid> → topic (nicht collection), bsid ignoriert', () => {
    const r = detect(
      `${STAGING}/components/topic-pages?collectionId=05ec7229-4f72-4244-ac72-294f72e2442c&bsid=bb-84c0a780-2a4f-4ebd-af07-02ba9a141826`,
    );
    expect(r.collection_id).toBe('05ec7229-4f72-4244-ac72-294f72e2442c');
    expect(r.page_kind).toBe('topic');
    expect(r.detection_source).toBe('url:/components/topic-pages');
  });

  it('darf NICHT mehr als collection erkannt werden (früherer generischer ?collectionId-Fang)', () => {
    const r = detect(`${STAGING}/components/topic-pages?collectionId=05ec7229-4f72-4244-ac72-294f72e2442c`);
    expect(r.page_kind).not.toBe('collection');
  });
});

describe('page-context-detector: T5 Suche /components/search + filters', () => {
  it('bare /components/search (ohne q) → search', () => {
    const r = detect(`${STAGING}/components/search`);
    expect(r.page_kind).toBe('search');
  });

  it('/components/search?q=Kartoffel → search_query', () => {
    const r = detect(`${STAGING}/components/search?sort=%7B%22active%22%3A%22cm%3Amodified%22%7D&q=Kartoffel`);
    expect(r.search_query).toBe('Kartoffel');
    expect(r.page_kind).toBe('search');
  });

  it('filters=…publisher…Serlo → search_filters.publisher', () => {
    const url = `${STAGING}/components/search?q=Kartoffel&filters=%7B%22ccm%3Aoeh_publisher_combined%22%3A%5B%22Serlo%22%5D%7D`;
    const r = detect(url);
    expect(r.search_query).toBe('Kartoffel');
    expect(r.search_filters).toEqual({ publisher: ['Serlo'] });
  });

  it('kaputtes filters-JSON → kein search_filters, kein Throw', () => {
    const r = detect(`${STAGING}/components/search?q=x&filters=%7Bnot-json`);
    expect(r.page_kind).toBe('search');
    expect(r.search_filters).toBeUndefined();
  });
});

describe('page-context-detector: T6 Host-Agnostik (staging === prod)', () => {
  const paths = [
    'components/render/e4640668-f482-4c6a-9998-eec0c1bdde3e',
    'components/collections?id=94f22c9b-0d3a-4c1c-8987-4c8e83f3a92e',
    'components/topic-pages?collectionId=05ec7229-4f72-4244-ac72-294f72e2442c',
    'components/search?q=Kartoffel',
  ];
  for (const p of paths) {
    it(`identische Felder für staging und prod: ${p}`, () => {
      expect(detect(`${STAGING}/${p}`)).toEqual(detect(`${PROD}/${p}`));
    });
  }
});
