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

  it('SW-4: bis vier Ebenen verschachtelt; eine übersprungene Ebene rückt nur eine Stufe ein', () => {
    const zeilen = [
      { id: 'a', titel: 'Optik', ebene: 1, art: 'vorhanden' },
      { id: 'b', titel: 'Linsen', ebene: 2, art: 'neu' },
      { id: 'c', titel: 'Sammellinsen', ebene: 3, art: 'neu' },
      { id: 'd', titel: 'Brennweite', ebene: 4, art: 'neu' },
      { id: 'e', titel: 'Spiegel', ebene: 2, art: 'neu' },
      { id: 'f', titel: 'Akustik', ebene: 1, art: 'neu' },
      { id: 'g', titel: 'Schall', ebene: 3, art: 'neu' },
      { id: 'h', titel: 'Zu tief', ebene: 7, art: 'neu' },
    ];
    const { wurzel } = erzeuge({ ...BEISPIEL, zeilen });
    const unter = (li: Element) => [...li.children].find((k) => k.classList.contains('a__liste--e2')) as HTMLElement | undefined;
    const namen = (ul: Element | undefined) => [...(ul?.children ?? [])].map((li) => li.firstElementChild?.querySelector('.a__name')?.textContent);
    expect(namen(wurzel.querySelector('.a > .a__liste') as HTMLElement)).toEqual(['Optik', 'Akustik', 'Zu tief']);
    const [optik, akustik, zuTief] = oben(wurzel);
    const e2 = unter(optik) as HTMLElement;
    expect(namen(e2)).toEqual(['Linsen', 'Spiegel']);
    const e3 = unter(e2.children[0]) as HTMLElement;
    expect(namen(e3)).toEqual(['Sammellinsen']);
    expect(namen(unter(e3.children[0]))).toEqual(['Brennweite']);
    expect(unter(e2.children[1])).toBeUndefined();
    // Ebene 3 direkt unter Ebene 1 (kaputte Daten): eine Stufe, nicht zwei
    expect(namen(unter(akustik))).toEqual(['Schall']);
    expect(unter(unter(akustik)!.children[0])).toBeUndefined();
    // eine Ebene außerhalb 1 bis 4 zählt als 1
    expect(unter(zuTief)).toBeUndefined();
  });

  it('SW-4: tiefe Zeilen ohne „nicht gezählt“, ein Hinweis im Abschnitt; nur in WLO mit Ebene 3 und Elternsammlung', () => {
    const mit = manifest.beispiele[1].daten as Record<string, unknown>;
    const zeilen = [
      { id: 'a', titel: 'Optik', ebene: 1, art: 'neu', abdeckung: { total: 90, luecke: false } },
      { id: 'b', titel: 'Linsen', ebene: 2, art: 'neu', abdeckung_fehlt: 'timeout' },
      { id: 'c', titel: 'Sammellinsen', ebene: 3, art: 'neu', abdeckung_fehlt: 'ebene' },
      { id: 'd', titel: 'Brennweite', ebene: 4, art: 'neu', abdeckung_fehlt: 'ebene' },
      { id: 'e', titel: 'Akustik', ebene: 1, art: 'neu', abdeckung: { total: 1, luecke: true } },
      { id: 'f', titel: 'Schall', ebene: 2, art: 'neu', abdeckung: { total: 2, luecke: true } },
    ];
    const nur = [{ nodeId: 'x', titel: 'Lupe', ebene: 3, eltern_titel: 'Linsen', anzahl: 2 },
      { nodeId: 'y', titel: 'Okular', ebene: 4, eltern_titel: 'Lupe' }];
    const { wurzel } = erzeuge({ ...mit, zeilen, nur_in_wlo: nur, abdeckung: { gezaehlt: 3, luecken: 2, ungezaehlt: 1, nur_bis_ebene: 2 } });
    const zeile = (name: string) => [...wurzel.querySelectorAll('.a > .a__liste .a__zeile')].find((z) => z.querySelector('.a__name')?.textContent === name);
    expect(zeile('Linsen')?.textContent).toContain('nicht gezählt');             // ausgefallen
    expect(zeile('Sammellinsen')?.textContent).not.toContain('nicht gezählt');   // nach Regel nicht
    expect(zeile('Brennweite')?.textContent).not.toContain('nicht gezählt');
    const abschnitt = [...wurzel.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent === 'Lücken (2)');
    expect(abschnitt?.textContent).toContain('Gezählt wird nur für Ebene 1 bis 2.');
    expect(abschnitt?.textContent).toContain('3 von 4 Punkten gezählt');
    // tiefere Zeilen zwischen Punkt und Unterpunkt ändern den Punkt einer Lücke nicht
    expect([...abschnitt!.querySelectorAll('.a__name')].map((n) => n.textContent)).toEqual(['Akustik', 'Akustik › Schall']);
    const nurAbschnitt = [...wurzel.querySelectorAll('details')].find((d) => d.querySelector('summary')?.textContent?.startsWith('Nur in WLO'));
    const eintraege = [...nurAbschnitt!.querySelectorAll('.a__eintrag')].map((e) => e.textContent ?? '');
    expect(eintraege[0]).toContain('Ebene 3');
    expect(eintraege[0]).toContain('unter Linsen · 2 Inhalte');
    expect(eintraege[1]).toContain('Ebene 4');
    expect(eintraege[1]).toContain('unter Lupe');
    // ohne tiefere Zeilen: kein Hinweis
    const { wurzel: flach } = erzeuge(mit);
    expect(flach.textContent).not.toContain('Gezählt wird nur');
  });

  it('SW-4: ohne Elternpunkt gefunden nennt die Sammlung darüber; nicht vollständig gelesen statt „größer“', () => {
    const zeilen = [
      { id: 'a', titel: 'Neues Thema', ebene: 1, art: 'neu' },
      { id: 'b', titel: 'Grundlagen', ebene: 2, art: 'vorhanden', wlo: { nodeId: 'g', titel: 'Grundlagen', anzahl: 3, eltern_titel: 'Mechanik' } },
      { id: 'c', titel: 'Wellen', ebene: 2, art: 'neu', ungewiss: true },
    ];
    const { wurzel } = erzeuge({ ...BEISPIEL, zeilen, gekuerzt: true, unvollstaendig: true });
    const wlo = wurzel.querySelector('.a > .a__liste .a__liste--e2 .a__wlo');
    expect(wlo?.textContent).toBe('in WLO: Grundlagen · unter Mechanik · 3 Inhalte');
    expect(wurzel.textContent).toContain('nicht vollständig gelesen');
    expect(wurzel.textContent).not.toContain('größer als hier gezeigt');
    expect(wurzel.textContent).toContain('Nicht gefunden');
    const { wurzel: en } = erzeuge({ ...BEISPIEL, zeilen, gekuerzt: true, unvollstaendig: true }, { sprache: 'en' });
    expect(en.textContent).toContain('was not read completely');
    // jede Liste trägt ihre Rolle ausdrücklich (list-style: none)
    expect([...wurzel.querySelectorAll('ul')].every((ul) => ul.getAttribute('role') === 'list')).toBe(true);
    expect(wurzel.querySelectorAll('ul').length).toBeGreaterThanOrEqual(3);
  });

  it('definiert sich nur einmal', () => {
    definiere();
    definiere();
    expect(customElements.get(ELEMENT)).toBeDefined();
  });
});
