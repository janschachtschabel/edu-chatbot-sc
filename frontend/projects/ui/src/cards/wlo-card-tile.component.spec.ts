import { Component, provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { WloCard } from './card-types';
import { WloCardTileComponent } from './wlo-card-tile.component';

/**
 * Charakterisierung des WloCardTile — der visuelle Port der ALT-`.wlo-card`
 * (chat.component.html:246-294). In ALT nur über die große
 * chat.component.spec.ts integrativ gedeckt (mit dem Tile 8-2f portiert).
 * Geprüft wird das gerenderte DOM: Link-Attribute, 3-Wege-Klassifikation,
 * Typ-Label/-Icon, Desc-Kürzung, Thumb + Lizenz-Badge, Footer-Meta,
 * Leerzustände. Verhalten aus ALT abgeleitet.
 */
function makeCard(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}

async function render(
  card: WloCard,
  href = 'https://example.test/x',
  tooltip: string | null = 'Titel',
): Promise<HTMLElement> {
  const fixture = TestBed.createComponent(WloCardTileComponent);
  fixture.componentRef.setInput('card', card);
  fixture.componentRef.setInput('href', href);
  fixture.componentRef.setInput('tooltip', tooltip);
  fixture.detectChanges();
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('WloCardTileComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [WloCardTileComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });

  it('Einzelinhalt: Link-Attribute, Typ-Label/-Icon, Desc-Kürzung, Thumb+Lizenz, Footer', async () => {
    const card = makeCard({
      node_type: 'content',
      title: 'Photosynthese erklärt',
      description: 'X'.repeat(200),
      learning_resource_types: ['Video'],
      educational_contexts: ['Sekundarstufe I'],
      disciplines: ['Biologie'],
      preview_url: 'https://img.test/p.jpg',
      license: 'CC BY-SA 4.0',
    });
    const host = await render(card, 'https://go.test/here', 'Photosynthese erklärt (Video)');

    const a = host.querySelector('a.wlo-card') as HTMLAnchorElement;
    expect(a).not.toBeNull();
    expect(a.getAttribute('href')).toBe('https://go.test/here');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    expect(a.getAttribute('title')).toBe('Photosynthese erklärt (Video)');

    // Klassifikation → is-inhalt am Wrapper
    expect(host.querySelector('.wlo-card-wrapper.is-inhalt')).not.toBeNull();

    // Typ-Label + Icon (SafeSvgPipe: SVG überlebt ins DOM)
    expect(host.querySelector('.card-content-label')?.textContent?.trim()).toBe('Video');
    expect(host.querySelector('.card-content-icon svg')).not.toBeNull();

    // Titel + Desc-Kürzung (120 + Ellipse)
    expect(host.querySelector('.card-title')?.textContent?.trim()).toBe('Photosynthese erklärt');
    const desc = host.querySelector('.card-desc')?.textContent?.trim() ?? '';
    expect(desc.length).toBe(121);
    expect(desc.endsWith('…')).toBe(true);

    // Thumb + Lizenz-Badge (getLicenseShort)
    const img = host.querySelector('img.card-img-side') as HTMLImageElement;
    expect(img.getAttribute('alt')).toBe('Photosynthese erklärt');
    expect(img.getAttribute('loading')).toBe('lazy');
    expect(host.querySelector('.card-license-badge-side')?.textContent?.trim()).toBe('CC BY-SA');

    // Footer: Bildungsstufe + Fach
    expect(host.querySelector('.footer-stufe')?.textContent).toContain('Sekundarstufe I');
    expect(host.querySelector('.footer-fach')?.textContent).toContain('Biologie');
  });

  it('Sammlung: is-sammlung + "Sammlung"-Label, keine Desc/Thumb, null-Tooltip → kein title', async () => {
    const card = makeCard({
      node_type: 'collection',
      title: 'Mathe-Sammlung',
      description: '',
      disciplines: [],
      educational_contexts: [],
    });
    const host = await render(card, '#', null);

    expect(host.querySelector('.wlo-card-wrapper.is-sammlung')).not.toBeNull();
    expect(host.querySelector('.card-content-label')?.textContent?.trim()).toBe('Sammlung');
    expect(host.querySelector('.card-desc')).toBeNull();
    expect(host.querySelector('.card-thumb-side')).toBeNull();
    expect(host.querySelector('.footer-stufe')).toBeNull();
    expect(host.querySelector('.footer-fach')).toBeNull();

    const a = host.querySelector('a.wlo-card') as HTMLAnchorElement;
    expect(a.hasAttribute('title')).toBe(false);
  });

  it('Themenseite: is-themenseite + "Themenseite"-Label', async () => {
    const card = makeCard({
      node_type: 'topic_page',
      title: 'Bruchrechnung',
      topic_pages: [{ url: 'https://tp.test', target_group: 'a', label: 'L', variant_id: 'v' }],
    });
    const host = await render(card, 'https://tp.test', 'Bruchrechnung (Themenseite)');

    expect(host.querySelector('.wlo-card-wrapper.is-themenseite')).not.toBeNull();
    expect(host.querySelector('.card-content-label')?.textContent?.trim()).toBe('Themenseite');
  });

  // Slot für die Sammlungs-Aktionsleiste (8-2i): in ALT liegt `.card-actions`
  // INNERHALB von `.wlo-card-wrapper`, direkt nach dem `<a class="wlo-card">`
  // (chat.component.html:299-347). Die SCSS-Regel
  // `.wlo-card-wrapper:not(:has(.card-actions)) .wlo-card` hängt an genau
  // dieser Verschachtelung — projizierter Inhalt muss also im Wrapper landen.
  it('projiziert Inhalt in den Wrapper, hinter die Karte (Slot für .card-actions)', async () => {
    @Component({
      standalone: true,
      imports: [WloCardTileComponent],
      template: `<boerdi-wlo-card-tile [card]="card" href="#">
        <div class="card-actions">Aktionen</div>
      </boerdi-wlo-card-tile>`,
    })
    class SlotHost { card = makeCard({ node_type: 'collection', title: 'Sammlung' }); }

    const fixture = TestBed.createComponent(SlotHost);
    fixture.detectChanges();
    await fixture.whenStable();
    const wrapper = (fixture.nativeElement as HTMLElement).querySelector('.wlo-card-wrapper')!;
    const projected = wrapper.querySelector('.card-actions');
    expect(projected).not.toBeNull();
    expect(projected!.previousElementSibling?.classList.contains('wlo-card')).toBe(true);
  });
});
