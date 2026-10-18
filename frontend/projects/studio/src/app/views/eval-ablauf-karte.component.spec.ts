// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { AblaufAuswertung } from '../core/eval-auswertung';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalAblaufKarteComponent } from './eval-ablauf-karte.component';
import type { TranscriptConv } from './eval-transcript';

/**
 * Eine Ablauf-Karte (Paket 13, F4): Kopf mit Kennzahlen, Skalen als Balken mit Zahl,
 * Statement und Auffälligkeiten; aufgeklappt die Züge mit Zug-Noten, Notiz, harten
 * Prüfungen, Werkzeugen und der Zeit je Schritt.
 */
const ABLAUF: AblaufAuswertung = {
  flow_id: 'GV-LEH-1', title: 'Lehrkraft: Lernpfad', zielgruppe: 'P-LEH',
  skalen: { zielgruppe: 5, verlauf: 2 }, gesamt: 3, statement: 'Lernpfad fehlt.',
  auffaelligkeiten: [{ zug: 2, art: 'verlauf', text: 'Kontext vergessen' }],
  urteil_fehler: '', harte_quote: { bestanden: 3, geprueft: 4 }, zug_mittel: 3.5, zuege: 2,
  chat_fehler: 0, latenz_p50_ms: 4200, kosten: null, werkzeugaufrufe: 2,
};

const CONV: TranscriptConv = {
  flow_id: 'GV-LEH-1',
  turns: [
    {
      user: 'Material zu Brüchen', anwendungsfall: 'suchen',
      judge: { gesamt: 5, anliegen: 5, angebot: 4, qualitaet: 5, ton: 5, notiz: 'passt' },
      golden: { checks: { register: true, structure: true } },
      debug: {
        tools_called: ['search_wlo_all', 'respond_to_user'],
        token_usage: { zeiten_ms: { assess: 300, respond: 3900, 'respond.werkzeuge': 1500 } },
      },
    },
    {
      user: 'Und als Lernpfad?', anwendungsfall: 'zusammenstellen', judge_failed: 'Judge weg',
      golden: { checks: { register: true, tools_any: false } }, debug: { tools_called: [] },
    },
  ],
};

/** Intl setzt vor Einheiten ein geschütztes Leerzeichen — die Prüfungen lesen normalen Text. */
const norm = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ');

describe('EvalAblaufKarteComponent (Paket 13, F4)', () => {
  let fixture: ComponentFixture<EvalAblaufKarteComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(EvalAblaufKarteComponent);
    fixture.componentRef.setInput('ablauf', ABLAUF);
    fixture.componentRef.setInput('conv', CONV);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('ist ein Sprungziel mit Überschrift und Kennzeile', () => {
    const karte = el.querySelector('section')!;
    expect(karte.id).toBe('ablauf-GV-LEH-1');
    expect(karte.getAttribute('tabindex')).toBe('-1');
    expect(el.querySelector('h5')?.textContent).toContain('GV-LEH-1');
    expect(el.querySelector('h5')?.textContent).toContain('Lehrkraft: Lernpfad');
    expect(el.querySelector('.ak-kennzeile')?.textContent).toContain('harte Prüfungen 3/4');
    expect(norm(el.querySelector('.ak-kennzeile')?.textContent)).toContain('4,2 s');
  });

  it('zeigt jede Skala mit Namen und Zahl, der Balken ist Zierde', () => {
    const zeilen = Array.from(
      el.querySelectorAll('.ak-skala'), (z) => norm(z.textContent).trim());
    expect(zeilen).toEqual(['Gesamt 3', 'Zielgruppe 5', 'Verlauf 2']);
    expect(el.querySelector('.ak-balken')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('zeigt Statement und Auffälligkeiten mit Zug', () => {
    expect(el.querySelector('.ak-statement')?.textContent).toContain('Lernpfad fehlt.');
    expect(el.querySelector('.ak-auff')?.textContent).toContain('Zug 2');
  });

  it('zeigt die Züge: Noten, Notiz, Prüfungen, Werkzeuge, Zeiten', () => {
    const zuege = el.querySelectorAll('.ak-zug');
    expect(zuege.length).toBe(2);
    const erster = norm(zuege[0].textContent);
    expect(erster).toContain('Zug 1');
    expect(erster).toContain('suchen');
    expect(erster).toContain('Angebot 4');
    expect(erster).toContain('passt');
    expect(erster).toContain('harte Prüfungen 2/2');
    expect(erster).toContain('search_wlo_all');
    expect(erster).not.toContain('respond_to_user'); // interne Muster-Werkzeuge
    expect(erster).toContain('assess 0,3 s');
    const zweiter = norm(zuege[1].textContent);
    expect(zweiter).toContain('Zug-Urteil fehlt: Judge weg');
    expect(zweiter).toContain('verfehlt: Werkzeug-Soll');
    expect(zweiter).toContain('keine Werkzeuge');
  });

  it('markiert die Züge des gewählten Anwendungsfalls und klappt auf', async () => {
    expect(el.querySelector('details')!.open).toBe(false);
    fixture.componentRef.setInput('anwendungsfall', 'zusammenstellen');
    await fixture.whenStable();
    expect(el.querySelector('details')!.open).toBe(true);
    const markiert = Array.from(el.querySelectorAll('.ak-zug--treffer'), (z) => z.textContent);
    expect(markiert).toHaveLength(1);
    expect(markiert[0]).toContain('passt zur gewählten Zelle');
  });
});
