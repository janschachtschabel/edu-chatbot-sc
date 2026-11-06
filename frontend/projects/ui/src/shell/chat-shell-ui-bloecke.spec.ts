import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UiBlock } from '@boerdi/ui-module';

import { ChatMessage, UiInfo } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
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

describe('ChatShellComponent — Module rendern nach Sprachwechsel und neuen vertrauten Seiten neu (Review U1 gesamt, Befund 2)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  const PARTNER = 'https://partner.example/x';
  const BLOECKE: UiBlock[] = [
    { block_id: 'b0000051', modul: 'ui_inhaltsrahmen', version: 1, art: 'anzeigen', status: 'nur_anzeige',
      daten: { titel: 'Plan', art: 'lernpfad', markdown: `[Partner](${PARTNER})` }, text: '' },
    { block_id: 'b0000052', modul: 'ui_linkbox', version: 1, art: 'anzeigen', status: 'nur_anzeige',
      daten: { links: [{ titel: 'Partner', url: PARTNER }] }, text: '' },
    { block_id: 'b0000053', modul: 'ui_themenbaum', version: 1, art: 'anzeigen', status: 'nur_anzeige',
      daten: { titel: 'Mathe', wurzel_id: 'aaaa-1111', wurzel_url: PARTNER, wurzel_mehr: true,
               knoten: [{ id: 'bbbb-2222', titel: 'Algebra' }] }, text: '' },
  ];
  // Je Modul die Titel aller Vorkommen: dieselben Daten in zwei Antworten — das zweite Modul trifft
  // beim ersten Zeichnen den Markdown-Cache und liest dabei kein Signal (der eigentliche Fehlerfall).
  const alle = (el: HTMLElement, sel: string) => [...el.querySelectorAll(sel)].map((a) => a.getAttribute('title'));
  const titel = (el: HTMLElement) => {
    const rahmen = alle(el, 'ui-inhaltsrahmen .inline-document__body a');
    const linkbox = alle(el, 'ui-linkbox a');
    const baum = alle(el, 'ui-themenbaum .ui-themenbaum__hinweis-link');
    expect([rahmen.length, linkbox.length, baum.length]).toEqual([2, 2, 2]);
    expect(rahmen[1]).toBe(rahmen[0]);
    expect(linkbox[1]).toBe(linkbox[0]);
    expect(baum[1]).toBe(baum[0]);
    return { rahmen: rahmen[0], linkbox: linkbox[0], baum: baum[0] };
  };
  const zweiAntworten = (c: ChatShellComponent) => {
    store(c).addBotMessage('Antwort', false, [], undefined, { ui_bloecke: BLOECKE });
    store(c).addBotMessage('Noch einmal', false, [], undefined, { ui_bloecke: BLOECKE });
  };

  it('neue vertraute Seiten: Inhaltsrahmen, Linkbox und Themenbaum ohne Fremd-Warnung', () => {
    const { c, f, el } = make();
    zweiAntworten(c);
    f.detectChanges();
    expect(titel(el)).toEqual({
      rahmen: DE['link.external'], linkbox: expect.stringContaining('—'), baum: expect.any(String) });
    f.componentRef.setInput('trustedHosts', ['partner.example']);
    f.detectChanges();
    expect(titel(el)).toEqual({ rahmen: null, linkbox: 'Partner (Webseite)', baum: null });
  });

  it('Sprachwechsel: der Inhaltsrahmen rendert seinen Markdown in der neuen Sprache', () => {
    const { c, f, el } = make();
    zweiAntworten(c);
    f.detectChanges();
    expect(titel(el).rahmen).toBe(DE['link.external']);
    f.componentRef.setInput('translate', createTranslator(EN, DE));
    f.componentRef.setInput('locale', 'en');
    f.detectChanges();
    expect(titel(el).rahmen).toBe(EN['link.external']);
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

describe('ChatShellComponent — Tore prüfen, ob das Modul den Block zeigt (Review U1 gesamt, Befund 5)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ChatShellComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  // Eine Hauptversion, die dieses Widget nicht kennt: das Modul zeigt nur die Textfassung — also
  // müssen die bisherigen Boxen bleiben.
  const fremd = (modul: string, daten: Record<string, unknown>, text: string): UiBlock => ({
    block_id: `b00000${modul.length}9`, modul, version: 99, art: 'anzeigen', status: 'nur_anzeige', daten, text,
  });
  const KARTE = { node_id: 'c1', title: 'Sammlung Optik', node_type: 'collection', url: 'https://wirlernenonline.de/c1' };
  const LINKS = [{ title: 'WLO', url: 'https://wirlernenonline.de/' }];

  it('Trefferliste fremder Version: die bisherigen Trefferboxen bleiben', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [KARTE as never], undefined,
      { ui_bloecke: [fremd('ui_trefferliste', { karten: [KARTE] }, 'Textfassung Treffer')] });
    f.detectChanges();
    expect(el.querySelector('ui-trefferliste')).toBeNull();
    expect(el.querySelectorAll('boerdi-result-groups').length).toBe(1);
  });

  it('Linkbox fremder Version: die bisherige Webseiten-Box bleibt', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('Antwort', false, [], undefined,
      { ui_bloecke: [fremd('ui_linkbox', { links: [{ titel: 'WLO', url: LINKS[0].url }] }, 'Textfassung Links')] },
      null, undefined, LINKS);
    f.detectChanges();
    expect(el.querySelector('ui-linkbox')).toBeNull();
    expect(el.querySelectorAll('.result-group--web').length).toBe(1);
  });

  it('Inhaltsrahmen fremder Version: die Druckleiste des Lernpfads bleibt', () => {
    const { c, f, el } = make();
    store(c).addBotMessage('> **Lernpfad: Brüche**\n### Schritt 1', false, [], undefined,
      { ui_bloecke: [fremd('ui_inhaltsrahmen', { titel: 'L', art: 'lernpfad', markdown: 'x' }, 'Textfassung')] });
    f.detectChanges();
    expect(el.querySelector('ui-inhaltsrahmen')).toBeNull();
    expect(el.querySelector('.lp-print-bar')).not.toBeNull();
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

  it('Querschnitts-Review FE-2: für einen nicht mehr offenen Block geht keine Antwort hin', () => {
    const { c } = make();
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const senden = vi.fn();
    (c as unknown as { _api: { stream: unknown; post: unknown } })._api.stream = senden;
    (c as unknown as { _api: { stream: unknown; post: unknown } })._api.post = senden;
    store(c).addBotMessage('F', false, [], undefined, { ui_bloecke: [{ ...frage('b0000027'), status: 'veraltet' }] });
    const id = c.messages()[0].id;
    (c as unknown as { modulAntworten: (a: object) => void })
      .modulAntworten({ nachrichtId: id, blockId: 'b0000027', daten: { gewaehlt: ['a'] }, text: 'Klasse 5' });
    expect(senden).not.toHaveBeenCalled();
    expect(c.messages().some((m) => m.sender === 'user')).toBe(false);
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

  // Review U1 gesamt, Befund 7: die Frage aus dem gespeicherten Verlauf (Neuladen der Seite).
  describe('aus dem Verlauf wiederhergestellt', () => {
    async function ausVerlauf(c: ChatShellComponent, f: ComponentFixture<ChatShellComponent>, verlauf: unknown[]) {
      (c as unknown as { _api: { loadHistory: unknown } })._api.loadHistory = vi.fn(async () => verlauf);
      await (c as unknown as { _lifecycle: { _restoreHistory: () => Promise<boolean> } })._lifecycle._restoreHistory();
      f.detectChanges();
      await f.whenStable();
    }

    it('offen: lässt sich nach dem Neuladen beantworten (ui_antwort geht mit)', async () => {
      const { c, f, el } = make();
      const { stream, fertig } = haengenderStrom(c);
      await ausVerlauf(c, f, [
        { role: 'user', content: 'Ich suche Material' },
        { role: 'assistant', content: 'Kurz nachgefragt:', ui: { ui_bloecke: [frage('b0000041')] } },
      ]);
      const block = el.querySelector('ui-entscheidung')!;
      expect(block).not.toBeNull();
      (block.querySelector('input[value="a"]') as HTMLInputElement).click();
      f.detectChanges();
      (block.querySelector('button[type="submit"]') as HTMLButtonElement).click();
      f.detectChanges();
      expect((stream.mock.calls[0] as unknown[])[6]).toEqual({ block_id: 'b0000041', daten: { gewaehlt: ['a'] } });
      expect(status(c)).toEqual([['b0000041', 'beantwortet']]);
      fertig(ANTWORT);
      await vi.waitFor(() => expect(c.isLoading()).toBe(false));
    });

    it('beantwortet: zeigt die Antwort des Servers nur lesend', async () => {
      const { c, f, el } = make();
      const beantwortet = { ...frage('b0000042'), status: 'beantwortet' as const, antwort: { gewaehlt: ['b'] } };
      await ausVerlauf(c, f, [
        { role: 'assistant', content: 'Kurz nachgefragt:', ui: { ui_bloecke: [beantwortet] } },
        { role: 'user', content: 'Klasse 6' },
      ]);
      expect(el.querySelector('ui-entscheidung button[type="submit"]')).toBeNull();
      expect(el.querySelector('ui-entscheidung fieldset')?.hasAttribute('disabled')).toBe(true);
      expect((el.querySelector('ui-entscheidung input[value="b"]') as HTMLInputElement).checked).toBe(true);
      expect(el.querySelector('.ui-entscheidung__status')?.textContent?.trim()).toBe('Deine Antwort: Klasse 6');
    });
  });

  // Review U1 gesamt, Befund 1: das Backend schließt die offene Frage mit JEDEM Zug im Vordergrund
  // (`services/ui_antwort`) — nur Kontext-Ping und Tour-Tick sind Hintergrund (`domain/hintergrund_zug`).
  describe('Vordergrund-Züge ohne Eingabefeld schließen offene Fragen', () => {
    const SEITEN = {
      total_count: 12, skip_count: 0, page_size: 5, has_more: true, collection_id: 'c1', collection_title: 'Mathe',
    };
    const LEER = { session_id: 's', content: '', cards: [], quick_replies: [], ui: {} } as never;

    function mitFrage(blockId: string) {
      const { c, f } = make();
      api(c).post = vi.fn(() => Promise.resolve(LEER));
      store(c).addBotMessage('F', false, [], undefined, { ui_bloecke: [frage(blockId)] });
      return { c, f };
    }

    const kartenAktionen: [string, (c: ChatShellComponent) => Promise<void>][] = [
      ['browseCollection', (c) => c.browseCollection('c1', 'Mathe')],
      ['showContentText', (c) => c.showContentText('n1', 'Text')],
      ['generateLearningPath', (c) => c.generateLearningPath('c1', 'Mathe')],
    ];
    for (const [name, ausloesen] of kartenAktionen) {
      it(`${name} → veraltet`, async () => {
        const { c } = mitFrage('b0000031');
        const zug = ausloesen(c);
        expect(status(c)).toEqual([['b0000031', 'veraltet']]);
        await zug;
      });
    }

    it('„Inhalte anzeigen“ im Themenbaum (Karten-Aktion sammlung) → veraltet', async () => {
      const { c } = mitFrage('b0000032');
      (c as unknown as { modulTreffer: { sammlung: (id: string, t: string) => void } }).modulTreffer.sammlung('c1', 'Mathe');
      expect(status(c)).toEqual([['b0000032', 'veraltet']]);
      await vi.waitFor(() => expect(c.isLoading()).toBe(false));
    });

    it('„Weitere laden“ → veraltet', async () => {
      const { c } = mitFrage('b0000033');
      const id = store(c).addBotMessage('Treffer', false, [], undefined, {}, SEITEN);
      const zug = c.loadMoreCards(id);
      expect(status(c)).toEqual([['b0000033', 'veraltet']]);
      await zug;
    });

    it('Web-Tour starten → veraltet', async () => {
      const { c } = mitFrage('b0000034');
      const zug = c.startTour();
      expect(status(c)).toEqual([['b0000034', 'veraltet']]);
      await zug;
    });

    it('Tour-Tick und Kontext-Ping (Hintergrund) → bleibt offen', async () => {
      const { c } = mitFrage('b0000035');
      const intern = c as unknown as {
        _tour: { sendTourTick: () => Promise<void> };
        _contextGreeting: { sendContextPing: () => Promise<boolean> };
      };
      await intern._tour.sendTourTick();
      await intern._contextGreeting.sendContextPing();
      expect(api(c).post).toHaveBeenCalledTimes(2);
      expect(status(c)).toEqual([['b0000035', 'offen']]);
    });

    it('ein laufender Zweig endet mit dem Widget (Abbruch beim Entfernen, Review U1 gesamt)', async () => {
      const { c } = make();
      let signal: AbortSignal | undefined;
      (c as unknown as { _api: { themenbaumZweig: unknown } })._api.themenbaumZweig =
        vi.fn((_s: string, _n: string, sig?: AbortSignal) => { signal = sig; return new Promise(() => undefined); });
      void (c as unknown as { modulTreffer: { zweig: (id: string) => Promise<unknown> } }).modulTreffer.zweig('aaaa-1111');
      expect(signal?.aborted).toBe(false);
      c.ngOnDestroy();
      expect(signal?.aborted).toBe(true);
    });

    it('Unterthemen nachladen (zweig) ist kein Zug → bleibt offen', async () => {
      const { c } = mitFrage('b0000036');
      const zweig = vi.fn(() => Promise.resolve({ knoten: [] }));
      (c as unknown as { _api: { themenbaumZweig: unknown } })._api.themenbaumZweig = zweig;
      await (c as unknown as { modulTreffer: { zweig: (id: string) => Promise<unknown> } }).modulTreffer.zweig('aaaa-1111');
      expect(zweig).toHaveBeenCalled();
      expect(status(c)).toEqual([['b0000036', 'offen']]);
    });
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
