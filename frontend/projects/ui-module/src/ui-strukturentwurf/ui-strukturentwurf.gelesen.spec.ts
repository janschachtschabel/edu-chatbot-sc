// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ModulKontext } from '../_vertrag/ui-block';
import { alsJson, type EntwurfDaten } from './entwurf-export';
import { definiere, ELEMENT, UiStrukturentwurfElement } from './ui-strukturentwurf.element';
import { STIL } from './ui-strukturentwurf.stil.generated';

/**
 * Plan 2026-11-19, A6 (E7): die Rückkontrolle „Gelesener Text“ beim Entwurf aus einem Dokument.
 * Eingeklappt unter dem Kopf (natives `<details>`: Tab erreicht die Zusammenfassung, Enter und
 * Leertaste klappen); aufgeklappt Weg, Abschnittstitel und Anfang des gelesenen Texts. Nur Anzeige:
 * `gelesen` geht weder in die Antwort noch in den Download.
 */
const KONTEXT: ModulKontext = {
  blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
};

let h = host();

function host() {
  return {
    antworten: vi.fn(), vormerken: vi.fn(), herunterladen: vi.fn(), beschaeftigt: vi.fn(() => false),
    drucken: vi.fn(), link: vi.fn(), aktion: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(), ablegen: vi.fn(), auftrag: vi.fn(),
  };
}

function render(daten: EntwurfDaten, kontext: Partial<ModulKontext> = {}) {
  h = host();
  definiere();
  const knoten = document.createElement(ELEMENT) as UiStrukturentwurfElement;
  knoten.host = h as never;
  knoten.daten = daten as unknown as Record<string, unknown>;
  knoten.kontext = { ...KONTEXT, ...kontext };
  document.body.appendChild(knoten);
  return { el: knoten.shadowRoot as ShadowRoot, knoten };
}

const ANFANG = 'Rahmenlehrplan für den Ausbildungsberuf Augenoptiker <b>fett</b>';
const AUS_DOKUMENT = {
  titel: 'Augenoptik', quelle: 'dokument', knoten: [{ id: 'k1', titel: 'Kunden beraten' }],
  gelesen: [
    { name: 'Augenoptiker.pdf', zeichen: 62600, weg: 'ganz', anfang: ANFANG, abschnitte: ['Teil I', 'Teil II'] },
    { name: 'Anhang.pdf', zeichen: 120000, weg: 'gliederung', anfang: 'Anhang', abschnitte: [] },
  ],
} as unknown as EntwurfDaten;

const gelesen = (el: ShadowRoot) => [...el.querySelectorAll<HTMLDetailsElement>('details.ui-strukturentwurf__gelesen')];
const text = (n: Element | null | undefined) => n?.textContent?.trim();

afterEach(() => {
  document.body.innerHTML = '';
});

