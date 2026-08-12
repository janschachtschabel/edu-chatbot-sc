import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { WloCard } from './card-types';
import { CardListComponent } from './card-list.component';
import { ChatMessage, QueryMetaEntry } from '../grouping/message-types';
import { ResultGroupsContext } from '../grouping/result-grouping';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';

/**
 * Flache Card-Liste (8-2i) — visueller Port des ALT-Blocks
 * chat.component.html:240-378: Tile-Grid + `.card-actions` (Inhalte / Lernpfad /
 * Themenseite samt Varianten-Dropdown) + Pagination-Leiste. Gepinnt werden die
 * ALT-Gates (welche Karte welche Buttons bekommt, wann welcher Mehr-Button
 * erscheint), das Sichtbarkeits-Fenster über `visibleCardCount` und die
 * Aktions-Outputs. Die Karte selbst ist in `wlo-card-tile.component.spec`
 * gepinnt.
 */

function card(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}

function msg(fields: Partial<ChatMessage>): ChatMessage {
  return { id: 'm1', sender: 'bot', content: '', timestamp: new Date(), ...fields } as ChatMessage;
}

/** Wie in `result-grouping.spec` — der Vertrag hat mehr Pflichtfelder, als ein
 *  einzelner Testfall braucht; die Cast-Attrappe hält den Fall lesbar. */
function meta(fields: Partial<QueryMetaEntry>): QueryMetaEntry {
  return fields as unknown as QueryMetaEntry;
}

const CTX: ResultGroupsContext = {
  withBsid: (u: string | null | undefined) => (u || '') + '?bsid=x',
  externalLinkWarning: () => '',
  isTrustedHost: () => false,
  t: createTranslator(DE, DE),
};

function render(message: ChatMessage, isLoading = false, ctx: ResultGroupsContext = CTX): {
  f: ComponentFixture<CardListComponent>; el: HTMLElement; c: CardListComponent;
} {
  const f = TestBed.createComponent(CardListComponent);
  f.componentRef.setInput('message', message);
  f.componentRef.setInput('ctx', ctx);
  f.componentRef.setInput('isLoading', isLoading);
  f.detectChanges();
  return { f, el: f.nativeElement as HTMLElement, c: f.componentInstance };
}

describe('CardListComponent — Grid + Sichtbarkeits-Fenster', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CardListComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('rendert nur die ersten `visibleCardCount` Karten (Default 5)', () => {
    const cards = Array.from({ length: 8 }, (_, i) => card({ title: 'K' + i, node_type: 'material' }));
    const { el } = render(msg({ cards }));
    expect(el.querySelectorAll('boerdi-wlo-card-tile').length).toBe(5);

    const { el: el2 } = render(msg({ cards, visibleCardCount: 7 }));
    expect(el2.querySelectorAll('boerdi-wlo-card-tile').length).toBe(7);
  });

  it('ohne Karten: kein Grid, keine Pagination', () => {
    const { el } = render(msg({ cards: [] }));
    expect(el.querySelector('.cards-list')).toBeNull();
    expect(el.querySelector('.pagination-bar')).toBeNull();
  });

  /** Knopf- und Zähler-Texte kommen über `ctx.t`; der Zähler bringt zwei
   *  Platzhalter mit, deren Reihenfolge je Sprache anders sein darf. */
  it('nimmt Knopf- und Zählertexte aus `ctx.t` (C1-b2)', () => {
    const cards = Array.from({ length: 8 }, (_, i) => card({ title: 'K' + i, node_type: 'material' }));
    const { el } = render(msg({ cards }));
    expect(el.querySelector('.pagination-info')?.textContent?.trim()).toBe('5 von 8 Ergebnissen');
    expect(el.querySelector('.btn-load-more')?.textContent?.trim()).toBe('Mehr anzeigen');

    const EN: Record<string, string> = {
      'cards.pagination.count': 'showing {visible} of {total}',
      'cards.pagination.showMore': 'Show more',
    };
    const { el: en } = render(msg({ cards }), false, {
      ...CTX,
      t: (key, params) => (EN[key] ?? key).replace(/\{(\w+)\}/g, (m, n) => String(params?.[n] ?? m)),
    });
    expect(en.querySelector('.pagination-info')?.textContent?.trim()).toBe('showing 5 of 8');
    expect(en.querySelector('.btn-load-more')?.textContent?.trim()).toBe('Show more');
  });
});

