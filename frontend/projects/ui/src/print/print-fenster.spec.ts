// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { printLearningPath } from './print-lernpfad';
import { printCanvasMaterial, printMarkdownDocument } from './print-utils';

/**
 * Paket 8 (P2): Ein leeres Pop-up erbt die Content-Security-Policy der Seite, die es
 * öffnet. Unter `script-src 'self'` (Studio-Vorschau) liefen ein Inline-Skript und
 * ein `onclick`-Attribut im Druckfenster nicht — der Druck startete nicht, der Knopf
 * blieb tot. Dasselbe auf jeder Gastseite mit strenger CSP.
 */

const t = createTranslator(DE, DE);
const SENTINEL = '<!-- boerdi:printable-canvas|arbeitsblatt|Bruchrechnen -->';
const INLINE_HANDLER = /\son[a-z]+\s*=/i;

function bot(content: string): ChatMessage {
  return { id: 'm1', sender: 'bot', content, timestamp: new Date() } as ChatMessage;
}

interface Attrappe {
  readonly html: () => string;
  readonly knopf: () => HTMLButtonElement | null;
  readonly print: ReturnType<typeof vi.fn>;
  readonly laden: () => void;
}

/** Nur die Browser-Grenze ist gefälscht: ein Fenster, dessen Dokument das
 *  Geschriebene wirklich parst — so lässt sich der Knopf darin drücken. */
function oeffne(readyState: DocumentReadyState = 'complete'): Attrappe {
  let geschrieben = '';
  let dom: Document | null = null;
  let beimLaden: (() => void) | null = null;
  const print = vi.fn();
  const fenster = {
    closed: false,
    print,
    // Die Uhr des Druckfensters — im Test die (falsche) Uhr der Seite.
    setTimeout: (f: () => void, ms: number) => setTimeout(f, ms),
    addEventListener: (typ: string, handler: () => void) => {
      if (typ === 'load') beimLaden = handler;
    },
    document: {
      readyState,
      open: () => { geschrieben = ''; },
      write: (html: string) => { geschrieben += html; },
      close: () => { dom = new DOMParser().parseFromString(geschrieben, 'text/html'); },
      querySelector: (selektor: string) => dom?.querySelector(selektor) ?? null,
    },
  };
  vi.stubGlobal('open', () => fenster);
  return {
    html: () => geschrieben,
    knopf: () => dom?.querySelector<HTMLButtonElement>('.print-bar button') ?? null,
    print,
    laden: () => beimLaden?.(),
  };
}

const DRUCKE = {
  dokument: () => printMarkdownDocument('Titel', '# Inhalt', t),
  arbeitsblatt: () => printCanvasMaterial(bot(SENTINEL + '\n# Aufgabe'), t),
  lernpfad: () => printLearningPath(bot('**Lernpfad:** los'), t),
};

describe('Druckfenster ohne Inline-Skript (Paket 8, CSP)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('keins der drei Fenster trägt ein Inline-Skript oder einen Inline-Handler', () => {
    for (const [art, drucke] of Object.entries(DRUCKE)) {
      const fenster = oeffne();
      drucke();
      expect(fenster.html(), art).toContain('<body');
      expect(fenster.html(), art).not.toContain('<script');
      expect(fenster.html(), art).not.toMatch(INLINE_HANDLER);
      vi.unstubAllGlobals();
    }
  });

  it('der Knopf im Arbeitsblatt- und im Lernpfad-Fenster druckt', () => {
    for (const drucke of [DRUCKE.arbeitsblatt, DRUCKE.lernpfad]) {
      const fenster = oeffne();
      drucke();
      expect(fenster.print).not.toHaveBeenCalled();
      fenster.knopf()!.click();
      expect(fenster.print).toHaveBeenCalledTimes(1);
      vi.unstubAllGlobals();
    }
  });

  it('ein Dokument druckt sich nach dem Laden von selbst', () => {
    vi.useFakeTimers();
    const fenster = oeffne('complete');
    DRUCKE.dokument();
    expect(fenster.print).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    expect(fenster.print).toHaveBeenCalledTimes(1);
  });

  it('der Druck läuft auf der Uhr des Druckfensters (Paket 9)', () => {
    // Review Paket 7 (MINOR 22): Timer und Listener gehörten der öffnenden Seite —
    // navigiert sie weiter, stehen ihre Timer still. Hier steht die Uhr der Seite.
    vi.useFakeTimers();
    const fenster = oeffne('complete');
    const geplant: Array<[unknown, number]> = [];
    Object.assign(globalThis.open() as object, {
      setTimeout: (f: unknown, ms: number) => { geplant.push([f, ms]); return 1; },
    });
    DRUCKE.dokument();
    vi.advanceTimersByTime(1000);
    expect(fenster.print).not.toHaveBeenCalled();
    expect(geplant.map(([, ms]) => ms)).toEqual([300]);
    (geplant[0][0] as () => void)();
    expect(fenster.print).toHaveBeenCalledTimes(1);
  });

  it('der Knopf ruft die Druckfunktion des Druckfensters selbst (Paket 9)', () => {
    const fenster = oeffne();
    const gebunden = vi.fn();
    const w = globalThis.open() as unknown as { print: { bind: (o: unknown) => unknown } };
    w.print.bind = () => gebunden;
    const anmelden = vi.spyOn(Element.prototype, 'addEventListener');
    DRUCKE.arbeitsblatt();
    expect(anmelden).toHaveBeenCalledWith('click', gebunden);
    expect(fenster.print).not.toHaveBeenCalled();
    anmelden.mockRestore();
  });

  it('lädt das Fenster noch, wartet der Druck auf das Laden', () => {
    vi.useFakeTimers();
    const fenster = oeffne('loading');
    DRUCKE.dokument();
    vi.advanceTimersByTime(1000);
    expect(fenster.print).not.toHaveBeenCalled();
    fenster.laden();
    vi.advanceTimersByTime(300);
    expect(fenster.print).toHaveBeenCalledTimes(1);
  });
});
