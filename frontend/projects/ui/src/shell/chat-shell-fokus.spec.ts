import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Fokus und Eingabe (Paket 10, Audit 2026-10-10 L-9): nach einem Zug riss die
 * Shell den Fokus zurück ins Eingabefeld — auch von der Gastseite weg, und auf
 * dem Handy öffnete sich die Tastatur über der Antwort. Enter schickte während
 * einer IME-Eingabe (Japanisch, Chinesisch) die halbe Komposition ab.
 */

function gerendert(): ComponentFixture<ChatShellComponent> {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  // Der Lebenszyklus ruft die API beim ersten Rendern — Attrappen statt Netz.
  (f.componentInstance as any)._api = {
    setUiLocale: vi.fn(), setGuideEnv: vi.fn(), setBaseUrl: vi.fn(), setResultSchema: vi.fn(),
    getSpeechEnabled: vi.fn(async () => false), loadHistory: vi.fn(async () => []),
    stream: vi.fn(), post: vi.fn(),
  };
  f.detectChanges();
  return f;
}

function eingabefeld(f: ComponentFixture<ChatShellComponent>): HTMLElement {
  return (f.nativeElement as HTMLElement).querySelector('textarea, input') as HTMLElement;
}

describe('ChatShellComponent — Fokus und Eingabe (Paket 10, L-9)', () => {
  afterEach(() => {
    vi.useRealTimers();
    document.querySelectorAll('[data-fremd]').forEach((e) => e.remove());
  });

  it('Enter während einer IME-Eingabe sendet nicht', () => {
    const c = gerendert().componentInstance;
    const senden = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    const taste = (init: KeyboardEventInit, keyCode?: number) => {
      const e = new KeyboardEvent('keydown', { key: 'Enter', ...init });
      if (keyCode !== undefined) Object.defineProperty(e, 'keyCode', { value: keyCode });
      c.onKeydown(e);
    };
    taste({ isComposing: true });
    taste({}, 229);              // Safari meldet die Komposition nur so
    expect(senden).not.toHaveBeenCalled();
    taste({});
    expect(senden).toHaveBeenCalledTimes(1);
  });

  it('nach einem Zug bleibt der Fokus auf der Gastseite, wenn er dort lag', () => {
    vi.useFakeTimers();
    const f = gerendert();
    const fremd = document.createElement('input');
    fremd.setAttribute('data-fremd', '');
    document.body.appendChild(fremd);
    fremd.focus();

    (f.componentInstance as any)._sendCtx.focusInput();
    vi.advanceTimersByTime(200);

    expect(document.activeElement).toBe(fremd);
  });

  it('nach einem Zug kommt der Fokus zurück, wenn er nirgends lag', () => {
    vi.useFakeTimers();
    const f = gerendert();
    (document.activeElement as HTMLElement | null)?.blur();

    (f.componentInstance as any)._sendCtx.focusInput();
    vi.advanceTimersByTime(200);

    expect(document.activeElement).toBe(eingabefeld(f));
  });
});
