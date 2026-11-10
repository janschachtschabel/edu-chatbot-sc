// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import type { AblaufTeil } from '../core/ablauf-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { ABLAEUFE_SEITE } from '../i18n/catalogue/ablaeufe-seite';
import { AblaufDatenComponent, TYP_NAMEN } from './ablauf-daten.component';
import { schrittFolge } from './ablauf-folge';
import { FORM_LISTENWAHL } from './form-listenwahl';

const FOLGE = schrittFolge({ schritte: [
  { id: 'entwurf', typ: 'werkzeug' }, { id: 'frage', typ: 'nachricht' }, { id: 'e', typ: 'ende' }] });

function teil(name: string, mehr: Partial<AblaufTeil>): AblaufTeil {
  return { name, typen: [], schreiber: [], leser: [], vor_dem_start: false, aus_gespraech: false,
    beispiel: null, ...mehr };
}

function bauen(teile: readonly AblaufTeil[] | null, listenwahl?: { waehlen: ReturnType<typeof vi.fn> }) {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(),
    ...(listenwahl ? [{ provide: FORM_LISTENWAHL, useValue: listenwahl }] : []),
  ] });
  const fixture = TestBed.createComponent(AblaufDatenComponent);
  fixture.componentRef.setInput('folge', FOLGE);
  fixture.componentRef.setInput('pfad', ['ablauf']);
  fixture.componentRef.setInput('teile', teile);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

/** Der sichtbare Text je Zelle — ohne den Text nur für Screenreader (`.sr`). */
function zeilen(el: HTMLElement): string[][] {
  return [...el.querySelectorAll('tbody tr')].map((tr) =>
    [...tr.children].map((c) => {
      const kopie = c.cloneNode(true) as HTMLElement;
      kopie.querySelectorAll('.sr').forEach((s) => s.remove());
      return kopie.textContent!.replace(/\s+/g, ' ').trim();
    }));
}

/** AS-Dc: die Sicht „Daten“ — eine Tabelle je Teil, Schritte mit ihrer Kennung. */
describe('AblaufDatenComponent (AS-Dc)', () => {
  it('zeigt je Teil Typ, Schreiber, Leser und Beispiel', () => {
    const el = bauen([
      teil('eigener', { typen: ['wlo.sammlungsstruktur@1'], schreiber: [0], leser: [1],
        beispiel: '{"titel": "Physik"}' }),
      teil('notiz', { typen: ['?'], schreiber: [0], leser: [1] }),
    ]);
    expect(el.querySelector('summary')!.textContent).toContain('2 Teile');
    expect(zeilen(el)).toEqual([
      ['eigener', 'Sammlungsstruktur', 'entwurf', 'frage', '{"titel": "Physik"}'],
      ['notiz', 'unbekannt (KI)', 'entwurf', 'frage', '—'],
    ]);
  });

  it('unterscheidet vor dem Start, aus dem Gespräch und von keinem Schritt (Review AS-Dc)', () => {
    const el = bauen([
      teil('ablage', { typen: ['wlo.ablage@1'], vor_dem_start: true, aus_gespraech: true, leser: [0] }),
      teil('draft', { typen: ['wlo.sammlungsstruktur@1'], aus_gespraech: true, leser: [0] }),
      teil('entwrf', { leser: [0] }),
      teil('modulteil', { typen: ['…'], schreiber: [0] }),
    ]);
    const z = zeilen(el);
    expect(z[0].slice(1, 3)).toEqual(['Abgelegte Dateien', 'vor dem Start']);
    expect(z[1][2]).toBe('aus dem Gespräch');
    expect(z[2].slice(1, 3)).toEqual(['—', 'von keinem Schritt']);
    // ein Tippfehler fällt auf: nicht nur durch Farbe, sondern durch den Text
    expect(el.querySelectorAll('tbody tr')[2].querySelector('.sf-error')!.textContent).toContain('von keinem Schritt');
    expect(z[3].slice(1, 4)).toEqual(['unbekannt', 'entwurf', 'niemandem']);
  });

  it('nennt bekannte Typen beim Namen, Werkzeugergebnisse nach dem Werkzeug (RB-2)', () => {
    const el = bauen([
      teil('a', { typen: ['text', 'wlo.start@1'] }),
      teil('b', { typen: ['wlo_create_collection_tree@1'] }),
      teil('c', { typen: ['search_wlo_all@1'] }),
      teil('d', { typen: ['fremd.typ@2'] }),
    ]);
    const z = zeilen(el);
    expect(z.map((r) => r[1])).toEqual([
      'Text, Startdaten', 'Angelegte Sammlungen', 'Ergebnis von search_wlo_all', 'fremd.typ@2']);
    // die Kennung bleibt für Fachleute erreichbar — auch ohne Maus (Review RB-2, Befund 4)
    const zelle = el.querySelectorAll('tbody tr')[0].children[1] as HTMLElement;
    expect(zelle.getAttribute('title')).toBe('text, wlo.start@1');
    expect(zelle.querySelector('.sr')!.textContent).toBe(' (text, wlo.start@1)');
  });

  it('Marken ohne Kennung tragen keinen title; Werkzeugnamen mit Bindestrich (Review RB-2)', () => {
    const el = bauen([teil('ki', { typen: ['?'] }), teil('w', { typen: ['srv-x@1'] })]);
    const [ki] = [...el.querySelectorAll('tbody tr')].map((tr) => tr.children[1] as HTMLElement);
    expect(ki.hasAttribute('title')).toBe(false);
    expect(ki.querySelector('.sr')).toBeNull();
    expect(zeilen(el)[1][1]).toBe('Ergebnis von srv-x');
  });

  it('jeder bekannte Typ hat einen Namen auf Deutsch und Englisch (RB-2)', () => {
    for (const typ of Object.keys(TYP_NAMEN)) {
      for (const sprache of ['de', 'en'] as const) {
        const name = ABLAEUFE_SEITE[sprache][`ablaufDaten.typName.${TYP_NAMEN[typ]}`];
        expect(name, `${sprache}: ${typ}`).toBeTruthy();
      }
    }
  });

  it('ein Schritt führt in die Liste der Schritte', () => {
    const listenwahl = { waehlen: vi.fn() };
    const el = bauen([teil('x', { typen: ['text'], schreiber: [1], leser: [0] })], listenwahl);
    const knoepfe = el.querySelectorAll<HTMLButtonElement>('button.ad-schritt');
    expect(knoepfe).toHaveLength(2);
    knoepfe[0].click();
    expect(listenwahl.waehlen).toHaveBeenCalledWith(['ablauf', 'schritte'], 1);
    expect(knoepfe[1].getAttribute('aria-label')).toContain('entwurf');
  });

  it('ohne Liste der Schritte bleiben die Schritte Text', () => {
    const el = bauen([teil('x', { typen: ['text'], schreiber: [1] })]);
    expect(el.querySelector('button')).toBeNull();
    expect(el.querySelector('span.ad-schritt')!.textContent).toBe('frage');
  });

  it('noch nicht (gültig) geprüft: nichts; geprüft ohne Teile: ein Satz (Review AS-Dc, Befund 12)', () => {
    expect(bauen(null).textContent!.trim()).toBe('');
    const el = bauen([]);
    expect(el.querySelector('details')).toBeNull();
    expect(el.textContent).toContain('Daten: keine Teile.');
  });
});
