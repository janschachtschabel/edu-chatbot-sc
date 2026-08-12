// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { splitRich } from '@boerdi/ui';
import { beforeEach, describe, expect, it } from 'vitest';

import { RichTextComponent } from './rich-text.component';

/**
 * Der Renderer zu `splitRich` (C1-d4b2). Geprüft wird genau das, was das
 * Zerlegen allein nicht belegt: dass aus den Stücken echte Elemente werden und
 * kein sichtbarer Stern übrig bleibt.
 */
async function mount(text: string, params?: Record<string, string | number>) {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(RichTextComponent);
  fixture.componentRef.setInput('parts', splitRich(text, params));
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('RichTextComponent', () => {
  let el: HTMLElement;

  beforeEach(() => {
    el = undefined as unknown as HTMLElement;
  });

  it('macht aus dem Stern-Abschnitt ein <strong>', async () => {
    el = await mount('Dieser Lauf trägt *keine Gold-Metriken* — sagt sie.');
    expect(el.querySelector('strong')?.textContent).toBe('keine Gold-Metriken');
  });

  it('macht aus dem Backtick-Abschnitt ein <code>', async () => {
    el = await mount('eine falsche `REPO_BASE_URL` scheitert');
    expect(el.querySelector('code')?.textContent).toBe('REPO_BASE_URL');
  });

  it('lässt keinen Marker sichtbar stehen', async () => {
    el = await mount('*A* und `B`');
    expect(el.textContent).not.toContain('*');
    expect(el.textContent).not.toContain('`');
  });

  it('gibt den Satz ungeteilt und in seiner Reihenfolge wieder', async () => {
    // Der ganze Grund für das Zerlegen: der Satz muss lesbar bleiben.
    el = await mount('harte Quote *{rate}* ({ok}/{total} Checks)',
      { rate: '83 %', ok: 10, total: 12 });
    expect(el.textContent).toBe('harte Quote 83 % (10/12 Checks)');
  });
});
