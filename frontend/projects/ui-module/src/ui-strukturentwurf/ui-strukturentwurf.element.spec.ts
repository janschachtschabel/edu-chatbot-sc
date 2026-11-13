// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ICONS } from '@boerdi/ui/icons/icons';

import type { ModulKontext } from '../_vertrag/ui-block';
import { PFEIL, SYMBOL } from './entwurf-symbole';
import type { EntwurfDaten } from './entwurf-export';
import manifest from './manifest.json';
import { definiere, ELEMENT, UiStrukturentwurfElement } from './ui-strukturentwurf.element';

/**
 * Paket U2-e (Plan 2026-11-04, T-10 … T-12): der Strukturentwurf — Baum nach APG wie der Bestand,
 * dazu Bearbeiten (Leiste, Tasten, Detailfeld, Rückgängig), Übernehmen, Vormerken und Herunterladen.
 *
 * Seit Paket BU-2 ein nachgeladenes Custom Element (Shadow Root): dieselben Fälle wie zuvor an der
 * Komponente, nur über `shadowRoot` gefragt. `f.whenStable()` bleibt als Name — das Element zeichnet
 * sofort.
 */
let beschaeftigt = false;

function host() {
  return {
    antworten: vi.fn(), vormerken: vi.fn(), herunterladen: vi.fn(), beschaeftigt: vi.fn(() => beschaeftigt),
    drucken: vi.fn(), link: vi.fn(), aktion: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(), ablegen: vi.fn(), auftrag: vi.fn(),
  };
}

let h = host();

const KONTEXT: ModulKontext = {
  blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
};

async function render(daten: EntwurfDaten, kontext: Partial<ModulKontext> = {}) {
  h = host();
  definiere();
  const knoten = document.createElement(ELEMENT) as UiStrukturentwurfElement;
  knoten.host = h as never;
  knoten.daten = daten as unknown as Record<string, unknown>;
  knoten.kontext = { ...KONTEXT, ...kontext };
  knoten.beschaeftigt = beschaeftigt;
  document.body.appendChild(knoten);
  const el = knoten.shadowRoot as ShadowRoot;
  const f = {
    knoten,
    whenStable: async () => undefined,
    setzeKontext: (k: ModulKontext) => { knoten.kontext = k; },
    destroy: () => knoten.remove(),
  };
  return { f, el };
}

const BEISPIEL = manifest.beispiele[0].daten as unknown as EntwurfDaten;

const items = (el: ShadowRoot) => [...el.querySelectorAll<HTMLElement>('[role="treeitem"]')];
const name = (el: ShadowRoot, item: HTMLElement) =>
  el.querySelector(`#${item.getAttribute('aria-labelledby')}`)?.textContent?.trim();
const titel = (el: ShadowRoot) => items(el).map((i) => name(el, i));
const knopf = (el: ShadowRoot, text: string) =>
  [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement;
const ansage = (el: ShadowRoot) => el.querySelector('[role="status"]')?.textContent?.trim();

async function taste(f: { whenStable(): Promise<unknown> }, item: HTMLElement, key: string, mehr: KeyboardEventInit = {}) {
  item.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, composed: true, ...mehr }));
  await f.whenStable();
}

/** Der sichtbare Text des Moduls (ohne das Stilblatt im Shadow Root). */
const text = (el: ShadowRoot) => el.querySelector('section')?.textContent ?? '';

afterEach(() => {
  document.body.innerHTML = '';
  beschaeftigt = false;
});