describe('CardListComponent — Material-Knöpfe', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CardListComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  // Nutzer-Vorgabe 2026-07-31: die Webkomponente soll Material-3-Elemente
  // nutzen. Für die Aktionsleiste heißt das ALLE Bedienelemente — eine halb
  // umgestellte Leiste (Material-Pille neben handgezeichnetem Rechteck) wäre
  // schlechter als die alte. `mat-mdc-button-base` setzt Material selbst an
  // jeden seiner Knöpfe; es ist hier die prüfbare Form der Anforderung.
  it('jedes Bedienelement der Sammlungs-Leiste ist ein Material-Knopf', () => {
    const { el } = render(msg({
      cards: [card({
        node_type: 'collection', node_id: 'c1', title: 'Sammlung',
        topic_pages: [
          { url: 'https://a.test', target_group: 'a', label: 'Variante A', variant_id: 'v1' },
          { url: 'https://b.test', target_group: 'b', label: 'Variante B', variant_id: 'v2' },
        ],
      })],
    }));

    const leiste = el.querySelector('.card-actions')!;
    const bedienelemente = Array.from(leiste.querySelectorAll('button, a'));
    expect(bedienelemente.length).toBe(4);   // Inhalte, Lernpfad, Themenseite, Varianten-Toggle
    for (const b of bedienelemente) {
      expect(b.classList.contains('mat-mdc-button-base'), `kein Material-Knopf: ${b.textContent?.trim()}`)
        .toBe(true);
    }
  });

  it('auch der Volltext-Knopf des Einzelinhalts ist ein Material-Knopf', () => {
    const { el } = render(msg({
      cards: [card({ node_type: 'content', node_id: 'n1', title: 'Material' })],
    }));
    const knopf = el.querySelector('.card-actions button')!;
    expect(knopf.classList.contains('mat-mdc-button-base')).toBe(true);
  });
});

describe('CardListComponent — .card-actions (nur Sammlungen)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CardListComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('Sammlung mit node_id: Inhalte- + Lernpfad-Button, Outputs tragen id+Titel', () => {
    const { el, c } = render(msg({ cards: [card({ node_type: 'collection', node_id: 'n1', title: 'Mathe' })] }));
    const browse: unknown[] = [];
    const lp: unknown[] = [];
    c.browse.subscribe((e: unknown) => browse.push(e));
    c.learningPath.subscribe((e: unknown) => lp.push(e));

    // `button` statt der früheren `.card-btn`-Klasse: seit der M3-Umstellung
    // tragen diese Knöpfe `matButton`, die Handklasse gibt es nicht mehr.
    const btns = el.querySelectorAll('.card-actions button');
    expect(btns.length).toBe(2);
    (btns[0] as HTMLButtonElement).click();
    (btns[1] as HTMLButtonElement).click();
    expect(browse).toEqual([{ nodeId: 'n1', title: 'Mathe' }]);
    expect(lp).toEqual([{ nodeId: 'n1', title: 'Mathe' }]);
  });

  it('Einzelinhalt mit node_id: Volltext-Button, Output trägt id+Titel (M17)', () => {
    // Bewusst geändert gegenüber 8-2i: dort bekam eine Nicht-Sammlung GAR
    // keine Aktionsleiste. Seit M17 hat der Einzelinhalt genau eine Aktion —
    // den Volltext holen; ohne sie wäre die Direkt-Aktion nicht auslösbar.
    const { el, c } = render(msg({ cards: [card({ node_type: 'material', node_id: 'n1', title: 'Arbeitsblatt' })] }));
    const seen: unknown[] = [];
    c.showContentText.subscribe((e: unknown) => seen.push(e));

    // Seit der M3-Umstellung trägt dieser Knopf `matButton`, nicht mehr die
    // handgeschriebene `.card-btn`-Klasse — deshalb über das Element gesucht.
    const btns = el.querySelectorAll('.card-actions button');
    expect(btns.length).toBe(1);
    (btns[0] as HTMLButtonElement).click();
    expect(seen).toEqual([{ nodeId: 'n1', title: 'Arbeitsblatt' }]);
  });

  it('fehlende node_id: keine Aktionsleiste (weder Sammlung noch Inhalt)', () => {
    expect(render(msg({ cards: [card({ node_type: 'collection' })] }))
      .el.querySelector('.card-actions')).toBeNull();
    expect(render(msg({ cards: [card({ node_type: 'material' })] }))
      .el.querySelector('.card-actions')).toBeNull();
  });

  it('Buttons während eines laufenden Turns gesperrt', () => {
    const { el } = render(msg({ cards: [card({ node_type: 'collection', node_id: 'n1' })] }), true);
    const btns = el.querySelectorAll<HTMLButtonElement>('.card-actions button');
    expect(btns.length).toBeGreaterThan(0);
    expect(Array.from(btns).every(b => b.disabled)).toBe(true);
  });
});

