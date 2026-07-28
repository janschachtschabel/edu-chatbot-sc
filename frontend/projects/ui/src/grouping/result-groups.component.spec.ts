import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { WloCard } from '../cards/card-types';
import { ChatMessage, QueryMetaEntry } from './message-types';
import { ResultGroupsComponent, ResultGroupsContext } from './result-groups.component';

/**
 * Charakterisierung des ResultGroups-Renderers — visueller Port des ALT
 * Inline-Result-Grouping-Blocks (`chat.component.html:133-236`). In ALT nur
 * über die große chat.component.spec.ts integrativ gedeckt; hier vor dem
 * Konsum durch die Chat-Shell (8-4) am gerenderten DOM gepinnt: 5 Boxen
 * (Themenseiten/Sammlungen/Materialien/Webseiten/Search-CTA), Box-Sichtbarkeit,
 * Item-Attribute (href = cardUrl/webLinkUrl, title, Icon), CTA-Titel/-Target,
 * Leer-/Tour-Unterdrückung. Verhalten aus ALT-Template + 8-2g-Utils abgeleitet.
 */
function msg(fields: Partial<ChatMessage>): ChatMessage {
  return fields as unknown as ChatMessage;
}
function card(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}
function meta(fields: Partial<QueryMetaEntry>): QueryMetaEntry {
  return fields as unknown as QueryMetaEntry;
}

/** Trusted-Host-Test-Kontext: withBsid identisch, keine Extern-Warnung,
 *  nichts host-trusted (→ Such-CTA öffnet in neuem Tab). */
const ctx: ResultGroupsContext = {
  withBsid: (u) => u ?? '',
  externalLinkWarning: () => '',
  isTrustedHost: () => false,
};
/** Wie `ctx`, aber jeder Host gilt als trusted (→ Such-CTA öffnet `_self`). */
const ctxTrusted: ResultGroupsContext = { ...ctx, isTrustedHost: () => true };

