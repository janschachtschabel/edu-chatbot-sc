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

  it('Sammlung MIT Filter (q) und sort-JSON → collection, q ist Filter und keine Suche', () => {
    // Echte Staging-Adresse aus der Nutzer-Anforderung 2026-08-11 („Geometrische
    // Optik"). Sie trägt DREI Signale gleichzeitig: `q=Optik` sieht aus wie eine
    // Suche, `id` ist die Sammlung, `sort` ein JSON-Blob. Stünde der generische
    // `?q`-Zweig vor dem Sammlungs-Zweig, läse der Bot hier eine Suche und
    // verlöre die Sammlung — samt ihrer Metadaten und ihrer Kontext-Chips.
    const r = detect(
      `${STAGING}/components/collections`
      + '?sort=%7B%22active%22:%22cm:modified%22,%22direction%22:%22desc%22%7D'
      + '&q=Optik&id=f35c17d1-a29e-4b26-9d22-802682fad43d&scope=TYPE_EDITORIAL',
    );
    expect(r.page_kind).toBe('collection');
    expect(r.collection_id).toBe('f35c17d1-a29e-4b26-9d22-802682fad43d');
    expect(r.search_query).toBe('Optik');
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

describe('page-context-detector: Seitenkontext-Erweiterung — Host und Adresse', () => {
  // Der Erkenner sah bislang nie den Hostnamen an. Eigene Startseite und fremde
  // Webseite landeten beide auf `other` — die Unterscheidung, an der das
  // Erschliessungs-Angebot hängt, gab es nicht. Entschieden wird sie im
  // Backend gegen eine redaktionell gepflegte Liste; das Widget liefert nur
  // den Hostnamen. Die volle Adresse reist mit, weil M20 ohne sie nichts
  // erschliessen kann — und weil `page_text` (bis 1500 Zeichen sichtbarer
  // Seitentext) ohnehin schon mitgeht, wäre ihr Zurückhalten kein Datenschutz.

  it('page_host ist der blosse Hostname — ohne Schema, Port und Pfad', () => {
    const r = detect('https://beispiel.org:8443/ein/pfad?q=x#frag');
    expect(r.page_host).toBe('beispiel.org');
  });

  it('page_url ist die volle Adresse — sonst findet der Dublettencheck die falsche Seite', () => {
    const url = 'https://beispiel.org/artikel?id=42';
    expect(detect(url).page_url).toBe(url);
  });

  it('beides steht auch an der echten Staging-Sammlung', () => {
    const r = detect(`${STAGING}/components/collections?id=94f22c9b-0d3a-4c1c-8987-4c8e83f3a92e`);
    expect(r.page_host).toBe('repository.staging.openeduhub.net');
    expect(r.page_url).toContain('94f22c9b-0d3a-4c1c-8987-4c8e83f3a92e');
    // Die Seitenart bleibt unberührt — der Host entscheidet nur, was der
    // URL-Erkenner NICHT einordnen konnte.
    expect(r.page_kind).toBe('collection');
  });
});

describe('page-context-detector: T6 Host-Agnostik (staging === prod)', () => {
  const paths = [
    'components/render/e4640668-f482-4c6a-9998-eec0c1bdde3e',
    'components/collections?id=94f22c9b-0d3a-4c1c-8987-4c8e83f3a92e',
    'components/topic-pages?collectionId=05ec7229-4f72-4244-ac72-294f72e2442c',
    'components/search?q=Kartoffel',
  ];

  /** Alles ausser den bewusst hostabhängigen Feldern. Die Aussage dieses
   *  Blocks ist „die EINORDNUNG hängt nicht am Host" — `page_host`/`page_url`
   *  unterscheiden sich zwischen Staging und Produktion natürlich, das ist ihr
   *  ganzer Zweck. Sie hier mitzuvergleichen prüfte das Gegenteil. */
  function classification(url: string) {
    const { page_host, page_url, ...rest } = detect(url);
    return rest;
  }

  for (const p of paths) {
    it(`identische Einordnung für staging und prod: ${p}`, () => {
      expect(classification(`${STAGING}/${p}`)).toEqual(classification(`${PROD}/${p}`));
    });

    it(`Host und Adresse folgen dagegen dem Ursprung: ${p}`, () => {
      expect(detect(`${STAGING}/${p}`).page_host).toBe('repository.staging.openeduhub.net');
      expect(detect(`${PROD}/${p}`).page_host).toBe('redaktion.openeduhub.net');
    });
  }
});

describe('page-context-detector: Nicht-Web-Herkünfte', () => {
  /**
   * Befund der Plugin-Entwickler (2026-08-14): in der Seitenleiste einer
   * Chrome-Erweiterung läuft das Widget unter
   * `chrome-extension://<id>/sidebar/index.html`. Der Detektor nahm die
   * Erweiterungs-Kennung als Hostnamen, und der Bot sagte der Person:
   * „Du bist auf dcchajcmmghejkhjmllhnmaggocmmjck — das gehört nicht zu WLO."
   *
   * Darüber lässt sich nichts aussagen: die Adresse bezeichnet die Erweiterung
   * selbst, nicht das, was die Person ansieht. Ohne Host und Adresse bleibt der
   * Kontext leer — und was der Gastgeber per `page-context` /
   * `replaceContext()` mitgibt, steht dann allein da, statt gegen eine
   * erfundene Seite anzukommen.
   */
  const fremd = [
    'chrome-extension://dcchajcmmghejkhjmllhnmaggocmmjck/sidebar/index.html',
    'moz-extension://a1b2c3d4-0000-0000-0000-000000000000/panel.html',
    'file:///C:/tmp/test.html',
    'about:blank',
  ];

  for (const u of fremd) {
    it(`kein Host, keine Adresse: ${u}`, () => {
      const r = detect(u);
      expect(r.page_host).toBeUndefined();
      expect(r.page_url).toBeUndefined();
      expect(r.page_kind).toBeUndefined();
    });
  }

  it('http bleibt unangetastet — auch ohne bekanntes Muster', () => {
    // Gegenprobe: eine gewöhnliche fremde Webseite SOLL erkannt werden, dafür
    // gibt es M20 („Seite für den Bestand vorschlagen").
    const r = detect('http://beispiel.test/irgendwas');
    expect(r.page_host).toBe('beispiel.test');
    expect(r.page_url).toBe('http://beispiel.test/irgendwas');
  });
});
