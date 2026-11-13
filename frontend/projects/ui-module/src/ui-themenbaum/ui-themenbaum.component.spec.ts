// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { UiThemenbaum, type UiThemenbaumDaten } from './ui-themenbaum.component';

/**
 * Paket U1-e: der Themenbaum nach dem WAI-ARIA-Muster „Tree View“ — Rollen und Zustände,
 * wandernder tabindex, Tasten ↑ ↓ → ← Pos1 Ende Enter/Leertaste. Aktionen für den aktiven Knoten
 * stehen unter dem Baum (keine Bedienelemente im Baumeintrag) und gehen über den Host.
 */
const beschaeftigt = signal(false);

/** Ein Zweig, den der Test später auflöst oder ablehnt (U1-h). */
interface Offen {
  readonly nodeId: string;
  aufloesen(daten: Record<string, unknown>): Promise<void>;
  ablehnen(status: number): Promise<void>;
}

let offene: Offen[] = [];

function host() {
  return {
    link: vi.fn((url: string) => ({ href: `${url}?bsid=s1`, hinweis: url.includes('fremd') ? 'Externe Seite' : '' })),
    aktion: vi.fn(),
    beschaeftigt: vi.fn(() => beschaeftigt()),
    // U1-h: jeder Zweig bleibt offen, bis der Test ihn auflöst — so ist „lädt“ prüfbar.
    zweig: vi.fn((nodeId: string) => new Promise<Record<string, unknown>>((ok, fehler) => {
      offene.push({
        nodeId,
        aufloesen: async (daten) => { ok(daten); await Promise.resolve(); },
        ablehnen: async (status) => { fehler(Object.assign(new Error(`HTTP ${status}`), { status })); await Promise.resolve(); },
      });
    })),
  };
}

let h = host();

async function render(daten: UiThemenbaumDaten, sprache: 'de' | 'en' = 'de') {
  h = host();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: h as unknown as ModulHost }],
  });
  const f = TestBed.createComponent(UiThemenbaum);
  f.componentRef.setInput('daten', daten);
  const kontext: ModulKontext = { blockId: 'b0000001', sprache, nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
  f.componentRef.setInput('kontext', kontext);
  await f.whenStable();
  const el = f.nativeElement as HTMLElement;
  document.body.appendChild(el);             // Fokus braucht ein Dokument
  return { f, el };
}

const BAUM = manifest.beispiele[0].daten as UiThemenbaumDaten;

function items(el: HTMLElement): HTMLElement[] {
  return [...el.querySelectorAll<HTMLElement>('[role="treeitem"]')];
}

function name(item: HTMLElement): string {
  const id = item.getAttribute('aria-labelledby') ?? '';
  return item.ownerDocument.getElementById(id)?.textContent?.trim() ?? '';
}

async function taste(f: { whenStable(): Promise<unknown> }, el: HTMLElement, key: string) {
  const ziel = (document.activeElement as HTMLElement | null) ?? el;
  ziel.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  await f.whenStable();
}

function aktiv(): string {
  return name(document.activeElement as HTMLElement);
}

function knopf(el: HTMLElement, text: string): HTMLButtonElement | undefined {
  return [...el.querySelectorAll<HTMLButtonElement>('.ui-themenbaum__aktionen button')]
    .find((b) => b.textContent?.trim() === text);
}

afterEach(() => {
  TestBed.resetTestingModule();
  document.body.innerHTML = '';
  beschaeftigt.set(false);
  offene = [];
});

