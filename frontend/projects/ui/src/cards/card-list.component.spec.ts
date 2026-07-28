import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { WloCard } from './card-types';
import { CardListComponent } from './card-list.component';
import { ChatMessage } from '../grouping/message-types';

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

const CTX = {
  withBsid: (u: string | null | undefined) => (u || '') + '?bsid=x',
  externalLinkWarning: () => '',
};

function render(message: ChatMessage, isLoading = false): {
  f: ComponentFixture<CardListComponent>; el: HTMLElement; c: CardListComponent;
} {
  const f = TestBed.createComponent(CardListComponent);
  f.componentRef.setInput('message', message);
  f.componentRef.setInput('ctx', CTX);
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

    const btns = el.querySelectorAll('.card-actions .card-btn');
    expect(btns.length).toBe(2);
    (btns[0] as HTMLButtonElement).click();
    (btns[1] as HTMLButtonElement).click();
    expect(browse).toEqual([{ nodeId: 'n1', title: 'Mathe' }]);
    expect(lp).toEqual([{ nodeId: 'n1', title: 'Mathe' }]);
  });

  it('Nicht-Sammlung ODER fehlende node_id: keine Aktionsleiste', () => {
    expect(render(msg({ cards: [card({ node_type: 'material', node_id: 'n1' })] }))
      .el.querySelector('.card-actions')).toBeNull();
    expect(render(msg({ cards: [card({ node_type: 'collection' })] }))
      .el.querySelector('.card-actions')).toBeNull();
  });

  it('Buttons während eines laufenden Turns gesperrt', () => {
    const { el } = render(msg({ cards: [card({ node_type: 'collection', node_id: 'n1' })] }), true);
    const btns = el.querySelectorAll<HTMLButtonElement>('.card-actions .card-btn');
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
    const link = el.querySelector<HTMLAnchorElement>('.card-btn--tertiary')!;
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