describe('CardListComponent — Themenseiten-Button + Varianten-Dropdown', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CardListComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  const withTopics = (n: number) => msg({
    cards: [card({
      node_type: 'collection', node_id: 'n1', title: 'S',
      topic_pages: Array.from({ length: n }, (_, i) => ({
        url: 'https://tp.test/' + i, label: 'Variante ' + i, target_group: 'g', variant_id: 'v' + i,
      })),
    })],
  });

  it('eine Themenseite: Link mit bsid, kein Dropdown-Toggle', () => {
    const { el } = render(withTopics(1));
    // Der Themenseiten-Knopf ist ein `<a matButton>` — der einzige Anker in
    // der Aktionsleiste (früher `.card-btn--tertiary`).
    const link = el.querySelector<HTMLAnchorElement>('.card-actions a')!;
    expect(link.getAttribute('href')).toBe('https://tp.test/0?bsid=x');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(el.querySelector('.tp-toggle')).toBeNull();
  });

  it('mehrere Themenseiten: Toggle öffnet/schließt die Varianten-Liste', () => {
    const { f, el } = render(withTopics(3));
    const toggle = el.querySelector<HTMLButtonElement>('.tp-toggle')!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(el.querySelector('.tp-dropdown')).toBeNull();

    toggle.click();
    f.detectChanges();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(el.querySelectorAll('.tp-dropdown-item').length).toBe(3);

    toggle.click();
    f.detectChanges();
    expect(el.querySelector('.tp-dropdown')).toBeNull();
  });

  it('Klick irgendwo im Dokument schließt das Dropdown wieder', () => {
    const { f, el } = render(withTopics(2));
    el.querySelector<HTMLButtonElement>('.tp-toggle')!.click();
    f.detectChanges();
    expect(el.querySelector('.tp-dropdown')).not.toBeNull();

    document.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    f.detectChanges();
    expect(el.querySelector('.tp-dropdown')).toBeNull();
  });

  it('Escape schließt das Dropdown und gibt den Fokus an den Toggle (8-6, APG)', () => {
    // Ohne Escape-Pfad wäre das Dropdown nur mit der Maus schließbar (ALTs
    // `document:click`) — Tastatur-Nutzer kämen nicht mehr heraus.
    const { f, el } = render(withTopics(2));
    const toggle = el.querySelector<HTMLButtonElement>('.tp-toggle')!;
    toggle.click();
    f.detectChanges();
    expect(el.querySelector('.tp-dropdown')).not.toBeNull();

    el.querySelector('.tp-dropdown-wrap')!
      .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    f.detectChanges();
    expect(el.querySelector('.tp-dropdown')).toBeNull();
    expect(document.activeElement).toBe(toggle);
  });

  it('Escape im Dropdown erreicht die Widget-Hülle NICHT (sonst klappt das Panel zu)', () => {
    // Die Hülle schließt bei Escape das ganze Chat-Panel
    // (`@HostListener('keydown.escape')`). Ohne `stopPropagation` im Dropdown
    // würde ein Escape dort beides schließen — hier stellvertretend über einen
    // Listener am document geprüft.
    const { f, el } = render(withTopics(2));
    el.querySelector<HTMLButtonElement>('.tp-toggle')!.click();
    f.detectChanges();

    let reachedOuter = false;
    const outer = () => { reachedOuter = true; };
    document.addEventListener('keydown', outer);
    try {
      el.querySelector('.tp-dropdown-wrap')!
        .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    } finally {
      document.removeEventListener('keydown', outer);
    }
    expect(reachedOuter).toBe(false);
  });

  it('Toggle kündigt das Popup an (aria-haspopup)', () => {
    const { el } = render(withTopics(2));
    expect(el.querySelector('.tp-toggle')!.getAttribute('aria-haspopup')).toBe('true');
  });
});

