import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UiBlock } from '@boerdi/ui-module';

import { ChatMessage, UiInfo } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Paket U1-a: Die Shell zeigt die UI-Blöcke einer Antwort über den einen Platzhalter — live wie
 * nach dem Neuladen steht `ui.ui_bloecke` an der Nachricht. Ohne registriertes Modul erscheint
 * die Textfassung (`ui_noch_nicht_da`); seit U1-b steht der Inhaltsrahmen im Register.
 */
const DE_T = createTranslator(DE, DE);

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

const BLOCK: UiBlock = {
  block_id: 'b0000001', modul: 'ui_noch_nicht_da', version: 1, art: 'anzeigen',
  daten: {}, text: 'Die Textfassung des Blocks', status: 'nur_anzeige',
};

describe('ChatShellComponent — UI-Blöcke', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('zeigt die Blöcke einer Antwort (hier als Textfassung)', () => {
    const { c, f, el } = make();
    const ui: UiInfo = { ui_bloecke: [BLOCK] };
    store(c).addBotMessage('Antwort', false, [], undefined, ui);
    f.detectChanges();
    expect(el.querySelector('boerdi-ui-bloecke')).not.toBeNull();
    expect(el.querySelector('.ui-block')?.textContent).toContain('Die Textfassung des Blocks');
  });

  it('ohne Blöcke kein Platzhalter', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [], undefined, {});
    f.detectChanges();
    expect(el.querySelector('boerdi-ui-bloecke')).toBeNull();
  });
});

describe('ChatShellComponent — Inhaltsrahmen (U1-b)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('zeigt das echte Modul aus dem Register und keine zweite Druckleiste', () => {
    const { c, f, el } = make();
    const rahmen: UiBlock = {
      block_id: 'b0000002', modul: 'ui_inhaltsrahmen', version: 1, art: 'anzeigen',
      daten: { titel: 'Lernpfad Brüche', art: 'lernpfad', markdown: '### Schritt 1\nErkennen' },
      text: '### Schritt 1\nErkennen', status: 'nur_anzeige',
    };
    store(c).addBotMessage('> **Lernpfad: Brüche', false, [], undefined, { ui_bloecke: [rahmen] });
    f.detectChanges();
    expect(el.querySelector('.inline-document__title')?.textContent?.trim()).toBe('Lernpfad Brüche');
    expect(el.querySelector('.lp-print-bar')).toBeNull();
  });
});

describe('ChatShellComponent — Linkbox (U1-c1)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  const LINKS = [{ title: 'WLO', url: 'https://wirlernenonline.de/' }];
  const LINKBOX: UiBlock = {
    block_id: 'b0000003', modul: 'ui_linkbox', version: 1, art: 'anzeigen',
    daten: { links: [{ titel: 'WLO', url: 'https://wirlernenonline.de/' }] },
    text: '- [WLO](https://wirlernenonline.de/)', status: 'nur_anzeige',
  };
  const KARTE = { node_id: 'c1', title: 'Sammlung Optik', node_type: 'collection' } as never;

  it('mit Linkbox-Block genau EINE Webseiten-Box — nach den Trefferboxen', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE], undefined, { ui_bloecke: [LINKBOX] },
      null, undefined, LINKS);
    f.detectChanges();
    const boxen = el.querySelectorAll('.result-group--web');
    expect(boxen.length).toBe(1);
    expect(boxen[0].closest('ui-linkbox')).not.toBeNull();
    const gruppen = el.querySelector('boerdi-result-groups')!;
    const linkbox = el.querySelector('ui-linkbox')!;
    expect(gruppen.compareDocumentPosition(linkbox) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('auch unter den Kacheln (show-cards="always") genau EINE Webseiten-Box', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('showCards', 'always');
    store(c).addBotMessage('Antwort', false, [KARTE], undefined, { ui_bloecke: [LINKBOX] },
      null, undefined, LINKS);
    f.detectChanges();
    expect(el.querySelector('boerdi-card-list')).not.toBeNull();
    expect(el.querySelectorAll('.result-group--web').length).toBe(1);
    expect(el.querySelector('ui-linkbox')).not.toBeNull();
  });

  it('ohne Block bleibt die bisherige Box', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE], undefined, {}, null, undefined, LINKS);
    f.detectChanges();
    expect(el.querySelectorAll('.result-group--web').length).toBe(1);
    expect(el.querySelector('ui-linkbox')).toBeNull();
  });
});