describe('ui_strukturentwurf (Element)', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const daten = beispiel.daten as unknown as EntwurfDaten;
      const { el } = await render(daten);
      expect(items(el).length).toBe(daten.knoten.length);            // zugeklappt: erste Ebene
      expect(text(el)).toContain(daten.titel);
    });
  }

  it('sagt im Kopf „Entwurf (KI)“ bzw. „Entwurf (aus WLO)“ — nie wie der Bestand', async () => {
    const { el } = await render(BEISPIEL);
    expect(el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Entwurf (KI)');
    const wlo = await render(manifest.beispiele[1].daten as unknown as EntwurfDaten);
    expect(wlo.el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Entwurf (aus WLO)');
    expect(text(wlo.el)).toContain('mehr Punkte, als der Entwurf übernommen hat');
  });

  it('Review U3-1, Befund 5: ein Entwurf aus Ordnern sagt seine Herkunft und kürzt ohne WLO-Satz', async () => {
    const { el } = await render({ ...BEISPIEL, quelle: 'ordner', gekuerzt: true } as EntwurfDaten);
    expect(el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Entwurf (aus Ordnern)');
    expect(text(el)).toContain('Der Ordner hat mehr Ebenen oder Unterordner');
    expect(text(el)).not.toContain('Sammlung in WLO');
  });

  it('Baum mit Ebene, Position, Zustand; ausstehende Punkte sagen es am Eintrag', async () => {
    const { el } = await render(manifest.beispiele[2].daten as unknown as EntwurfDaten);
    const [ursachen, folgen] = items(el);
    expect(el.querySelector('[role="tree"]')?.getAttribute('aria-labelledby')).toBe('se-b0000001-kopf');
    expect(ursachen.getAttribute('aria-expanded')).toBe('false');
    expect(ursachen.getAttribute('aria-level')).toBe('1');
    expect(folgen.getAttribute('aria-posinset')).toBe('2');
    expect(folgen.getAttribute('aria-expanded')).toBeNull();
    expect(el.querySelector(`#${folgen.getAttribute('aria-describedby')}`)?.textContent).toBe('Unterthemen fehlen noch');
    expect(ursachen.getAttribute('tabindex')).toBe('0');
  });

  it('Pfeiltasten wie im Bestand: → klappt auf, ↓ geht ins Kind', async () => {
    const { f, el } = await render(BEISPIEL);
    const [licht] = items(el);
    licht.focus();
    await taste(f, licht, 'ArrowRight');
    expect(licht.getAttribute('aria-expanded')).toBe('true');
    await taste(f, licht, 'ArrowDown');
    expect(el.activeElement?.id).toBe('se-b0000001-k-k1-1');
  });

  it('Unterpunkt und Punkt danach; das Titelfeld bekommt den Fokus', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Punkt danach').click();
    await f.whenStable();
    expect(titel(el)).toEqual(['Ausbreitung des Lichts', 'Neuer Punkt', 'Reflexion', 'Brechung']);
    expect(el.activeElement?.id).toBe('se-b0000001-titel');
    expect(ansage(el)).toBe('Neuer Punkt. Titel eingeben.');
    const feld = el.activeElement as HTMLInputElement;
    feld.value = 'Linsen';
    feld.dispatchEvent(new Event('input'));
    await f.whenStable();
    expect(titel(el)[1]).toBe('Linsen');
    knopf(el, 'Unterpunkt').click();
    await f.whenStable();
    expect(titel(el)).toEqual(['Ausbreitung des Lichts', 'Linsen', 'Neuer Punkt', 'Reflexion', 'Brechung']);
    expect(items(el)[2].getAttribute('aria-level')).toBe('2');
  });

  it('Tasten: Alt+Umschalt+↓ verschiebt, Entf löscht, Strg+Z nimmt zurück — jeweils angesagt', async () => {
    const { f, el } = await render(BEISPIEL);
    let [licht] = items(el);
    licht.focus();
    await taste(f, licht, 'ArrowDown', { altKey: true, shiftKey: true });
    expect(titel(el)).toEqual(['Reflexion', 'Ausbreitung des Lichts', 'Brechung']);
    expect(ansage(el)).toBe('„Ausbreitung des Lichts“ nach unten verschoben.');
    expect(el.activeElement?.id).toBe('se-b0000001-k-k1');
    [, licht] = items(el);
    await taste(f, licht, 'Delete');
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
    expect(ansage(el)).toBe('„Ausbreitung des Lichts“ gelöscht. Rückgängig mit Strg+Z.');
    expect(el.activeElement?.id).toBe('se-b0000001-k-k3');         // der nächste Punkt
    await taste(f, el.activeElement as HTMLElement, 'z', { ctrlKey: true });
    expect(titel(el)).toEqual(['Reflexion', 'Ausbreitung des Lichts', 'Brechung']);
  });

  it('ein unmöglicher Schritt sagt seinen Grund und ändert nichts', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Hoch').click();
    await f.whenStable();
    expect(ansage(el)).toBe('Schon ganz oben.');
    knopf(el, 'Einrücken').click();
    await f.whenStable();
    expect(ansage(el)).toBe('Der erste Punkt lässt sich nicht einrücken.');
    expect(titel(el)).toEqual(['Ausbreitung des Lichts', 'Reflexion', 'Brechung']);
  });

  it('Einrücken macht den Punkt zum Unterpunkt und hält ihn sichtbar', async () => {
    const { f, el } = await render(BEISPIEL);
    items(el)[2].focus();
    await taste(f, items(el)[2], 'ArrowRight', { altKey: true, shiftKey: true });
    const brechung = el.querySelector('#se-b0000001-k-k3') as HTMLElement;
    expect(brechung.getAttribute('aria-level')).toBe('2');
    expect(ansage(el)).toBe('„Brechung“ eingerückt, Ebene 2.');
  });

  it('Beschreibung und Schlagworte im Detailfeld; Komma und Leerzeichen bleiben beim Tippen', async () => {
    const { f, el } = await render(BEISPIEL);
    const [, beschreibung] = [...el.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('.ui-strukturentwurf__feld input, .ui-strukturentwurf__feld textarea')];
    beschreibung.dispatchEvent(new Event('focus'));
    beschreibung.value = 'Neu beschrieben.';
    beschreibung.dispatchEvent(new Event('input'));
    const kw = el.querySelectorAll<HTMLInputElement>('.ui-strukturentwurf__feld input')[1];
    kw.dispatchEvent(new Event('focus'));
    kw.value = 'Licht, ';
    kw.dispatchEvent(new Event('input'));
    await f.whenStable();
    expect(kw.value).toBe('Licht, ');
    knopf(el, 'Übernehmen').click();
    const [daten] = h.antworten.mock.calls[0];
    expect(daten.knoten[0]).toMatchObject({ beschreibung: 'Neu beschrieben.', keywords: ['Licht'] });
  });

  it('Übernehmen antwortet mit dem bereinigten Stand und einem lesbaren Satz', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Punkt danach').click();
    await f.whenStable();
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.value = '   ';
    feld.dispatchEvent(new Event('input'));
    await f.whenStable();
    knopf(el, 'Übernehmen').click();
    const [daten, text] = h.antworten.mock.calls[0];
    expect(daten).toMatchObject({ titel: 'Optik in Klasse 8', quelle: 'ki', uebernommen: true, bearbeitet: true });
    expect(daten.knoten[1].titel).toBe('Neuer Punkt');           // nie leer (Schema)
    expect(text).toBe('Entwurf „Optik in Klasse 8“ übernommen (7 Punkte).');
  });

  it('während eines Zugs geht nichts hinaus', async () => {
    beschaeftigt = true;
    const { el } = await render(BEISPIEL);
    knopf(el, 'Übernehmen').click();
    expect(h.antworten).not.toHaveBeenCalled();
    expect(knopf(el, 'Übernehmen').getAttribute('aria-disabled')).toBe('true');
  });

  it('merkt den Stand vor — unverändert und nach jeder Änderung (T-10)', async () => {
    const { f, el } = await render(BEISPIEL);
    expect(h.vormerken).toHaveBeenLastCalledWith(expect.objectContaining({ uebernommen: false, bearbeitet: false }));
    knopf(el, 'Löschen').click();
    await f.whenStable();
    const letzte = h.vormerken.mock.calls.at(-1)![0];
    expect(letzte).toMatchObject({ bearbeitet: true });
    expect(letzte.knoten).toHaveLength(2);
  });

  it('herunterladen als JSON und Markdown', async () => {
    const { el } = await render(BEISPIEL);
    knopf(el, 'Als JSON herunterladen').click();
    knopf(el, 'Als Markdown herunterladen').click();
    const [[datei, mime, json], [md]] = h.herunterladen.mock.calls;
    expect([datei, mime]).toEqual(['optik-in-klasse-8.json', 'application/json']);
    expect(JSON.parse(json).typ).toBe('wlo.sammlungsstruktur@1');
    expect(md).toBe('optik-in-klasse-8.md');
  });

  it('beantwortet: nur lesend mit der Antwort der Person, Herunterladen bleibt', async () => {
    const antwort = manifest.beispiele[0].antwort as Record<string, unknown>;
    const { el } = await render(BEISPIEL, { nurLesen: true, antwort });
    expect(titel(el)).toEqual(['Licht und Schatten', 'Linsen']);
    expect(text(el)).toContain('Übernommen.');
    expect(knopf(el, 'Übernehmen')).toBeUndefined();
    expect(knopf(el, 'Löschen')).toBeUndefined();
    expect(knopf(el, 'Als JSON herunterladen')).toBeDefined();
    // Nur lesend nichts vormerken — die Vormerkung wird zurückgenommen (Review U2, Befund 12).
    expect(h.vormerken.mock.calls.every(([d]) => d === null)).toBe(true);
  });

  it('veraltet ohne Antwort: der ursprüngliche Entwurf, nur lesend', async () => {
    const { f, el } = await render(BEISPIEL, { nurLesen: true });
    expect(text(el)).toContain('Dieser Entwurf ist nicht mehr offen.');
    await taste(f, items(el)[0], 'Delete');
    expect(items(el)).toHaveLength(3);
  });

  it('leer: ein Knopf für den ersten Punkt', async () => {
    const { f, el } = await render({ titel: 'Leer', quelle: 'ki', knoten: [{ id: 'k1', titel: 'Nur' }] });
    knopf(el, 'Löschen').click();
    await f.whenStable();
    expect(text(el)).toContain('Der Entwurf ist leer.');
    knopf(el, 'Punkt hinzufügen').click();
    await f.whenStable();
    expect(titel(el)).toEqual(['Neuer Punkt']);
  });

  it('englisch', async () => {
    const { el } = await render(BEISPIEL, { sprache: 'en' });
    expect(el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Draft (AI)');
    expect(knopf(el, 'Accept')).toBeDefined();
    expect(text(el)).toContain('6 items');
  });
});

