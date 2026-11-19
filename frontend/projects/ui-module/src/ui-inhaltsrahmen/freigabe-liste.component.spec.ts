// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DomSanitizer } from '@angular/platform-browser';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import { UiInhaltsrahmen, type UiInhaltsrahmenDaten } from './ui-inhaltsrahmen.component';

/** Paket N4: die Freigabe-Box — kompakt, Liste eingeklappt, Probleme sichtbar, danach Quittung. */
function host(antwort: Record<string, unknown> = { gesendet: true }) {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(),
    markdown: vi.fn((text: string) => TestBed.inject(DomSanitizer).bypassSecurityTrustHtml(text)),
    auftrag: vi.fn(async () => antwort),
  } as unknown as ModulHost & { auftrag: ReturnType<typeof vi.fn>; markdown: ReturnType<typeof vi.fn> };
}

function daten(n = 3, probleme = [{ titel: 'Gesperrt', grund: 'not_writable' }], mehr: Record<string, unknown> = {}): UiInhaltsrahmenDaten {
  const eintraege = Array.from({ length: n }, (_, i) => ({ titel: `Material ${i + 1}`, ordner: i % 2 ? 'Klasse 7' : '' }));
  return {
    titel: 'Erschließung in WLO freigeben', art: 'schreib_vorschau', markdown: 'Textfassung',
    freigabe: {
      ablauf: 'themenbaum', id: 'f1', anzahl: n, eintraege, probleme,
      flow: 'edusharing.chatbot/node-metadata-write', metadaten: true, ...mehr,
    },
  } as UiInhaltsrahmenDaten;
}

async function render(d: UiInhaltsrahmenDaten, mehr: Partial<ModulKontext> = {}, h = host()) {
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: h }] });
  const f = TestBed.createComponent(UiInhaltsrahmen);
  f.componentRef.setInput('daten', d);
  f.componentRef.setInput('kontext', {
    blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null, ...mehr,
  });
  await f.whenStable();
  return { f, el: f.nativeElement as HTMLElement, h };
}

const knopf = (el: HTMLElement, text: string) =>
  [...el.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(text)) as HTMLButtonElement;

afterEach(() => TestBed.resetTestingModule());

describe('Freigabe-Box (Paket N4)', () => {
  it('zeigt Kopf, Satz und die Liste eingeklappt — nicht den Markdown', async () => {
    const { el, h } = await render(daten());
    expect(el.textContent).toContain('3 Materialien werden in WLO erschlossen');
    expect(el.textContent).toContain('Titel, Beschreibung, Schlagworte, Fach, Stufe, Zielgruppe, Typ und Sprache');
    expect(h.markdown).not.toHaveBeenCalled();
    const auf = knopf(el, 'Liste zeigen');
    expect(auf.getAttribute('aria-expanded')).toBe('false');
    expect(el.textContent).not.toContain('Material 1');
  });

  it('klappt die Liste auf, nach Ordner gruppiert', async () => {
    const { f, el } = await render(daten());
    knopf(el, 'Liste zeigen').click();
    await f.whenStable();
    expect(knopf(el, 'Liste zeigen').getAttribute('aria-expanded')).toBe('true');
    const gruppen = [...el.querySelectorAll('[data-ordner]')].map((g) => g.getAttribute('data-ordner'));
    expect(gruppen).toEqual(['', 'Klasse 7']);
    expect(el.textContent).toContain('Material 2');
  });

  it('zeigt Probleme getrennt und sichtbar, mit Grund', async () => {
    const { el } = await render(daten());
    const probleme = el.querySelector('.freigabe__probleme') as HTMLElement;
    expect(probleme.textContent).toContain('1 Material geht nicht mit');
    expect(probleme.textContent).toContain('Gesperrt');
    expect(probleme.textContent).toContain('für dich nicht schreibbar');
  });

  it('ab mehr als 20 Einträgen mit Filterfeld und seitenweise', async () => {
    const { f, el } = await render(daten(45, []));
    knopf(el, 'Liste zeigen').click();
    await f.whenStable();
    expect(el.querySelectorAll('li.freigabe__eintrag')).toHaveLength(20);
    const feld = el.querySelector('input[type="search"]') as HTMLInputElement;
    expect(el.querySelector(`label[for="${feld.id}"]`)?.textContent).toContain('Liste filtern');
    knopf(el, 'Weitere zeigen').click();
    await f.whenStable();
    expect(el.querySelectorAll('li.freigabe__eintrag')).toHaveLength(40);
    feld.value = 'material 4';
    feld.dispatchEvent(new Event('input'));
    await f.whenStable();
    expect(el.querySelectorAll('li.freigabe__eintrag')).toHaveLength(7);
  });

  it('Freigeben schickt die Direktaktion und wird zur einzeiligen Quittung', async () => {
    const { f, el, h } = await render(daten());
    document.body.appendChild(f.nativeElement);
    knopf(el, 'Freigeben').click();
    await f.whenStable();
    expect(h.auftrag).toHaveBeenCalledWith({ schritt: 'freigeben', ablauf: 'themenbaum', freigabe: 'f1' });
    const quittung = el.querySelector('[role="status"]') as HTMLElement;
    expect(quittung.textContent?.trim()).toBe('Entscheidung gesendet: Freigeben');
    await new Promise((r) => setTimeout(r));
    expect(document.activeElement).toBe(quittung);           // der Fokus geht nicht verloren
    expect(el.querySelector('ui-freigabe-liste')!.querySelectorAll('button')).toHaveLength(0);
  });

  it('Abbrechen: Quittung ohne Überschreiben', async () => {
    const { f, el, h } = await render(daten());
    knopf(el, 'Abbrechen').click();
    await f.whenStable();
    expect(h.auftrag).toHaveBeenCalledWith({ schritt: 'verwerfen', ablauf: 'themenbaum', freigabe: 'f1' });
    expect(el.querySelector('[role="status"]')?.textContent?.trim()).toBe('Entscheidung gesendet: Abbrechen');
  });

  it('kam die Entscheidung nicht an, bleiben die Knöpfe — mit Hinweis', async () => {
    const { f, el } = await render(daten(), {}, host({ gesendet: false }));
    knopf(el, 'Freigeben').click();
    await f.whenStable();
    expect(knopf(el, 'Freigeben')).toBeTruthy();
    expect(el.querySelector('[role="status"]')?.textContent).toContain('kam nicht an');
  });

  it('nur lesend (Verlauf, nächster Zug): eine Zeile, keine Knöpfe', async () => {
    const { el } = await render(daten(), { nurLesen: true });
    expect(el.querySelector('ui-freigabe-liste')!.querySelectorAll('button')).toHaveLength(0);
    expect(el.querySelector('[role="status"]')?.textContent).toContain('nicht mehr offen');
  });

  it('englisch', async () => {
    const { el } = await render(daten(1, []), { sprache: 'en' });
    expect(el.textContent).toContain('1 material will be indexed in WLO');
    expect(knopf(el, 'Approve')).toBeTruthy();
  });
});

