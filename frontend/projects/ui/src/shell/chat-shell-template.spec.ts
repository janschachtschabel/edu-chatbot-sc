import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatMessage, DebugInfo, InlineDocument, TopicPageView } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/** Deutscher Übersetzer ohne Signal-Maschinerie (C1-b2). Die Bestandstests
 *  unten prüfen den deutschen Wortlaut weiter wörtlich und sind damit das
 *  Regressionsnetz der Umstellung; das Umschalten ist eigens gepinnt. */
const DE_T = createTranslator(DE, DE);

/**
 * Message-Row-Template + Eingabe-Footer der Chat-Shell (8-4S-f3). Gepinnt wird,
 * was das Template GARANTIERT: die Zeilen-/Bubble-Struktur aus ALT
 * chat.component.html (1-419 + 609-632), die Gates der Sub-Renderer, die beiden
 * ViewChild-Anker (`#messagesContainer` fürs Auto-Follow, `#inputField` fürs
 * Refokussieren) und die Footer-Interaktion. Die Sub-Renderer selbst sind in
 * ihren eigenen 8-2-Specs gepinnt — hier zählt die Komposition.
 */

/** Erst-Render (löst `ngOnInit` aus), dann den Verlauf leeren: die Begrüßungs-
 *  Bubble ist in `lifecycle.spec` gepinnt und würde hier nur mitzählen. */
function make(): { c: ChatShellComponent; f: ComponentFixture<ChatShellComponent>; el: HTMLElement } {
  const f = TestBed.createComponent(ChatShellComponent);
  const c = f.componentInstance;
  f.componentRef.setInput('translate', DE_T);
  f.detectChanges();
  (c as unknown as { _store: { set: (m: ChatMessage[]) => void } })._store.set([]);
  f.detectChanges();
  return { c, f, el: f.nativeElement as HTMLElement };
}

/** Vollständiges DebugInfo — das Panel dereferenziert die Pflichtfelder direkt. */
const DEBUG_FIXTURE: DebugInfo = {
  persona: 'lehrkraft', intent: 'search', state: 'explore', turn_type: 'normal',
  signals: [], pattern: 'M06', entities: {}, tools_called: [],
  phase1_eliminated: [], phase2_scores: {}, phase3_modulations: {},
};

/** Store-Zugriff: die Reducer sind absichtlich nicht Teil der Public API. */
function store(c: ChatShellComponent) {
  return (c as unknown as {
    _store: {
      addUserMessage: (s: string) => void;
      addBotMessage: (...args: unknown[]) => string;
      set: (m: ChatMessage[]) => void;
      updateLoadingPhase: (id: string, label: string) => void;
    };
  })._store;
}

