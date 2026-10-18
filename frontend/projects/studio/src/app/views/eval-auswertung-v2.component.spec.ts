// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { EvalRunDetail } from '../core/eval-api.service';
import type { AblaufAuswertung, AuswertungV2 } from '../core/eval-auswertung';
import { StudioAnsicht } from '../core/studio-ansicht.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalAuswertungV2Component } from './eval-auswertung-v2.component';

/**
 * Die Auswertung v2 im Lauf-Detail (Paket 13, F7) in der Reihenfolge des Plans (§5.6):
 * Messbedingungen, Kennzahlen, Kurzbericht, Matrizen, Problemliste, Abläufe, Zeiten.
 */
function ablauf(id: string, zielgruppe: string, gesamt: number): AblaufAuswertung {
  return {
    flow_id: id, title: id, zielgruppe, skalen: { verlauf: gesamt }, gesamt,
    statement: `S ${id}`, auffaelligkeiten: [], urteil_fehler: '',
    harte_quote: { bestanden: 2, geprueft: 2 }, zug_mittel: gesamt, zuege: 1, chat_fehler: 0,
    latenz_p50_ms: 2000, kosten: 0.01, werkzeugaufrufe: 1,
  };
}

const AUSWERTUNG: AuswertungV2 = {
  je_ablauf: [ablauf('GV-LEH-1', 'P-LEH', 3), ablauf('GV-LER-1', 'P-LER', 5)],
  gesamt: {
    ablaeufe: 2, zuege: 2, gesamt_mittel: 4, skalen_mittel: { verlauf: 4 }, zug_mittel: 4,
    harte_quote: { bestanden: 4, geprueft: 4 }, latenz: { p50_ms: 2000, p95_ms: 6000 },
    kosten_je_zug: 0.0123, chat_fehler: 0, judge_fehler: 1, judge_kosten: 0.05,
    judge_aufrufe: 5, judge_fassung: 'f4ssung',
  },
  matrix_zielgruppe_anwendungsfall: {
    'P-LEH': { suchen: { mittel: 3, n: 1 } }, 'P-LER': { erklaeren: { mittel: 5, n: 1 } },
  },
  matrix_ablauf_skala: { 'GV-LEH-1': { verlauf: 3, gesamt: 3 }, 'GV-LER-1': { verlauf: 5, gesamt: 5 } },
  matrix_persona_intent: { 'P-LER': { I03: { mittel: 2, n: 1 } } },
  zeiten: { knoten: { respond: { p50_ms: 2000, p95_ms: 3000, n: 2 } }, schritte: {}, llm: {} },
};

const RUN = {
  id: 'r1', engine: 'pattern', mode: 'golden', status: 'done',
  summary: {
    messbedingungen: { maschine: 'pattern', weg: { modell: 'gpt-6-luna' } },
    judge_fassung: 'f4ssung',
    kurzbericht: { text: 'Trägt meistens.', baustellen: [{ ablauf: 'GV-LEH-1', text: 'Lernpfad' }] },
  },
  conversations: [
    { flow_id: 'GV-LEH-1', zielgruppe: 'P-LEH', turns: [{ user: 'u', anwendungsfall: 'suchen' }] },
    { flow_id: 'GV-LER-1', zielgruppe: 'P-LER', turns: [{ user: 'u', anwendungsfall: 'erklaeren' }] },
  ],
  auswertung: AUSWERTUNG,
  profile: { currency: 'EUR' },
} as unknown as EvalRunDetail;

const norm = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ').trim();

