// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { type EntwurfDaten, UiStrukturentwurf } from './ui-strukturentwurf.component';

/**
 * Paket U2-e (Plan 2026-11-04, T-10 … T-12): der Strukturentwurf — Baum nach APG wie der Bestand,
 * dazu Bearbeiten (Leiste, Tasten, Detailfeld, Rückgängig), Übernehmen, Vormerken und Herunterladen.
 */
const beschaeftigt = signal(false);

function host() {
  return {
    antworten: vi.fn(), vormerken: vi.fn(), herunterladen: vi.fn(), beschaeftigt: vi.fn(() => beschaeftigt()),
  };
}

let h = host();

async function render(daten: EntwurfDaten, kontext: Partial<ModulKontext> = {}) {
  h = host();
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: h as unknown as ModulHost }],
  });
  const f = TestBed.createComponent(UiStrukturentwurf);
  f.componentRef.setInput('daten', daten);
  f.componentRef.setInput('kontext', {
    blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
    ...kontext,
  } satisfies ModulKontext);
  await f.whenStable();
  const el = f.nativeElement as HTMLElement;
  document.body.appendChild(el);
  return { f, el };
}

const BEISPIEL = manifest.beispiele[0].daten as unknown as EntwurfDaten;

const items = (el: HTMLElement) => [...el.querySelectorAll<HTMLElement>('[role="treeitem"]')];
const name = (el: HTMLElement, item: HTMLElement) =>
  el.querySelector(`#${item.getAttribute('aria-labelledby')}`)?.textContent?.trim();
const titel = (el: HTMLElement) => items(el).map((i) => name(el, i));
const knopf = (el: HTMLElement, text: string) =>
  [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement;
const ansage = (el: HTMLElement) => el.querySelector('[role="status"]')?.textContent?.trim();

async function taste(f: { whenStable(): Promise<unknown> }, item: HTMLElement, key: string, mehr: KeyboardEventInit = {}) {
  item.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...mehr }));
  await f.whenStable();
}

afterEach(() => {
  document.body.innerHTML = '';
  beschaeftigt.set(false);
});

describe('UiStrukturentwurf', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const daten = beispiel.daten as unknown as EntwurfDaten;
      const { el } = await render(daten);
      expect(items(el).length).toBe(daten.knoten.length);            // zugeklappt: erste Ebene
      expect(el.textContent).toContain(daten.titel);
    });
  }

  it('sagt im Kopf „Entwurf (KI)“ bzw. „Entwurf (aus WLO)“ — nie wie der Bestand', async () => {
    const { el } = await render(BEISPIEL);
    expect(el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Entwurf (KI)');
    const wlo = await render(manifest.beispiele[1].daten as unknown as EntwurfDaten);
    expect(wlo.el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Entwurf (aus WLO)');
    expect(wlo.el.textContent).toContain('mehr Punkte, als der Entwurf übernommen hat');
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
    expect(document.activeElement?.id).toBe('se-b0000001-k-k1-1');
  });

  it('Unterpunkt und Punkt danach; das Titelfeld bekommt den Fokus', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Punkt danach').click();
    await f.whenStable();
    expect(titel(el)).toEqual(['Ausbreitung des Lichts', 'Neuer Punkt', 'Reflexion', 'Brechung']);
    expect(document.activeElement?.id).toBe('se-b0000001-titel');
    expect(ansage(el)).toBe('Neuer Punkt. Titel eingeben.');
    const feld = document.activeElement as HTMLInputElement;
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
    expect(document.activeElement?.id).toBe('se-b0000001-k-k1');
    [, licht] = items(el);
    await taste(f, licht, 'Delete');
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
    expect(ansage(el)).toBe('„Ausbreitung des Lichts“ gelöscht. Rückgängig mit Strg+Z.');
    expect(document.activeElement?.id).toBe('se-b0000001-k-k3');         // der nächste Punkt
    await taste(f, document.activeElement as HTMLElement, 'z', { ctrlKey: true });
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
    beschaeftigt.set(true);
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
    expect(el.textContent).toContain('Übernommen.');
    expect(knopf(el, 'Übernehmen')).toBeUndefined();
    expect(knopf(el, 'Löschen')).toBeUndefined();
    expect(knopf(el, 'Als JSON herunterladen')).toBeDefined();
    // Nur lesend nichts vormerken — die Vormerkung wird zurückgenommen (Review U2, Befund 12).
    expect(h.vormerken.mock.calls.every(([d]) => d === null)).toBe(true);
  });

  it('veraltet ohne Antwort: der ursprüngliche Entwurf, nur lesend', async () => {
    const { f, el } = await render(BEISPIEL, { nurLesen: true });
    expect(el.textContent).toContain('Dieser Entwurf ist nicht mehr offen.');
    await taste(f, items(el)[0], 'Delete');
    expect(items(el)).toHaveLength(3);
  });

  it('leer: ein Knopf für den ersten Punkt', async () => {
    const { f, el } = await render({ titel: 'Leer', quelle: 'ki', knoten: [{ id: 'k1', titel: 'Nur' }] });
    knopf(el, 'Löschen').click();
    await f.whenStable();
    expect(el.textContent).toContain('Der Entwurf ist leer.');
    knopf(el, 'Punkt hinzufügen').click();
    await f.whenStable();
    expect(titel(el)).toEqual(['Neuer Punkt']);
  });

  it('englisch', async () => {
    const { el } = await render(BEISPIEL, { sprache: 'en' });
    expect(el.querySelector('.ui-strukturentwurf__marke')?.textContent).toBe('Draft (AI)');
    expect(knopf(el, 'Accept')).toBeDefined();
    expect(el.textContent).toContain('6 items');
  });
});

