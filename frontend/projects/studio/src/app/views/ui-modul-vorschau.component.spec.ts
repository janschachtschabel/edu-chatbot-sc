// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { UI_MODUL_REGISTER, type UiModulManifest } from '@boerdi/ui-module';
import entscheidung from '@boerdi/ui-module/ui-entscheidung/manifest.json';
import inhaltsrahmen from '@boerdi/ui-module/ui-inhaltsrahmen/manifest.json';
import linkbox from '@boerdi/ui-module/ui-linkbox/manifest.json';
import strukturentwurf from '@boerdi/ui-module/ui-strukturentwurf/manifest.json';
import themenbaum from '@boerdi/ui-module/ui-themenbaum/manifest.json';
import trefferliste from '@boerdi/ui-module/ui-trefferliste/manifest.json';
import fortschritt from '@boerdi/ui-module/ui-fortschritt/manifest.json';
import strukturabgleich from '@boerdi/ui-module/ui-strukturabgleich/manifest.json';
import upload from '@boerdi/ui-module/ui-upload/manifest.json';
import { MODUL_REGISTER } from '@boerdi/ui-module/register.generated';

import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
import type { UiModulEintrag } from './ui-module';
import { UiModulVorschauComponent } from './ui-modul-vorschau.component';

/**
 * Paket U1-f: die Vorschau zeigt jedes Beispiel eines Manifests mit der ECHTEN Komponente aus dem
 * Register — und nichts davon verlässt die Seite: Herunterladen, Drucken, Aktionen und Antworten
 * werden angesagt, Links öffnen nicht.
 */
const MANIFESTE = [entscheidung, fortschritt, inhaltsrahmen, linkbox, strukturabgleich, strukturentwurf, themenbaum, trefferliste, upload] as unknown as UiModulManifest[];

/** Text der Bühne samt Shadow Roots (nachgeladene Module zeichnen in ihren Shadow Root, U3-1a). */
function text(e: Element | null): string {
  if (!e) return '';
  const innen = e.shadowRoot ? [...e.shadowRoot.children].map(text).join(' ') : '';
  return [e.childElementCount ? [...e.children].map(text).join(' ') : (e.textContent ?? ''), innen].join(' ');
}

/** Bis ein nachgeladenes Element da ist: Lazy-Chunk laden, Effekt laufen lassen. */
async function geladen(f: { whenStable(): Promise<unknown> }): Promise<void> {
  for (let i = 0; i < 5; i++) {
    await new Promise((r) => setTimeout(r, 0));
    await f.whenStable();
  }
}

function eintrag(manifest: UiModulManifest): UiModulEintrag {
  return { name: manifest.name, manifest, schaltbar: { aktiv: true, agent: true }, abgeleitet: false };
}

async function render(manifest: UiModulManifest, register: object = MODUL_REGISTER) {
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), { provide: UI_MODUL_REGISTER, useValue: register }],
  });
  const f = TestBed.createComponent(UiModulVorschauComponent);
  f.componentRef.setInput('eintrag', eintrag(manifest));
  await f.whenStable();
  const el = f.nativeElement as HTMLElement;
  document.body.appendChild(el);
  return { f, el };
}

async function waehle(f: { whenStable(): Promise<unknown> }, el: HTMLElement, index: number) {
  const radio = el.querySelectorAll<HTMLInputElement>('input[type="radio"][name^="umv-beispiel"]')[index];
  radio.click();
  await f.whenStable();
}

function status(el: HTMLElement): string {
  // Die Ansage der Vorschau — nicht die Statuszeile eines Moduls auf der Bühne (Themenbaum, U1-h).
  return el.querySelector('.umv-meldung[role="status"]')?.textContent?.trim() ?? '';
}

afterEach(() => {
  TestBed.resetTestingModule();
  document.body.innerHTML = '';
  sessionStorage.removeItem(STUDIO_LOCALE_STORAGE_KEY);
  vi.restoreAllMocks();
});