describe('ui_strukturentwurf (Element) — Review U2 (Frontend)', () => {
  const kontext = (mehr: Partial<ModulKontext> = {}): ModulKontext => ({
    blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null, ...mehr,
  });

  it('Befund 1: beantwortet → wieder offen (Zug kam nicht an) behält die Bearbeitung', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Löschen').click();
    await f.whenStable();
    knopf(el, 'Übernehmen').click();
    const [gesendet] = h.antworten.mock.calls[0];
    f.setzeKontext(kontext({ nurLesen: true, antwort: gesendet }));
    await f.whenStable();
    f.setzeKontext(kontext());           // `wiederOffen`: antwort null
    await f.whenStable();
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
    expect(h.vormerken).toHaveBeenLastCalledWith(expect.objectContaining({ bearbeitet: true }));
  });

  it('Befund 2: Esc im Titelfeld bleibt im Modul und führt in den Baum', async () => {
    const { f, el } = await render(BEISPIEL);
    const aussen = vi.fn();
    f.knoten.addEventListener('keydown', aussen);
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.focus();
    feld.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true }));
    await f.whenStable();
    expect(aussen).not.toHaveBeenCalled();
    expect(el.activeElement?.id).toBe('se-b0000001-k-k1');
  });

  it('Befund 3: Strg+Z nach dem Einrücken und nach dem Hinzufügen lässt den Fokus im Baum', async () => {
    const { f, el } = await render(BEISPIEL);
    const brechung = () => el.querySelector<HTMLElement>('#se-b0000001-k-k3')!;
    brechung().focus();
    await taste(f, brechung(), 'ArrowRight', { altKey: true, shiftKey: true });
    await taste(f, brechung(), 'z', { ctrlKey: true });
    await f.whenStable();
    expect(el.activeElement?.id).toBe('se-b0000001-k-k3');
    expect(brechung().getAttribute('aria-level')).toBe('1');
    knopf(el, 'Punkt danach').click();
    await f.whenStable();
    const neu = items(el).find((i) => name(el, i) === 'Neuer Punkt')!;
    neu.focus();
    await taste(f, neu, 'z', { ctrlKey: true });
    await f.whenStable();
    expect(el.activeElement?.getAttribute('role')).toBe('treeitem');
    expect(titel(el)).not.toContain('Neuer Punkt');
  });

  it('Befund 4: nach „Übernehmen“ steht der Fokus auf der Statuszeile', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Übernehmen').click();
    f.setzeKontext(kontext({ nurLesen: true, antwort: h.antworten.mock.calls[0][0] }));
    await f.whenStable();
    expect(el.activeElement?.textContent?.trim()).toBe('Übernommen.');
  });

  it('Befund 8: zu viele Schlagworte werden angesagt, der Hinweis hängt am Feld', async () => {
    const { f, el } = await render(BEISPIEL);
    const kw = el.querySelectorAll<HTMLInputElement>('.ui-strukturentwurf__feld input')[1];
    expect(el.querySelector(`#${kw.getAttribute('aria-describedby')}`)?.textContent).toContain('8');
    kw.dispatchEvent(new Event('focus'));
    kw.value = Array.from({ length: 9 }, (_, i) => `w${i}`).join(', ');
    kw.dispatchEvent(new Event('input'));
    await f.whenStable();
    expect(ansage(el)).toContain('Höchstens 8 Schlagworte');
  });

  it('Befund 10: aus der Leiste bleibt der Fokus am Knopf', async () => {
    const { f, el } = await render(BEISPIEL);
    const runter = knopf(el, 'Runter');
    runter.focus();
    runter.click();
    await f.whenStable();
    expect(el.activeElement).toBe(knopf(el, 'Runter'));
  });

  it('Befund 12: nur lesend nimmt die Vormerkung zurück, ebenso beim Zerstören', async () => {
    const lesend = await render(BEISPIEL, { nurLesen: true });
    expect(h.vormerken).toHaveBeenLastCalledWith(null);
    lesend.f.destroy();
    const { f } = await render(BEISPIEL);
    h.vormerken.mockClear();
    f.destroy();
    expect(h.vormerken).toHaveBeenCalledWith(null);
  });

  it('Befund 14: Strg+Umschalt+Z ist kein Rückgängig; Rücktaste löscht wie Entf', async () => {
    const { f, el } = await render(BEISPIEL);
    const [licht] = items(el);
    licht.focus();
    await taste(f, licht, 'Backspace');
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
    await taste(f, el.activeElement as HTMLElement, 'Z', { ctrlKey: true, shiftKey: true });
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
  });

  it('Befund 15: wer den letzten Punkt löscht, landet auf „Punkt hinzufügen“', async () => {
    const { f, el } = await render({ titel: 'Leer', quelle: 'ki', knoten: [{ id: 'k1', titel: 'Nur' }] });
    const [nur] = items(el);
    nur.focus();
    await taste(f, nur, 'Delete');
    await f.whenStable();
    expect(el.activeElement).toBe(knopf(el, 'Punkt hinzufügen'));
  });
});

