import { provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { EN } from '../i18n/en';
import { type EigenerVorgang, MeineVorgaengeController } from './meine-vorgaenge';
import { MeineVorgaengeComponent } from './meine-vorgaenge.component';

/**
 * AS-Ud (Plan 2026-11-09 §5j): die Liste „Meine Vorgänge“ — Lade-, Fehler- und Leerzustand, je
 * Vorgang Titel, Zustand in Worten und Datum, „Fortsetzen“ und „Löschen“ mit Rückfrage im Panel,
 * Fokus beim Öffnen, Nachfragen und Löschen, Esc schließt (ohne das Widget zu schließen).
 */
const HIER = 'bb-12345678-1234-4123-8123-123456789abc';
const V1: EigenerVorgang = {
  id: '0a1b2c3d-0000-4000-8000-000000000001', titel: 'Lesen', ablauf: 'lesen',
  status: 'wartet_auftrag', session_id: 'bb-87654321-4321-4321-8321-cba987654321',
  geaendert: '2026-11-07T09:30:00Z',
};

let fixture: ComponentFixture<MeineVorgaengeComponent> | null = null;

async function render(liste: EigenerVorgang[] | Error = [V1], katalog = DE) {
  const abrufen = vi.fn(async () => {
    if (liste instanceof Error) throw liste;
    return liste;
  });
  const loeschen = vi.fn(async () => undefined as void);
  const c = new MeineVorgaengeController({ abrufen, loeschen, sessionId: () => HIER, block: () => 'b' });
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(MeineVorgaengeComponent);
  fixture = f;
  f.componentRef.setInput('vorgaenge', c);
  f.componentRef.setInput('translate', createTranslator(katalog, DE));
  f.componentRef.setInput('locale', katalog === EN ? 'en' : 'de');
  document.body.appendChild(f.nativeElement);
  const geoeffnet = c.umschalten();
  f.detectChanges();
  await geoeffnet;
  await f.whenStable();
  const el = f.nativeElement as HTMLElement;
  const knopf = (text: string) =>
    [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === text);
  return { f, c, el, knopf, abrufen, loeschen };
}

afterEach(() => {
  fixture?.destroy();
  fixture = null;
  document.body.innerHTML = '';
  TestBed.resetTestingModule();
});

describe('MeineVorgaengeComponent', () => {
  it('zeigt je Vorgang Titel, Zustand in Worten und Datum; die Knöpfe nennen den Vorgang', async () => {
    const { el, knopf } = await render();
    expect(el.querySelector('.meine-vorgaenge__name')?.textContent?.trim()).toBe('Lesen');
    expect(el.querySelector('.meine-vorgaenge__stand')?.textContent).toMatch(/^Auftrag läuft · zuletzt 7\. Nov/);
    expect(knopf('Fortsetzen')?.getAttribute('aria-label')).toBe('„Lesen“ fortsetzen');
    expect(knopf('Löschen')?.getAttribute('aria-label')).toBe('„Lesen“ löschen');
    expect(el.querySelector('section')?.getAttribute('aria-labelledby'))
      .toBe(el.querySelector('.meine-vorgaenge__titel')?.id);
  });

  it('beim Öffnen hat der Titel den Fokus', async () => {
    const { el } = await render();
    expect(document.activeElement).toBe(el.querySelector('.meine-vorgaenge__titel'));
  });

  it('leer: ein Satz statt einer leeren Liste', async () => {
    const { el } = await render([]);
    expect(el.textContent).toContain('In anderen Gesprächen ist nichts offen.');
    expect(el.querySelector('ul')).toBeNull();
  });

  it('Fehler: ein Satz und „Erneut versuchen“, das neu lädt', async () => {
    const { f, el, knopf, abrufen } = await render(new Error('netz'));
    expect(el.textContent).toContain('Die Liste ließ sich nicht laden.');
    abrufen.mockResolvedValueOnce([V1]);
    knopf('Erneut versuchen')!.click();
    await vi.waitFor(() => expect(abrufen).toHaveBeenCalledTimes(2));
    await f.whenStable();
    expect(el.querySelector('.meine-vorgaenge__name')?.textContent?.trim()).toBe('Lesen');
  });

  it('„Fortsetzen“ meldet den Vorgang nach außen', async () => {
    const { f, knopf } = await render();
    const fortsetzen = vi.fn();
    f.componentInstance.fortsetzen.subscribe(fortsetzen);
    knopf('Fortsetzen')!.click();
    expect(fortsetzen).toHaveBeenCalledWith(V1);
  });

  it('während eines Zugs geht „Fortsetzen“ nicht', async () => {
    const { f, knopf } = await render();
    f.componentRef.setInput('beschaeftigt', true);
    await f.whenStable();
    expect(knopf('Fortsetzen')!.disabled).toBe(true);
  });

  it('Löschen fragt im Panel nach; „Behalten“ führt zurück, „Ja“ löscht und sagt es an', async () => {
    const { f, el, knopf, loeschen } = await render([V1, { ...V1, id: '0a1b2c3d-0000-4000-8000-000000000002', titel: 'Optik' }]);
    knopf('Löschen')!.click();
    await f.whenStable();
    expect(el.textContent).toContain('„Lesen“ löschen? Die gesammelten Daten gehen verloren');
    expect(document.activeElement).toBe(knopf('Ja, löschen'));
    knopf('Behalten')!.click();
    await f.whenStable();
    expect(loeschen).not.toHaveBeenCalled();
    expect(document.activeElement?.getAttribute('aria-label')).toBe('„Lesen“ löschen');
    knopf('Löschen')!.click();
    await f.whenStable();
    knopf('Ja, löschen')!.click();
    await vi.waitFor(() => expect(el.querySelectorAll('.meine-vorgaenge__name')).toHaveLength(1));
    await f.whenStable();
    expect(el.querySelector('[role="status"][aria-live="polite"]')?.textContent?.trim()).toBe('„Lesen“ gelöscht.');
    expect(document.activeElement).toBe(el.querySelector('.meine-vorgaenge__titel'));
  });

  it('Esc schließt das Panel und steigt nicht weiter auf (das Widget bliebe sonst nicht offen)', async () => {
    const { f, el } = await render();
    const schliessen = vi.fn();
    const aussen = vi.fn();
    f.componentInstance.schliessen.subscribe(schliessen);
    document.body.addEventListener('keydown', aussen);
    el.querySelector<HTMLElement>('.meine-vorgaenge__titel')!
      .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(schliessen).toHaveBeenCalled();
    expect(aussen).not.toHaveBeenCalled();
    document.body.removeEventListener('keydown', aussen);
  });

  it('englisch', async () => {
    const { el, knopf } = await render([V1], EN);
    expect(el.querySelector('.meine-vorgaenge__stand')?.textContent).toMatch(/^Job running · last activity/);
    expect(knopf('Continue')).toBeDefined();
  });
});

describe('MeineVorgaengeComponent — Review AS-Ud', () => {
  it('Befund 2a: während eines Zugs geht auch Löschen nicht (der Zug arbeitet vielleicht darauf)', async () => {
    const { f, knopf, loeschen } = await render();
    knopf('Löschen')!.click();
    await f.whenStable();
    f.componentRef.setInput('beschaeftigt', true);
    await f.whenStable();
    expect(knopf('Ja, löschen')!.getAttribute('aria-disabled')).toBe('true');
    knopf('Ja, löschen')!.click();
    await f.whenStable();
    expect(loeschen).not.toHaveBeenCalled();
    knopf('Behalten')!.click();
    await f.whenStable();
    expect(knopf('Löschen')!.disabled).toBe(true);
  });

  it('Befund 4: Laden, Fehler und leere Liste sagt die ständige Statuszeile an', async () => {
    const leer = await render([]);
    const zeile = leer.el.querySelector('[role="status"][aria-live="polite"]')!;
    expect(zeile.textContent?.trim()).toBe('In anderen Gesprächen ist nichts offen.');
    leer.f.destroy();
    fixture = null;
    TestBed.resetTestingModule();
    const fehler = await render(new Error('netz'));
    expect(fehler.el.querySelector('[role="status"][aria-live="polite"]')!.textContent?.trim())
      .toBe('Die Liste ließ sich nicht laden.');
    expect(fehler.el.querySelectorAll('[role="status"]')).toHaveLength(1);
  });

  it('Befund 5: „Erneut versuchen“ — danach steht der Fokus auf dem Titel, nicht im Leeren', async () => {
    const { f, el, knopf, abrufen } = await render(new Error('netz'));
    abrufen.mockResolvedValueOnce([V1]);
    knopf('Erneut versuchen')!.focus();
    knopf('Erneut versuchen')!.click();
    await vi.waitFor(() => expect(el.querySelector('.meine-vorgaenge__name')).not.toBeNull());
    await f.whenStable();
    expect(document.activeElement).toBe(el.querySelector('.meine-vorgaenge__titel'));
  });

  it('Kleinigkeit 10: Esc in der Rückfrage schließt nur die Rückfrage', async () => {
    const { f, knopf } = await render();
    const schliessen = vi.fn();
    f.componentInstance.schliessen.subscribe(schliessen);
    knopf('Löschen')!.click();
    await f.whenStable();
    knopf('Ja, löschen')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await f.whenStable();
    expect(schliessen).not.toHaveBeenCalled();
    expect(knopf('Ja, löschen')).toBeUndefined();
    expect(document.activeElement?.getAttribute('aria-label')).toBe('„Lesen“ löschen');
    knopf('Löschen')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(schliessen).toHaveBeenCalled();
  });
});

describe('MeineVorgaengeComponent — Querschnitts-Review Q-7', () => {
  it('der Laufstatus in Worten — feiner als der Vorgang, „Ablauf beendet“ für fertige', async () => {
    const { el } = await render([
      { ...V1, status: 'wartet_person', lauf_status: 'wartet_freigabe' },
      { ...V1, id: '0a1b2c3d-0000-4000-8000-000000000002', status: 'aktiv', lauf_status: 'fertig' },
    ]);
    const staende = [...el.querySelectorAll('.meine-vorgaenge__stand')].map((s) => s.textContent ?? '');
    expect(staende[0]).toMatch(/^Wartet auf deine Freigabe · /);
    expect(staende[1]).toMatch(/^Ablauf beendet · /);
  });
});

describe('MeineVorgaengeComponent — AS-7b', () => {
  it('eine wartende Führung heißt „Wartet auf den Seitenwechsel“', async () => {
    const { el } = await render([{ ...V1, status: 'wartet_person', lauf_status: 'wartet_seite' }]);
    expect(el.querySelector('.meine-vorgaenge__stand')?.textContent ?? '')
      .toMatch(/^Wartet auf den Seitenwechsel · /);
  });
});