describe('ChatShellComponent — Trefferliste (U1-c2a)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  const KARTE = { node_id: 'c1', title: 'Sammlung Optik', node_type: 'collection', url: 'https://wirlernenonline.de/c1' };
  const TREFFERLISTE: UiBlock = {
    block_id: 'b0000005', modul: 'ui_trefferliste', version: 1, art: 'anzeigen',
    daten: { karten: [KARTE], such_metas: [], seiten: null, typ_fokus: '' },
    text: '- [Sammlung Optik](https://wirlernenonline.de/c1)', status: 'nur_anzeige',
  };

  it('Trefferboxen genau einmal — aus dem Modul', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE as never], undefined, { ui_bloecke: [TREFFERLISTE] });
    f.detectChanges();
    expect(el.querySelectorAll('boerdi-result-groups').length).toBe(1);
    expect(el.querySelector('ui-trefferliste boerdi-result-groups')).not.toBeNull();
    expect(el.textContent).toContain('Sammlung Optik');
  });

  it('Kacheln mit Trefferliste: die Kachelliste genau einmal (aus dem Modul), Web-Links danach', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('showCards', 'always');
    store(c).addBotMessage('Antwort', false, [KARTE as never], undefined, { ui_bloecke: [TREFFERLISTE] },
      null, undefined, [{ title: 'WLO', url: 'https://wirlernenonline.de/' }]);
    f.detectChanges();
    expect(el.querySelectorAll('boerdi-card-list').length).toBe(1);
    expect(el.querySelector('ui-trefferliste boerdi-card-list')).not.toBeNull();
    const web = el.querySelectorAll('.result-group--web');
    expect(web.length).toBe(1);
    expect(el.querySelector('ui-trefferliste')!.compareDocumentPosition(web[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('wechselt zur Laufzeit zwischen Boxen und Kacheln', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE as never], undefined, { ui_bloecke: [TREFFERLISTE] });
    f.detectChanges();
    expect(el.querySelector('ui-trefferliste boerdi-result-groups')).not.toBeNull();
    f.componentRef.setInput('showCards', 'always');
    f.detectChanges();
    expect(el.querySelector('ui-trefferliste boerdi-result-groups')).toBeNull();
    expect(el.querySelector('ui-trefferliste boerdi-card-list')).not.toBeNull();
    f.componentRef.setInput('showCards', 'never');
    f.detectChanges();
    expect(el.querySelector('ui-trefferliste boerdi-result-groups')).not.toBeNull();
  });

  it('Trefferliste ohne Linkbox: die Web-Links gehen nicht verloren', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE as never], undefined, { ui_bloecke: [TREFFERLISTE] },
      null, undefined, [{ title: 'WLO', url: 'https://wirlernenonline.de/' }]);
    f.detectChanges();
    const boxen = el.querySelectorAll('.result-group--web');
    expect(boxen.length).toBe(1);
    const liste = el.querySelector('ui-trefferliste')!;
    expect(liste.compareDocumentPosition(boxen[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('ohne Block bleiben die bisherigen Boxen', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE as never], undefined, {});
    f.detectChanges();
    expect(el.querySelector('ui-trefferliste')).toBeNull();
    expect(el.querySelectorAll('boerdi-result-groups').length).toBe(1);
  });
});

describe('ChatShellComponent — „mehr laden“ trifft die richtige Nachricht (Review U1-c2b)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('gleiche Block-Kennung in zwei Antworten: der Klick in der zweiten lädt für die zweite', () => {
    const { c, f, el } = make();
    f.componentRef.setInput('showCards', 'always');
    const karten = Array.from({ length: 5 }, (_, i) => ({
      node_id: `k${i}`, title: `Karte ${i}`, node_type: 'content', url: `https://wirlernenonline.de/k${i}`,
    }));
    const seiten = { total_count: 12, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe' };
    const block: UiBlock = {
      block_id: 'b0000009', modul: 'ui_trefferliste', version: 1, art: 'anzeigen', status: 'nur_anzeige',
      daten: { karten, such_metas: [], seiten, typ_fokus: '' }, text: '',
    };
    const erste = store(c).addBotMessage('Erste', false, karten as never, undefined, { ui_bloecke: [block] }, seiten);
    const zweite = store(c).addBotMessage('Zweite', false, karten as never, undefined, { ui_bloecke: [block] }, seiten);
    f.detectChanges();
    const laden = vi.spyOn(c, 'loadMoreCards').mockResolvedValue();
    const listen = el.querySelectorAll('ui-trefferliste');
    expect(listen.length).toBe(2);
    (listen[1].querySelector('.pagination-bar button') as HTMLButtonElement).click();
    expect(laden).toHaveBeenCalledWith(zweite);
    expect(laden).not.toHaveBeenCalledWith(erste);
  });
});