describe('EvalAuswertungV2Component (Paket 13, F7)', () => {
  let fixture: ComponentFixture<EvalAuswertungV2Component>;
  let el: HTMLElement;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    localStorage.clear();
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    TestBed.inject(StudioAnsicht).waehle('pattern');
    fixture = TestBed.createComponent(EvalAuswertungV2Component);
    fixture.componentRef.setInput('run', RUN);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('ordnet die Abschnitte wie im Plan', () => {
    const titel = Array.from(el.querySelectorAll('h4'), (h) => norm(h.textContent));
    expect(titel).toEqual([
      'Kennzahlen', 'Kurzbericht', 'Zielgruppe × Anwendungsfall', 'Ablauf × Skala',
      'Persona × Intent (nur Muster-Züge)', 'Problemliste', 'Abläufe', 'Zeiten je Schritt',
    ]);
    // Die Messbedingungen stehen davor, aufklappbar.
    expect(el.firstElementChild?.querySelector('studio-eval-messbedingungen')).not.toBeNull();
  });

  it('nennt die Kennzahlen mit Preis in der Währung der Preistafel', () => {
    const paare = Object.fromEntries(Array.from(el.querySelectorAll('.av-kennzahlen > div'),
      (d) => [norm(d.querySelector('dt')?.textContent), norm(d.querySelector('dd')?.textContent)]));
    expect(paare['Gesamt (Mittel der Abläufe)']).toBe('4');
    expect(paare['Harte Prüfungen']).toBe('4/4');
    expect(paare['Antwortzeit Median / p95']).toBe('2,0 s / 6,0 s');
    expect(paare['Kosten je Zug']).toBe('0,01 €'); // Cent-Genauigkeit wie überall im Studio
    expect(paare['Chat-Fehler / Judge-Ausfälle']).toBe('0 / 1');
  });

  it('zeigt ohne Währung Bruchteile eines Cents, nicht „0“ (Review PR #18)', async () => {
    fixture.componentRef.setInput('run', { ...RUN, profile: undefined, auswertung: {
      ...RUN.auswertung!, gesamt: { ...RUN.auswertung!.gesamt, kosten_je_zug: 0.0031 } } });
    await fixture.whenStable();
    const paare = Object.fromEntries(Array.from(el.querySelectorAll('.av-kennzahlen > div'),
      (d) => [norm(d.querySelector('dt')?.textContent), norm(d.querySelector('dd')?.textContent)]));
    expect(paare['Kosten je Zug']).toBe('0,0031');
  });

  it('zeigt den Kurzbericht mit Baustellen', () => {
    const b = norm(el.querySelector('.av-bericht')?.textContent);
    expect(b).toContain('Trägt meistens.');
    expect(b).toContain('GV-LEH-1');
    expect(b).toContain('Lernpfad');
  });

  it('blendet Persona × Intent in der Agent-Ansicht aus', async () => {
    TestBed.inject(StudioAnsicht).waehle('agent');
    await fixture.whenStable();
    expect(norm(el.textContent)).not.toContain('Persona × Intent');
  });

  it('eine Zelle Zielgruppe × Anwendungsfall zeigt nur die Abläufe dieser Zielgruppe', async () => {
    el.querySelector<HTMLButtonElement>('studio-eval-matrix button')!.click(); // P-LEH × suchen
    await fixture.whenStable();
    const karten = Array.from(el.querySelectorAll('studio-eval-ablauf-karte section'), (s) => s.id);
    expect(karten).toEqual(['ablauf-GV-LEH-1']);
    expect(norm(el.querySelector('.av-filter')?.textContent)).toContain('P-LEH');
    el.querySelector<HTMLButtonElement>('.av-filter button')!.click();
    await fixture.whenStable();
    expect(el.querySelectorAll('studio-eval-ablauf-karte').length).toBe(2);
  });

  it('ein Ablauf ohne Zielgruppe gehört zur Zeile „?“ der Matrix (Review PR #18)', async () => {
    // Die Matrix schlüsselt eine fehlende Zielgruppe als „?“, die Karte trägt "" — ein Klick
    // auf die „?“-Zeile ließ die Liste leer.
    const ohne = { ...RUN, auswertung: { ...AUSWERTUNG,
      je_ablauf: [{ ...AUSWERTUNG.je_ablauf[0], zielgruppe: '' }, AUSWERTUNG.je_ablauf[1]] } };
    fixture.componentRef.setInput('run', ohne as unknown as EvalRunDetail);
    await fixture.whenStable();
    fixture.componentInstance.waehleZa({ zeile: '?', spalte: 'suchen' });
    await fixture.whenStable();
    const karten = Array.from(el.querySelectorAll('studio-eval-ablauf-karte section'), (k) => k.id);
    expect(karten).toEqual(['ablauf-GV-LEH-1']);
  });

  it('sagt es, wenn eine Auswahl keinen Ablauf trifft (Review PR #18)', async () => {
    fixture.componentInstance.waehleZa({ zeile: 'P-NIEMAND', spalte: 'suchen' });
    await fixture.whenStable();
    expect(el.querySelectorAll('studio-eval-ablauf-karte').length).toBe(0);
    expect(norm(el.querySelector('.av-leer')?.textContent)).toContain('Kein Ablauf');
  });

  it('springt aus der Problemliste zur Ablauf-Karte', async () => {
    el.querySelector<HTMLButtonElement>('.ep-sprung')!.click();
    await fixture.whenStable();
    expect(document.activeElement?.id).toBe('ablauf-GV-LEH-1');
  });

  it('sagt es, wenn der Kurzbericht ausfiel', async () => {
    fixture.componentRef.setInput('run', {
      ...RUN, summary: { ...RUN.summary, kurzbericht: undefined, kurzbericht_fehler: 'Judge weg' },
    });
    await fixture.whenStable();
    expect(norm(el.querySelector('.av-bericht')?.textContent)).toContain('Kein Kurzbericht: Judge weg');
  });
});