describe('UiThemenbaum', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const daten = beispiel.daten as UiThemenbaumDaten;
      const { el } = await render(daten);
      expect(el.textContent?.trim()).not.toBe('');
      expect(items(el).length).toBe(daten.knoten.length);   // zugeklappt: nur die erste Ebene
    });
  }

  it('Baum mit Namen, Ebenen, Position und Zustand (Tree View)', async () => {
    const { el } = await render(BAUM);
    const baum = el.querySelector('[role="tree"]') as HTMLElement;
    expect(document.getElementById(baum.getAttribute('aria-labelledby') ?? '')?.textContent)
      .toContain('Mathematik');
    const [algebra, geometrie] = items(el);
    expect(name(algebra)).toBe('Algebra');
    expect(algebra.getAttribute('aria-level')).toBe('1');
    expect(algebra.getAttribute('aria-setsize')).toBe('2');
    expect(algebra.getAttribute('aria-posinset')).toBe('1');
    expect(algebra.getAttribute('aria-expanded')).toBe('false');
    // Ohne Kinder kein Auf/Zu-Zustand.
    expect(geometrie.hasAttribute('aria-expanded')).toBe(false);
    // Wandernder tabindex: genau ein Eintrag ist per Tab erreichbar.
    expect(items(el).map((i) => i.getAttribute('tabindex'))).toEqual(['0', '-1']);
  });

  it('ein Klick klappt auf; Kinder stehen in einer Gruppe auf Ebene 2', async () => {
    const { f, el } = await render(BAUM);
    items(el)[0].click();
    await f.whenStable();
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('true');
    const gruppe = items(el)[0].querySelector('[role="group"]') as HTMLElement;
    const kinder = [...gruppe.querySelectorAll<HTMLElement>('[role="treeitem"]')];
    expect(kinder.map(name)).toEqual(['Gleichungen', 'Terme']);
    expect(kinder.map((k) => k.getAttribute('aria-level'))).toEqual(['2', '2']);
    expect(kinder[1].getAttribute('aria-posinset')).toBe('2');
    // Der Name des Elternknotens enthält nicht die Kinder (aria-labelledby statt Inhalt).
    expect(name(items(el)[0])).toBe('Algebra');
  });

  it('Tastatur: ↓ ↑ → ← Pos1 Ende und Enter', async () => {
    const { f, el } = await render(BAUM);
    items(el)[0].focus();
    await taste(f, el, 'ArrowDown');
    expect(aktiv()).toBe('Geometrie');
    await taste(f, el, 'ArrowUp');
    expect(aktiv()).toBe('Algebra');
    await taste(f, el, 'ArrowRight');                     // öffnet
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('true');
    expect(aktiv()).toBe('Algebra');
    await taste(f, el, 'ArrowRight');                     // in das erste Kind
    expect(aktiv()).toBe('Gleichungen');
    await taste(f, el, 'End');
    expect(aktiv()).toBe('Geometrie');
    await taste(f, el, 'ArrowUp');
    expect(aktiv()).toBe('Terme');
    await taste(f, el, 'ArrowLeft');                      // zum Elternknoten
    expect(aktiv()).toBe('Algebra');
    await taste(f, el, 'ArrowLeft');                      // schließt
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('false');
    await taste(f, el, 'Enter');                          // öffnet wieder
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('true');
    await taste(f, el, ' ');                              // Leertaste schließt
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('false');
    await taste(f, el, 'End');
    await taste(f, el, 'Home');
    expect(aktiv()).toBe('Algebra');
    expect(items(el).filter((i) => i.getAttribute('tabindex') === '0').map(name)).toEqual(['Algebra']);
  });

  it('→ → im selben Frame: der Fokus landet im eben aufgeklappten Kind (CI-Kippler)', async () => {
    const { f, el } = await render(BAUM);
    items(el)[0].focus();
    const druecke = (key: string) => (document.activeElement as HTMLElement).dispatchEvent(
      new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
    druecke('ArrowRight');                                // öffnet — die Kinder sind noch nicht gezeichnet
    druecke('ArrowRight');                                // ins erste Kind
    await f.whenStable();
    expect(aktiv()).toBe('Gleichungen');
  });

  it('ein Tastendruck im Kind wirkt einmal (nicht noch einmal im Eltern-Eintrag)', async () => {
    const { f, el } = await render(BAUM);
    items(el)[0].focus();
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowRight');                     // Gleichungen
    await taste(f, el, 'ArrowDown');
    expect(aktiv()).toBe('Terme');                        // nicht zwei Schritte bis Geometrie
  });

  it('die Auswahl folgt dem Fokus: der aktive Eintrag ist ausgewählt (für die Aktionsleiste)', async () => {
    const { f, el } = await render(BAUM);
    expect(items(el).map((i) => i.getAttribute('aria-selected'))).toEqual(['true', 'false']);
    items(el)[0].focus();
    await taste(f, el, 'ArrowDown');
    expect(items(el).map((i) => i.getAttribute('aria-selected'))).toEqual(['false', 'true']);
  });

  it('behandelte Tasten scrollen die Seite nicht (preventDefault)', async () => {
    const { el } = await render(BAUM);
    items(el)[0].focus();
    const e = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true });
    items(el)[0].dispatchEvent(e);
    expect(e.defaultPrevented).toBe(true);
    const tab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    items(el)[0].dispatchEvent(tab);
    expect(tab.defaultPrevented).toBe(false);
  });

  it('Aktionen für den aktiven Knoten gehen über den Host', async () => {
    const { f, el } = await render(BAUM);
    const leiste = el.querySelector('.ui-themenbaum__aktionen') as HTMLElement;
    expect(leiste.getAttribute('role')).toBe('group');
    expect(leiste.getAttribute('aria-label')).toBe('Aktionen für Algebra');
    knopf(el, 'Inhalte anzeigen')!.click();
    expect(h.aktion).toHaveBeenCalledWith('sammlung', { nodeId: 'bbbb-2222', title: 'Algebra' });
    // U1-h: kein Knopf „Unterthemen öffnen“ mehr — Aufklappen lädt im selben Baum.
    expect(knopf(el, 'Unterthemen öffnen')).toBeUndefined();
    const link = leiste.querySelector('a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('https://wirlernenonline.de/sammlung/algebra?bsid=s1');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');

    // Geometrie: erste Ebene ohne Kinder und ohne „mehr“ — tiefer gibt es nichts.
    items(el)[1].click();
    await f.whenStable();
    expect(leiste.getAttribute('aria-label')).toBe('Aktionen für Geometrie');
    expect(h.zweig).not.toHaveBeenCalled();
  });

  it('Knoten der zweiten Ebene ohne Adresse: kein Link; ein Klick aufs Kind klappt den Eltern nicht zu', async () => {
    const { f, el } = await render(BAUM);
    items(el)[0].click();
    await f.whenStable();
    const terme = items(el).find((i) => name(i) === 'Terme')!;
    terme.click();
    await f.whenStable();
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('true');
    expect(el.querySelector('.ui-themenbaum__aktionen a')).toBeNull();
  });

  it('Anzahl, „weitere“ und der Hinweis auf gekürzte Zweige sind sichtbar', async () => {
    const { f, el } = await render(BAUM);
    expect(items(el)[1].textContent).toContain('7 Inhalte');
    expect(items(el)[0].textContent).toContain('weitere');
    expect(el.querySelector('.ui-themenbaum__hinweis')?.textContent).toContain('Nicht alle Unterthemen');
    items(el)[0].click();
    await f.whenStable();
    expect(items(el)[1].textContent).toContain('12 Inhalte');
  });

  it('ohne Unterthemen: Leerzustand, Aktionen für die Sammlung selbst', async () => {
    const { el } = await render(manifest.beispiele[2].daten as UiThemenbaumDaten);
    expect(el.querySelector('[role="tree"]')).toBeNull();
    expect(el.querySelector('.ui-themenbaum__leer')?.textContent).toContain('keine Unterthemen');
    knopf(el, 'Inhalte anzeigen')!.click();
    expect(h.aktion).toHaveBeenCalledWith('sammlung', { nodeId: 'hhhh-8888', title: 'Optik' });
  });

  it('ohne Unterthemen und ohne Kennung: keine Aktionsleiste', async () => {
    const { el } = await render({ knoten: [] });
    expect(el.querySelector('.ui-themenbaum__aktionen')).toBeNull();
  });

  // ── Review U1-e ────────────────────────────────────────────────────────

  const MEHR_OBEN = manifest.beispiele[3].daten as UiThemenbaumDaten;

  it('mehr Themen oben, als der Baum zeigt: Hinweis mit Link zur Sammlung in WLO (Befund 2)', async () => {
    const { el } = await render(MEHR_OBEN);
    const hinweis = el.querySelector('.ui-themenbaum__hinweis--wurzel') as HTMLElement;
    expect(hinweis.textContent).toContain('Es gibt mehr Unterthemen, als hier stehen.');
    const link = hinweis.querySelector('a') as HTMLAnchorElement;
    expect(link.textContent?.trim()).toBe('Alle in WLO ansehen');
    expect(link.getAttribute('href')).toBe(`${MEHR_OBEN.wurzel_url}?bsid=s1`);
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    // Ohne Kürzung oben kein solcher Hinweis.
    TestBed.resetTestingModule();
    const ohne = await render(BAUM);
    expect(ohne.el.querySelector('.ui-themenbaum__hinweis--wurzel')).toBeNull();
  });

  it('mehr Themen oben, ohne Adresse: Hinweis ohne Link; englisch', async () => {
    const { el } = await render({ ...MEHR_OBEN, wurzel_url: undefined }, 'en');
    const hinweis = el.querySelector('.ui-themenbaum__hinweis--wurzel') as HTMLElement;
    expect(hinweis.textContent).toContain('There are more subtopics than shown here.');
    expect(hinweis.querySelector('a')).toBeNull();
  });

  it('leerer Baum mit Adresse der Wurzel: „In WLO öffnen“ für die Sammlung selbst', async () => {
    const { el } = await render({ ...MEHR_OBEN, wurzel_mehr: undefined, knoten: [] });
    const link = el.querySelector('.ui-themenbaum__aktionen a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe(`${MEHR_OBEN.wurzel_url}?bsid=s1`);
  });

  it('Anzahl und „weitere“ gehören zur Beschreibung des Eintrags (Befund 4)', async () => {
    const { f, el } = await render(BAUM);
    const beschreibung = (item: HTMLElement) => (item.getAttribute('aria-describedby') ?? '')
      .split(' ').filter(Boolean).map((id) => document.getElementById(id)?.textContent?.trim());
    const [algebra, geometrie] = items(el);
    expect(beschreibung(algebra)).toEqual(['weitere']);
    expect(beschreibung(geometrie)).toEqual(['7 Inhalte']);
    items(el)[0].click();
    await f.whenStable();
    const [gleichungen, terme] = [...items(el)[0].querySelectorAll<HTMLElement>('[role="treeitem"]')];
    expect(beschreibung(gleichungen)).toEqual(['12 Inhalte']);
    expect(terme.hasAttribute('aria-describedby')).toBe(false);
  });

  it('Enter auf einem Eintrag ohne Kinder zeigt dessen Inhalte (Befund 12)', async () => {
    const { f, el } = await render(BAUM);
    items(el)[1].focus();                                  // Geometrie: ohne Kinder
    await taste(f, el, 'Enter');
    expect(h.aktion).toHaveBeenCalledWith('sammlung', { nodeId: 'eeee-5555', title: 'Geometrie' });
    // Mit Kindern klappt Enter (wie bisher) und ruft nichts.
    h.aktion.mockClear();
    items(el)[0].focus();
    await taste(f, el, 'Enter');
    expect(items(el)[0].getAttribute('aria-expanded')).toBe('true');
    expect(h.aktion).not.toHaveBeenCalled();
    // U1-h: ein Kind der zweiten Ebene hat unbekannte Unterthemen — Enter klappt es auf (lädt).
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'Enter');
    expect(h.zweig).toHaveBeenCalledWith('cccc-3333');
    expect(h.aktion).not.toHaveBeenCalled();
  });

  it('Enter auf einem Blatt während eines Zugs tut nichts', async () => {
    beschaeftigt.set(true);
    const { f, el } = await render(BAUM);
    items(el)[1].focus();
    await taste(f, el, 'Enter');
    expect(h.aktion).not.toHaveBeenCalled();
  });

  // Review U1 gesamt, Befund 6: `aria-disabled` statt `disabled` — fiel der Knopf beim Zugbeginn aus
  // der Tab-Reihenfolge, ging der Fokus verloren (WCAG 2.4.3).
  it('während eines Zugs ist „Inhalte anzeigen“ gesperrt (aria-disabled, bleibt fokussierbar) — Klick tut nichts', async () => {
    beschaeftigt.set(true);
    const { el } = await render(BAUM);
    const k = knopf(el, 'Inhalte anzeigen')!;
    expect(k.disabled).toBe(false);
    expect(k.getAttribute('aria-disabled')).toBe('true');
    k.click();
    expect(h.aktion).not.toHaveBeenCalled();
  });

  it('englische Texte', async () => {
    const { el } = await render(BAUM, 'en');
    expect(el.textContent).toContain('Subtopics of Mathematik');
    expect(knopf(el, 'Show contents')).toBeDefined();
    expect(items(el)[1].textContent).toContain('7 items');
    expect(el.querySelector('.ui-themenbaum__aktionen')?.getAttribute('aria-label')).toBe('Actions for Algebra');
  });

  it('die Element-Kennungen sind je Block eindeutig', async () => {
    const { f, el } = await render(BAUM);
    items(el)[0].click();
    await f.whenStable();
    const ids = [...el.querySelectorAll('[id]')].map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.every((id) => id.startsWith('tb-b0000001-'))).toBe(true);
  });
});