describe('ui_strukturentwurf (Element) — Gegenreview U2 (Befund 2)', () => {
  const kontext = (mehr: Partial<ModulKontext> = {}): ModulKontext => ({
    blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null, ...mehr,
  });

  it('ohne Bearbeitung bleibt „bearbeitet“ auch nach beantwortet → wieder offen falsch', async () => {
    const { f } = await render(BEISPIEL);
    f.setzeKontext(kontext({ nurLesen: true, antwort: { ...structuredClone(BEISPIEL), uebernommen: true, bearbeitet: false } }));
    await f.whenStable();
    f.setzeKontext(kontext());
    await f.whenStable();
    expect(h.vormerken).toHaveBeenLastCalledWith(expect.objectContaining({ bearbeitet: false }));
  });

  it('Rückgängig bis zum Anfang: wieder unbearbeitet', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Löschen').click();
    await f.whenStable();
    expect(h.vormerken).toHaveBeenLastCalledWith(expect.objectContaining({ bearbeitet: true }));
    knopf(el, 'Rückgängig').click();
    await f.whenStable();
    expect(h.vormerken).toHaveBeenLastCalledWith(expect.objectContaining({ bearbeitet: false }));
  });
});

describe('ui_strukturentwurf (Element) — drittes Review U2 (Befund 4)', () => {
  it('nach „Alles zuklappen“ gilt die Leiste dem nächsten sichtbaren Vorfahren, nicht dem ersten Punkt', async () => {
    const { f, el } = await render(BEISPIEL);
    const reflexion = el.querySelector<HTMLElement>('#se-b0000001-k-k2')!;
    reflexion.focus();
    await taste(f, reflexion, 'ArrowRight');
    el.querySelector<HTMLElement>('#se-b0000001-k-k2-1')!.click();
    await f.whenStable();
    knopf(el, 'Alles aufklappen').click();
    await f.whenStable();
    knopf(el, 'Alles zuklappen').click();
    await f.whenStable();
    expect(el.querySelector('.ui-strukturentwurf__aktionen .ui-strukturentwurf__ziel')?.textContent?.trim()).toBe('Reflexion');
    knopf(el, 'Löschen').click();
    await f.whenStable();
    expect(titel(el)).toEqual(['Ausbreitung des Lichts', 'Brechung']);
  });
});

