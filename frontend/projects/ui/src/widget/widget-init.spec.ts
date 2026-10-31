// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { computeInitialExpanded, resolveMergedPageContext } from './widget-init';

/**
 * Charakterisierung der Widget-Bootstrap-Entscheidungen. Übernimmt die ALT-Blöcke
 * „WidgetComponent ngOnInit Open-Entscheidung" und „ngOnInit Page-Context-Merge"
 * (widget.component.spec.ts:235-349) — dort über die Komponente gefahren, hier
 * direkt gegen die beiden Funktionen, weil sie in ALT schon extrahiert sind.
 *
 * Boundaries echt: jsdom-`localStorage`/`history`/`document`. Kein Netzwerk.
 */
const VALID_SID = 'bb-6f9619ff-8b86-4d01-b42d-00cf4fc964ff';

describe('computeInitialExpanded', () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState({}, '', '/');
  });
  afterEach(() => localStorage.clear());

  it('initial-state="expanded" startet offen, "collapsed" zu', () => {
    expect(computeInitialExpanded('expanded')).toBe(true);
    expect(computeInitialExpanded('collapsed')).toBe(false);
  });

  it('?bsid= öffnet automatisch NUR bei gültiger Session-ID (C9)', () => {
    history.replaceState({}, '', '/?bsid=irgendwas');
    expect(computeInitialExpanded('collapsed')).toBe(false);
    history.replaceState({}, '', `/?bsid=${VALID_SID}`);
    expect(computeInitialExpanded('collapsed')).toBe(true);
  });

  it('aktive Web-Tour (localStorage="1") öffnet automatisch, "0" nicht', () => {
    localStorage.setItem('boerdi_tour_active', '1');
    expect(computeInitialExpanded('collapsed')).toBe(true);
    localStorage.setItem('boerdi_tour_active', '0');
    expect(computeInitialExpanded('collapsed')).toBe(false);
  });
});

describe('resolveMergedPageContext', () => {
  beforeEach(() => history.replaceState({}, '', '/'));

  it('autoContext: path/query + widget-Marker + Detector-Felder (page_kind)', () => {
    const ctx = resolveMergedPageContext(true, '');
    expect(ctx['path']).toBe('/');
    expect(ctx['widget']).toBe(true);
    expect(ctx['page_kind']).toBe('other');  // Detector auf leerer jsdom-Seite
  });

  it('autoContext="false": nur widget-Marker + manueller Kontext', () => {
    expect(resolveMergedPageContext('false', '{"thema":"eiszeit"}'))
      .toEqual({ widget: true, thema: 'eiszeit' });
  });

  it('manueller JSON-Kontext kann den widget-Marker NICHT kippen (C10)', () => {
    expect(resolveMergedPageContext('false', '{"widget": false}')['widget']).toBe(true);
  });

  it('unparsebarer JSON-String landet als raw; Objekt-Input wird gemerged', () => {
    expect(resolveMergedPageContext('false', 'kein json{')['raw']).toBe('kein json{');
    expect(resolveMergedPageContext('false', { fach: 'mathe' })['fach']).toBe('mathe');
  });

  // Paket 19, Audit 2026-10-31 N-1: `auto-context` schickte ALLE URL-Parameter
  // und `document.referrer` mit — das Backend liest beides nicht (der
  // Klassifikator nimmt eine Erlaubnisliste, `classify_prompt.py`).
  it('kein query-Objekt und kein referrer im Kontext (N-1)', () => {
    history.replaceState({}, '', '/suche?q=eiszeit&token=geheim');
    Object.defineProperty(document, 'referrer', { configurable: true, value: 'https://vorher.example/?s=geheim' });
    try {
      const ctx = resolveMergedPageContext(true, '');
      expect(ctx['query']).toBeUndefined();
      expect(ctx['referrer']).toBeUndefined();
      expect(JSON.stringify(ctx)).not.toContain('geheim');
      expect(ctx['path']).toBe('/suche');
    } finally {
      delete (document as { referrer?: string }).referrer;
    }
  });
});
