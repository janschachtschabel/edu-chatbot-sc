import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatShellComponent } from './chat-shell.component';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';

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

  it('onQuickReply: der Tour-Chip startet die Tour in BEIDEN Sprachen (C1-g1b)', () => {
    // Der Chip wird per TEXT verglichen, und ein Sprachwechsel uebersetzt den
    // Verlauf NICHT nach (C1-c). Nach dem Umschalten steht der deutsche Chip
    // also weiter in der Blase — er muss die Tour trotzdem starten. Deshalb
    // vergleicht die Weiche gegen beide Fassungen, nicht gegen die aktuelle.
    const { c, fixture } = make();
    fixture.componentRef.setInput('tourReply', 'Los, zeig mir alles');
    fixture.componentRef.setInput('tourReplyEn', 'Show me around');
    const startTour = vi.spyOn(c, 'startTour').mockResolvedValue();
    c.onQuickReply('Show me around');
    c.onQuickReply('Los, zeig mir alles');
    expect(startTour).toHaveBeenCalledTimes(2);
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

// ── WLO-Anmeldung (C5-c2) ──────────────────────────────────────────
// Der Anmelde-Chip ist der dritte Marker der Reihe. Zwei Dinge müssen halten:
// er darf NICHT als Text durchrutschen (sonst stünde `__auth__` im Verlauf),
// und ohne bekannte MCP-Herkunft muss er das SAGEN statt still nichts zu tun.
describe('ChatShellComponent — WLO-Anmeldung (C5-c2)', () => {
  afterEach(() => vi.restoreAllMocks());

  /** Wie `make()`, aber mit gesetztem Übersetzer: dieser Pfad ist der ERSTE im
   *  Routing, der einen Text erzeugt — die übrigen Weichen kommen ohne aus. */
  function mitSprache() {
    const { c, fixture } = make();
    fixture.componentRef.setInput('translate', createTranslator(DE, DE));
    return { c, fixture };
  }

  it('onQuickReply: der Anmelde-Chip sendet keine Nachricht', async () => {
    const { c } = mitSprache();
    const sendMessage = vi.spyOn(c, 'sendMessage').mockResolvedValue();
    c.onQuickReply('__auth__');
    await Promise.resolve();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(c.messages().some(m => m.content === '__auth__')).toBe(false);
  });

  it('onQuickReply: ohne MCP-Herkunft sagt er das, statt ein Fenster zu öffnen', async () => {
    const { c } = mitSprache(); // `mcpAuthBase` bleibt leer = nicht angeboten
    c.onQuickReply('__auth__');
    await Promise.resolve();
    const letzte = c.messages().at(-1);
    expect(letzte?.sender).toBe('bot');
    expect(letzte?.content).toBe(DE['auth.unavailable']);
    // Und ausdrücklich NICHT der allgemeine Fehlersatz: „nicht angeboten" ist
    // eine Eigenschaft der Anlage, keine Panne.
    expect(letzte?.content).not.toBe(DE['auth.failed']);
  });
});
