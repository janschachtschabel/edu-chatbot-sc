import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Lifecycle-Verdrahtung der Chat-Shell (8-4S-e5): dass die Angular-Hooks + Public-
 * API der Komponente an die gepinnten Module delegieren (ShellLifecycle /
 * ScrollFollowController / SpeechService). Die Logik selbst ist in lifecycle.spec/
 * scroll-follow.spec/history-restore.spec/session-boot.spec gepinnt; hier zählt
 * das Wiring. Ein realer `ngOnInit`-Lauf (frische Session) verifiziert die Kette
 * end-to-end.
 */

function make(): { c: ChatShellComponent; fixture: ComponentFixture<ChatShellComponent> } {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const fixture = TestBed.createComponent(ChatShellComponent);
  // Pflicht-Input (C1-b2): das Template liest ihn beim ersten `detectChanges`.
  fixture.componentRef.setInput('translate', createTranslator(DE, DE));
  return { c: fixture.componentInstance, fixture };
}

describe('ChatShellComponent — Lifecycle-Wiring (8-4S-e5)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('ngOnInit: frische Session + Begrüßung, Speech-Capability gesetzt (delegiert an ShellLifecycle.init)', async () => {
    const { c, fixture } = make();
    fixture.componentRef.setInput('persistSession', false);
    (c as unknown as { _api: unknown })._api = {
      setBaseUrl: vi.fn(), getSpeechEnabled: async () => true, loadHistory: async () => [],
      setUiLocale: vi.fn(),  // C1-f1: ngOnInit meldet dem Client die Widget-Sprache
    };
    fixture.detectChanges(); // triggert ngOnInit

    expect(c.sessionId).toMatch(/^bb-/);
    expect(c.messages().length).toBe(1); // Begrüßungs-Bubble
    await Promise.resolve(); await Promise.resolve();
    expect(c.speechBackendEnabled()).toBe(true);
  });

  it('restart/resetSession/updateContext/onSpaContextChange/scrollToLatest delegieren an die Module', () => {
    const { c } = make();
    const lc = (c as unknown as { _lifecycle: Record<string, () => void> })._lifecycle;
    const scroll = (c as unknown as { _scroll: Record<string, () => void> })._scroll;
    const restart = vi.spyOn(lc, 'restart').mockImplementation(() => {});
    const reset = vi.spyOn(lc, 'resetSession').mockImplementation(() => {});
    const upd = vi.spyOn(lc, 'updateContext').mockImplementation(() => {});
    const spa = vi.spyOn(lc, 'onSpaContextChange').mockImplementation(() => {});
    const s2l = vi.spyOn(scroll, 'scrollToLatest').mockImplementation(() => {});

    c.restart();
    c.resetSession();
    c.updateContext({ a: 1 });
    c.onSpaContextChange({ b: 2 });
    c.scrollToLatest();

    expect(restart).toHaveBeenCalledTimes(1);
    expect(reset).toHaveBeenCalledTimes(1);
    expect(upd).toHaveBeenCalledWith({ a: 1 });
    expect(spa).toHaveBeenCalledWith({ b: 2 });
    expect(s2l).toHaveBeenCalledTimes(1);
  });

  it('ngAfterViewChecked delegiert an ScrollFollowController.afterViewChecked', () => {
    const { c } = make();
    const spy = vi.spyOn((c as unknown as { _scroll: Record<string, () => void> })._scroll, 'afterViewChecked');
    c.ngAfterViewChecked();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('ngOnDestroy trennt Scroll-Observer UND Speech-Cluster', () => {
    const { c } = make();
    const s = vi.spyOn((c as unknown as { _scroll: Record<string, () => void> })._scroll, 'destroy');
    const sp = vi.spyOn((c as unknown as { _speech: Record<string, () => void> })._speech, 'destroy');
    c.ngOnDestroy();
    expect(s).toHaveBeenCalledTimes(1);
    expect(sp).toHaveBeenCalledTimes(1);
  });
});