describe('ui_strukturentwurf (Element) — Paket BU-2', () => {
  it('die Symbole sind dieselben wie im Widget (ICONS): gleiche viewBox, gleicher Pfad', () => {
    const teile = (svg: string) => ({ viewBox: /viewBox="([^"]+)"/.exec(svg)![1], d: /<path d="([^"]+)"/.exec(svg)![1] });
    expect(SYMBOL).toEqual(teile(ICONS.edit_note));
    expect(PFEIL).toEqual(teile(ICONS.chevron_right));
  });

  it('Querschnitts-Review Q-3: auf einer Seite mit Trusted Types (String an innerHTML wirft) zeichnet das Element', async () => {
    const tt = vi.spyOn(Element.prototype, 'innerHTML', 'set').mockImplementation(() => {
      throw new TypeError('This document requires TrustedHTML assignment');
    });
    try {
      const { el } = await render(manifest.beispiele[2].daten as unknown as EntwurfDaten);
      expect(items(el).length).toBeGreaterThan(0);
      expect(el.querySelector('.ui-strukturentwurf__kopf svg path')?.getAttribute('d')).toBe(SYMBOL.d);
      expect(el.querySelector('.ui-strukturentwurf__pfeil svg')?.getAttribute('viewBox')).toBe(PFEIL.viewBox);
    } finally {
      tt.mockRestore();
    }
  });

  it('ein zweites Laden des Bündels definiert nicht noch einmal (Element-Vertrag)', () => {
    definiere();
    expect(() => definiere()).not.toThrow();
    expect(customElements.get(ELEMENT)).toBe(UiStrukturentwurfElement);
  });

  it('die Statuszeile bleibt dasselbe Element (sonst sagen Vorleser nichts an)', async () => {
    const { f, el } = await render(BEISPIEL);
    const zeile = el.querySelector('[role="status"]');
    knopf(el, 'Hoch').click();
    await f.whenStable();
    expect(el.querySelector('[role="status"]')).toBe(zeile);
    expect(ansage(el)).toBe('Schon ganz oben.');
  });

  it('ein Mausklick auf einen Eintrag: der Fokus ersetzt den Eintrag nicht, der Klick klappt auf', async () => {
    const { f, el } = await render(BEISPIEL);
    const reflexion = el.querySelector<HTMLElement>('#se-b0000001-k-k2')!;
    reflexion.focus();                                     // Maus: erst Fokus, dann Klick
    expect(el.querySelector('#se-b0000001-k-k2')).toBe(reflexion);
    reflexion.click();
    await f.whenStable();
    expect(el.querySelector('#se-b0000001-k-k2')?.getAttribute('aria-expanded')).toBe('true');
    expect(el.querySelector('.ui-strukturentwurf__aktionen .ui-strukturentwurf__ziel')?.textContent?.trim()).toBe('Reflexion');
  });

  it('beim Tippen bleibt das Feld dasselbe; der Baum zeigt den neuen Titel', async () => {
    const { f, el } = await render(BEISPIEL);
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.focus();
    feld.value = 'Licht';
    feld.dispatchEvent(new Event('input'));
    await f.whenStable();
    expect(el.querySelector('#se-b0000001-titel')).toBe(feld);
    expect(el.activeElement).toBe(feld);
    expect(titel(el)[0]).toBe('Licht');
    expect(el.querySelector('.ui-strukturentwurf__aktionen')?.getAttribute('aria-label')).toBe('Bearbeiten: Licht');
  });

  it('„beschäftigt“ schaltet nur den Übernehmen-Knopf, ein Feld bleibt beim Tippen stehen', async () => {
    const { f, el } = await render(BEISPIEL);
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.focus();
    f.knoten.beschaeftigt = true;
    expect(el.querySelector('#se-b0000001-titel')).toBe(feld);
    expect(knopf(el, 'Übernehmen').getAttribute('aria-disabled')).toBe('true');
    f.knoten.beschaeftigt = false;
    expect(knopf(el, 'Übernehmen').hasAttribute('aria-disabled')).toBe(false);
  });

  it('das Schlagwort-Feld zeigt nach dem Verlassen die bereinigte Liste', async () => {
    const { f, el } = await render(BEISPIEL);
    const kw = el.querySelectorAll<HTMLInputElement>('.ui-strukturentwurf__feld input')[1];
    kw.focus();
    kw.value = 'Licht, , licht, Schatten';
    kw.dispatchEvent(new Event('input'));
    kw.blur();
    await f.whenStable();
    expect(el.querySelectorAll<HTMLInputElement>('.ui-strukturentwurf__feld input')[1].value).toBe('Licht, Schatten');
  });
});

