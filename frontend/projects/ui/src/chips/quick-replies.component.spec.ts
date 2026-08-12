import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { QuickRepliesComponent } from './quick-replies.component';

/**
 * Charakterisierung des QuickReplies-Renderers — visueller Port der ALT
 * Quick-Reply-Chip-Reihe (`chat.component.html:400-416`). In ALT nur über die
 * große chat.component.spec.ts integrativ gedeckt; hier vor dem Konsum durch die
 * Chat-Shell (8-4) am gerenderten DOM + an den emittierten ROH-Strings gepinnt:
 * Wrapper-Gate (enabled/leer), Standard- vs. Guide-Chip, Action-Pill-Label,
 * Guide-Ausblendung bei ausgeschaltetem Lotsen-Modus, Klick-Emits (der Shell
 * routet den Roh-String — Tour/Action/Text bzw. Navigation).
 */
const GUIDE_QR = '__guide__|Zur Mathe-Seite|https://wirlernenonline.de/mathe';
const ACTION_QR = '__action__|Sammlung öffnen|browse_collection|{"id":"c1"}';

async function render(
  inputs: {
    quickReplies?: string[]; enabled?: boolean; guideModeActive?: boolean; translate?: TranslateFn;
  } = {},
): Promise<ComponentFixture<QuickRepliesComponent>> {
  const fixture = TestBed.createComponent(QuickRepliesComponent);
  if (inputs.quickReplies !== undefined) fixture.componentRef.setInput('quickReplies', inputs.quickReplies);
  if (inputs.enabled !== undefined) fixture.componentRef.setInput('enabled', inputs.enabled);
  if (inputs.guideModeActive !== undefined) fixture.componentRef.setInput('guideModeActive', inputs.guideModeActive);
  fixture.componentRef.setInput('translate', inputs.translate ?? createTranslator(DE, DE));
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture;
}

describe('QuickRepliesComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [QuickRepliesComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('rendert nichts (kein Wrapper) bei leerer Liste', async () => {
    const host = (await render({ quickReplies: [] })).nativeElement as HTMLElement;
    expect(host.querySelector('.quick-replies')).toBeNull();
  });

  it('rendert nichts, wenn enabled=false (ALT quickRepliesEnabledBool)', async () => {
    const host = (await render({ quickReplies: ['Ja', 'Nein'], enabled: false })).nativeElement as HTMLElement;
    expect(host.querySelector('.quick-replies')).toBeNull();
  });

  it('rendert je einen Standard-Chip mit rohem Label', async () => {
    const host = (await render({ quickReplies: ['Ja', 'Nein'] })).nativeElement as HTMLElement;
    const btns = host.querySelectorAll('button.qr-btn');
    expect(btns.length).toBe(2);
    expect(btns[0].classList.contains('qr-btn--guide')).toBe(false);
    expect(btns[0].textContent?.trim()).toBe('Ja');
    expect(btns[1].textContent?.trim()).toBe('Nein');
  });

  it('beide Chip-Sorten sind Material-Knöpfe', async () => {
    // Nutzer-Vorgabe 2026-07-31: Material-3-Elemente. Bewusst `matButton`
    // statt `mat-chip-set`: eine weitere Material-Komponentenfamilie kostet
    // eine Größenordnung wie `mat-form-field` (dort +106 kB gemessen), während
    // MatButtonModule bereits im Bundle liegt.
    const host = (await render({ quickReplies: ['Ja', GUIDE_QR] })).nativeElement as HTMLElement;
    const chips = Array.from(host.querySelectorAll('.qr-btn'));
    expect(chips.length).toBe(2);
    for (const c of chips) {
      expect(c.classList.contains('mat-mdc-button-base'), `kein Material-Knopf: ${c.textContent?.trim()}`)
        .toBe(true);
    }
  });

  it('Action-Pill zeigt das Label, nicht den rohen __action__-String', async () => {
    const host = (await render({ quickReplies: [ACTION_QR] })).nativeElement as HTMLElement;
    const btn = host.querySelector('button.qr-btn')!;
    expect(btn.textContent?.trim()).toBe('Sammlung öffnen');
    expect(btn.textContent).not.toContain('__action__');
  });

  it('Guide-QR → qr-btn--guide mit Guide-Label + Icon (Lotsen-Modus an)', async () => {
    const host = (await render({ quickReplies: [GUIDE_QR] })).nativeElement as HTMLElement;
    const guide = host.querySelector('button.qr-btn--guide')!;
    expect(guide).not.toBeNull();
    expect(guide.textContent?.trim()).toBe('Zur Mathe-Seite');
    expect(guide.getAttribute('title')).toBe('Im aktuellen Tab zur Seite navigieren');
    expect(guide.querySelector('.bb-icon svg')).not.toBeNull();
  });

  it('Guide-Chip ohne Label: der Rückfall kommt aus dem Übersetzer (C1-b4)', async () => {
    const en = createTranslator({ 'chips.guideFallback': 'Take me there' }, DE);
    const host = (await render({
      quickReplies: ['__guide__||https://wirlernenonline.de/mathe'], translate: en,
    })).nativeElement as HTMLElement;
    expect(host.querySelector('button.qr-btn--guide')!.textContent?.trim()).toBe('Take me there');
  });

  it('Guide-QR wird bei ausgeschaltetem Lotsen-Modus komplett ausgeblendet', async () => {
    const host = (await render({ quickReplies: [GUIDE_QR, 'Normal'], guideModeActive: false })).nativeElement as HTMLElement;
    const btns = host.querySelectorAll('button.qr-btn');
    expect(btns.length).toBe(1);
    expect(btns[0].textContent?.trim()).toBe('Normal');
    expect(host.querySelector('.qr-btn--guide')).toBeNull();
  });

  it('Klick auf Standard-Chip emittiert den rohen qr-String über quickReply', async () => {
    const fixture = await render({ quickReplies: [ACTION_QR] });
    const emitted: string[] = [];
    fixture.componentInstance.quickReply.subscribe((v) => emitted.push(v));
    (fixture.nativeElement.querySelector('button.qr-btn') as HTMLButtonElement).click();
    expect(emitted).toEqual([ACTION_QR]);
  });

  it('Klick auf Guide-Chip emittiert den rohen qr-String über guideQuickReply', async () => {
    const fixture = await render({ quickReplies: [GUIDE_QR] });
    const emittedGuide: string[] = [];
    const emittedRegular: string[] = [];
    fixture.componentInstance.guideQuickReply.subscribe((v) => emittedGuide.push(v));
    fixture.componentInstance.quickReply.subscribe((v) => emittedRegular.push(v));
    (fixture.nativeElement.querySelector('button.qr-btn--guide') as HTMLButtonElement).click();
    expect(emittedGuide).toEqual([GUIDE_QR]);
    expect(emittedRegular).toEqual([]);
  });
});