describe('ui_strukturentwurf: Gelesener Text (A6)', () => {
  it('steht eingeklappt unter dem Kopf, vor dem Baum, je Dokument einmal', () => {
    const { el } = render(AUS_DOKUMENT);
    const [eins, zwei] = gelesen(el);
    // Review A, NIT 14: ohne „– anzeigen“ (der Zustand sagt der Vorleser), der Name isoliert (<bdi>)
    expect(text(eins.querySelector('summary'))).toBe('Gelesener Text (Augenoptiker.pdf, 62.600 Zeichen)');
    expect(text(zwei.querySelector('summary'))).toBe('Gelesener Text (Anhang.pdf, 120.000 Zeichen)');
    expect(text(eins.querySelector('summary bdi'))).toBe('Augenoptiker.pdf');
    expect(eins.open).toBe(false);
    const baum = el.querySelector('[role="tree"]')!;
    expect(eins.compareDocumentPosition(baum) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(eins.compareDocumentPosition(el.querySelector('.ui-strukturentwurf__kopf')!)
      & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });

  it('zeigt Weg, Abschnitte und Anfang — der Anfang als Text, nie als HTML', () => {
    const { el } = render(AUS_DOKUMENT);
    const [eins, zwei] = gelesen(el);
    expect(text(eins.querySelector('.ui-strukturentwurf__gelesen-weg'))).toBe('Gelesen: der ganze Text.');
    expect(text(zwei.querySelector('.ui-strukturentwurf__gelesen-weg'))).toContain('Gliederung');
    expect([...eins.querySelectorAll('li')].map((li) => li.textContent)).toEqual(['Teil I', 'Teil II']);
    expect(zwei.querySelector('ul')).toBeNull();
    const anfang = eins.querySelector<HTMLElement>('.ui-strukturentwurf__gelesen-anfang')!;
    // Review A, MINOR 8: ein benannter Bereich (ein <p> trägt kein aria-label)
    expect(anfang.tagName).toBe('DIV');
    expect(anfang.getAttribute('role')).toBe('region');
    expect(anfang.textContent).toBe(ANFANG);
    expect(anfang.querySelector('b')).toBeNull();
    expect(anfang.dir).toBe('auto');
    // der Anfang rollt ab seiner Höhengrenze — per Tastatur erreichbar und benannt
    expect(anfang.tabIndex).toBe(0);
    expect(anfang.getAttribute('aria-label')).toBe('Anfang des gelesenen Texts (Augenoptiker.pdf)');
  });

  it('bleibt aufgeklappt, wenn das Element neu zeichnet', () => {
    const { el, knoten } = render(AUS_DOKUMENT);
    gelesen(el)[0].open = true;
    gelesen(el)[0].dispatchEvent(new Event('toggle'));
    knoten.kontext = { ...KONTEXT, sprache: 'de' };
    expect(gelesen(el)[0].open).toBe(true);
    expect(gelesen(el)[1].open).toBe(false);
  });

  it('behält den Fokus auf Zusammenfassung und Anfang, wenn das Element neu zeichnet', () => {
    // Review A, NIT 15: das Element findet den Fokus über `data-fokus` zurück
    const { el, knoten } = render(AUS_DOKUMENT);
    gelesen(el)[1].querySelector<HTMLElement>('summary')!.focus();
    knoten.kontext = { ...KONTEXT, sprache: 'de' };
    expect(el.activeElement).toBe(gelesen(el)[1].querySelector('summary'));
    gelesen(el)[0].open = true;
    gelesen(el)[0].dispatchEvent(new Event('toggle'));
    gelesen(el)[0].querySelector<HTMLElement>('.ui-strukturentwurf__gelesen-anfang')!.focus();
    knoten.kontext = { ...KONTEXT, sprache: 'de' };
    expect(el.activeElement).toBe(gelesen(el)[0].querySelector('.ui-strukturentwurf__gelesen-anfang'));
  });

  it('die Zusammenfassung ist ein Ziel von mindestens 24 px Höhe (WCAG 2.5.8)', () => {
    // Zweites Review A, NIT 12 — jsdom misst keine Layouts, deshalb die Regel im erzeugten Stil
    expect(STIL).toMatch(/\.ui-strukturentwurf__gelesen summary\{[^}]*min-block-size:24px/);
  });

  it('spricht Englisch', () => {
    const { el } = render(AUS_DOKUMENT, { sprache: 'en' });
    const [eins] = gelesen(el);
    expect(text(eins.querySelector('summary'))).toBe('Text read (Augenoptiker.pdf, 62,600 characters)');
    expect(text(eins.querySelector('.ui-strukturentwurf__gelesen-weg'))).toBe('Read: the whole text.');
  });

  it('fehlt ohne gelesen', () => {
    const { el } = render({ titel: 'Optik', quelle: 'ki', knoten: [{ id: 'k1', titel: 'Licht' }] } as EntwurfDaten);
    expect(gelesen(el)).toEqual([]);
  });

  it('geht weder in die Antwort noch in den Download', () => {
    render(AUS_DOKUMENT);
    const vorgemerkt = h.vormerken.mock.calls.at(-1)?.[0] as Record<string, unknown>;
    expect(vorgemerkt).toBeTruthy();
    expect('gelesen' in vorgemerkt).toBe(false);
    expect(alsJson(AUS_DOKUMENT)).not.toContain('Augenoptiker.pdf');
  });
});
