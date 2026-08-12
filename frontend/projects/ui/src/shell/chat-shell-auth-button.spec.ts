import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ICONS } from '../icons/icons';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { MCP_ACCESS_STORAGE_KEY, writeAccessBlock } from '../session/mcp-access';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Der Anmelde-/Abmelde-Knopf in der Eingabezeile. Gepinnt wird, was still
 * schiefgehen kann: dass er im rahmenlosen Modus verschwindet (er hängt an
 * KEINER Kopfzeile — das ist der Grund für die Platzierung), dass der Klick
 * seine Nutzergeste verliert (dann blockt der Browser das Anmeldefenster,
 * ohne dass irgendwo etwas steht), und dass Abmelden nur die Anzeige räumt
 * statt den Speicher.
 */

const BASIS = 'https://mcp.example.org';
const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';

function make(over: { mcpAuthBase?: string; sizeToggleVisible?: string } = {}) {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f: ComponentFixture<ChatShellComponent> = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('mcpAuthBase', over.mcpAuthBase ?? BASIS);
  if (over.sizeToggleVisible !== undefined) {
    f.componentRef.setInput('sizeToggleVisible', over.sizeToggleVisible);
  }
  f.detectChanges();
  return { c: f.componentInstance, f, el: f.nativeElement as HTMLElement };
}

const knopf = (el: HTMLElement) => el.querySelector('.btn-auth') as HTMLButtonElement | null;

beforeEach(() => sessionStorage.clear());
afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });

describe('Anmelde-Knopf — Sichtbarkeit', () => {
  it('fehlt, wenn diese Anlage keine Anmeldung anbietet', () => {
    // Ein Knopf, der nur scheitern kann, ist schlechter als keiner.
    expect(knopf(make({ mcpAuthBase: '' }).el)).toBeNull();
  });

  it('steht da, sobald eine Anmelde-Adresse gesetzt ist', () => {
    expect(knopf(make().el)).not.toBeNull();
  });

  it('bleibt im rahmenlosen Einbettungs-Modus stehen', () => {
    // Der ausdrückliche Grund für die Platzierung unten: rahmenlos gibt es
    // keine Kopfzeile mehr, an der er sonst hinge.
    const { el } = make({ sizeToggleVisible: 'false' });
    expect(el.querySelector('.btn-size')).toBeNull();
    expect(knopf(el)).not.toBeNull();
  });

  it('sitzt rechts vom Eingabefeld und links von Neustart und Senden', () => {
    const { el } = make();
    const reihe = Array.from(el.querySelectorAll('.chat-footer > *'))
      .map(e => e.className.split(' ')[0]);
    expect(reihe.indexOf('btn-auth')).toBeGreaterThan(reihe.indexOf('chat-input'));
    expect(reihe.indexOf('btn-auth')).toBeLessThan(reihe.indexOf('btn-restart'));
    expect(reihe.indexOf('btn-auth')).toBeLessThan(reihe.indexOf('btn-send'));
  });
});

describe('Anmelde-Knopf — die beiden Zustände', () => {
  it('abgemeldet: Beschriftung, Ansage und Symbol laden zum Anmelden ein', () => {
    const b = knopf(make().el)!;
    expect(b.getAttribute('aria-label')).toBe(DE['auth.signIn']);
    expect(b.getAttribute('title')).toBe(DE['auth.signIn']);
    expect(b.innerHTML).toContain('M840-800');  // Rahmen rechts = Pfeil hinein
  });

  it('angemeldet: Beschriftung sagt die Wirkung, und das Symbol dreht sich um', () => {
    writeAccessBlock(BLOCK);
    const b = knopf(make().el)!;
    expect(b.getAttribute('aria-label')).toBe(DE['auth.signOut']);
    expect(b.innerHTML).toContain('M120-800');  // Rahmen links = Pfeil hinaus
  });

  it('trennt die Zustände nicht über Farbe — die Symbole sind verschieden', () => {
    expect(ICONS.login).not.toBe(ICONS.logout);
  });
});

describe('Anmelde-Knopf — Klick', () => {
  it('startet die Anmeldung SYNCHRON — der Klick ist die Nutzergeste', () => {
    // Ohne diese Zusage blockt der Browser das Anmeldefenster, und zwar
    // stumm: es gäbe keine Fehlermeldung, der Knopf täte scheinbar nichts.
    // Deshalb steht zwischen Klick und Start bewusst kein `await`.
    const { c } = make();
    const start = vi.spyOn(c as unknown as { startSignIn: () => Promise<void> }, 'startSignIn')
      .mockResolvedValue(undefined);
    c.onAuthClick();
    expect(start).toHaveBeenCalledTimes(1);  // KEIN await davor — das ist der Test
  });

  it('räumt beim Abmelden den Speicher, nicht nur die Anzeige', () => {
    writeAccessBlock(BLOCK);
    const { c, f, el } = make();
    c.onAuthClick();
    f.detectChanges();

    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY)).toBeNull();
    expect(c.messages().at(-1)?.content).toBe(DE['auth.signedOut']);
    expect(knopf(el)!.getAttribute('aria-label')).toBe(DE['auth.signIn']);
  });

  it('beendet beim Abmelden NICHT das Gespräch', () => {
    // Daneben sitzt der Neustart-Knopf, der genau das tut. Abmelden räumt den
    // Zugang, der Verlauf bleibt — sonst wären zwei Knöpfe dasselbe.
    writeAccessBlock(BLOCK);
    const { c } = make();
    const vorher = c.messages().length;
    c.onAuthClick();
    expect(c.messages().length).toBe(vorher + 1);
  });
});
