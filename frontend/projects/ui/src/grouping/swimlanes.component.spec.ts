import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { WloCard } from '../cards/card-types';
import { GroupingContext } from './result-grouping';
import { TopicPageView } from './message-types';
import { SwimlanesComponent } from './swimlanes.component';

/**
 * Charakterisierung des Swimlanes-Renderers — visueller Port des ALT
 * Themenseiten-Schwimmlinien-Blocks (`chat.component.html:97-131`, Pattern
 * M16). In ALT nur integrativ gedeckt; hier am DOM gepinnt: je Schwimmlinie
 * eine `result-group--topic`-Box (Heading „<heading|Inhalte> (Auszug)", Items
 * = cardUrl/cardTooltip/Icon) + ein `result-group--cta`-Absprung auf die
 * vollständige Themenseite (href = rohe topic_page_url wie ALT).
 */
function card(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}

const ctx: GroupingContext = { withBsid: (u) => u ?? '', externalLinkWarning: () => '' };

async function render(topicPage: TopicPageView): Promise<HTMLElement> {
  const fixture = TestBed.createComponent(SwimlanesComponent);
  fixture.componentRef.setInput('topicPage', topicPage);
  fixture.componentRef.setInput('ctx', ctx);
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('SwimlanesComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [SwimlanesComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('rendert je Schwimmlinie eine Topic-Box + den Themenseiten-CTA', async () => {
    const tp: TopicPageView = {
      variant_title: 'Bruchrechnung',
      topic_page_url: 'https://tp.test/full',
      swimlanes: [
        { heading: 'Videos', cards: [card({ node_type: 'content', node_id: 'v1', title: 'Video A', link: 'https://repo.test/v1' })] },
        { heading: '', cards: [card({ node_type: 'content', node_id: 'x1', title: 'X', link: 'https://repo.test/x1' })] },
      ],
    };
    const host = await render(tp);

    const boxes = host.querySelectorAll('.result-group--topic');
    expect(boxes.length).toBe(2);
    // Heading + Fallback „Inhalte"
    expect(boxes[0].querySelector('.result-group__heading')?.textContent).toContain('Videos (Auszug)');
    expect(boxes[1].querySelector('.result-group__heading')?.textContent).toContain('Inhalte (Auszug)');

    // Item: href = cardUrl (withBsid∘getCardPrimaryUrl), Titel, Icon
    const item = boxes[0].querySelector('a.result-group__item') as HTMLAnchorElement;
    expect(item.getAttribute('href')).toBe('https://repo.test/v1');
    expect(item.getAttribute('target')).toBe('_blank');
    expect(item.getAttribute('rel')).toBe('noopener noreferrer');
    expect(item.querySelector('.result-group__item-title')?.textContent?.trim()).toBe('Video A');
    expect(item.querySelector('.result-group__item-icon svg')).not.toBeNull();

    // CTA: rohe topic_page_url, Titel + Sub, title-Attribut
    const cta = host.querySelector('a.result-group--cta') as HTMLAnchorElement;
    expect(cta.getAttribute('href')).toBe('https://tp.test/full');
    expect(cta.getAttribute('target')).toBe('_blank');
    expect(cta.querySelector('strong')?.textContent?.trim()).toBe('Zur Themenseite „Bruchrechnung"');
    expect(cta.querySelector('.result-group__cta-sub')?.textContent?.trim()).toBe('Alle Inhalte auf der Themenseite ansehen');
    expect(cta.getAttribute('title')).toBe('Zur vollständigen Themenseite: Bruchrechnung');
  });

  it('leere swimlanes → kein Wrapper', async () => {
    const host = await render({ variant_title: 'X', topic_page_url: 'https://x', swimlanes: [] });
    expect(host.querySelector('.result-groups')).toBeNull();
  });

  it('ohne topic_page_url → Boxen ja, CTA nein', async () => {
    const host = await render({
      variant_title: 'Y',
      topic_page_url: '',
      swimlanes: [{ heading: 'H', cards: [card({ node_type: 'content', node_id: 'a', title: 'A', link: 'https://a' })] }],
    });
    expect(host.querySelector('.result-group--topic')).not.toBeNull();
    expect(host.querySelector('.result-group--cta')).toBeNull();
  });
});