describe('CardListComponent — Pagination', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CardListComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  const cards = (n: number) => Array.from({ length: n }, (_, i) => card({ title: 'K' + i }));

  it('eine einzelne Karte bekommt keine Leiste', () => {
    expect(render(msg({ cards: cards(1) })).el.querySelector('.pagination-bar')).toBeNull();
  });

  it('mehr Karten als sichtbar: Zähler + „Mehr anzeigen" (client-seitig)', () => {
    const { el, c } = render(msg({ cards: cards(9) }));
    expect(el.querySelector('.pagination-info')?.textContent).toContain('5 von 9');

    const seen: string[] = [];
    c.showMore.subscribe((id: string) => seen.push(id));
    el.querySelector<HTMLButtonElement>('.btn-load-more')!.click();
    expect(seen).toEqual(['m1']);
  });

  it('alle geladenen sichtbar + Backend hat mehr: „Weitere laden" (server-seitig)', () => {
    const message = msg({
      cards: cards(5),
      pagination: {
        total_count: 20, skip_count: 0, page_size: 5, has_more: true,
        collection_id: 'c1', collection_title: 'T',
      },
    });
    const { el, c } = render(message);
    const seen: string[] = [];
    c.loadMore.subscribe((id: string) => seen.push(id));

    const btn = el.querySelector<HTMLButtonElement>('.btn-load-more')!;
    expect(btn.textContent).toContain('Weitere laden');
    btn.click();
    expect(seen).toEqual(['m1']);
  });

  it('während eines Turns: „Weitere laden" gesperrt und beschriftet als Ladend', () => {
    const message = msg({
      cards: cards(5),
      pagination: {
        total_count: 20, skip_count: 0, page_size: 5, has_more: true,
        collection_id: 'c1', collection_title: 'T',
      },
    });
    const { el } = render(message, true);
    const btn = el.querySelector<HTMLButtonElement>('.btn-load-more')!;
    expect(btn.disabled).toBe(true);
    expect(btn.textContent).toContain('Lade');
  });

  it('kein has_more/collection_id → kein Server-Button', () => {
    const message = msg({
      cards: cards(5),
      pagination: {
        total_count: 5, skip_count: 0, page_size: 5, has_more: false,
        collection_id: 'c1', collection_title: 'T',
      },
    });
    expect(render(message).el.querySelector('.btn-load-more')).toBeNull();
  });
});

/**
 * U6b: Der Absprung in die WLO-Suche (mit den Filtern des Turns) hing bis
 * 2026-08-09 allein an der Gruppen-Box. Seit U2b zeigt der große Modus statt
 * der Box das Kachelraster — und verlor damit genau den Knopf, der aus dem
 * Chat in die vollständige, gefilterte Trefferliste führt. Er gehört an BEIDE
 * Darstellungen; welche gerade läuft, ist eine Anzeige-Entscheidung und darf
 * keine Funktion wegnehmen.
 */
describe('CardListComponent — Such-Absprung (U6b)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CardListComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('zeigt den Such-Absprung unter dem Raster, mit Suchbegriff im Text', () => {
    const message = msg({
      cards: [card({ title: 'K', node_type: 'material' })],
      queryMetas: [meta({
        tool_name: 'search_wlo_content',
        search_url: 'https://such.test/q',
        search_term: 'Bruchrechnung',
      })],
    });
    const cta = render(message).el.querySelector<HTMLAnchorElement>('a.result-group--cta');
    expect(cta).not.toBeNull();
    expect(cta!.getAttribute('href')).toBe('https://such.test/q?bsid=x');
    expect(cta!.textContent).toContain('Bruchrechnung');
  });

  it('ohne Such-URL kein Absprung — ein toter Knopf wäre schlimmer als keiner', () => {
    const message = msg({ cards: [card({ title: 'K', node_type: 'material' })] });
    expect(render(message).el.querySelector('a.result-group--cta')).toBeNull();
  });
});
