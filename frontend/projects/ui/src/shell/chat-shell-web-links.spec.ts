import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { ChatMessage, UiInfo, WebLink } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * „Webseiten-Inhalte" in BEIDEN Fenstergrößen (Befund 2026-09-30).
 *
 * Seit U2b wählt `cardsVisible` im großen Fenster das Kachelraster statt der
 * Textlink-Boxen. Die Web-Links sind aber keine Karten: sie standen nur in den
 * Boxen und fielen im großen Fenster ganz weg — „Was ist WissenLebtOnline?"
 * zeigte klein die Box mit WLO-Startseite, groß nichts.
 */
const DE_T = createTranslator(DE, DE);
const LINKS: WebLink[] = [{ title: 'WLO-Startseite', url: 'https://wirlernenonline.de/' }];

function make(): { c: ChatShellComponent; f: ComponentFixture<ChatShellComponent>; el: HTMLElement } {
  const f = TestBed.createComponent(ChatShellComponent);
  const c = f.componentInstance;
  f.componentRef.setInput('translate', DE_T);
  f.detectChanges();
  store(c).set([]);
  f.detectChanges();
  return { c, f, el: f.nativeElement as HTMLElement };
}

function store(c: ChatShellComponent) {
  return (c as unknown as {
    _store: { addBotMessage: (...args: unknown[]) => string; set: (m: ChatMessage[]) => void };
  })._store;
}

/** Bot-Antwort nur mit Web-Links — ohne Karten, wie die Orientierungs-Antwort. */
function antwortMitLinks(c: ChatShellComponent, ui?: UiInfo): void {
  store(c).addBotMessage('Mehr dazu auf der WLO-Startseite.', false, [], undefined,
    ui, undefined, undefined, LINKS);
}

describe('ChatShellComponent — Webseiten-Inhalte in beiden Fenstergrößen', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('großes Fenster (Kachelraster): die Box „Webseiten-Inhalte" bleibt', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('sizeStep', 'large');
    antwortMitLinks(c);
    f.detectChanges();

    expect(el.querySelector('boerdi-card-list')).not.toBeNull();
    expect(el.querySelectorAll('.result-group--web').length).toBe(1);
    expect(el.querySelector('.result-group--web')?.textContent).toContain('Webseiten-Inhalte');
    expect(el.querySelector('.result-group--web')?.textContent).toContain('WLO-Startseite');
  });

  it('kleines Fenster: die Box steht genau einmal da (keine Doppelung)', () => {
    const { c, f, el } = make();
    antwortMitLinks(c);
    f.detectChanges();

    expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
    expect(el.querySelectorAll('.result-group--web').length).toBe(1);
  });

  it('großes Fenster: eine Tour-Nachricht zeigt keine Box (wie klein)', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('sizeStep', 'large');
    antwortMitLinks(c, { pattern: 'TOUR:intro' });
    f.detectChanges();

    expect(el.querySelector('.result-group--web')).toBeNull();
  });
});
