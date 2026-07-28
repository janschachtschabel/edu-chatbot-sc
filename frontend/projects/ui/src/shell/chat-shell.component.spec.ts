import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { ChatShellComponent } from './chat-shell.component';

/**
 * Default-Zustand der Chat-Shell + dass der Verlauf des State-Core (8-4S-b,
 * Modul `message-store.ts` seit 8-4S-f0) am Template-Signal `messages` hängt.
 * Die Reducer-Semantik selbst ist in `message-store.spec.ts` gepinnt — hier
 * zählt nur die Verdrahtung.
 */

function make(): ChatShellComponent {
  return TestBed.createComponent(ChatShellComponent).componentInstance;
}

describe('ChatShellComponent — Default-State', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('Default-State: leere messages, isLoading false, latestDebug null', () => {
    const c = make();
    expect(c.messages()).toEqual([]);
    expect(c.isLoading()).toBe(false);
    expect(c.latestDebug()).toBeNull();
  });

  it('`messages` ist das Signal des Stores (Reducer schreiben ins Template-Signal)', () => {
    const c = make();
    const store = (c as unknown as { _store: { addUserMessage: (s: string) => void } })._store;
    store.addUserMessage('Hallo');
    expect(c.messages().map(m => m.content)).toEqual(['Hallo']);
  });
});

/**
 * Widget-Header-Oberfläche (8-5c): die Panel-Kopfzeile der Widget-Hülle liest
 * `debugButtonVisible`/`autoSpeak` und ruft `toggleAutoSpeak`/`focusInput` —
 * in ALT `widget.component.html:42-60` über `chatRef?.…`. Verhalten wie ALT
 * chat.component.ts:1249-1252 (`debugButtonVisible`) bzw. 937-939.
 */
describe('ChatShellComponent — Widget-Header-Oberfläche', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('debugButtonVisible koerziert `show-debug-button` wie die anderen Bool-Attribute', () => {
    const f = TestBed.createComponent(ChatShellComponent);
    expect(f.componentInstance.debugButtonVisible).toBe(false);  // Default aus
    f.componentRef.setInput('showDebugButton', 'true');
    expect(f.componentInstance.debugButtonVisible).toBe(true);
    f.componentRef.setInput('showDebugButton', true);
    expect(f.componentInstance.debugButtonVisible).toBe(true);
    f.componentRef.setInput('showDebugButton', 'nein');
    expect(f.componentInstance.debugButtonVisible).toBe(false);
  });

  it('autoSpeak spiegelt den SpeechService, toggleAutoSpeak schaltet ihn um', () => {
    const c = make();
    expect(c.autoSpeak).toBe(false);
    c.toggleAutoSpeak();
    expect(c.autoSpeak).toBe(true);
    c.toggleAutoSpeak();
    expect(c.autoSpeak).toBe(false);
  });

  it('focusInput ist öffentlich (Widget fokussiert nach dem Panel-Öffnen)', () => {
    expect(typeof make().focusInput).toBe('function');
  });
});