describe('UiModulVorschauComponent', () => {
  it('kennt jedes Modul des Registers (ein neues Modul muss hier dazu)', () => {
    expect(MANIFESTE.map((m) => m.name).sort()).toEqual(Object.keys(MODUL_REGISTER).sort());
  });

  for (const manifest of MANIFESTE) {
    for (const [index, beispiel] of manifest.beispiele.entries()) {
      it(`rendert ${manifest.name} „${beispiel.titel}“ mit der echten Komponente`, async () => {
        const { f, el } = await render(manifest);
        await waehle(f, el, index);
        await geladen(f);
        const buehne = el.querySelector('.umv-buehne');
        expect(buehne?.children.length).toBeGreaterThan(0);
        expect(text(buehne).trim()).not.toBe('');
        expect(el.querySelector('.umv-unbekannt')).toBeNull();
      });
    }
  }

  // Review U1 gesamt, Befund 18 (Datenschutz): die Bühne lädt nichts von fremden Servern — kein
  // Vorschaubild, kein eingebetteter Rahmen. Je Beispiel in Boxen und, für die Trefferliste, in Kacheln.
  for (const manifest of MANIFESTE) {
    for (const [index, beispiel] of manifest.beispiele.entries()) {
      for (const kacheln of manifest.name === 'ui_trefferliste' ? [false, true] : [false]) {
        it(`${manifest.name} „${beispiel.titel}“${kacheln ? ' (Kacheln)' : ''}: kein fremdes Bild, kein iframe`, async () => {
          const { f, el } = await render(manifest);
          await waehle(f, el, index);
          if (kacheln) {
            el.querySelector<HTMLInputElement>('.umv-kacheln input[type="checkbox"]')!.click();
            await f.whenStable();
            expect(el.querySelector('.umv-buehne boerdi-card-list')).not.toBeNull();
          }
          expect(el.querySelectorAll('.umv-buehne img[src^="http"], .umv-buehne iframe').length).toBe(0);
          expect(el.querySelectorAll('.umv-buehne [srcset*="http"], .umv-buehne source[src^="http"]').length).toBe(0);
        });
      }
    }
  }

  it('je Beispiel eine Auswahl mit Namen; die erste ist gewählt', async () => {
    const { el } = await render(entscheidung as unknown as UiModulManifest);
    const radios = [...el.querySelectorAll<HTMLInputElement>('input[type="radio"][name^="umv-beispiel"]')];
    expect(radios.length).toBe(entscheidung.beispiele.length);
    expect(radios[0].checked).toBe(true);
    expect(radios.every((r) => r.closest('label')?.textContent?.trim())).toBe(true);
    expect(el.querySelector('fieldset legend')?.textContent?.trim()).toBeTruthy();
  });

  it('ein Link öffnet nichts, sondern wird angesagt', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    const { f, el } = await render(linkbox as unknown as UiModulManifest);
    const link = el.querySelector<HTMLAnchorElement>('.umv-buehne a[href]');
    expect(link).not.toBeNull();
    const klick = new MouseEvent('click', { bubbles: true, cancelable: true });
    link!.dispatchEvent(klick);
    await f.whenStable();
    expect(klick.defaultPrevented).toBe(true);
    expect(open).not.toHaveBeenCalled();
    const t = TestBed.inject(StudioLanguageService).t;
    expect(status(el)).toBe(t('uiModule.vorschau.link', { url: link!.href }));
  });

  // Review U1-f, Befund 1: Die Kachel (`wlo-card-tile`) hält ihren Klick mit `stopPropagation`
  // an — ein Abfangen in der Bubble-Phase kam dort nie an. Die Vorschau hört deshalb in der
  // Capture-Phase mit, bevor ein Modul den Klick sieht.
  async function inKacheln(f: { whenStable(): Promise<unknown> }, el: HTMLElement): Promise<HTMLAnchorElement> {
    el.querySelector<HTMLInputElement>('.umv-kacheln input[type="checkbox"]')!.click();
    await f.whenStable();
    const link = el.querySelector<HTMLAnchorElement>('.umv-buehne .wlo-card-wrapper a[href]');
    expect(link).not.toBeNull();
    return link!;
  }

  function erwarteAbgefangen(el: HTMLElement, link: HTMLAnchorElement, ereignis: Event): void {
    expect(ereignis.defaultPrevented).toBe(true);
    const t = TestBed.inject(StudioLanguageService).t;
    expect(status(el)).toBe(t('uiModule.vorschau.link', { url: link.href }));
  }

  it('ein Kachel-Link der Trefferliste öffnet nichts (Klick)', async () => {
    const { f, el } = await render(trefferliste as unknown as UiModulManifest);
    const link = await inKacheln(f, el);
    const klick = new MouseEvent('click', { bubbles: true, cancelable: true, detail: 1 });
    link.dispatchEvent(klick);
    await f.whenStable();
    erwarteAbgefangen(el, link, klick);
  });

  it('ein Kachel-Link öffnet auch mit Enter nichts (der Browser löst `click` mit detail 0 aus)', async () => {
    const { f, el } = await render(trefferliste as unknown as UiModulManifest);
    const link = await inKacheln(f, el);
    link.focus();
    const enter = new MouseEvent('click', { bubbles: true, cancelable: true, detail: 0 });
    link.dispatchEvent(enter);
    await f.whenStable();
    erwarteAbgefangen(el, link, enter);
  });

  it('ein Mittelklick (auxclick, Taste 1) auf einen Kachel-Link öffnet keinen Tab', async () => {
    const { f, el } = await render(trefferliste as unknown as UiModulManifest);
    const link = await inKacheln(f, el);
    const mitte = new MouseEvent('auxclick', { bubbles: true, cancelable: true, button: 1 });
    link.dispatchEvent(mitte);
    await f.whenStable();
    erwarteAbgefangen(el, link, mitte);
  });

  it('„In WLO öffnen“ im Themenbaum öffnet nichts', async () => {
    const { f, el } = await render(themenbaum as unknown as UiModulManifest);
    const link = el.querySelector<HTMLAnchorElement>('.umv-buehne .ui-themenbaum__aktionen a[href]');
    expect(link).not.toBeNull();
    const klick = new MouseEvent('click', { bubbles: true, cancelable: true });
    link!.dispatchEvent(klick);
    await f.whenStable();
    erwarteAbgefangen(el, link!, klick);
  });

  it('U1-h: Aufklappen im Themenbaum lädt nichts — Beispiel-Unterthemen und eine Ansage', async () => {
    const { f, el } = await render(themenbaum as unknown as UiModulManifest);
    const algebra = el.querySelector<HTMLElement>('.umv-buehne [role="treeitem"]')!;
    algebra.click();                                   // „weitere“ → lädt über den Host
    await f.whenStable();
    await vi.waitFor(() => expect(status(el)).toContain('Nothing is loaded in the preview (bbbb-2222)'));
    const namen = [...algebra.querySelectorAll('[role="group"] [role="treeitem"]')].map((i) => i.textContent?.trim());
    expect(namen.some((n) => n?.includes('Beispiel-Unterthema'))).toBe(true);
  });

  it('ein Formular der Bühne schickt nichts ab — die Antwort sagt der Host an', async () => {
    const { f, el } = await render(entscheidung as unknown as UiModulManifest);
    el.querySelector<HTMLInputElement>('.umv-buehne input[type="radio"]')!.click();
    await f.whenStable();
    const absenden = new Event('submit', { bubbles: true, cancelable: true });
    el.querySelector('.umv-buehne form')!.dispatchEvent(absenden);
    await f.whenStable();
    expect(absenden.defaultPrevented).toBe(true);
    expect(status(el)).toContain(entscheidung.beispiele[0].daten.optionen[0].label);
  });

  // Review U1-f, Befund 6: eine Ansage gehört zu Modul, Beispiel und Darstellung.
  it('die Ansage verschwindet beim Wechsel des Moduls', async () => {
    const { f, el } = await render(linkbox as unknown as UiModulManifest);
    el.querySelector<HTMLAnchorElement>('.umv-buehne a[href]')!.click();
    await f.whenStable();
    expect(status(el)).not.toBe('');
    f.componentRef.setInput('eintrag', eintrag(entscheidung as unknown as UiModulManifest));
    await f.whenStable();
    expect(status(el)).toBe('');
  });

  it('die Ansage verschwindet beim Umschalten auf Kacheln', async () => {
    const { f, el } = await render(trefferliste as unknown as UiModulManifest);
    el.querySelector<HTMLAnchorElement>('.umv-buehne a[href]')!.click();
    await f.whenStable();
    expect(status(el)).not.toBe('');
    await inKacheln(f, el);
    expect(status(el)).toBe('');
  });

  it('die Ansage verschwindet beim Umschalten auf „Beantwortet zeigen“', async () => {
    const { f, el } = await render(entscheidung as unknown as UiModulManifest);
    el.querySelector<HTMLInputElement>('.umv-buehne input[type="radio"]')!.click();
    await f.whenStable();
    el.querySelector<HTMLButtonElement>('.umv-buehne button[type="submit"]')!.click();
    await f.whenStable();
    expect(status(el)).not.toBe('');
    el.querySelector<HTMLInputElement>('.umv-beantwortet input[type="checkbox"]')!.click();
    await f.whenStable();
    expect(status(el)).toBe('');
  });

  // Review U1-f, Befund 5 (WCAG 3.1.2): die Beispiele sind deutsch — auch im englischen Studio.
  it('Beispieltitel, Bühne und Beispieldaten tragen lang="de", auch im englischen Studio', async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'en');
    const { el } = await render(linkbox as unknown as UiModulManifest);
    expect(TestBed.inject(StudioLanguageService).i18n.locale()).toBe('en');
    const titel = [...el.querySelectorAll('.umv-beispiele label')];
    expect(titel.length).toBeGreaterThan(0);
    expect(titel.every((l) => l.querySelector('[lang="de"]')?.textContent?.trim())).toBe(true);
    expect(el.querySelector('.umv-buehne')?.getAttribute('lang')).toBe('de');
    expect(el.querySelector('.umv-daten pre')?.getAttribute('lang')).toBe('de');
  });

  it('Herunterladen und Drucken werden angesagt statt ausgeführt', async () => {
    const createObjectURL = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { value: createObjectURL, configurable: true });
    const drucken = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const { f, el } = await render(inhaltsrahmen as unknown as UiModulManifest);
    const knoepfe = [...el.querySelectorAll<HTMLButtonElement>('.umv-buehne button')];
    expect(knoepfe.length).toBeGreaterThanOrEqual(2);
    for (const knopf of knoepfe) {
      knopf.click();
      await f.whenStable();
      expect(status(el)).not.toBe('');
    }
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(drucken).not.toHaveBeenCalled();
  });

  it('eine Antwort wird angesagt, nicht gesendet — das Beispiel startet offen', async () => {
    const { f, el } = await render(entscheidung as unknown as UiModulManifest);
    const erste = el.querySelector<HTMLInputElement>('.umv-buehne input[type="radio"]');
    erste!.click();
    await f.whenStable();
    el.querySelector<HTMLButtonElement>('.umv-buehne button[type="submit"]')!.click();
    await f.whenStable();
    expect(status(el)).toContain(entscheidung.beispiele[0].daten.optionen[0].label);
  });

  it('mit „Beantwortet zeigen“ steht das Modul nur lesend mit der Beispiel-Antwort', async () => {
    const { f, el } = await render(entscheidung as unknown as UiModulManifest);
    const schalter = el.querySelector<HTMLInputElement>('.umv-beantwortet input[type="checkbox"]');
    expect(schalter?.closest('label')?.textContent?.trim()).toBeTruthy();
    schalter!.click();
    await f.whenStable();
    expect(el.querySelectorAll('.umv-buehne button:not([disabled])').length).toBe(0);
    expect(el.querySelector('.umv-buehne')?.textContent).toContain('Klasse 7');
  });

  it('ohne Beispiel-Antwort gibt es den Schalter nicht', async () => {
    const { el } = await render(linkbox as unknown as UiModulManifest);
    expect(el.querySelector('.umv-beantwortet')).toBeNull();
  });

  it('kennt das Studio das Modul nicht, stehen Hinweis und Beispieldaten', async () => {
    const { el } = await render(linkbox as unknown as UiModulManifest, {});
    expect(el.querySelector('.umv-unbekannt')).not.toBeNull();
    expect(el.querySelector('.umv-buehne')).toBeNull();
    expect(el.querySelector('pre')?.textContent).toContain('"links"');
  });

  it('eine andere Hauptversion im Studio zeigt ebenfalls den Hinweis', async () => {
    const register = { ui_linkbox: { ...MODUL_REGISTER['ui_linkbox'],
      manifest: { ...MODUL_REGISTER['ui_linkbox'].manifest, version: 2 } } };
    const { el } = await render(linkbox as unknown as UiModulManifest, register);
    expect(el.querySelector('.umv-unbekannt')).not.toBeNull();
  });
});