async function render(
  message: ChatMessage,
  context: ResultGroupsContext = ctx,
): Promise<HTMLElement> {
  const fixture = TestBed.createComponent(ResultGroupsComponent);
  fixture.componentRef.setInput('message', message);
  fixture.componentRef.setInput('ctx', context);
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

/** Vollbesetzte Message: je 1 Themenseite/Sammlung/Material + 1 Web-Link +
 *  Such-Meta — alle 5 Boxen sichtbar. */
function fullMessage(): ChatMessage {
  return msg({
    cards: [
      card({ node_type: 'topic_page', node_id: 't1', title: 'TP Eins', topic_pages: [{ url: 'https://tp.test/1', target_group: '', label: '', variant_id: '' }] }),
      card({ node_type: 'collection', node_id: 'c1', title: 'Sammlung Eins', link: 'https://repo.test/c1' }),
      card({ node_type: 'content', node_id: 'm1', title: 'Material Eins', link: 'https://repo.test/m1' }),
    ],
    webLinks: [{ title: 'Web Eins', url: 'https://web.test/a' }],
    queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://search.test/q', search_term: 'Klima' })],
  });
}

describe('ResultGroupsComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ResultGroupsComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('rendert alle 5 Boxen mit Heading, Items und aufgelösten Links', async () => {
    const host = await render(fullMessage());

    // Wrapper vorhanden
    expect(host.querySelector('.result-groups')).not.toBeNull();

    // Themenseiten-Box
    const topic = host.querySelector('.result-group--topic')!;
    expect(topic.querySelector('.result-group__heading')?.textContent).toContain('Themenseiten');
    const topicItem = topic.querySelector('a.result-group__item') as HTMLAnchorElement;
    expect(topicItem.getAttribute('href')).toBe('https://tp.test/1');
    expect(topicItem.getAttribute('target')).toBe('_blank');
    expect(topicItem.getAttribute('rel')).toBe('noopener noreferrer');
    expect(topicItem.querySelector('.result-group__item-title')?.textContent?.trim()).toBe('TP Eins');
    expect(topicItem.querySelector('.result-group__item-icon svg')).not.toBeNull();

    // Sammlungen-Box
    const coll = host.querySelector('.result-group--collection')!;
    expect(coll.querySelector('.result-group__heading')?.textContent).toContain('Sammlungen');
    expect((coll.querySelector('a.result-group__item') as HTMLAnchorElement).getAttribute('href'))
      .toBe('https://repo.test/c1');

    // Materialien-Box
    const mat = host.querySelector('.result-group--material')!;
    expect(mat.querySelector('.result-group__heading')?.textContent).toContain('Ausgewählte Materialien');
    expect((mat.querySelector('a.result-group__item') as HTMLAnchorElement).getAttribute('href'))
      .toBe('https://repo.test/m1');

    // Webseiten-Inhalte-Box: href = webLinkUrl, title = itemTooltip(„… (Webseite)")
    const web = host.querySelector('.result-group--web')!;
    expect(web.querySelector('.result-group__heading')?.textContent).toContain('Webseiten-Inhalte');
    const webItem = web.querySelector('a.result-group__item') as HTMLAnchorElement;
    expect(webItem.getAttribute('href')).toBe('https://web.test/a');
    expect(webItem.getAttribute('title')).toBe('Web Eins (Webseite)');
    expect(webItem.querySelector('.result-group__item-title')?.textContent?.trim()).toBe('Web Eins');

    // Search-CTA
    const cta = host.querySelector('a.result-group--cta') as HTMLAnchorElement;
    expect(cta.getAttribute('href')).toBe('https://search.test/q');
  });

  it('rendert nichts (kein Wrapper), wenn die Message keine Gruppen hat', async () => {
    const host = await render(msg({ content: 'Nur Text.' }));
    expect(host.querySelector('.result-groups')).toBeNull();
    expect(host.querySelector('.result-group')).toBeNull();
  });

  it('blendet leere Boxen aus — nur Materialien vorhanden', async () => {
    const host = await render(msg({
      cards: [card({ node_type: 'content', node_id: 'm1', title: 'Nur Material', link: 'https://repo.test/m1' })],
    }));
    expect(host.querySelector('.result-group--material')).not.toBeNull();
    expect(host.querySelector('.result-group--topic')).toBeNull();
    expect(host.querySelector('.result-group--collection')).toBeNull();
    expect(host.querySelector('.result-group--web')).toBeNull();
    expect(host.querySelector('.result-group--cta')).toBeNull();
  });

  it('Search-CTA: Titel mit Suchbegriff', async () => {
    const host = await render(msg({
      queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s.test', search_term: 'Mathe' })],
    }));
    const cta = host.querySelector('.result-group--cta')!;
    expect(cta.querySelector('strong')?.textContent?.trim()).toBe('Treffer zur Suche „Mathe"');
    expect(cta.querySelector('.result-group__cta-sub')?.textContent?.trim()).toBe('Alle passenden Materialien anzeigen');
  });

  it('Search-CTA: Titel ohne Suchbegriff', async () => {
    const host = await render(msg({
      queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://s.test', search_term: '' })],
    }));
    expect(host.querySelector('.result-group--cta strong')?.textContent?.trim())
      .toBe('Alle Treffer in der Suche');
  });

  it('Search-CTA target: extern+untrusted → _blank, trusted → _self', async () => {
    const m = msg({
      queryMetas: [meta({ tool_name: 'search_wlo_content', search_url: 'https://external.test/q', search_term: 'x' })],
    });
    const blankHost = await render(m, ctx);
    expect((blankHost.querySelector('a.result-group--cta') as HTMLAnchorElement).getAttribute('target')).toBe('_blank');

    const selfHost = await render(m, ctxTrusted);
    expect((selfHost.querySelector('a.result-group--cta') as HTMLAnchorElement).getAttribute('target')).toBe('_self');
  });

  it('Tour-Antwort unterdrückt die gesamte Gruppen-Anzeige', async () => {
    const host = await render(msg({
      debug: { pattern: 'TOUR:step1' },
      cards: [card({ node_type: 'topic_page', node_id: 't1', title: 'TP', topic_pages: [{ url: 'https://tp.test/1', target_group: '', label: '', variant_id: '' }] })],
    }));
    expect(host.querySelector('.result-groups')).toBeNull();
  });
});
