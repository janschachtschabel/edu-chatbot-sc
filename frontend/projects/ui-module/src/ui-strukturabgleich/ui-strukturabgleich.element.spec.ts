// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { definiere, ELEMENT } from './ui-strukturabgleich.element';

const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const BEISPIEL = manifest.beispiele[0].daten as Record<string, unknown>;

function host(): ElementHost {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), aktion: vi.fn(), beschaeftigt: vi.fn(() => false),
    antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(),
    link: vi.fn((url: string) => (url.startsWith('https://') ? { href: url, hinweis: 'öffnet WLO' } : { href: '', hinweis: '' })),
  } as never;
}

function erzeuge(daten: Record<string, unknown> = BEISPIEL, kontext: Partial<ModulKontext> = {}) {
  definiere();
  const el = document.createElement(ELEMENT) as NachladeElement;
  el.host = host();
  el.daten = daten;
  el.kontext = { ...KONTEXT, ...kontext };
  document.body.appendChild(el);
  return { el, wurzel: el.shadowRoot as ShadowRoot };
}

const oben = (w: ShadowRoot) => [...(w.querySelector('.a > .a__liste') as HTMLElement).children] as HTMLElement[];

afterEach(() => document.body.replaceChildren());

describe('ui_strukturabgleich', () => {
  it('zeigt je Punkt die Art als Wort, Ebene 2 verschachtelt, die Sammlung mit Inhaltszahl', () => {
    const { wurzel } = erzeuge();
    expect(wurzel.querySelector('h3')?.textContent).toBe('Abgleich: Optik');
    expect(wurzel.querySelector('.a__zahlen')?.textContent).toBe('1 vorhanden · 1 ähnlich · 2 neu · 2 nur in WLO');
    const [licht, linsen] = oben(wurzel);
    expect(oben(wurzel)).toHaveLength(2);
    expect(licht.firstElementChild?.querySelector('.a__art')?.textContent).toBe('Vorhanden');
    expect(licht.textContent).toContain('42 Inhalte');
    const unter = licht.querySelector('.a__liste--e2') as HTMLElement;
    expect(unter.querySelector('.a__art')?.textContent).toBe('Ähnlich');
    expect(linsen.firstElementChild?.querySelector('.a__art')?.textContent).toBe('Neu');
    expect(linsen.firstElementChild?.querySelector('.a__wlo')).toBeNull();
    // gekürzt: „nicht gefunden“ statt „neu“, als Wort
    expect(linsen.querySelector('.a__liste--e2 .a__art')?.textContent).toBe('Nicht gefunden');
    expect(wurzel.textContent).toContain('direkt in einer Sammlung');
  });

  it('verlinkt nur über den Host und mit sicherem Ziel', () => {
    const { wurzel } = erzeuge();
    const a = wurzel.querySelector('.a__unter a') as HTMLAnchorElement;
    expect(a.href).toContain('https://redaktion.openeduhub.net');
    expect(a.rel).toBe('noopener noreferrer');
    expect(a.getAttribute('aria-label')).toContain('öffnet WLO');
    const { wurzel: w2 } = erzeuge({ ...BEISPIEL, sammlung: { nodeId: 'x', titel: '', url: 'http://unsicher' } });
    expect(w2.querySelector('.a__unter a')).toBeNull();
    expect(w2.querySelector('.a__unter')?.textContent).toBe('mit der Sammlung in WLO');
  });

  it('Fremdtext bleibt Text', () => {
    const boese = '<img src=x onerror=alert(1)>';
    const { wurzel } = erzeuge({ ...BEISPIEL, titel: boese, zeilen: [{ id: 'k', titel: boese, ebene: 1, art: 'neu' }] });
    expect(wurzel.querySelector('img')).toBeNull();
    expect(wurzel.querySelector('.a__name')?.textContent).toBe(boese);
  });

  it('nur in WLO mit Ebene und Elternsammlung als Text, gekürzt, gezeigt von gesamt', () => {
    const { wurzel } = erzeuge({ ...BEISPIEL, gekuerzt: true, zahlen: { ...(BEISPIEL['zahlen'] as object), nur_in_wlo: 120 } });
    expect(wurzel.querySelector('summary')?.textContent).toBe('Nur in WLO (2 von 120)');
    const eintraege = [...wurzel.querySelectorAll('details .a__eintrag')].map((e) => e.textContent ?? '');
    expect(eintraege[0]).toContain('Ebene 1');
    expect(eintraege[1]).toContain('Ebene 2');
    expect(eintraege[1]).toContain('unter Licht und Schatten');
    expect(wurzel.textContent).toContain('größer als hier gezeigt');
    const { wurzel: leer } = erzeuge({ ...BEISPIEL, zeilen: [], nur_in_wlo: [], zahlen: {} });
    expect(leer.textContent).toContain('keine Punkte');
    expect(leer.textContent).toContain('Jede Sammlung hat einen Punkt');
    expect(leer.querySelector('summary')?.textContent).toBe('Nur in WLO (0)');
  });

  it('englisch, und unbekannte Arten fallen weg', () => {
    const { wurzel } = erzeuge({ ...BEISPIEL, zeilen: [...(BEISPIEL['zeilen'] as unknown[]), { id: 'x', titel: 'X', ebene: 1, art: 'kaputt' }] },
      { sprache: 'en' });
    expect(wurzel.querySelector('.a__zahlen')?.textContent).toBe('1 exist · 1 similar · 2 new · 2 only in WLO');
    expect(oben(wurzel)).toHaveLength(2);
    expect(wurzel.textContent).toContain('Not found');
  });

  it('ein Punkt der Ebene 2 ohne Punkt davor steht oben', () => {
    const { wurzel } = erzeuge({ ...BEISPIEL, zeilen: [{ id: 'a', titel: 'Waise', ebene: 2, art: 'neu' }] });
    expect(oben(wurzel)).toHaveLength(1);
  });

  it('U5: Treffer je Punkt, Lücke als Wort, Abschnitt Lücken mit Beispielen', () => {
    const mit = manifest.beispiele[1].daten as Record<string, unknown>;
    const { wurzel } = erzeuge(mit);
    const [licht, linsen] = oben(wurzel);
    expect(licht.firstElementChild?.textContent).toContain('85 Treffer in ganz WLO');
    expect(linsen.firstElementChild?.textContent).toContain('Lücke');
    expect(linsen.textContent).toContain('nicht gezählt');                  // Ebene 2: abdeckung_fehlt
    const abschnitt = [...wurzel.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent === 'Lücken (1)');
    expect(abschnitt?.open).toBe(true);
    expect(abschnitt?.textContent).toContain('ganz WLO');
    const a = abschnitt?.querySelector('a') as HTMLAnchorElement;
    expect(a.textContent).toBe('Linsen im Alltag');
    // ohne Abdeckung: kein Abschnitt, keine Trefferzeile
    const { wurzel: ohne } = erzeuge();
    expect(ohne.textContent).not.toContain('Treffer in ganz WLO');
    expect([...ohne.querySelectorAll('summary')].map((x) => x.textContent)).toEqual(['Nur in WLO (2)']);
  });

  it('R3-c: eine Lücke der Ebene 2 nennt ihren Punkt', () => {
    const mit = manifest.beispiele[1].daten as Record<string, unknown>;
    const zeilen = [
      { id: 'a', titel: 'Optik', ebene: 1, art: 'neu', abdeckung: { total: 90, luecke: false } },
      { id: 'b', titel: 'Linsen', ebene: 2, art: 'neu', abdeckung: { total: 0, luecke: true } },
    ];
    const { wurzel } = erzeuge({ ...mit, zeilen, abdeckung: { gezaehlt: 2, luecken: 1 } });
    const abschnitt = [...wurzel.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent === 'Lücken (1)');
    expect(abschnitt?.querySelector('.a__name')?.textContent).toBe('Optik › Linsen');
  });

  it('U5: Filter unbekannt und keine Lücken', () => {
    const mit = manifest.beispiele[1].daten as Record<string, unknown>;
    const { wurzel } = erzeuge({ ...mit, abdeckung: { gezaehlt: 0, luecken: 0, filter_unaufgeloest: true } });
    expect(wurzel.textContent).toContain('kennt WLO nicht');
    const zeilen = (mit['zeilen'] as Record<string, unknown>[]).map((z) => ({ ...z, abdeckung: { total: 9, luecke: false } }));
    const { wurzel: voll } = erzeuge({ ...mit, zeilen, abdeckung: { gezaehlt: 4, luecken: 0 } });
    expect(voll.textContent).toContain('mehr als 2 Treffer');
  });

  it('Review U5: nichts gezählt ist nicht „keine Lücken“, gesperrt, gezählt von, Etikett mit Einheit, geschätzt', () => {
    const mit = manifest.beispiele[1].daten as Record<string, unknown>;
    const nichts = (mit['zeilen'] as Record<string, unknown>[]).map(({ abdeckung: _a, ...z }) => ({ ...z, abdeckung_fehlt: 'keine_antwort' }));
    const { wurzel } = erzeuge({ ...mit, zeilen: nichts, abdeckung: { gezaehlt: 0, luecken: 0, ungezaehlt: 4 } });
    expect(wurzel.textContent).toContain('kam nicht zustande');
    expect(wurzel.textContent).not.toContain('mehr als 2 Treffer');
    const { wurzel: zu } = erzeuge({ ...mit, zeilen: nichts, abdeckung: { gezaehlt: 0, luecken: 0, gesperrt: true } });
    expect(zu.textContent).toContain('gerade nicht möglich');
    const { wurzel: normal } = erzeuge(mit);
    expect(normal.textContent).toContain('3 von 4 Punkten gezählt');
    const abschnitt = [...normal.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent?.startsWith('Lücken'));
    expect(abschnitt?.querySelector('.a__art--luecke')?.textContent).toBe('1 Treffer');
    expect(normal.textContent).toContain('(Fach oder Stufe geschätzt)');
    const link = abschnitt?.querySelector('a') as HTMLAnchorElement;
    expect(link.getAttribute('aria-label')).toContain('öffnet WLO');
  });

  it('Review U5: der Klappzustand bleibt beim Neuzeichnen; englisch', () => {
    const mit = manifest.beispiele[1].daten as Record<string, unknown>;
    const { el, wurzel } = erzeuge(mit);
    const finde = () => [...wurzel.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent?.startsWith('Lücken'))!;
    finde().open = false;
    finde().dispatchEvent(new Event('toggle'));
    el.kontext = { ...KONTEXT, sprache: 'en' };
    const en = [...wurzel.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent?.startsWith('Gaps'))!;
    expect(en.open).toBe(false);
    expect(wurzel.textContent).toContain('matches in all of WLO');
  });

  it('definiert sich nur einmal', () => {
    definiere();
    definiere();
    expect(customElements.get(ELEMENT)).toBeDefined();
  });
});
