// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { MarkdownVorschauComponent } from './markdown-vorschau.component';

/**
 * Die Markdown-Vorschau des Studios (Paket 14, D2): derselbe Renderer wie im Widget
 * (marked + DOMPurify), ohne Sitzung und ohne vertraute Hosts — Vorlagen lesbar, aber nichts,
 * was Skripte ausführt oder ohne Klick nachlädt.
 */
describe('MarkdownVorschauComponent (Paket 14, D2)', () => {
  let fixture: ComponentFixture<MarkdownVorschauComponent>;
  let el: HTMLElement;

  async function zeige(text: string): Promise<void> {
    fixture.componentRef.setInput('text', text);
    await fixture.whenStable();
  }

  beforeEach(() => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(MarkdownVorschauComponent);
    el = fixture.nativeElement as HTMLElement;
  });

  it('rendert Überschriften und Listen', async () => {
    await zeige('# Arbeitsblatt: Thema\n\n1. Erste Aufgabe\n2. Zweite Aufgabe\n\n- Punkt');
    expect(el.querySelector('h1')?.textContent).toBe('Arbeitsblatt: Thema');
    expect(el.querySelectorAll('ol li')).toHaveLength(2);
    expect(el.querySelectorAll('ul li')).toHaveLength(1);
  });

  it('führt keine Skripte und Ereignisse aus', async () => {
    await zeige('Text <script>alert(1)</script> <a href="javascript:alert(2)">x</a> '
      + '<b onclick="alert(3)">fett</b>');
    expect(el.querySelector('script')).toBeNull();
    expect(el.querySelector('[onclick]')).toBeNull();
    expect(el.querySelector('a')?.getAttribute('href') ?? '').not.toContain('javascript:');
  });

  it('warnt bei einem externen Link mit übersetztem Text (Review #6)', async () => {
    await zeige('[Seite](https://example.org/a)');
    expect(el.querySelector('a')?.getAttribute('title')).toBe('Achtung! Externe URL.');
  });

  it('lädt nichts nach — kein Bild', async () => {
    await zeige('![Bild](https://example.org/x.png) <img src="https://example.org/y.png">');
    expect(el.querySelector('img')).toBeNull();
  });

  it('zeigt bei leerer Vorlage einen Hinweis statt einer leeren Fläche', async () => {
    await zeige('   ');
    expect(el.textContent).toContain('Keine Vorlage');
  });
});