describe('ChatShellComponent — Message-Row-Template (8-4S-f3)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('eine .message-row je Nachricht, mit bot-row/user-row + id="msg-<id>"', () => {
    const { c, f, el } = make();
    store(c).addUserMessage('Frage');
    const botId = store(c).addBotMessage('Antwort');
    f.detectChanges();

    const rows = el.querySelectorAll('.message-row');
    expect(rows.length).toBe(2);
    expect(rows[0].classList.contains('user-row')).toBe(true);
    expect(rows[1].classList.contains('bot-row')).toBe(true);
    expect(el.querySelector('#msg-' + botId)).not.toBeNull();
  });

  it('Bot-Avatar nur in Bot-Zeilen (dekorativ: alt="")', () => {
    const { c, f, el } = make();
    store(c).addUserMessage('Frage');
    f.detectChanges();
    expect(el.querySelector('.msg-avatar')).toBeNull();

    store(c).addBotMessage('Antwort');
    f.detectChanges();
    const img = el.querySelector('.msg-avatar') as HTMLImageElement;
    expect(img).not.toBeNull();
    expect(img.getAttribute('alt')).toBe('');
    expect(img.getAttribute('src')).toContain('data:image/svg+xml'); // inline, kein externes Asset (DSGVO)
  });

  it('Lade-Bubble: Typing-Dots + Live-Phasen-Label, kein Inhalt', () => {
    const { c, f, el } = make();
    const id = store(c).addBotMessage('', true);
    f.detectChanges();
    expect(el.querySelector('.typing-dots')).not.toBeNull();
    expect(el.querySelector('.msg-content')).toBeNull();

    store(c).updateLoadingPhase(id, 'sucht Inhalte…');
    f.detectChanges();
    expect(el.querySelector('.typing-phase')?.textContent).toContain('sucht Inhalte…');
  });

  it('Inhalts-Bubble: Markdown gerendert (kein Roh-Markdown im DOM)', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Das ist **wichtig**');
    f.detectChanges();
    const content = el.querySelector('.msg-content')!;
    expect(content.querySelector('strong')?.textContent).toBe('wichtig');
    expect(content.textContent).not.toContain('**');
  });

  it('#messagesContainer + #inputField sind verdrahtet (Auto-Follow + Refokus)', () => {
    const { c, f, el } = make();
    f.detectChanges();
    expect(el.querySelector('.messages-area')).not.toBeNull();
    expect(el.querySelector('.chat-input')).not.toBeNull();

    const view = c as unknown as {
      _messagesContainer: () => { nativeElement: HTMLElement } | undefined;
      _inputField: () => { nativeElement: HTMLElement } | undefined;
    };
    expect(view._messagesContainer()?.nativeElement).toBe(el.querySelector('.messages-area'));
    expect(view._inputField()?.nativeElement).toBe(el.querySelector('.chat-input'));
  });

  it('Messages-Bereich ist eine Live-Region (Screenreader hören neue Antworten)', () => {
    const { f, el } = make();
    f.detectChanges();
    const area = el.querySelector('.messages-area')!;
    expect(area.getAttribute('role')).toBe('log');
    expect(area.getAttribute('aria-live')).toBe('polite');
    expect(area.getAttribute('aria-label')).toBeTruthy();
  });

  it('Quick-Replies: gerendert und Klick löst den Routing-Pfad aus', () => {
    const { c, f, el } = make();
    const spy = vi.spyOn(c, 'onQuickReply').mockImplementation(() => {});
    store(c).addBotMessage('Antwort', false, undefined, ['Mehr dazu']);
    f.detectChanges();

    const btn = el.querySelector('.qr-btn') as HTMLButtonElement;
    expect(btn?.textContent).toContain('Mehr dazu');
    btn.click();
    expect(spy).toHaveBeenCalledWith('Mehr dazu');
  });

  it('Sub-Renderer werden nur mit Daten komponiert (Grouping/Swimlanes/Inline-Doc)', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Nur Text');
    f.detectChanges();
    expect(el.querySelector('boerdi-swimlanes')).toBeNull();
    expect(el.querySelector('boerdi-inline-documents')).toBeNull();

    const docs: InlineDocument[] = [{ kind: 'lernpfad', title: 'Mein Pfad', content: '# Schritt' }];
    const topic: TopicPageView = {
      variant_title: 'Mathe', topic_page_url: 'https://wirlernenonline.de/t',
      swimlanes: [{ heading: 'Videos', cards: [] }],
    };
    store(c).addBotMessage(
      'Mit Boxen', false, undefined, undefined, undefined, null,
      undefined, undefined, docs, undefined, topic,
    );
    f.detectChanges();
    expect(el.querySelector('boerdi-swimlanes')).not.toBeNull();
    expect(el.querySelector('boerdi-inline-documents')).not.toBeNull();
    // Result-Groups hängen am Host-Flag statt an den Daten (das Daten-Gate liegt
    // in der Komponente) — aber nur in Bot-Zeilen.
    expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
  });

  it('User-Bubbles instanziieren KEINEN Sub-Renderer (nichts zu rendern)', () => {
    const { c, f, el } = make();
    store(c).addUserMessage('Meine Frage');
    f.detectChanges();
    expect(el.querySelector('boerdi-result-groups')).toBeNull();
    expect(el.querySelector('boerdi-quick-replies')).toBeNull();
    expect(el.querySelector('boerdi-swimlanes')).toBeNull();
    expect(el.querySelector('boerdi-inline-documents')).toBeNull();
  });

  it('Druck-Leiste: Lernpfad ohne Box bekommt sie, MIT Box nicht (kein Doppel-Button)', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('> **Lernpfad: Bruchrechnen**\n\n### Schritt 1');
    f.detectChanges();
    expect(el.querySelector('.lp-print-bar')).not.toBeNull();

    const docs: InlineDocument[] = [{ kind: 'lernpfad', title: 'P', content: '# S' }];
    store(c).set([]);
    store(c).addBotMessage('> **Lernpfad: x**', false, undefined, undefined, undefined, null,
      undefined, undefined, docs);
    f.detectChanges();
    expect(el.querySelector('.lp-print-bar')).toBeNull();
    expect(el.querySelector('boerdi-inline-documents')).not.toBeNull();
  });

  // 8-2i: `inline-result-grouping` ist wieder ein echtes Host-Attribut (in ALT
  // seit Welle E eine auf `true` eingefrorene Compat-Hülle, wodurch der flache
  // Tile-Grid unerreichbar war). Default bleibt `true` → Boxen-Layout wie bisher;
  // `false` schaltet auf den klassischen Tile-Grid + Pagination um.
  it('Default: Boxen-Layout, KEIN flacher Tile-Grid', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('mit Karten', false, [{ node_id: 'n', title: 'K' } as never]);
    f.detectChanges();
    expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
    expect(el.querySelector('boerdi-card-list')).toBeNull();
  });

  it('inline-result-grouping="false": flacher Tile-Grid statt Boxen', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('inlineResultGrouping', false);
    store(c).addBotMessage('mit Karten', false, [{ node_id: 'n', title: 'K' } as never]);
    f.detectChanges();
    expect(el.querySelector('boerdi-card-list')).not.toBeNull();
    expect(el.querySelector('boerdi-result-groups')).toBeNull();
  });

  it('Flat-Grid: Aktions-Outputs laufen in die collection-actions-Delegates', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('inlineResultGrouping', false);
    const browse = vi.spyOn(c, 'browseCollection').mockResolvedValue(undefined);
    const lp = vi.spyOn(c, 'generateLearningPath').mockResolvedValue(undefined);
    const more = vi.spyOn(c, 'showMoreCards').mockImplementation(() => {});
    store(c).addBotMessage('mit Karten', false, [
      { node_type: 'collection', node_id: 'n1', title: 'Mathe' } as never,
      { node_type: 'material', node_id: 'n2', title: 'B' } as never,
    ]);
    f.detectChanges();

    // Erste Karte ist die Sammlung: ihre Leiste trägt Inhalte + Lernpfad. Die
    // Handklasse `.card-btn` gibt es seit der M3-Umstellung nicht mehr, deshalb
    // über das Element — und über die ERSTE Leiste, weil die zweite Karte
    // inzwischen ihre eigene (M17-)Leiste hat.
    const sammlung = el.querySelectorAll('.card-actions')[0];
    sammlung.querySelectorAll<HTMLButtonElement>('button')[0].click();
    sammlung.querySelectorAll<HTMLButtonElement>('button')[1].click();
    expect(browse).toHaveBeenCalledWith('n1', 'Mathe');
    expect(lp).toHaveBeenCalledWith('n1', 'Mathe');

    // 2 Karten > 1 → Pagination-Leiste; beide sichtbar → kein Aufdeck-Button.
    expect(el.querySelector('.pagination-info')?.textContent).toContain('2 von 2');
    expect(more).not.toHaveBeenCalled();
  });

  it('Debug-Panel: aus by default, sichtbar nach toggleDebug()', () => {
    const { c, f, el } = make();
    f.detectChanges();
    expect(el.querySelector('.debug-panel')).toBeNull();

    c.latestDebug.set({ ...DEBUG_FIXTURE });
    c.toggleDebug();
    f.detectChanges();
    expect(el.querySelector('.debug-panel')).not.toBeNull();
  });
});

