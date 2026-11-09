// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import manifest from './manifest.json';
import { UiEntscheidung, type UiEntscheidungDaten } from './ui-entscheidung.component';

const [EINZEL, MEHRFACH] = manifest.beispiele.map((b) => b.daten as UiEntscheidungDaten);

/** Host-Attrappe: „beschäftigt“ als Signal, wie die Shell es über `isLoading` liefert. */
function host(beschaeftigt = signal(false)) {
  return {
    antworten: vi.fn(), beschaeftigt: () => beschaeftigt(),
    herunterladen: vi.fn(), drucken: vi.fn(), markdown: vi.fn(), link: vi.fn(), treffer: vi.fn(), aktion: vi.fn(),
  };
}

async function render(daten: UiEntscheidungDaten, kontext: Partial<ModulKontext> = {}, h = host()) {
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: h as unknown as ModulHost }],
  });
  const f = TestBed.createComponent(UiEntscheidung);
  f.componentRef.setInput('daten', daten);
  f.componentRef.setInput('kontext', {
    blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
    ...kontext,
  } satisfies ModulKontext);
  await f.whenStable();
  const el = f.nativeElement as HTMLElement;
  const knopf = () => el.querySelector<HTMLButtonElement>('button[type="submit"]');
  const option = (id: string) => el.querySelector<HTMLInputElement>(`input[value="${id}"]`)!;
  const waehle = async (id: string) => { option(id).click(); await f.whenStable(); };
  const eigen = () => el.querySelector<HTMLInputElement>('input[data-eigen]')!;
  const feld = () => el.querySelector<HTMLTextAreaElement>('textarea')!;
  const tippe = async (text: string) => {
    feld().value = text;
    feld().dispatchEvent(new Event('input'));
    await f.whenStable();
  };
  return { f, el, h, knopf, option, waehle, eigen, feld, tippe };
}

afterEach(() => TestBed.resetTestingModule());