describe('Freigabe-Box — Review N4', () => {
  it('zeigt von 150 Problemen die ersten 5, den Rest hinter „alle zeigen“', async () => {
    const viele = Array.from({ length: 150 }, (_, i) => ({ titel: `Problem ${i + 1}`, grund: 'not_found' }));
    const { f, el } = await render(daten(2, viele));
    const probleme = () => el.querySelectorAll('.freigabe__probleme li');
    expect(probleme()).toHaveLength(5);
    const alle = knopf(el, 'Alle zeigen');
    expect(alle.getAttribute('aria-expanded')).toBe('false');
    alle.click();
    await f.whenStable();
    expect(probleme()).toHaveLength(150);
    expect(knopf(el, 'Alle zeigen').getAttribute('aria-expanded')).toBe('true');
  });

  it('ein anderer Flow: neutraler Kopf, ohne Satz zu den Feldern, ohne „0 Materialien“', async () => {
    const { el } = await render(daten(0, [], { flow: 'f/andere', metadaten: false }));
    expect(el.textContent).toContain('Dieser Auftrag schreibt in WLO: f/andere');
    expect(el.textContent).not.toContain('0 Materialien');
    expect(el.textContent).not.toContain('Schlagworte');
  });

  it('ein anderer Flow mit Einträgen nennt die Zahl', async () => {
    const { el } = await render(daten(1, [], { flow: 'f/andere', metadaten: false }));
    expect(el.textContent).toContain('Dieser Auftrag schreibt in WLO: f/andere (1 Material)');
  });

  it('aria-controls nur, wenn die Liste da ist', async () => {
    const { f, el } = await render(daten());
    const auf = knopf(el, 'Liste zeigen');
    expect(auf.hasAttribute('aria-controls')).toBe(false);
    auf.click();
    await f.whenStable();
    expect(el.querySelector(`#${knopf(el, 'Liste zeigen').getAttribute('aria-controls')}`)).not.toBeNull();
  });

  it('Einzahl: „1 Material wird …“ (de) und „1 material …“ (en)', async () => {
    const de = await render(daten(1, []));
    expect(de.el.textContent).toContain('1 Material wird in WLO erschlossen');
    TestBed.resetTestingModule();
    const en = await render(daten(1, []), { sprache: 'en' });
    expect(en.el.textContent).toContain('1 material will be indexed in WLO');
  });
});