describe('ChatShellComponent — Eingabe-Footer (8-4S-f3)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('Eingabefeld hat einen programmatischen Namen (8-6, WCAG 1.3.1/4.1.2)', () => {
    // Ein `placeholder` ist KEIN Label: er verschwindet beim Tippen und wird
    // von Screenreadern je nach Kombination gar nicht als Name gemeldet.
    // Betrifft das zentrale Bedienelement des ganzen Widgets.
    const { f, el } = make();
    f.detectChanges();
    const input = el.querySelector('.chat-input') as HTMLInputElement;
    expect(input.getAttribute('aria-label')).toBeTruthy();
  });

  it('Eingabe schreibt ins userInput-Signal, Senden-Button ruft sendMessage', () => {
    const { c, f, el } = make();
    const spy = vi.spyOn(c, 'sendMessage').mockResolvedValue(undefined);
    f.detectChanges();

    const input = el.querySelector('.chat-input') as HTMLInputElement;
    input.value = 'Hallo Boerdi';
    input.dispatchEvent(new Event('input'));
    f.detectChanges();
    expect(c.userInput()).toBe('Hallo Boerdi');

    (el.querySelector('.btn-send') as HTMLButtonElement).click();
    expect(spy).toHaveBeenCalled();
  });

  it('Senden-Button gesperrt bei leerer Eingabe und während eines Turns', () => {
    const { c, f, el } = make();
    f.detectChanges();
    const send = () => el.querySelector('.btn-send') as HTMLButtonElement;
    expect(send().disabled).toBe(true); // leer

    c.userInput.set('   ');
    f.detectChanges();
    expect(send().disabled).toBe(true); // nur Whitespace

    c.userInput.set('Frage');
    f.detectChanges();
    expect(send().disabled).toBe(false);

    c.isLoading.set(true);
    f.detectChanges();
    expect(send().disabled).toBe(true); // Turn läuft
  });

  it('Eingabefeld: Placeholder + disabled folgen dem Turn-Zustand', () => {
    const { c, f, el } = make();
    f.detectChanges();
    const input = () => el.querySelector('.chat-input') as HTMLInputElement;
    expect(input().disabled).toBe(false);
    expect(input().placeholder).toContain('Nachricht');

    c.isLoading.set(true);
    f.detectChanges();
    expect(input().disabled).toBe(true);
    expect(input().placeholder).toContain('denkt nach');
  });

  it('Enter (ohne Shift) sendet, Shift+Enter nicht', () => {
    const { c, f, el } = make();
    const spy = vi.spyOn(c, 'sendMessage').mockResolvedValue(undefined);
    f.detectChanges();
    const input = el.querySelector('.chat-input') as HTMLInputElement;

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, bubbles: true }));
    expect(spy).not.toHaveBeenCalled();
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('Mikro-/Vorlese-Buttons nur wenn Host UND Backend sie erlauben', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort');
    f.detectChanges();
    // Default: `show-language-buttons` nicht gesetzt → keine Sprach-Buttons.
    expect(el.querySelector('.btn-mic')).toBeNull();
    expect(el.querySelector('.btn-speak')).toBeNull();

    f.componentRef.setInput('showLanguageButtons', true);
    f.detectChanges();
    expect(el.querySelector('.btn-mic')).not.toBeNull();
    expect(el.querySelector('.btn-speak')).not.toBeNull();

    // Backend ohne Speech (B-API-academiccloud) → ehrlich aus, trotz Host-Wunsch.
    c.speechBackendEnabled.set(false);
    f.detectChanges();
    expect(el.querySelector('.btn-mic')).toBeNull();
    expect(el.querySelector('.btn-speak')).toBeNull();
  });

  /** Die deutschen Texte allein beweisen nur den Wortlaut — sie stünden auch
   *  fest verdrahtet im Template. Erst der Wechsel beweist, dass das Template
   *  wirklich über `[translate]` geht. */
  it('nimmt seine Oberflächentexte aus dem Übersetzer (C1-b2)', () => {
    const { f, el } = make();
    expect(el.querySelector('.btn-send')?.getAttribute('aria-label')).toBe('Senden');
    expect(el.querySelector('.messages-area')?.getAttribute('aria-label')).toBe('Chat-Verlauf');

    const EN: Record<string, string> = { 'chat.send': 'Send', 'chat.log': 'Chat history' };
    f.componentRef.setInput('translate', (key: string) => EN[key] ?? key);
    f.detectChanges();

    expect(el.querySelector('.btn-send')?.getAttribute('aria-label')).toBe('Send');
    expect(el.querySelector('.messages-area')?.getAttribute('aria-label')).toBe('Chat history');
  });
});