describe('ui_strukturentwurf (Element) — Review BU-2', () => {
  it('Befund 1: Rückgängig bei fokussiertem Feld zeigt im Feld den zurückgenommenen Stand', async () => {
    const { f, el } = await render(BEISPIEL);
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.focus();
    feld.value = 'Licht';
    feld.dispatchEvent(new Event('input'));
    knopf(el, 'Rückgängig').click();                       // Klick ohne Fokuswechsel (Tippen auf iOS, jsdom)
    await f.whenStable();
    expect(titel(el)[0]).toBe('Ausbreitung des Lichts');
    expect(el.querySelector<HTMLInputElement>('#se-b0000001-titel')!.value).toBe('Ausbreitung des Lichts');
  });

  it('Befund 5: neue Daten/neuer Kontext mit gleichem Stand lassen das Feld beim Tippen stehen (Cursor bleibt)', async () => {
    const { f, el } = await render(BEISPIEL);
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.focus();
    feld.value = 'Licht und Farbe';
    feld.dispatchEvent(new Event('input'));
    feld.setSelectionRange(5, 5);
    f.setzeKontext({ ...KONTEXT });                         // der Platzhalter setzt neu (neues Objekt)
    f.knoten.daten = { ...(BEISPIEL as unknown as Record<string, unknown>) };
    expect(el.querySelector('#se-b0000001-titel')).toBe(feld);
    expect(el.activeElement).toBe(feld);
    expect([feld.value, feld.selectionStart]).toEqual(['Licht und Farbe', 5]);
  });

  it('Befund 2: lehnt die Shell die Antwort ab, holt eine spätere Statuszeile den Fokus nicht', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Übernehmen').click();
    f.setzeKontext({ ...KONTEXT });                         // nicht angenommen: weiter offen
    const eingabe = document.createElement('input');
    document.body.appendChild(eingabe);
    eingabe.focus();
    f.setzeKontext({ ...KONTEXT, nurLesen: true });         // später veraltet (z. B. getippte Nachricht)
    expect(document.activeElement).toBe(eingabe);
  });

  it('Befund 2: während eines Zugs (live am Host) geht nichts hinaus, auch bevor der Spiegel ankommt', async () => {
    const { el } = await render(BEISPIEL);
    beschaeftigt = true;                                    // Host weiß es schon, das Element noch nicht
    knopf(el, 'Übernehmen').click();
    expect(h.antworten).not.toHaveBeenCalled();
  });

  it('Befund 6: eine unbekannte Herkunft zeigt keine falsche Marke', async () => {
    const { el } = await render({ ...BEISPIEL, quelle: 'unbekannt' } as unknown as EntwurfDaten);
    expect(el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('');
  });
});

