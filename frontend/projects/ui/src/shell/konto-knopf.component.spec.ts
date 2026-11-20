import { provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ICONS } from '../icons/icons';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { EN } from '../i18n/en';
import { KontoKnopfComponent } from './konto-knopf.component';

/**
 * Paket D1 (Plan 2026-11-20, E-D1): EIN Konto-Knopf statt Kürzel-Kreis und Anmelde-Knopf.
 *
 * - Abgemeldet: Umriss einer Person, gestrichelt; der Klick meldet an (synchron — die Nutzergeste).
 * - Angemeldet: Initialen (ohne Namen das gefüllte Personen-Symbol); der Klick öffnet ein kleines
 *   Menü nach dem APG-Muster „Menu Button“: `aria-haspopup`, `aria-expanded`, Pfeiltasten, Esc
 *   schließt und gibt den Fokus an den Knopf, Klick außerhalb und Tab hinaus schließen.
 */

let fixture: ComponentFixture<KontoKnopfComponent> | null = null;

function render(over: { angemeldet?: boolean; name?: string; en?: boolean } = {}) {
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(KontoKnopfComponent);
  fixture = f;
  f.componentRef.setInput('angemeldet', over.angemeldet ?? false);
  f.componentRef.setInput('name', over.name ?? '');
  f.componentRef.setInput('translate', over.en ? createTranslator(EN, DE) : createTranslator(DE, DE));
  document.body.appendChild(f.nativeElement);
  f.detectChanges();
  const el = f.nativeElement as HTMLElement;
  const knopf = () => el.querySelector('button.btn-auth') as HTMLButtonElement;
  const menue = () => el.querySelector('[role="menu"]') as HTMLElement | null;
  const eintraege = () => Array.from(el.querySelectorAll<HTMLElement>('[role="menuitem"]'));
  const anmelden = vi.fn();
  const abmelden = vi.fn();
  f.componentInstance.anmelden.subscribe(anmelden);
  f.componentInstance.abmelden.subscribe(abmelden);
  return { f, el, knopf, menue, eintraege, anmelden, abmelden };
}

async function stabil(f: ComponentFixture<KontoKnopfComponent>): Promise<void> {
  f.detectChanges();
  await f.whenStable();
}

const taste = (ziel: Element, key: string) => {
  const e = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, composed: true });
  ziel.dispatchEvent(e);
  return e;
};

const pfad = (svg: string) => svg.match(/ d="([^"]+)"/)![1];

afterEach(() => {
  fixture?.destroy();
  fixture = null;
  document.body.innerHTML = '';
  vi.restoreAllMocks();
  TestBed.resetTestingModule();
});

describe('Konto-Knopf — abgemeldet', () => {
  it('ein Knopf mit Umriss-Symbol, gestrichelt markiert und „Anmelden – nicht angemeldet“ genannt', () => {
    const { el, knopf } = render();
    const b = knopf();
    expect(el.querySelectorAll('button')).toHaveLength(1);
    expect(b.getAttribute('aria-label')).toBe('Anmelden – nicht angemeldet');
    expect(b.getAttribute('title')).toBe('Anmelden – nicht angemeldet');
    expect(b.classList).toContain('btn-auth--aus');
    expect(b.innerHTML).toContain(pfad(ICONS.person_outline));
    expect(b.hasAttribute('aria-haspopup'), 'abgemeldet öffnet er kein Menü').toBe(false);
    expect(b.hasAttribute('aria-expanded')).toBe(false);
  });

  it('der Klick meldet SYNCHRON an und öffnet kein Menü', () => {
    const { knopf, menue, anmelden } = render();
    knopf().click();
    expect(anmelden).toHaveBeenCalledTimes(1);   // kein await davor — die Nutzergeste
    expect(menue()).toBeNull();
  });

  it('Pfeiltasten öffnen abgemeldet nichts', () => {
    const { f, knopf, menue } = render();
    taste(knopf(), 'ArrowDown');
    f.detectChanges();
    expect(menue()).toBeNull();
  });
});

