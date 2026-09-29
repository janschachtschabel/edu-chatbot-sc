// @vitest-environment jsdom
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { TraceDebug } from '../core/sessions-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AgentTraceComponent } from './agent-trace.component';

/** Ein Agent-Zug mit zwei Runden, wie ihn `GET /sessions/{id}/messages` liefert. */
const AGENT_ZUG: TraceDebug = {
  engine: 'agent',
  token_usage: { prompt_tokens: 6500, cached_tokens: 5800, completion_tokens: 250, calls: 2 },
  trace: [
    {
      step: 'agent_round', label: 'Runde 1: search_wlo_content', duration_ms: 1200,
      data: {
        runde: 1, dauer_ms: 1200, prompt_tokens: 3000, cached_tokens: 2800,
        completion_tokens: 40,
        werkzeuge: [{ name: 'search_wlo_content', argumente: ['maxItems', 'query'] }],
      },
    },
    {
      step: 'agent_round', label: 'Runde 2: ohne Werkzeug', duration_ms: 2300,
      data: {
        runde: 2, dauer_ms: 2300, prompt_tokens: 3500, cached_tokens: 3000,
        completion_tokens: 210, werkzeuge: [],
      },
    },
    {
      step: 'agent_stop', label: 'Ende: text', duration_ms: 3500,
      data: { stop_reason: 'text', runden: 2 },
    },
    { step: 'skill', label: 'Quiz erstellen', data: { node_id: 'abc-1', titel: 'Quiz erstellen' } },
  ],
};

@Component({
  selector: 'studio-trace-host',
  imports: [AgentTraceComponent],
  template: '<studio-agent-trace [debug]="debug()" />',
})
class HostComponent {
  readonly debug = signal<TraceDebug | undefined>(undefined);
}

async function mount(debug: TraceDebug | undefined, locale = 'de'): Promise<HTMLElement> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(HostComponent);
  fixture.componentInstance.debug.set(debug);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

/** Der Wert zu einer Beschriftung der Kennzahlen — `null`, wenn sie fehlt. */
function fakt(el: HTMLElement, label: string): string | null {
  for (const paar of Array.from(el.querySelectorAll('.atr-facts > div'))) {
    if (paar.querySelector('dt')?.textContent?.trim() === label) {
      return paar.querySelector('dd')?.textContent?.trim().replace(/\s+/g, ' ') ?? null;
    }
  }
  return null;
}

function zellen(zeile: Element): string[] {
  return Array.from(zeile.querySelectorAll('th, td'))
    .map((c) => (c.textContent ?? '').trim().replace(/\s+/g, ' '));
}

describe('AgentTraceComponent (ST-8a)', () => {
  it('nennt Maschine, Token, Ende und geholte Anleitung des Zugs', async () => {
    const el = await mount(AGENT_ZUG);
    expect(fakt(el, 'Maschine')).toBe('Agent-Schleife');
    expect(fakt(el, 'Token')).toBe('Eingabe 6.500 (davon 5.800 gecacht) · Ausgabe 250');
    expect(fakt(el, 'Ende')).toBe('Antwort geschrieben · 2 Runden · 3,5 s');
    expect(fakt(el, 'Geholter Skill')).toBe('Quiz erstellen');
  });

  it('listet die Runden mit Werkzeugen, Argument-Namen, Dauer und Token', async () => {
    const el = await mount(AGENT_ZUG);
    const zeilen = Array.from(el.querySelectorAll('.atr-table tbody tr'));
    expect(zeilen.map(zellen)).toEqual([
      ['1', 'search_wlo_content (maxItems, query)', '1,2 s', '3.000', '2.800', '40'],
      ['2', 'ohne Werkzeug', '2,3 s', '3.500', '3.000', '210'],
    ]);
    expect(zellen(el.querySelector('.atr-table thead tr')!)).toEqual(
      ['Runde', 'Werkzeuge', 'Dauer', 'Eingabe', 'davon gecacht', 'Ausgabe'],
    );
    // Die Werte der Argumente speichert der Server nicht (Nutzerinhalt) — die
    // Überschrift sagt es, damit niemand sie in der Tabelle sucht.
    expect(el.querySelector('.atr-table caption')?.textContent).toContain('nur ihre Namen');
  });

  it('klappt die Runden unter einer Zusammenfassung ein', async () => {
    const el = await mount(AGENT_ZUG);
    const details = el.querySelector<HTMLDetailsElement>('details.atr-rounds')!;
    expect(details.open).toBe(false);
    expect(details.querySelector('summary')?.textContent?.trim()).toBe('Runden im Einzelnen (2)');
  });

  it('zeigt einen fremden Ende-Grund roh', async () => {
    const el = await mount({
      ...AGENT_ZUG,
      trace: [{ step: 'agent_stop', duration_ms: 900, data: { stop_reason: 'warp', runden: 1 } }],
    });
    expect(fakt(el, 'Ende')).toBe('warp · 1 Runde · 0,9 s');
  });

  it('zeigt bei einem Muster-Zug Maschine und Token, aber keine Runden', async () => {
    const el = await mount({
      engine: 'pattern', token_usage: { prompt_tokens: 900, completion_tokens: 80 }, trace: [],
    });
    expect(fakt(el, 'Maschine')).toBe('Muster-Maschine');
    expect(fakt(el, 'Token')).toBe('Eingabe 900 (davon 0 gecacht) · Ausgabe 80');
    expect(fakt(el, 'Ende')).toBeNull();
    expect(el.querySelector('.atr-rounds')).toBeNull();
  });

  // Tour, Kontext-Begrüßung und Direktaktionen antworten vor jeder Maschine
  // (`engine` leer, AG-1) — „Maschine unbekannt" wäre dort falsch.
  it('bleibt leer bei einem Zug vor jeder Maschine', async () => {
    expect((await mount({ engine: '', trace: [] })).querySelector('.atr')).toBeNull();
    expect((await mount(undefined)).querySelector('.atr')).toBeNull();
  });

  it('spricht Englisch', async () => {
    const el = await mount(AGENT_ZUG, 'en');
    expect(fakt(el, 'Engine')).toBe('Agent loop');
    expect(fakt(el, 'Tokens')).toBe('Input 6,500 (5,800 cached) · Output 250');
    expect(fakt(el, 'End')).toBe('Answer written · 2 rounds · 3.5 s');
    expect(zellen(el.querySelector('.atr-table tbody tr')!)[1])
      .toBe('search_wlo_content (maxItems, query)');
    expect(el.querySelector('.atr-rounds summary')?.textContent?.trim()).toBe('Rounds in detail (2)');
  });
});