// ── U1-h: Unterthemen im selben Baum aufklappen ─────────────────────────

describe('UiThemenbaum — Nachladen im Baum (U1-h)', () => {
  /** Algebra auf, dann das Kind „Terme“ (unbekannte Unterthemen) aktiv. */
  async function termeAktiv() {
    const r = await render(BAUM);
    items(r.el)[0].focus();
    await taste(r.f, r.el, 'ArrowRight');                  // Algebra auf (lädt „weitere“)
    await taste(r.f, r.el, 'ArrowRight');                  // Gleichungen
    await taste(r.f, r.el, 'ArrowDown');                   // Terme
    return r;
  }

  function eintrag(el: HTMLElement, titel: string): HTMLElement {
    return items(el).find((i) => name(i) === titel)!;
  }

  function beschreibung(item: HTMLElement): string[] {
    return (item.getAttribute('aria-describedby') ?? '').split(' ').filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent?.trim() ?? '');
  }

  function ansage(el: HTMLElement): string {
    return el.querySelector('[aria-live="polite"]')?.textContent?.trim() ?? '';
  }

  const ZWEIG = {
    knoten: [
      { id: 'x1', titel: 'Klammern', kinder: [{ id: 'x2', titel: 'Ausmultiplizieren' }] },
      { id: 'x3', titel: 'Faktorisieren', anzahl: 4 },
    ],
  };

  it('ein Knoten der zweiten Ebene ist aufklappbar; Aufklappen lädt über den Host, ohne Zug', async () => {
    const { f, el } = await termeAktiv();
    const terme = eintrag(el, 'Terme');
    expect(terme.getAttribute('aria-expanded')).toBe('false');
    await taste(f, el, 'ArrowRight');
    expect(h.zweig).toHaveBeenLastCalledWith('dddd-4444');
    expect(h.aktion).not.toHaveBeenCalled();
    // Lädt: busy am Eintrag, ein sichtbarer Hinweis, der Fokus bleibt.
    expect(terme.getAttribute('aria-expanded')).toBe('true');
    expect(terme.getAttribute('aria-busy')).toBe('true');
    expect(beschreibung(terme)).toContain('lädt …');
    expect(aktiv()).toBe('Terme');
  });

  it('die geladenen Unterthemen stehen im selben Baum: Ebene, Position, Größe; angesagt', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.find((o) => o.nodeId === 'dddd-4444')!.aufloesen(ZWEIG);
    await f.whenStable();

    const terme = eintrag(el, 'Terme');
    expect(terme.hasAttribute('aria-busy')).toBe(false);
    const gruppe = terme.querySelector(':scope > [role="group"]') as HTMLElement;
    const kinder = [...gruppe.querySelectorAll<HTMLElement>(':scope > [role="treeitem"]')];
    expect(kinder.map(name)).toEqual(['Klammern', 'Faktorisieren']);
    expect(kinder.map((k) => k.getAttribute('aria-level'))).toEqual(['3', '3']);
    expect(kinder.map((k) => k.getAttribute('aria-setsize'))).toEqual(['2', '2']);
    expect(kinder.map((k) => k.getAttribute('aria-posinset'))).toEqual(['1', '2']);
    expect(el.querySelectorAll('[role="tree"]').length).toBe(1);         // kein zweiter Baum
    expect(ansage(el)).toBe('2 Unterthemen von Terme geladen.');
    expect(aktiv()).toBe('Terme');
    expect(items(el).filter((i) => i.getAttribute('tabindex') === '0').map(name)).toEqual(['Terme']);
  });

  it('mitgelieferte Kinder klappen ohne Laden auf; ein Knoten ohne Kinder ist ein Blatt; tiefer wieder aufklappbar', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.aufloesen(ZWEIG);
    await f.whenStable();
    const aufrufe = h.zweig.mock.calls.length;

    await taste(f, el, 'ArrowRight');                      // in „Klammern“
    expect(aktiv()).toBe('Klammern');
    await taste(f, el, 'ArrowRight');                      // Klammern auf: Kinder sind bekannt
    expect(h.zweig.mock.calls.length).toBe(aufrufe);
    const aus = eintrag(el, 'Ausmultiplizieren');
    expect(aus.getAttribute('aria-level')).toBe('4');
    expect(aus.getAttribute('aria-expanded')).toBe('false');            // unbekannt → aufklappbar
    expect(eintrag(el, 'Faktorisieren').hasAttribute('aria-expanded')).toBe(false);   // bekannt leer
  });

  it('ohne Unterthemen wird der Knoten ein Blatt: Hinweis, Ansage, Enter zeigt dann die Inhalte', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.aufloesen({ knoten: [] });
    await f.whenStable();

    const terme = eintrag(el, 'Terme');
    expect(terme.hasAttribute('aria-expanded')).toBe(false);
    expect(beschreibung(terme)).toContain('keine Unterthemen');
    expect(ansage(el)).toBe('Terme hat keine Unterthemen.');
    await taste(f, el, 'Enter');
    expect(h.aktion).toHaveBeenCalledWith('sammlung', { nodeId: 'dddd-4444', title: 'Terme' });
  });

  it('ein Fehler steht am Knoten; „Erneut laden“ und erneutes Aufklappen versuchen es noch einmal', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();

    const terme = eintrag(el, 'Terme');
    expect(terme.hasAttribute('aria-busy')).toBe(false);
    expect(beschreibung(terme)).toContain('nicht geladen');
    expect(ansage(el)).toBe('Die Unterthemen von Terme ließen sich nicht laden.');
    expect(aktiv()).toBe('Terme');

    knopf(el, 'Erneut laden')!.click();
    await f.whenStable();
    expect(h.zweig.mock.calls.filter(([id]) => id === 'dddd-4444').length).toBe(2);
    await offene.at(-1)!.aufloesen(ZWEIG);
    await f.whenStable();
    expect(eintrag(el, 'Klammern')).toBeDefined();
    expect(knopf(el, 'Erneut laden')).toBeUndefined();

    // Erneutes Aufklappen nach einem Fehler lädt ebenso (hier ein tieferer Knoten).
    eintrag(el, 'Terme').focus();
    await taste(f, el, 'ArrowRight');                       // in Klammern
    await taste(f, el, 'ArrowRight');                       // auf
    await taste(f, el, 'ArrowRight');                       // in Ausmultiplizieren
    await taste(f, el, 'ArrowRight');                       // lädt
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();
    await taste(f, el, 'ArrowRight');                       // Review U1-h, 2: direkt der zweite Versuch
    expect(h.zweig.mock.calls.filter(([id]) => id === 'x2').length).toBe(2);
  });

  // Review U1-h, Befund 2: ohne bekannte Kinder schließt ein Fehler den Eintrag wieder — sonst
  // stünde aria-expanded="true" ohne Gruppe da, und Enter/Klick klappten zu statt neu zu laden.
  it('nach einem Fehler ist ein Knoten ohne bekannte Kinder zu; →, Enter und Klick versuchen es direkt neu', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();
    const terme = eintrag(el, 'Terme');
    expect(terme.getAttribute('aria-expanded')).toBe('false');
    expect(terme.querySelector('[role="group"]')).toBeNull();
    expect(beschreibung(terme)).toContain('nicht geladen');

    await taste(f, el, 'Enter');
    expect(h.zweig.mock.calls.filter(([id]) => id === 'dddd-4444').length).toBe(2);
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();
    expect(eintrag(el, 'Terme').getAttribute('aria-expanded')).toBe('false');

    eintrag(el, 'Terme').click();
    await f.whenStable();
    expect(h.zweig.mock.calls.filter(([id]) => id === 'dddd-4444').length).toBe(3);
  });

  it('nach einem Fehler bleibt ein gekürzter Zweig mit mitgelieferten Kindern offen', async () => {
    const { f, el } = await termeAktiv();                   // Algebra („weitere“) lädt
    await offene.find((o) => o.nodeId === 'bbbb-2222')!.ablehnen(502);
    await f.whenStable();
    const algebra = eintrag(el, 'Algebra');
    expect(algebra.getAttribute('aria-expanded')).toBe('true');
    expect(eintrag(el, 'Terme')).toBeDefined();
    expect(beschreibung(algebra)).toContain('nicht geladen');
  });

  // Review U1-h, Befund 3: nur ein Fokus IM BAUM wird nach dem Laden zurückgeholt.
  it('wer während des Ladens in die Aktionsleiste geht, bleibt dort', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');                       // Terme lädt
    const knopfInhalte = knopf(el, 'Inhalte anzeigen')!;
    knopfInhalte.focus();
    await offene.at(-1)!.aufloesen(ZWEIG);
    await f.whenStable();
    expect(eintrag(el, 'Klammern')).toBeDefined();
    expect(document.activeElement).toBe(knopfInhalte);
  });

  // Review U1-h, Befund 4: ein Zweig, der einen Vorfahren wieder enthält, endet als Blatt.
  it('ein Kreis im Repositorium (Vorfahr im nachgeladenen Zweig) wird ein Blatt, kein Endlos-Baum', async () => {
    const { f, el } = await termeAktiv();
    await offene.find((o) => o.nodeId === 'bbbb-2222')!.aufloesen({ knoten: [
      { id: 'dddd-4444', titel: 'Terme', mehr: true },
    ] });
    await f.whenStable();
    eintrag(el, 'Terme').focus();
    await taste(f, el, 'ArrowRight');                       // Terme lädt
    await offene.find((o) => o.nodeId === 'dddd-4444')!.aufloesen({ knoten: [
      { id: 'bbbb-2222', titel: 'Algebra', kinder: [{ id: 'dddd-4444', titel: 'Terme' }] },
    ] });
    await f.whenStable();

    const wiederholt = items(el).filter((i) => name(i) === 'Algebra');
    expect(wiederholt.map((i) => i.getAttribute('aria-level'))).toEqual(['1', '3']);
    expect(wiederholt[1].hasAttribute('aria-expanded')).toBe(false);
    expect(wiederholt[1].querySelector('[role="group"]')).toBeNull();
    expect(items(el).length).toBe(4);                       // Algebra, Terme, Algebra, Geometrie
    await taste(f, el, 'ArrowRight');                       // in die Wiederholung
    expect(aktiv()).toBe('Algebra');
    const aufrufe = h.zweig.mock.calls.length;
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'Enter');                            // Blatt: zeigt die Inhalte
    expect(h.zweig.mock.calls.length).toBe(aufrufe);
    expect(h.aktion).toHaveBeenCalledWith('sammlung', { nodeId: 'bbbb-2222', title: 'Algebra' });
  });

  // Review U1-h, Befund 10: eigene Ansage bei 429; derselbe Text wird erneut angesagt.
  it('429: „zu viele Anfragen“ am Eintrag und angesagt; „Erneut laden“ bleibt', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.ablehnen(429);
    await f.whenStable();
    const terme = eintrag(el, 'Terme');
    expect(beschreibung(terme)).toContain('zu viele Anfragen – bitte kurz warten');
    expect(ansage(el)).toBe('Zu viele Anfragen – bitte kurz warten und die Unterthemen von Terme dann erneut laden.');
    expect(knopf(el, 'Erneut laden')).toBeDefined();
    expect(h.zweig.mock.calls.filter(([id]) => id === 'dddd-4444').length).toBe(1);   // kein Selbstversuch
  });

  it('429 englisch', async () => {
    const { f, el } = await render(BAUM, 'en');
    items(el)[0].focus();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.ablehnen(429);
    await f.whenStable();
    expect(beschreibung(eintrag(el, 'Algebra'))).toContain('too many requests – please wait a moment');
    expect(ansage(el)).toBe('Too many requests – please wait a moment, then retry loading the subtopics of Algebra.');
  });

  it('dieselbe Meldung zweimal: die Statuszeile wird dazwischen geleert (erneute Ansage)', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();
    const zeile = el.querySelector('[aria-live="polite"]') as HTMLElement;
    const texte: string[] = [];
    const beobachter = new MutationObserver(() => texte.push(zeile.textContent?.trim() ?? ''));
    beobachter.observe(zeile, { childList: true, characterData: true, subtree: true });

    knopf(el, 'Erneut laden')!.click();
    await f.whenStable();
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();
    expect(ansage(el)).toBe('');                            // erst geleert …
    await new Promise((r) => setTimeout(r, 150));           // … dann in einem eigenen Schritt gesetzt
    await f.whenStable();
    beobachter.disconnect();
    expect(texte).toEqual(['', 'Die Unterthemen von Terme ließen sich nicht laden.']);
  });

  it('403 (hier nicht angeboten): kein neuer Versuch, der Knoten bleibt ohne Auf/Zu', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.ablehnen(403);
    await f.whenStable();
    const terme = eintrag(el, 'Terme');
    expect(terme.hasAttribute('aria-expanded')).toBe(false);
    expect(knopf(el, 'Erneut laden')).toBeUndefined();
    await taste(f, el, 'ArrowRight');
    expect(h.zweig.mock.calls.filter(([id]) => id === 'dddd-4444').length).toBe(1);
  });

  for (const status of [404, 422]) {
    it(`R3-d: ${status} (Sitzung weg bzw. keine gültige Kennung): kein „Erneut laden“`, async () => {
      const { f, el } = await termeAktiv();
      await taste(f, el, 'ArrowRight');
      await offene.at(-1)!.ablehnen(status);
      await f.whenStable();
      expect(knopf(el, 'Erneut laden')).toBeUndefined();
    });
  }

  it('während des Ladens löst ein zweites Aufklappen keinen zweiten Abruf aus', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowLeft');
    await taste(f, el, 'ArrowRight');
    expect(h.zweig.mock.calls.filter(([id]) => id === 'dddd-4444').length).toBe(1);
  });

  it('„weitere“: die bekannten Kinder stehen sofort, die volle Liste ersetzt sie; der Fokus bleibt beim selben Thema', async () => {
    const { f, el } = await termeAktiv();                   // Algebra lädt seit dem Aufklappen
    expect(h.zweig).toHaveBeenCalledWith('bbbb-2222');
    expect(eintrag(el, 'Algebra').getAttribute('aria-busy')).toBe('true');
    expect(aktiv()).toBe('Terme');

    await offene.find((o) => o.nodeId === 'bbbb-2222')!.aufloesen({ knoten: [
      { id: 'zz-1', titel: 'Bruchterme' }, { id: 'cccc-3333', titel: 'Gleichungen', anzahl: 12 },
      { id: 'dddd-4444', titel: 'Terme' },
    ] });
    await f.whenStable();

    const algebra = eintrag(el, 'Algebra');
    const kinder = [...algebra.querySelectorAll<HTMLElement>(':scope > [role="group"] > [role="treeitem"]')];
    expect(kinder.map(name)).toEqual(['Bruchterme', 'Gleichungen', 'Terme']);
    expect(kinder.map((k) => k.getAttribute('aria-setsize'))).toEqual(['3', '3', '3']);
    expect(beschreibung(algebra)).not.toContain('weitere');                // jetzt vollständig
    expect(aktiv()).toBe('Terme');
    expect(eintrag(el, 'Terme').getAttribute('aria-posinset')).toBe('3');
    expect(items(el).filter((i) => i.getAttribute('tabindex') === '0').map(name)).toEqual(['Terme']);
    expect(ansage(el)).toBe('3 Unterthemen von Algebra geladen.');
  });

  it('bleibt ein Zweig nach dem Laden gekürzt, bleibt „weitere“ — ohne neuen Abruf', async () => {
    const { f, el } = await termeAktiv();
    await offene.find((o) => o.nodeId === 'bbbb-2222')!.aufloesen({
      knoten: [{ id: 'cccc-3333', titel: 'Gleichungen' }], wurzel_mehr: true,
    });
    await f.whenStable();
    const algebra = eintrag(el, 'Algebra');
    expect(beschreibung(algebra)).toContain('weitere');
    algebra.focus();
    await taste(f, el, 'ArrowLeft');
    await taste(f, el, 'ArrowRight');
    expect(h.zweig.mock.calls.filter(([id]) => id === 'bbbb-2222').length).toBe(1);
  });

  it('Tiefe: ab Ebene 8 wird nicht mehr nachgeladen (dann bleibt „In WLO öffnen“)', async () => {
    const { f, el } = await termeAktiv();
    // Jeder Zweig liefert eine Ebene mit Kind (zwei Ebenen je Abruf).
    let n = 0;
    async function naechsteEbene() {
      n += 1;
      await taste(f, el, 'ArrowRight');                    // aufklappen → lädt
      await offene.at(-1)!.aufloesen({ knoten: [{ id: `t${n}`, titel: `T${n}`, kinder: [{ id: `u${n}`, titel: `U${n}` }] }] });
      await f.whenStable();
      await taste(f, el, 'ArrowRight');                    // in T
      await taste(f, el, 'ArrowRight');                    // T auf (bekannt)
      await taste(f, el, 'ArrowRight');                    // in U
    }
    await naechsteEbene();                                  // Terme (2) → T1 (3), U1 (4)
    await naechsteEbene();                                  // U1 → T2 (5), U2 (6)
    await naechsteEbene();                                  // U2 → T3 (7), U3 (8)
    const u3 = eintrag(el, 'U3');
    expect(aktiv()).toBe('U3');
    expect(u3.getAttribute('aria-level')).toBe('8');
    expect(u3.hasAttribute('aria-expanded')).toBe(false);
    const aufrufe = h.zweig.mock.calls.length;
    await taste(f, el, 'ArrowRight');
    expect(h.zweig.mock.calls.length).toBe(aufrufe);
  });

  // Review U1-h, Befund 6: ein gekürzter Knoten auf Ebene 7 lädt Kinder mit eigenen Kindern —
  // sichtbar bleibt trotzdem höchstens Ebene 8.
  it('Tiefe: höchstens Ebene 8 ist sichtbar, auch wenn ein Zweig tiefere Kinder mitbringt', async () => {
    const { f, el } = await termeAktiv();
    let n = 0;
    async function naechsteEbene(zweig?: Record<string, unknown>) {
      n += 1;
      await taste(f, el, 'ArrowRight');                    // aufklappen → lädt
      await offene.at(-1)!.aufloesen(zweig ?? { knoten: [{ id: `t${n}`, titel: `T${n}`, kinder: [{ id: `u${n}`, titel: `U${n}` }] }] });
      await f.whenStable();
      await taste(f, el, 'ArrowRight');                    // in T
    }
    await naechsteEbene();                                  // T1 (3)
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowRight');                       // U1 (4)
    await naechsteEbene();                                  // T2 (5)
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowRight');                       // U2 (6)
    await naechsteEbene({ knoten: [{ id: 't3', titel: 'T3', mehr: true, kinder: [{ id: 'u3', titel: 'U3' }] }] });
    expect(aktiv()).toBe('T3');                             // Ebene 7, gekürzt
    await taste(f, el, 'ArrowRight');                       // auf: lädt die volle Liste
    expect(h.zweig).toHaveBeenLastCalledWith('t3');
    await offene.at(-1)!.aufloesen({ knoten: [{ id: 'v', titel: 'V', kinder: [{ id: 'w', titel: 'W' }] }] });
    await f.whenStable();

    const v = eintrag(el, 'V');
    expect(v.getAttribute('aria-level')).toBe('8');
    expect(v.hasAttribute('aria-expanded')).toBe(false);
    await taste(f, el, 'ArrowRight');                       // in V
    expect(aktiv()).toBe('V');
    await taste(f, el, 'ArrowRight');
    expect(el.querySelector('[aria-level="9"]')).toBeNull();
    expect(eintrag(el, 'W')).toBeUndefined();
  });

  it('eine Ansage-Zeile für Vorleser ist da (höflich), anfangs leer', async () => {
    const { el } = await render(BAUM);
    const zeile = el.querySelector('[aria-live="polite"]') as HTMLElement;
    expect(zeile.getAttribute('role')).toBe('status');
    expect(zeile.textContent?.trim()).toBe('');
  });

  it('englische Texte beim Laden, Fehler und Ergebnis', async () => {
    const { f, el } = await render(BAUM, 'en');
    items(el)[0].focus();
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowDown');                        // Terme
    await taste(f, el, 'ArrowRight');
    expect(beschreibung(eintrag(el, 'Terme'))).toContain('loading …');
    await offene.at(-1)!.ablehnen(502);
    await f.whenStable();
    expect(ansage(el)).toBe('The subtopics of Terme could not be loaded.');
    knopf(el, 'Retry loading')!.click();
    await offene.at(-1)!.aufloesen({ knoten: [{ id: 'x1', titel: 'Klammern' }] });
    await f.whenStable();
    expect(ansage(el)).toBe('1 subtopic of Terme loaded.');
  });

  it('die Element-Kennungen bleiben auch tief unten je Block eindeutig', async () => {
    const { f, el } = await termeAktiv();
    await taste(f, el, 'ArrowRight');
    await offene.at(-1)!.aufloesen(ZWEIG);
    await f.whenStable();
    await taste(f, el, 'ArrowRight');
    await taste(f, el, 'ArrowRight');
    const ids = [...el.querySelectorAll('[id]')].map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.every((id) => id.startsWith('tb-b0000001-'))).toBe(true);
  });
});