describe('Konto-Knopf — angemeldet', () => {
  it('zeigt die Initialen und nennt die Person', () => {
    const { knopf } = render({ angemeldet: true, name: 'Jan Schachtschabel' });
    const b = knopf();
    expect(b.textContent?.trim()).toBe('JS');
    expect(b.querySelector('svg'), 'kein Symbol, wenn Buchstaben da sind').toBeNull();
    expect(b.classList).not.toContain('btn-auth--aus');
    expect(b.getAttribute('aria-label')).toBe('Konto – angemeldet als Jan Schachtschabel');
    expect(b.getAttribute('aria-haspopup')).toBe('menu');
    expect(b.getAttribute('aria-expanded')).toBe('false');
    expect(b.hasAttribute('aria-controls'), 'zeigt nicht auf ein Menü, das es nicht gibt').toBe(false);
  });

  it('ohne Namen das gefüllte Personen-Symbol und „Konto – angemeldet“', () => {
    const { knopf } = render({ angemeldet: true });
    const b = knopf();
    expect(b.textContent?.trim()).toBe('');
    expect(b.innerHTML).toContain(pfad(ICONS.person));
    expect(b.innerHTML).not.toContain(pfad(ICONS.person_outline));
    expect(b.getAttribute('aria-label')).toBe('Konto – angemeldet');
  });

  it('der Klick öffnet das Menü: wer angemeldet ist, „Abmelden“ hat den Fokus', async () => {
    const { f, knopf, menue, eintraege, abmelden } = render({ angemeldet: true, name: 'Jan Schachtschabel' });
    knopf().click();
    await stabil(f);
    const m = menue()!;
    expect(knopf().getAttribute('aria-expanded')).toBe('true');
    expect(knopf().getAttribute('aria-controls')).toBe(m.id);
    const wer = document.getElementById(m.getAttribute('aria-labelledby')!)!;
    expect(wer.textContent?.trim()).toBe('Angemeldet als Jan Schachtschabel');
    expect(eintraege().map((e) => e.textContent?.trim())).toEqual(['Abmelden']);
    expect(document.activeElement).toBe(eintraege()[0]);
    expect(abmelden).not.toHaveBeenCalled();
  });

  it('ohne Namen sagt der Kopf des Menüs nur „Angemeldet“', async () => {
    const { f, knopf, menue } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    const wer = document.getElementById(menue()!.getAttribute('aria-labelledby')!)!;
    expect(wer.textContent?.trim()).toBe('Angemeldet');
  });

  it('„Abmelden“ schließt das Menü, gibt den Fokus an den Knopf und meldet ab', async () => {
    const { f, knopf, menue, eintraege, abmelden } = render({ angemeldet: true, name: 'Jan' });
    knopf().click();
    await stabil(f);
    eintraege()[0].click();
    await stabil(f);
    expect(abmelden).toHaveBeenCalledTimes(1);
    expect(menue()).toBeNull();
    expect(document.activeElement).toBe(knopf());
  });

  it('ein zweiter Klick auf den Knopf schließt das Menü wieder', async () => {
    const { f, knopf, menue } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    knopf().click();
    await stabil(f);
    expect(menue()).toBeNull();
    expect(knopf().getAttribute('aria-expanded')).toBe('false');
  });
});

describe('Konto-Knopf — Tastatur und Schließen', () => {
  it('Pfeil runter auf dem Knopf öffnet und fokussiert den ersten Eintrag, Pfeil hoch den letzten', async () => {
    const { f, knopf, eintraege } = render({ angemeldet: true });
    expect(taste(knopf(), 'ArrowDown').defaultPrevented).toBe(true);   // die Seite scrollt nicht
    await stabil(f);
    expect(document.activeElement).toBe(eintraege()[0]);
    taste(document.activeElement!, 'Escape');
    await stabil(f);
    taste(knopf(), 'ArrowUp');
    await stabil(f);
    expect(document.activeElement).toBe(eintraege().at(-1));
  });

  it('im Menü wandern Pfeile, Pos1 und Ende über die Einträge (mit Umlauf)', async () => {
    const { f, knopf, eintraege } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    for (const key of ['ArrowDown', 'ArrowUp', 'Home', 'End']) {
      expect(taste(document.activeElement!, key).defaultPrevented, key).toBe(true);
      expect(document.activeElement, key).toBe(eintraege()[0]);   // ein Eintrag: bleibt bei ihm
    }
  });

  it('Esc schließt, gibt den Fokus an den Knopf und endet hier (schließt nicht das Chat-Fenster)', async () => {
    const { f, knopf, menue } = render({ angemeldet: true });
    const draussen = vi.fn();
    document.body.addEventListener('keydown', draussen);
    knopf().click();
    await stabil(f);
    taste(document.activeElement!, 'Escape');
    await stabil(f);
    document.body.removeEventListener('keydown', draussen);
    expect(menue()).toBeNull();
    expect(document.activeElement).toBe(knopf());
    expect(draussen).not.toHaveBeenCalled();
  });

  it('Esc bei geschlossenem Menü bleibt unberührt (das Chat-Fenster darf schließen)', () => {
    const { knopf } = render({ angemeldet: true });
    const draussen = vi.fn();
    document.body.addEventListener('keydown', draussen);
    taste(knopf(), 'Escape');
    document.body.removeEventListener('keydown', draussen);
    expect(draussen).toHaveBeenCalledTimes(1);
  });

  it('ein Klick außerhalb schließt das Menü, ohne den Fokus zu holen', async () => {
    const { f, knopf, menue } = render({ angemeldet: true });
    const anderes = document.createElement('button');
    document.body.appendChild(anderes);
    knopf().click();
    await stabil(f);
    anderes.focus();
    anderes.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, composed: true }));
    await stabil(f);
    expect(menue()).toBeNull();
    expect(document.activeElement).toBe(anderes);
  });

  it('ein Klick im Menü schließt es nicht', async () => {
    const { f, knopf, menue } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    menue()!.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, composed: true }));
    await stabil(f);
    expect(menue()).not.toBeNull();
  });

  it('Tab aus dem Menü hinaus schließt es', async () => {
    const { f, knopf, menue, eintraege } = render({ angemeldet: true });
    const anderes = document.createElement('button');
    document.body.appendChild(anderes);
    knopf().click();
    await stabil(f);
    eintraege()[0].dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: anderes }));
    await stabil(f);
    expect(menue()).toBeNull();
  });

  it('wird die Person abgemeldet, während das Menü offen ist, geht es zu', async () => {
    const { f, knopf, menue } = render({ angemeldet: true, name: 'Jan' });
    knopf().click();
    await stabil(f);
    f.componentRef.setInput('angemeldet', false);
    await stabil(f);
    expect(menue()).toBeNull();
    expect(knopf().getAttribute('aria-label')).toBe('Anmelden – nicht angemeldet');
  });
});

