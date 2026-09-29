// @vitest-environment jsdom
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { RunProfile } from '../core/eval-profile';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalRunProfileComponent } from './eval-run-profile.component';

const NBSP = '\u00a0';

function profil(over: Partial<RunProfile> = {}): RunProfile {
  return {
    quality: {
      hard_rate: 0.96, hard_passed: 86, hard_total: 90,
      axes: {
        intent_fit: 1.8, persona_tone: 1.0, pattern_match: null,
        safety: 2, info_quality: 1.55, auftrag_erfuellt: 1.4,
      },
    },
    speed: { p50_ms: 12340, p95_ms: 21800, over_30s: 0.05, over_90s: 0 },
    cost: {
      turns_with_usage: 42, prompt: 8123.4, cached: 2000, completion: 450.2,
      cost_per_turn: 0.00015, cost_total: 0.0063, price_unavailable: [],
    },
    robustness: { turns: 42, chat_errors: 1, judge_failed: 0, empty: 2, fallback: 0 },
    currency: 'USD',
    ...over,
  };
}

@Component({
  selector: 'studio-profile-host',
  imports: [EvalRunProfileComponent],
  template: '<studio-eval-run-profile [profile]="profile()" />',
})
class HostComponent {
  readonly profile = signal<RunProfile>(profil());
}

let f: ComponentFixture<HostComponent>;

async function mount(p: RunProfile = profil(), locale = 'de'): Promise<HTMLElement> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  f = TestBed.createComponent(HostComponent);
  f.componentInstance.profile.set(p);
  await f.whenStable();
  return f.nativeElement as HTMLElement;
}

const achsen = (el: HTMLElement): string[][] =>
  Array.from(el.querySelectorAll('.rp-axes tbody tr')).map((tr) => [
    tr.querySelector('th')?.textContent?.trim() ?? '',
    tr.querySelector('.rp-axis-value')?.textContent?.replace(/\s+/g, ' ').trim() ?? '',
  ]);

const fakt = (el: HTMLElement, name: string): string =>
  Array.from(el.querySelectorAll('.rp-facts > div'))
    .find((d) => d.querySelector('dt')?.textContent?.trim() === name)
    // Nur trimmen: `\s` fasste auch das geschützte Leerzeichen vor „s" und „%".
    ?.querySelector('dd')?.textContent?.trim() ?? '';

describe('EvalRunProfileComponent (ST-7b)', () => {
  it('zeigt je Judge-Achse den Mittelwert auf 0–2, „Auftrag erfüllt“ zuerst', async () => {
    const el = await mount();
    expect(el.querySelector('.rp-axes caption')?.textContent).toContain('0–2');
    expect(achsen(el)).toEqual([
      ['Auftrag erfüllt', '1,4'],
      ['Passt zur Absicht', '1,8'],
      ['Ton für die Zielgruppe', '1 (schwach)'],
      ['Informationsqualität', '1,55'],
      ['Sicherheit', '2'],
      ['Muster passt', 'nicht bewertet'],
    ]);
  });

  it('markiert eine schwache Achse mit einem Wort, nicht nur mit Farbe', async () => {
    const el = await mount();
    const zeile = Array.from(el.querySelectorAll('.rp-axes tbody tr'))
      .find((tr) => tr.textContent?.includes('Ton für die Zielgruppe'))!;
    expect(zeile.classList).toContain('rp-axis--weak');
    // Der Balken ist nur Beiwerk — der Wert steht als Text daneben.
    expect(zeile.querySelector('.rp-bar')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('nennt die Dauer je Zug als p50 und p95 samt den langen Zügen', async () => {
    const el = await mount();
    expect(fakt(el, 'Dauer je Zug')).toBe(
      `p50 12,3${NBSP}s · p95 21,8${NBSP}s · 5${NBSP}% über 30${NBSP}s · 0 über 90${NBSP}s`);
  });

  it('nennt Token und Kosten je Zug in der Währung der Preistafel', async () => {
    const el = await mount();
    expect(fakt(el, 'Token je Zug')).toBe('8.123 Eingabe, davon 2.000 gecacht · 450 Ausgabe');
    expect(fakt(el, 'Kosten')).toBe(`0,00015${NBSP}$ je Zug · 0,0063${NBSP}$ gesamt`);
  });

  it('sagt, für welches Modell der Preis fehlt, statt 0 zu zeigen', async () => {
    const el = await mount(profil({
      cost: {
        turns_with_usage: 3, prompt: 10, cached: 0, completion: 5,
        cost_per_turn: null, cost_total: null, price_unavailable: ['gpt-6-luna'],
      },
    }));
    expect(fakt(el, 'Kosten')).toContain('Kein Preis gepflegt für gpt-6-luna');
    expect(fakt(el, 'Kosten')).not.toContain('0,00');
  });

  it('zählt die Robustheit — Fehler, Ausfälle, leere und Ersatzantworten', async () => {
    // „Name: Zahl" statt „1 Judge-Ausfälle": die Form braucht keine Mehrzahl.
    const el = await mount();
    expect(fakt(el, 'Robustheit')).toBe(
      'Chat-Fehler: 1 · Judge-Ausfälle: 0 · leere Antworten: 2 · Ersatzantworten: 0');
  });

  it('lässt weg, wozu der Lauf nichts sagt — ohne Judge kein Wort vom Judge', async () => {
    const el = await mount(profil({
      quality: {
        hard_rate: null, hard_passed: 0, hard_total: 0,
        axes: {
          intent_fit: null, persona_tone: null, pattern_match: null,
          safety: null, info_quality: null, auftrag_erfuellt: null,
        },
      },
      speed: { p50_ms: null, p95_ms: null, over_30s: null, over_90s: 0 },
      cost: {
        turns_with_usage: 0, prompt: null, cached: null, completion: null,
        cost_per_turn: null, cost_total: null, price_unavailable: [],
      },
    }));
    expect(el.querySelector('.rp-axes')).toBeNull();
    // Auch die Robustheit schweigt dann vom Judge — es gab keinen.
    expect(fakt(el, 'Robustheit')).toBe('Chat-Fehler: 1 · leere Antworten: 2 · Ersatzantworten: 0');
    expect(el.textContent).not.toContain('Judge');
    expect(fakt(el, 'Dauer je Zug')).toBe('');
    expect(fakt(el, 'Token je Zug')).toBe('');
    expect(fakt(el, 'Kosten')).toBe('');
  });

  it('spricht Englisch', async () => {
    const el = await mount(profil(), 'en');
    expect(achsen(el)[0]).toEqual(['Task fulfilled', '1.4']);
    expect(fakt(el, 'Cost')).toBe(`US$0.00015 per turn · US$0.0063 total`);
    expect(el.textContent).not.toMatch(/[äöüß]/);
  });
});
