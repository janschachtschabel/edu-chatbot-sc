// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { AblaufAuswertung } from '../core/eval-auswertung';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalProblemlisteComponent } from './eval-problemliste.component';

/**
 * Die Problemliste (Paket 13, F5): Abläufe mit Schwächen, schwächste zuerst — je Eintrag die
 * Noten unter 4, das Statement und die Auffälligkeiten, dazu ein Sprung zur Ablauf-Karte.
 */
function ablauf(id: string, gesamt: number | null, skalen: Record<string, number>,
  extra: Partial<AblaufAuswertung> = {}): AblaufAuswertung {
  return {
    flow_id: id, title: `Titel ${id}`, zielgruppe: 'P-LEH', skalen, gesamt,
    statement: `Statement ${id}`, auffaelligkeiten: [], urteil_fehler: '',
    harte_quote: { bestanden: 1, geprueft: 1 }, zug_mittel: gesamt, zuege: 2, chat_fehler: 0,
    latenz_p50_ms: 1000, kosten: null, werkzeugaufrufe: 1, ...extra,
  };
}

describe('EvalProblemlisteComponent (Paket 13, F5)', () => {
  let fixture: ComponentFixture<EvalProblemlisteComponent>;
  let el: HTMLElement;

  async function mit(ablaeufe: readonly AblaufAuswertung[]): Promise<void> {
    fixture.componentRef.setInput('ablaeufe', ablaeufe);
    await fixture.whenStable();
  }

  beforeEach(() => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(EvalProblemlisteComponent);
    el = fixture.nativeElement as HTMLElement;
  });

  it('nimmt Abläufe mit Schwächen auf, schwächste zuerst; ohne Urteil ganz oben', async () => {
    await mit([
      ablauf('A', 5, { verlauf: 5 }),
      ablauf('B', 3, { verlauf: 2, ton: 5 }),
      ablauf('C', 4, { werkzeuge: 3 }),
      ablauf('D', null, {}, { urteil_fehler: 'Judge weg' }),
    ]);
    const ids = Array.from(el.querySelectorAll('li.ep-eintrag'), (li) => li.getAttribute('data-ablauf'));
    expect(ids).toEqual(['D', 'B', 'C']);
  });

  it('zeigt nur die Noten unter 4, mit Namen und Zahl', async () => {
    await mit([ablauf('B', 3, { verlauf: 2, ton: 5 })]);
    const chips = Array.from(el.querySelectorAll('.ep-chip'), (c) => c.textContent?.trim());
    expect(chips).toEqual(['Gesamt 3', 'Verlauf 2']);
    expect(el.textContent).toContain('Statement B');
  });

  it('springt zur Ablauf-Karte', async () => {
    await mit([ablauf('B', 3, {})]);
    let ziel = '';
    fixture.componentInstance.springe.subscribe((id) => (ziel = id));
    el.querySelector<HTMLButtonElement>('.ep-sprung')!.click();
    expect(ziel).toBe('B');
  });

  it('sagt es, wenn kein Ablauf unter 4 liegt', async () => {
    await mit([ablauf('A', 5, { verlauf: 4 })]);
    expect(el.textContent).toContain('Kein Ablauf unter 4');
  });
});