describe('Konto-Knopf — Review Paket D', () => {
  it('1: Umschalt+Tab aus dem Eintrag zurück auf den Knopf schließt das Menü (ohne Fokus-Sprung)', async () => {
    const { f, knopf, menue, eintraege } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    knopf().focus();   // wohin Umschalt+Tab den Fokus bringt
    eintraege()[0]?.dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: knopf() }));
    await stabil(f);
    expect(menue()).toBeNull();
    expect(knopf().getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(knopf());
  });

  it('2: am Dokument lauscht es nur, solange das Menü offen ist', async () => {
    const an = vi.spyOn(document, 'addEventListener');
    const ab = vi.spyOn(document, 'removeEventListener');
    const zeiger = (spy: typeof an) => spy.mock.calls.filter(([typ]) => typ === 'pointerdown').length;
    const { f, knopf } = render({ angemeldet: true });
    expect(zeiger(an), 'geschlossen: kein Lauscher').toBe(0);
    knopf().click();
    await stabil(f);
    expect(zeiger(an)).toBe(1);
    knopf().click();   // zu
    await stabil(f);
    expect(zeiger(ab)).toBe(1);
    knopf().click();   // wieder auf, dann zerstört
    await stabil(f);
    f.destroy();
    fixture = null;
    expect(zeiger(an)).toBe(2);
    expect(zeiger(ab), 'beim Zerstören abgemeldet').toBe(2);
  });

  it('7: wird abgemeldet, während der Fokus im Menü liegt, geht er an den Knopf', async () => {
    const { f, knopf, menue, eintraege } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    expect(document.activeElement).toBe(eintraege()[0]);
    f.componentRef.setInput('angemeldet', false);
    await stabil(f);
    expect(menue()).toBeNull();
    expect(document.activeElement).toBe(knopf());
  });

  it('8: ein gehaltenes Enter (Wiederholung) im Menü meldet nicht ab', async () => {
    const { f, knopf, eintraege, abmelden } = render({ angemeldet: true });
    knopf().click();
    await stabil(f);
    for (const key of ['Enter', ' ']) {
      const e = new KeyboardEvent('keydown', { key, repeat: true, bubbles: true, cancelable: true });
      eintraege()[0].dispatchEvent(e);
      expect(e.defaultPrevented, key).toBe(true);   // kein Klick aus der Wiederholung
    }
    expect(abmelden).not.toHaveBeenCalled();
  });
});

describe('Konto-Knopf — Sprache', () => {
  it('spricht Englisch, wenn das Widget Englisch spricht', async () => {
    const aus = render({ en: true });
    expect(aus.knopf().getAttribute('aria-label')).toBe('Sign in – not signed in');
    fixture?.destroy();
    TestBed.resetTestingModule();

    const { f, knopf, menue, eintraege } = render({ angemeldet: true, name: 'Jan Schachtschabel', en: true });
    expect(knopf().getAttribute('aria-label')).toBe('Account – signed in as Jan Schachtschabel');
    knopf().click();
    await stabil(f);
    expect(document.getElementById(menue()!.getAttribute('aria-labelledby')!)!.textContent?.trim())
      .toBe('Signed in as Jan Schachtschabel');
    expect(eintraege()[0].textContent?.trim()).toBe('Sign out');
  });
});
