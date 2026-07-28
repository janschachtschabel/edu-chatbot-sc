import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatShellComponent } from './chat-shell.component';

/**
 * Input-Routing der Chat-Shell (8-4S-d2b): wie die Shell rohe Quick-Reply-/
 * Guide-Strings, Enter und den Debug-Toggle auf Aktionen abbildet — ALT
 * `onQuickReply`/`onGuideQuickReply`/`onGuideNavigate`/`onKeydown`/`toggleDebug`.
 * Die Parser/Guards selbst sind bereits gepinnt (action-qr/guide-qr/link-handoff);
 * hier zählt die WEICHE (Tour-Start vs. Action-Pill vs. Text; Same-Tab-Nav
 * fail-closed).
 */

function make(): { c: ChatShellComponent; fixture: ComponentFixture<ChatShellComponent> } {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const fixture = TestBed.createComponent(ChatShellComponent);
  return { c: fixture.componentInstance, fixture };
}

describe('ChatShellComponent — Input-Routing (8-4S-d2b)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('onQuickReply: Web-Tour-Startbutton → startTour, kein sendMessage', () => {
    const { c } = make();
    const startTour = vi.spyOn(c, 'startTour').mockResolvedValue();
    const sendMessage = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    c.onQuickReply('Web-Tour starten');
    expect(startTour).toHaveBeenCalledTimes(1);
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('onQuickReply: Studio-Tour-Chip (tourReply-Match) → startTour', () => {
    const { c, fixture } = make();
    fixture.componentRef.setInput('tourReply', 'Los, zeig mir alles');
    const startTour = vi.spyOn(c, 'startTour').mockResolvedValue();
    c.onQuickReply('Los, zeig mir alles');
    expect(startTour).toHaveBeenCalledTimes(1);
  });

  it('onQuickReply: gültiges Action-Pill → sendMessage(label, action, params)', () => {
    const { c } = make();
    const sendMessage = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    c.onQuickReply('__action__|Sammlung öffnen|browse_collection|{"collection_id":"c1"}');
    expect(sendMessage).toHaveBeenCalledWith('Sammlung öffnen', 'browse_collection', { collection_id: 'c1' });
  });

  it('onQuickReply: kaputtes Action-JSON → Label als Textnachricht (Fallback, kein Throw)', () => {
    const { c } = make();
    const sendMessage = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    c.onQuickReply('__action__|Nur Label|browse_collection|{kaputt');
    expect(sendMessage).toHaveBeenCalledWith('Nur Label');
  });

  it('onQuickReply: normaler Chip → sendMessage(reply)', () => {
    const { c } = make();
    const sendMessage = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    c.onQuickReply('Was ist Photosynthese?');
    expect(sendMessage).toHaveBeenCalledWith('Was ist Photosynthese?');
  });

  it('onGuideQuickReply: extrahiert URL und ruft onGuideNavigate', () => {
    const { c } = make();
    const nav = vi.spyOn(c, 'onGuideNavigate').mockImplementation(() => {});
    c.onGuideQuickReply('__guide__|Themenseite|https://wirlernenonline.de/thema');
    expect(nav).toHaveBeenCalledWith('https://wirlernenonline.de/thema');
  });

  it('onGuideNavigate: untrusted/javascript-URL → fail-closed (keine Navigation, kein Throw)', () => {
    const { c } = make();
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    expect(() => c.onGuideNavigate('javascript:alert(1)')).not.toThrow();
    expect(() => c.onGuideNavigate('https://evil.example/phish')).not.toThrow();
    expect(open).not.toHaveBeenCalled();
  });

  it('onKeydown: Enter ohne Shift → preventDefault + sendMessage; Shift+Enter → nichts', () => {
    const { c } = make();
    const sendMessage = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    const enter = { key: 'Enter', shiftKey: false, preventDefault: vi.fn() } as unknown as KeyboardEvent;
    c.onKeydown(enter);
    expect(enter.preventDefault).toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledTimes(1);

    const shiftEnter = { key: 'Enter', shiftKey: true, preventDefault: vi.fn() } as unknown as KeyboardEvent;
    c.onKeydown(shiftEnter);
    expect(shiftEnter.preventDefault).not.toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledTimes(1); // unverändert
  });

  it('toggleDebug: kippt showDebug', () => {
    const { c } = make();
    expect(c.showDebug()).toBe(false);
    c.toggleDebug();
    expect(c.showDebug()).toBe(true);
    c.toggleDebug();
    expect(c.showDebug()).toBe(false);
  });
});