describe('UiThemenbaum — Bestand und Entwurf (Paket U2)', () => {
  const knopf = (el: HTMLElement, text: string) =>
    [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === text);

  it('sagt im Kopf „Aus WLO“ — der Bestand sieht nie aus wie ein Entwurf', async () => {
    const { el } = await render(BAUM);
    expect(el.querySelector('.ui-themenbaum__marke')?.textContent).toBe('Aus WLO');
    TestBed.resetTestingModule();
    const en = await render(BAUM, 'en');
    expect(en.el.querySelector('.ui-themenbaum__marke')?.textContent).toBe('From WLO');
  });

  it('„Als Entwurf bearbeiten“ öffnet die Wurzel als Entwurf (Host-Aktion)', async () => {
    const { el } = await render(BAUM);
    knopf(el, 'Als Entwurf bearbeiten')!.click();
    expect(h.aktion).toHaveBeenCalledWith('alsEntwurf', { nodeId: 'aaaa-1111', title: 'Mathematik' });
  });

  it('ohne Wurzel keine Brücke; während eines Zugs gesperrt', async () => {
    const ohne = await render(manifest.beispiele[1].daten as UiThemenbaumDaten);
    expect(knopf(ohne.el, 'Als Entwurf bearbeiten')).toBeUndefined();
    // Review U2, Befund 9: ohne Erlaubnis des Backends (Entwurf im Studio aus) kein Knopf.
    TestBed.resetTestingModule();
    const aus = await render({ ...BAUM, entwurf_moeglich: false });
    expect(knopf(aus.el, 'Als Entwurf bearbeiten')).toBeUndefined();
    TestBed.resetTestingModule();
    beschaeftigt.set(true);
    const { el } = await render(BAUM);
    const b = knopf(el, 'Als Entwurf bearbeiten')!;
    expect(b.getAttribute('aria-disabled')).toBe('true');
    b.click();
    expect(h.aktion).not.toHaveBeenCalled();
  });
});