describe('ChatShellComponent — Entscheidung (U1-d1)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  const frage = (block_id: string): UiBlock => ({
    block_id, modul: 'ui_entscheidung', version: 1, art: 'abfragen', status: 'offen',
    daten: { frage: 'Welche Klasse?', optionen: [{ id: 'a', label: 'Klasse 5' }, { id: 'b', label: 'Klasse 6' }] },
    text: 'Welche Klasse?',
  });
  const ANTWORT = { session_id: 's', content: 'Gut, Klasse 6.', cards: [], quick_replies: [], ui: {} } as never;

  function haengenderStrom(c: ChatShellComponent) {
    let fertig: (r: unknown) => void = () => undefined;
    const stream = vi.fn(() => new Promise((r) => { fertig = r; }));
    (c as unknown as { _api: { stream: unknown } })._api.stream = stream;
    return { stream, fertig: (r: unknown) => fertig(r) };
  }

  const status = (c: ChatShellComponent) =>
    c.messages().flatMap((m) => m.ui?.ui_bloecke ?? []).map((b) => [b.block_id, b.status]);

  it('die Antwort geht als nächster Zug mit ui_antwort; danach nur lesend, ältere offene veraltet', async () => {
    const { c, f, el } = make();
    const { stream, fertig } = haengenderStrom(c);
    store(c).addBotMessage('Alt', false, [], undefined, { ui_bloecke: [frage('b0000021')] });
    store(c).addBotMessage('Kurz nachgefragt:', false, [], undefined, { ui_bloecke: [frage('b0000022')] });
    f.detectChanges();
    const jung = el.querySelectorAll('ui-entscheidung')[1];
    (jung.querySelector('input[value="b"]') as HTMLInputElement).click();
    f.detectChanges();
    (jung.querySelector('button[type="submit"]') as HTMLButtonElement).click();
    f.detectChanges();

    expect(stream).toHaveBeenCalledTimes(1);
    const args = stream.mock.calls[0] as unknown[];
    expect(args[1]).toBe('Klasse 6');                                  // Nutzerblase = lesbare Fassung
    expect(args[4]).toBeUndefined();                                    // keine action
    expect(args[6]).toEqual({ block_id: 'b0000022', daten: { gewaehlt: ['b'] } });
    expect(c.messages().some((m) => m.sender === 'user' && m.content === 'Klasse 6')).toBe(true);
    expect(status(c)).toEqual([['b0000021', 'veraltet'], ['b0000022', 'beantwortet']]);
    const texte = [...el.querySelectorAll('.ui-entscheidung__status')].map((p) => p.textContent?.trim());
    expect(texte).toEqual(['Diese Frage ist nicht mehr offen.', 'Deine Antwort: Klasse 6']);
    expect(el.querySelector('ui-entscheidung button[type="submit"]')).toBeNull();

    fertig(ANTWORT);
    await new Promise((weiter) => setTimeout(weiter));
    expect(c.messages().some((m) => m.sender === 'bot' && m.content === 'Gut, Klasse 6.')).toBe(true);
  });

  it('eine getippte Nachricht schließt offene Fragen ebenfalls', async () => {
    const { c, f } = make();
    const { fertig } = haengenderStrom(c);
    store(c).addBotMessage('Kurz nachgefragt:', false, [], undefined, { ui_bloecke: [frage('b0000023')] });
    f.detectChanges();
    void c.sendMessage('lieber etwas anderes');
    expect(status(c)).toEqual([['b0000023', 'veraltet']]);
    fertig(ANTWORT);
    await f.whenStable();
  });

  it('während eines Zugs nimmt die Shell keine Antwort an', () => {
    const { c } = make();
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const senden = vi.fn();
    (c as unknown as { _api: { stream: unknown } })._api.stream = senden;
    store(c).addBotMessage('F', false, [], undefined, { ui_bloecke: [frage('b0000024')] });
    const id = c.messages()[0].id;
    c.isLoading.set(true);
    (c as unknown as { modulAntworten: (a: object) => void })
      .modulAntworten({ nachrichtId: id, blockId: 'b0000024', daten: { gewaehlt: ['a'] }, text: 'Klasse 5' });
    expect(senden).not.toHaveBeenCalled();
    expect(status(c)).toEqual([['b0000024', 'offen']]);
    expect(warn).toHaveBeenCalled();
  });

  it('meldet dem Backend die Module seines Registers (Review U1-d1, Befund 8)', () => {
    const { c } = make();
    const env = (c as unknown as { _api: { buildEnvironment: () => Record<string, unknown> } })._api.buildEnvironment();
    expect(env['ui_module']).toEqual(expect.arrayContaining(['ui_entscheidung', 'ui_inhaltsrahmen']));
  });

  // Review U1-d1, Befund 7: lokal `beantwortet` nur, wenn der Server den Zug angenommen hat.
  function antworten(c: ChatShellComponent, blockId: string) {
    const nachrichtId = c.messages().find((m) => m.ui?.ui_bloecke?.some((b) => b.block_id === blockId))!.id;
    (c as unknown as { modulAntworten: (a: object) => void })
      .modulAntworten({ nachrichtId, blockId, daten: { gewaehlt: ['a'] }, text: 'Klasse 5' });
  }

  function api(c: ChatShellComponent) {
    return (c as unknown as { _api: { stream: unknown; post: unknown } })._api;
  }

  it('scheitert der Zug, bevor der Server ihn hat, ist die Frage wieder offen (Fehlerblase)', async () => {
    const { c, f } = make();
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    api(c).stream = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));
    api(c).post = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));
    store(c).addBotMessage('Alt', false, [], undefined, { ui_bloecke: [frage('b0000025')] });
    store(c).addBotMessage('F', false, [], undefined, { ui_bloecke: [frage('b0000026')] });

    antworten(c, 'b0000026');
    expect(status(c)).toEqual([['b0000025', 'veraltet'], ['b0000026', 'beantwortet']]);
    await vi.waitFor(() => expect(c.isLoading()).toBe(false));
    await f.whenStable();

    expect(c.messages().some((m) => m.sender === 'bot' && m.content === DE['error.generic'])).toBe(true);
    // Die ältere bleibt veraltet (jeder Zug der Person schließt sie); die beantwortete ist wieder offen.
    expect(status(c)).toEqual([['b0000025', 'veraltet'], ['b0000026', 'offen']]);
    const block = c.messages().flatMap((m) => m.ui?.ui_bloecke ?? []).find((b) => b.block_id === 'b0000026');
    expect(block?.antwort ?? null).toBeNull();
  });

  it('hatte der Server den Zug (connected), bleibt die Antwort stehen — auch wenn er danach scheitert', async () => {
    const { c, f } = make();
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    api(c).stream = vi.fn((_s: string, _m: string, onEvent: (e: unknown) => void) => {
      onEvent({ event: 'connected', data: { history: false } });
      return Promise.reject(Object.assign(new Error('kaputt'), { name: 'StreamServerError' }));
    });
    store(c).addBotMessage('F', false, [], undefined, { ui_bloecke: [frage('b0000027')] });

    antworten(c, 'b0000027');
    await vi.waitFor(() => expect(c.isLoading()).toBe(false));
    await f.whenStable();

    expect(status(c)).toEqual([['b0000027', 'beantwortet']]);
  });

  it('mit Antwort des Servers bleibt der Block beantwortet', async () => {
    const { c, f } = make();
    const { fertig } = haengenderStrom(c);
    store(c).addBotMessage('F', false, [], undefined, { ui_bloecke: [frage('b0000028')] });

    antworten(c, 'b0000028');
    fertig(ANTWORT);
    await vi.waitFor(() => expect(c.isLoading()).toBe(false));
    await f.whenStable();

    expect(status(c)).toEqual([['b0000028', 'beantwortet']]);
  });
});