describe('ChatShellComponent — ngOnChanges Trusted-Hosts (8-4S-f3)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('geänderte trustedHosts verwerfen den Markdown-Cache (Links neu klassifizieren)', () => {
    const { c } = make();
    const spy = vi.spyOn(c.render, 'clearCache');

    c.ngOnChanges({ trustedHosts: { previousValue: [], currentValue: [], firstChange: true } });
    expect(spy).not.toHaveBeenCalled(); // erster Wert: nichts gecacht

    c.ngOnChanges({ trustedHosts: { previousValue: [], currentValue: ['neu.example'], firstChange: false } });
    expect(spy).toHaveBeenCalledTimes(1);

    c.ngOnChanges({ trustedHosts: { previousValue: ['a'], currentValue: ['a'], firstChange: false } });
    expect(spy).toHaveBeenCalledTimes(1); // gleicher Wert → kein Reset
  });

  it('eine geänderte Sprache verwirft den Markdown-Cache ebenfalls (C1-c)', () => {
    // Der Cache-Key ist `sender|session|text` — die Sprache steht NICHT darin.
    // In den gerenderten Bubbles stecken aber übersetzte Icon-Labels und die
    // Extern-Warnung; ohne Reset bliebe der Verlauf nach dem Umschalten in der
    // alten Sprache stehen. In C1-b3 gefunden, mit dem Umschalter fällig.
    const { c } = make();
    const spy = vi.spyOn(c.render, 'clearCache');

    c.ngOnChanges({ locale: { previousValue: 'de', currentValue: 'de', firstChange: true } });
    expect(spy).not.toHaveBeenCalled();

    c.ngOnChanges({ locale: { previousValue: 'de', currentValue: 'en', firstChange: false } });
    expect(spy).toHaveBeenCalledTimes(1);

    c.ngOnChanges({ locale: { previousValue: 'en', currentValue: 'en', firstChange: false } });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  // ── U1: Neustart-Knopf in der Eingabezeile ────────────────────────────
  // Er stand in der Kopfzeile der Widget-Hülle. Rahmenlos gibt es die nicht
  // mehr — und der Neustart ist keine Zierde der Kopfzeile, sondern eine
  // Aktion am Gespräch. Er gehört dorthin, wo das Gespräch geführt wird.

  it('Neustart sitzt in der Eingabezeile, direkt links vom Senden-Knopf', () => {
    const { el } = make();
    const row = el.querySelector('.chat-footer');
    expect(row, 'Eingabezeile').not.toBeNull();
    const restart = row!.querySelector('.btn-restart');
    expect(restart, 'Neustart-Knopf').not.toBeNull();
    // Reihenfolge ist die Anforderung („links neben dem Absende-Button"), nicht
    // bloße Anwesenheit — sonst bestünde der Test auch mit dem Knopf ganz vorn.
    expect(restart!.nextElementSibling?.classList.contains('btn-send')).toBe(true);
  });

  it('Neustart ruft restart() und trägt den Katalogtext als zugänglichen Namen', () => {
    const { c, el } = make();
    const spy = vi.spyOn(c, 'restart').mockImplementation(() => undefined);
    const btn = el.querySelector('.btn-restart') as HTMLButtonElement;

    expect(btn.getAttribute('aria-label')).toBe(DE['widget.restart']);
    btn.click();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('Neustart bleibt bedienbar, während der Bot arbeitet', () => {
    // Genau dann braucht man ihn: ein Zug, der sich festgefahren anfühlt, muss
    // abbrechbar sein. Eingabefeld und Senden sind in dieser Lage gesperrt —
    // der Neustart absichtlich nicht.
    const { c, f, el } = make();
    c.isLoading.set(true);
    f.detectChanges();
    expect((el.querySelector('.btn-restart') as HTMLButtonElement).disabled).toBe(false);
    expect((el.querySelector('.btn-send') as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('ChatShell — Größen-Umschalter (U2a)', () => {
  // Er wirkt auf die HÜLLE, nicht auf das Gespräch: die Shell meldet nur den
  // Wunsch nach oben. Deshalb ein Output statt eigener Zustand — die Stufe
  // gehört dem Panel, das seine Maße kennt.

  it('bleibt weg, solange die Hülle ihn nicht anfordert', () => {
    // Standard aus: die Shell läuft auch ohne Hülle (Studio-Vorschau), und ein
    // Knopf, den niemand hört, würde nichts bewirken.
    const { el } = make();
    expect(el.querySelector('.btn-size')).toBeNull();
  });

  it('sitzt links vom Neustart-Knopf, wenn die Hülle ihn anfordert', () => {
    const { f, el } = make();
    f.componentRef.setInput('sizeToggleVisible', true);
    f.detectChanges();
    const btn = el.querySelector('.btn-size');
    expect(btn, 'Größen-Knopf').not.toBeNull();
    expect(btn!.nextElementSibling?.classList.contains('btn-restart')).toBe(true);
  });

  it('meldet den Umschaltwunsch nach oben, statt selbst etwas zu ändern', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('sizeToggleVisible', true);
    f.detectChanges();
    const seen: unknown[] = [];
    c.sizeToggle.subscribe((v) => seen.push(v));
    (el.querySelector('.btn-size') as HTMLButtonElement).click();
    expect(seen).toHaveLength(1);
  });

  it('benennt die Aktion nach dem Ziel, nicht nach dem Zustand', () => {
    // Klein ⇒ „vergrößern", groß ⇒ „verkleinern". Ein Knopf, der den IST-Zustand
    // benennt, lässt offen, was ein Klick tut.
    const { f, el } = make();
    f.componentRef.setInput('sizeToggleVisible', true);
    f.detectChanges();
    const btn = () => el.querySelector('.btn-size') as HTMLButtonElement;
    expect(btn().getAttribute('aria-label')).toBe(DE['widget.size.larger']);

    f.componentRef.setInput('sizeStep', 'large');
    f.detectChanges();
    expect(btn().getAttribute('aria-label')).toBe(DE['widget.size.smaller']);
  });
});

describe('ChatShell — Kachel-Regel (U2b)', () => {
  // Beide Darstellungen gab es schon; U2b entscheidet nur, welche greift.
  // `boerdi-result-groups` = Textlinks in Boxen, `boerdi-card-list` = Kacheln.

  function withCards(): { c: ChatShellComponent; f: ComponentFixture<ChatShellComponent>; el: HTMLElement } {
    const r = make();
    store(r.c).addBotMessage('mit Treffern', false, [{ node_id: 'n', title: 'K' } as never]);
    r.f.detectChanges();
    return r;
  }

  it('Vorgabe (klein, auto): Textlinks, keine Kacheln — Bestandsverhalten', () => {
    const { el } = withCards();
    expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
    expect(el.querySelector('boerdi-card-list')).toBeNull();
  });

  it('große Stufe schaltet auf Kacheln um', () => {
    const { f, el } = withCards();
    f.componentRef.setInput('sizeStep', 'large');
    f.detectChanges();
    expect(el.querySelector('boerdi-card-list')).not.toBeNull();
    expect(el.querySelector('boerdi-result-groups')).toBeNull();
  });

  it('show-cards="never" hält die Kacheln auch groß aus', () => {
    const { f, el } = withCards();
    f.componentRef.setInput('sizeStep', 'large');
    f.componentRef.setInput('showCards', 'never');
    f.detectChanges();
    expect(el.querySelector('boerdi-card-list')).toBeNull();
    expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
  });

  it('show-cards="always" zeigt sie auch klein', () => {
    const { f, el } = withCards();
    f.componentRef.setInput('showCards', 'always');
    f.detectChanges();
    expect(el.querySelector('boerdi-card-list')).not.toBeNull();
  });

  it('unbekannter show-cards-Wert fällt auf „auto"', () => {
    const { f, el } = withCards();
    f.componentRef.setInput('showCards', 'vielleicht');
    f.detectChanges();
    expect(el.querySelector('boerdi-result-groups')).not.toBeNull();
  });
});