describe('UiStrukturentwurf — Review U2 (Frontend)', () => {
  const kontext = (mehr: Partial<ModulKontext> = {}): ModulKontext => ({
    blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null, ...mehr,
  });

  it('Befund 1: beantwortet → wieder offen (Zug kam nicht an) behält die Bearbeitung', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Löschen').click();
    await f.whenStable();
    knopf(el, 'Übernehmen').click();
    const [gesendet] = h.antworten.mock.calls[0];
    f.componentRef.setInput('kontext', kontext({ nurLesen: true, antwort: gesendet }));
    await f.whenStable();
    f.componentRef.setInput('kontext', kontext());           // `wiederOffen`: antwort null
    await f.whenStable();
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
    expect(h.vormerken).toHaveBeenLastCalledWith(expect.objectContaining({ bearbeitet: true }));
  });

  it('Befund 2: Esc im Titelfeld bleibt im Modul und führt in den Baum', async () => {
    const { f, el } = await render(BEISPIEL);
    const aussen = vi.fn();
    el.addEventListener('keydown', aussen);
    const feld = el.querySelector<HTMLInputElement>('#se-b0000001-titel')!;
    feld.focus();
    feld.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await f.whenStable();
    expect(aussen).not.toHaveBeenCalled();
    expect(document.activeElement?.id).toBe('se-b0000001-k-k1');
  });

  it('Befund 3: Strg+Z nach dem Einrücken und nach dem Hinzufügen lässt den Fokus im Baum', async () => {
    const { f, el } = await render(BEISPIEL);
    const brechung = () => el.querySelector<HTMLElement>('#se-b0000001-k-k3')!;
    brechung().focus();
    await taste(f, brechung(), 'ArrowRight', { altKey: true, shiftKey: true });
    await taste(f, brechung(), 'z', { ctrlKey: true });
    await f.whenStable();
    expect(document.activeElement?.id).toBe('se-b0000001-k-k3');
    expect(brechung().getAttribute('aria-level')).toBe('1');
    knopf(el, 'Punkt danach').click();
    await f.whenStable();
    const neu = items(el).find((i) => name(el, i) === 'Neuer Punkt')!;
    neu.focus();
    await taste(f, neu, 'z', { ctrlKey: true });
    await f.whenStable();
    expect(document.activeElement?.getAttribute('role')).toBe('treeitem');
    expect(titel(el)).not.toContain('Neuer Punkt');
  });

  it('Befund 4: nach „Übernehmen“ steht der Fokus auf der Statuszeile', async () => {
    const { f, el } = await render(BEISPIEL);
    knopf(el, 'Übernehmen').click();
    f.componentRef.setInput('kontext', kontext({ nurLesen: true, antwort: h.antworten.mock.calls[0][0] }));
    await f.whenStable();
    expect(document.activeElement?.textContent?.trim()).toBe('Übernommen.');
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
    expect(document.activeElement).toBe(knopf(el, 'Runter'));
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
    await taste(f, document.activeElement as HTMLElement, 'Z', { ctrlKey: true, shiftKey: true });
    expect(titel(el)).toEqual(['Reflexion', 'Brechung']);
  });

  it('Befund 15: wer den letzten Punkt löscht, landet auf „Punkt hinzufügen“', async () => {
    const { f, el } = await render({ titel: 'Leer', quelle: 'ki', knoten: [{ id: 'k1', titel: 'Nur' }] });
    const [nur] = items(el);
    nur.focus();
    await taste(f, nur, 'Delete');
    await f.whenStable();
    expect(document.activeElement).toBe(knopf(el, 'Punkt hinzufügen'));
  });
});

describe('UiStrukturentwurf — Gegenreview U2 (Befund 2)', () => {
  const kontext = (mehr: Partial<ModulKontext> = {}): ModulKontext => ({
    blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null, ...mehr,
  });

  it('ohne Bearbeitung bleibt „bearbeitet“ auch nach beantwortet → wieder offen falsch', async () => {
    const { f } = await render(BEISPIEL);
    f.componentRef.setInput('kontext', kontext({ nurLesen: true, antwort: { ...structuredClone(BEISPIEL), uebernommen: true, bearbeitet: false } }));
    await f.whenStable();
    f.componentRef.setInput('kontext', kontext());
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

describe('UiStrukturentwurf — drittes Review U2 (Befund 4)', () => {
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
