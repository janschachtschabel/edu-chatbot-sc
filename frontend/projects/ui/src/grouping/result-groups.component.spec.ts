import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { WloCard } from '../cards/card-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';

import { ChatMessage, QueryMetaEntry } from './message-types';
import { ResultGroupsComponent } from './result-groups.component';
import { ResultGroupsContext } from './result-grouping';

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
  t: createTranslator(DE, DE),
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

  /** Die deutschen Überschriften unten belegen nur den Wortlaut — sie stünden
   *  auch fest verdrahtet da. Erst der Wechsel zeigt, dass sie über `ctx.t`
   *  laufen; die Materialien-Zeile prüft zusätzlich den Platzhalter. */
  it('nimmt Box-Überschriften und Knopf-Beschriftung aus `ctx.t` (C1-b2)', async () => {
    const EN: Record<string, string> = {
      'groups.topics': 'Topic pages',
      'groups.materials': 'Selected materials',
      'groups.showContent': 'Show content of {title} in the chat',
    };
    const host = await render(fullMessage(), {
      ...ctx,
      t: (key, params) => (EN[key] ?? key).replace(/\{(\w+)\}/g, (m, n) => String(params?.[n] ?? m)),
    });

    expect(host.querySelector('.result-group--topic .result-group__heading')?.textContent)
      .toContain('Topic pages');
    expect(host.querySelector('.result-group--material .result-group__heading')?.textContent)
      .toContain('Selected materials');
    expect(host.querySelector('.result-group__item-btn')?.getAttribute('aria-label'))
      .toBe('Show content of Material Eins in the chat');
  });

  /** Der Live-Befund „Optik" (15.08.2026): von vier Optik-Sammlungen zeigte
   *  der Chat nur die zwei OHNE Themenseite. Die anderen tragen
   *  `node_type: 'topic_page'` und fielen aus jeder Sammlungs-Prüfung. Sie
   *  stehen jetzt in beiden Kästen — mit dem Ziel, das zum Kasten passt. */
  it('zeigt eine Sammlung MIT Themenseite in beiden Boxen, je mit eigenem Ziel', async () => {
    const host = await render(msg({
      cards: [
        card({
          node_type: 'topic_page', node_id: 'opt1', title: 'Optik',
          link: 'https://wirlernenonline.de/themenseite/optik',
          collection_link: 'https://repo.test/edu-sharing/components/collections?id=opt1',
        }),
      ],
    }));

    const themenseite = host.querySelector(
      '.result-group--topic a.result-group__item',
    ) as HTMLAnchorElement;
    const sammlung = host.querySelector(
      '.result-group--collection a.result-group__item',
    ) as HTMLAnchorElement;

    expect(themenseite.querySelector('.result-group__item-title')?.textContent?.trim())
      .toBe('Optik');
    expect(sammlung.querySelector('.result-group__item-title')?.textContent?.trim())
      .toBe('Optik');
    expect(themenseite.getAttribute('href')).toBe('https://wirlernenonline.de/themenseite/optik');
    expect(sammlung.getAttribute('href'))
      .toBe('https://repo.test/edu-sharing/components/collections?id=opt1');
    // Im Sammlungen-Kasten ist sie als Sammlung beschriftet, nicht als
    // Themenseite — sonst stünde dieselbe Zeile zweimal gleich da.
    expect(sammlung.getAttribute('title')).toBe('Optik (Sammlung)');
    expect(themenseite.getAttribute('title')).toBe('Optik (Themenseite)');
    // Zwei Verweise, gleicher sichtbarer Text, verschiedene Ziele: ohne
    // `aria-label` hiessen beide vorgelesen nur „Optik".
    expect(sammlung.getAttribute('aria-label')).toBe('Optik (Sammlung)');
    expect(themenseite.getAttribute('aria-label')).toBe('Optik (Themenseite)');
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

  it('Materialien-Zeile trägt den Volltext-Knopf; Klick meldet id+Titel (M17)', async () => {
    // Diese Box ist die DEFAULT-Oberfläche (inline-result-grouping="true").
    // Säße der Knopf nur im Flach-Grid, wäre die Volltext-Aktion im
    // Normalbetrieb gar nicht auslösbar.
    const fixture = TestBed.createComponent(ResultGroupsComponent);
    fixture.componentRef.setInput('message', msg({
      cards: [card({ node_type: 'content', node_id: 'm1', title: 'Arbeitsblatt Brüche', link: 'https://repo.test/m1' })],
    }));
    fixture.componentRef.setInput('ctx', ctx);
    fixture.detectChanges();
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    const seen: unknown[] = [];
    fixture.componentInstance.showContentText.subscribe((e: unknown) => seen.push(e));

    const btn = host.querySelector('.result-group--material .result-group__item-btn') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    // Icon-Knopf ohne sichtbaren Text → sein Name kommt aus dem aria-label,
    // und er muss das Material benennen (eine Box hat mehrere Zeilen).
    expect(btn.getAttribute('aria-label')).toContain('Arbeitsblatt Brüche');
    btn.click();
    expect(seen).toEqual([{ nodeId: 'm1', title: 'Arbeitsblatt Brüche' }]);
  });

  it('Volltext-Knopf trägt KEIN Inhaltstyp-Symbol, sondern ein Handlungs-Symbol', async () => {
    // Nutzer-Rückmeldung 2026-07-31: die Zeile wirkte, als stünde der
    // Inhaltstyp zweimal drin — vorn und hinten. Vorn gehört der Typ, hinten
    // die Handlung. Es reicht NICHT, dass die Glyphen verschieden sind
    // (`article` neben `description` sieht gleich aus): das Knopf-Symbol darf
    // aus der Typ-Menge gar nicht stammen.
    // „Arbeitsblatt" ist der Typ, dessen Symbol mit dem alten Knopf-Symbol
    // kollidierte (beides `article`). Verglichen werden zwei GERENDERTE
    // Symbole — die Sanitizer-Pipe normalisiert das SVG, ein Vergleich gegen
    // die Roh-Konstante ginge daran vorbei.
    const host = await render(msg({
      cards: [card({
        node_type: 'content', node_id: 'm1', title: 'Ein Arbeitsblatt',
        link: 'https://repo.test/m1', learning_resource_types: ['Arbeitsblatt'],
      })],
    }));
    const typIcon = host.querySelector('.result-group--material .result-group__item-icon')!.innerHTML;
    const knopfIcon = host.querySelector('.result-group--material .result-group__item-btn .bb-icon')!.innerHTML;
    expect(knopfIcon.trim()).not.toBe('');
    expect(knopfIcon).not.toBe(typIcon);
  });

  it('Material ohne node_id: Zeile bleibt, aber ohne Volltext-Knopf', async () => {
    const host = await render(msg({
      cards: [card({ node_type: 'content', title: 'Ohne ID', link: 'https://repo.test/x' })],
    }));
    expect(host.querySelector('.result-group--material')).not.toBeNull();
    expect(host.querySelector('.result-group__item-btn')).toBeNull();
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