describe('UiEntscheidung', () => {
  for (const beispiel of manifest.beispiele) {
    it(`rendert das Beispiel „${beispiel.titel}“`, async () => {
      const daten = beispiel.daten as UiEntscheidungDaten;
      const { el } = await render(daten);
      expect(el.querySelector('fieldset legend')?.textContent?.trim()).toBe(daten.frage);
      const typ = daten.mehrfach ? 'checkbox' : 'radio';
      expect(el.querySelectorAll(`input[type="${typ}"]`).length).toBe(daten.optionen.length + (daten.freitext ? 1 : 0));
      expect(!!el.querySelector('textarea')).toBe(!!daten.freitext);
    });
  }

  it('jede Möglichkeit ist beschriftet, ein Hinweis beschreibt sie (aria-describedby)', async () => {
    const { el, option } = await render(MEHRFACH);
    const video = option('video');
    expect(video.closest('label')?.textContent).toContain('Video');
    const hinweis = el.querySelector(`#${video.getAttribute('aria-describedby')}`);
    expect(hinweis?.textContent?.trim()).toBe('kurze Erklärfilme bis 10 Minuten');
    expect(option('interaktiv').hasAttribute('aria-describedby')).toBe(false);
    // Freitext: benannt durch den Punkt „Eigene Antwort“, mit Deckel.
    const feld = el.querySelector('textarea')!;
    expect(el.querySelector(`#${feld.getAttribute('aria-labelledby')}`)?.textContent).toContain('Eigene Antwort');
    expect(feld.maxLength).toBe(1000);
  });

  it('eine Möglichkeit mit der Kennung „freitext“ teilt keine id mit dem Freitextfeld (Review U1-d1)', async () => {
    const { el, option } = await render({
      frage: 'Wie weiter?', freitext: true,
      optionen: [{ id: 'freitext', label: 'Frei formulieren', hinweis: 'ein eigener Satz' }, { id: 'liste', label: 'Liste' }],
    });
    const ids = [...el.querySelectorAll('[id]')].map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    const hinweis = el.querySelector(`#${option('freitext').getAttribute('aria-describedby')}`);
    expect(hinweis?.textContent?.trim()).toBe('ein eigener Satz');
    const feld = el.querySelector('textarea')!;
    expect(el.querySelector(`#${feld.getAttribute('aria-labelledby')}`)?.textContent).toContain('Eigene Antwort');
  });

  it('Einzelwahl: eine Gruppe (gleicher Name), „Antworten“ erst mit Wahl', async () => {
    const { knopf, option, waehle } = await render(EINZEL);
    const namen = new Set(EINZEL.optionen.map((o) => option(o.id).name));
    expect(namen.size).toBe(1);
    expect(knopf()?.textContent?.trim()).toBe('Antworten');
    expect(knopf()?.disabled).toBe(true);
    await waehle('klasse_7_8');
    expect(knopf()?.disabled).toBe(false);
  });

  it('die Antwort geht an den Host: Kennungen und die lesbare Fassung', async () => {
    const { h, knopf, waehle } = await render(EINZEL);
    await waehle('klasse_5_6');
    await waehle('klasse_7_8');
    knopf()!.click();
    expect(h.antworten).toHaveBeenCalledWith({ gewaehlt: ['klasse_7_8'] }, 'Klasse 7–8');
  });

  it('Mehrfachwahl mit Freitext: in der Reihenfolge der Möglichkeiten, Ergänzung dazu', async () => {
    const { f, el, h, knopf, waehle } = await render(MEHRFACH);
    await waehle('interaktiv');
    await waehle('video');
    await waehle('arbeitsblatt');
    await waehle('arbeitsblatt');                       // wieder abgewählt
    const feld = el.querySelector('textarea')!;
    feld.value = '  ohne Anmeldung  ';
    feld.dispatchEvent(new Event('input'));
    await f.whenStable();
    expect(el.querySelector<HTMLInputElement>('input[data-eigen]')!.checked).toBe(true);
    knopf()!.click();
    expect(h.antworten).toHaveBeenCalledWith(
      { gewaehlt: ['video', 'interaktiv'], freitext: 'ohne Anmeldung' }, 'Video, Interaktive Übung\nohne Anmeldung');
  });

  it('Tastatur: Absenden des Formulars (Enter) antwortet wie der Knopf', async () => {
    const { el, h, waehle } = await render(EINZEL);
    await waehle('klasse_9_10');
    el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(h.antworten).toHaveBeenCalledWith({ gewaehlt: ['klasse_9_10'] }, 'Klasse 9–10');
  });

  // Review U1 gesamt, Befund 6 (WCAG 2.4.3): während eines Zugs `aria-disabled` statt `disabled` —
  // ein gesperrter Knopf fiele aus der Tab-Reihenfolge, und der Fokus ginge verloren.
  it('während eines Zugs ist der Knopf gesperrt (aria-disabled, bleibt fokussierbar) — Klick und Enter senden nichts', async () => {
    const zug = signal(true);
    const { f, el, h, knopf, waehle } = await render(EINZEL, {}, host(zug));
    await waehle('klasse_5_6');
    expect(knopf()?.disabled).toBe(false);
    expect(knopf()?.getAttribute('aria-disabled')).toBe('true');
    knopf()!.focus();
    expect(document.activeElement).toBe(knopf());
    knopf()!.click();
    el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(h.antworten).not.toHaveBeenCalled();
    zug.set(false);
    await f.whenStable();
    expect(knopf()?.hasAttribute('aria-disabled')).toBe(false);
    expect(document.activeElement).toBe(knopf());
  });

  it('nach „Antworten“ geht der Fokus an die Statuszeile, nicht verloren (WCAG 2.4.3)', async () => {
    const { f, el, knopf, waehle } = await render(EINZEL);
    document.body.appendChild(el);
    try {
      await waehle('klasse_7_8');
      knopf()!.focus();
      knopf()!.click();
      // Die Shell vermerkt die Antwort sofort — das Modul wird nur lesend, der Knopf verschwindet.
      f.componentRef.setInput('kontext', {
        blockId: 'b0000001', sprache: 'de', nurLesen: true, antwort: { gewaehlt: ['klasse_7_8'] },
        schriftSkala: 0.85, anzeigeRegeln: null,
      } satisfies ModulKontext);
      await f.whenStable();
      const status = el.querySelector<HTMLElement>('.ui-entscheidung__status')!;
      expect(knopf()).toBeNull();
      expect(status.getAttribute('tabindex')).toBe('-1');
      expect(document.activeElement).toBe(status);
    } finally {
      el.remove();
    }
  });

  it('ein schon beantworteter Block (Verlauf) zieht den Fokus nicht an sich', async () => {
    const vorher = document.activeElement;
    const { el } = await render(EINZEL, { nurLesen: true, antwort: { gewaehlt: ['klasse_5_6'] } });
    expect(el.querySelector('.ui-entscheidung__status')).not.toBeNull();
    expect(document.activeElement).toBe(vorher);
  });

  it('beantwortet: nur lesend mit der gegebenen Antwort, ohne Knopf', async () => {
    const { el, knopf, option } = await render(MEHRFACH, {
      nurLesen: true, antwort: { gewaehlt: ['video'], freitext: 'kurz' } });
    expect(knopf()).toBeNull();
    expect(el.querySelector('fieldset')?.disabled).toBe(true);
    expect(option('video').checked).toBe(true);
    expect(option('interaktiv').checked).toBe(false);
    expect(el.querySelector('.ui-entscheidung__status')?.textContent?.trim()).toBe('Deine Antwort: Video — kurz');
  });

  it('veraltet: nur lesend, ehrlich als nicht mehr offen', async () => {
    const { el, knopf } = await render(EINZEL, { nurLesen: true, antwort: null });
    expect(knopf()).toBeNull();
    expect(el.querySelector('.ui-entscheidung__status')?.textContent?.trim()).toBe('Diese Frage ist nicht mehr offen.');
  });

  // Rückmeldung 2026-11-09: wer erst oben wählt und dann unten schreibt, bekam die Wahl nicht mehr
  // weg und schickte beides. Die eigene Antwort ist jetzt ein Punkt der Gruppe.
  describe('Eigene Antwort als eigener Punkt', () => {
    const EINZEL_FREI: UiEntscheidungDaten = { ...EINZEL, freitext: true };

    it('Einzelwahl: Tippen wählt „Eigene Antwort“ und nimmt die Wahl oben heraus', async () => {
      const { h, knopf, option, waehle, eigen, tippe } = await render(EINZEL_FREI);
      expect(eigen().type).toBe('radio');
      expect(eigen().name).toBe(option('klasse_5_6').name);
      await waehle('klasse_5_6');
      await tippe('Klasse 11');
      expect(option('klasse_5_6').checked).toBe(false);
      expect(eigen().checked).toBe(true);
      knopf()!.click();
      expect(h.antworten).toHaveBeenCalledWith({ gewaehlt: [], freitext: 'Klasse 11' }, 'Klasse 11');
    });

    it('Einzelwahl: wer danach wieder oben wählt, schickt nur diese Wahl — der Text bleibt stehen', async () => {
      const { h, knopf, option, waehle, eigen, feld, tippe } = await render(EINZEL_FREI);
      await tippe('Klasse 11');
      await waehle('klasse_7_8');
      expect(eigen().checked).toBe(false);
      expect(option('klasse_7_8').checked).toBe(true);
      expect(feld().value).toBe('Klasse 11');
      knopf()!.click();
      expect(h.antworten).toHaveBeenCalledWith({ gewaehlt: ['klasse_7_8'] }, 'Klasse 7–8');
    });

    it('„Eigene Antwort“ anklicken: ohne Text noch kein Antworten, mit Text schon', async () => {
      const { f, el, knopf, eigen, tippe } = await render(EINZEL_FREI);
      document.body.appendChild(el);
      try {
        eigen().dispatchEvent(new Event('pointerdown', { bubbles: true }));
        eigen().click();
        await f.whenStable();
        expect(eigen().checked).toBe(true);
        expect(document.activeElement).toBe(el.querySelector('textarea'));
        expect(knopf()?.disabled).toBe(true);
        await tippe('   ');
        expect(knopf()?.disabled).toBe(true);
        await tippe('Klasse 11');
        expect(knopf()?.disabled).toBe(false);
      } finally {
        el.remove();
      }
    });

    // Review, Befund 1 (WCAG 3.2.2): Pfeiltasten wählen in der Radio-Gruppe (change, Klick ohne
    // Zeiger) — der Fokus bleibt dann in der Gruppe, sonst kämen Tastatur und Screenreader nicht weiter.
    it('ohne Zeiger (Tastatur) bleibt der Fokus auf „Eigene Antwort“', async () => {
      const { f, el, eigen } = await render(EINZEL_FREI);
      document.body.appendChild(el);
      try {
        eigen().focus();
        eigen().click();                                 // wie Pfeiltaste/Leertaste: kein pointerdown
        await f.whenStable();
        expect(eigen().checked).toBe(true);
        expect(document.activeElement).toBe(eigen());
      } finally {
        el.remove();
      }
    });

    it('das Textfeld sagt, dass Schreiben „Eigene Antwort“ wählt (aria-describedby)', async () => {
      const { el, feld } = await render(EINZEL_FREI);
      const hinweis = el.querySelector(`#${feld().getAttribute('aria-describedby')}`);
      expect(hinweis?.textContent).toContain('Schreiben wählt „Eigene Antwort“');
    });

    it('Mehrfachwahl: abgehakt und dann geschrieben — der Text zählt wieder', async () => {
      const { f, h, knopf, waehle, eigen, tippe } = await render(MEHRFACH);
      await waehle('video');
      await tippe('ohne');
      eigen().click();
      await f.whenStable();                              // wie im Browser: gerendert vor dem Weiterschreiben
      expect(eigen().checked).toBe(false);
      await tippe('ohne Anmeldung');
      expect(eigen().checked).toBe(true);
      knopf()!.click();
      expect(h.antworten).toHaveBeenCalledWith({ gewaehlt: ['video'], freitext: 'ohne Anmeldung' },
        'Video\nohne Anmeldung');
    });

    it('Mehrfachwahl: „Eigene Antwort“ abhaken schickt den Text nicht mit', async () => {
      const { h, knopf, waehle, eigen, tippe } = await render(MEHRFACH);
      expect(eigen().type).toBe('checkbox');
      await waehle('video');
      await tippe('ohne Anmeldung');
      eigen().click();
      await waehle('interaktiv');
      knopf()!.click();
      expect(h.antworten).toHaveBeenCalledWith({ gewaehlt: ['video', 'interaktiv'] }, 'Video, Interaktive Übung');
    });

    it('beantwortet nur mit eigener Antwort: die Statuszeile nennt den Text', async () => {
      const { el, eigen, option } = await render(EINZEL_FREI, {
        nurLesen: true, antwort: { gewaehlt: [], freitext: 'Klasse 11' } });
      expect(el.querySelector('.ui-entscheidung__status')?.textContent?.trim()).toBe('Deine Antwort: Klasse 11');
      // Review, Befund 3: der Punkt steht angehakt da, ohne Textfeld
      expect(eigen().checked).toBe(true);
      expect(option('klasse_5_6').checked).toBe(false);
      expect(el.querySelector('textarea')).toBeNull();
    });
  });

  it('spricht Englisch, wenn das Widget es tut', async () => {
    const { el, knopf } = await render(MEHRFACH, { sprache: 'en' });
    expect(knopf()?.textContent?.trim()).toBe('Answer');
    expect(el.textContent).toContain('You can choose more than one.');
    expect(el.textContent).toContain('Your own answer');
  });
});