describe('R4: Hinweise zur Struktur (Leitfaden, nur Warnungen)', () => {
  it('nennt Abweichungen in einem zugeklappten Abschnitt', async () => {
    const daten = { ...BEISPIEL, knoten: [
      { id: 'a', titel: 'Optik', kinder: [{ id: 'a1', titel: 'Linsen' }] },
      { id: 'b', titel: 'Arbeitsblätter' },
    ] } as unknown as EntwurfDaten;
    const { el } = await render(daten);
    const abschnitt = el.querySelector('details.ui-strukturentwurf__hinweise') as HTMLDetailsElement;
    expect(abschnitt).toBeTruthy();
    expect(abschnitt.open).toBe(false);
    expect(abschnitt.querySelector('summary')?.textContent).toBe('Hinweise zur Struktur (3)');
    const saetze = [...abschnitt.querySelectorAll('li')].map((li) => li.textContent);
    expect(saetze).toContain('„Optik“ hat genau einen Unterpunkt – fasse ihn mit dem Punkt zusammen oder ergänze weitere.');
    expect(saetze.some((s) => s?.startsWith('Oben stehen 2 Punkte'))).toBe(true);
  });

  it('Querschnitts-Review, Befund 5: die Überschrift nennt ALLE Hinweise, nicht nur die gezeigten', async () => {
    const knoten = Array.from({ length: 14 }, (_v, i) => ({ id: `k${i}`, titel: `Klasse ${i + 1}` }));
    const { el } = await render({ ...BEISPIEL, knoten } as unknown as EntwurfDaten);
    expect(el.querySelector('details.ui-strukturentwurf__hinweise summary')?.textContent).toBe('Hinweise zur Struktur (14)');
  });

  it('ohne Abweichung kein Abschnitt', async () => {
    const knoten = ['A', 'B', 'C', 'D', 'E'].map((t) => ({ id: t, titel: `Thema ${t}` }));
    const { el } = await render({ ...BEISPIEL, knoten } as unknown as EntwurfDaten);
    expect(el.querySelector('details.ui-strukturentwurf__hinweise')).toBeNull();
  });
});
