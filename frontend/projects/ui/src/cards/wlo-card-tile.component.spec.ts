import { Component, provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { WloCard } from './card-types';
import { WloCardTileComponent } from './wlo-card-tile.component';

/**
 * Charakterisierung des WloCardTile. Ursprünglich der visuelle Port der
 * ALT-`.wlo-card` (chat.component.html:246-294); 2026-07-31 auf den Aufbau der
 * edu-sharing-Kachel umgestellt (Nutzer-Vorlage, siehe
 * docs/plans/2026-07-31-material3-edu-sharing.md): Vorschaubild formatfüllend
 * oben, darunter Quelle → Titel → Beschreibung → Metazeilen.
 *
 * Geprüft wird das gerenderte DOM: Link-Attribute, 3-Wege-Klassifikation,
 * Reihenfolge Medium/Text, Quellzeile, Typ-Label/-Icon, Desc-Kürzung,
 * Lizenz-Badge, Meta-Zeilen, Leerzustände.
 */
function makeCard(fields: Partial<WloCard>): WloCard {
  return fields as unknown as WloCard;
}

async function render(
  card: WloCard,
  href = 'https://example.test/x',
  tooltip: string | null = 'Titel',
  translate: TranslateFn = createTranslator(DE, DE),
): Promise<HTMLElement> {
  const fixture = TestBed.createComponent(WloCardTileComponent);
  fixture.componentRef.setInput('card', card);
  fixture.componentRef.setInput('href', href);
  fixture.componentRef.setInput('tooltip', tooltip);
  fixture.componentRef.setInput('translate', translate);
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

  it('Einzelinhalt: Link-Attribute, Quelle, Typ-Label/-Icon, Desc-Kürzung, Bild+Lizenz, Meta', async () => {
    const card = makeCard({
      node_type: 'content',
      title: 'Photosynthese erklärt',
      description: 'X'.repeat(200),
      learning_resource_types: ['Video'],
      educational_contexts: ['Sekundarstufe I'],
      disciplines: ['Biologie'],
      preview_url: 'https://img.test/p.jpg',
      license: 'CC BY-SA 4.0',
      publisher: 'Geogebra',
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

    // edu-sharing-Aufbau: das Medium steht VOR dem Textblock, nicht daneben.
    expect(a.firstElementChild?.classList.contains('card-media')).toBe(true);
    expect(a.children[1]?.classList.contains('card-body')).toBe(true);

    // Quellzeile (`publisher`) über dem Titel — in der Vorlage „Geogebra"
    expect(host.querySelector('.card-source')?.textContent?.trim()).toBe('Geogebra');

    // Typ-Label + Icon (SafeSvgPipe: SVG überlebt ins DOM)
    expect(host.querySelector('.card-content-label')?.textContent?.trim()).toBe('Video');
    expect(host.querySelector('.card-content-icon svg')).not.toBeNull();

    // Titel + Desc-Kürzung (120 + Ellipse)
    expect(host.querySelector('.card-title')?.textContent?.trim()).toBe('Photosynthese erklärt');
    const desc = host.querySelector('.card-desc')?.textContent?.trim() ?? '';
    expect(desc.length).toBe(121);
    expect(desc.endsWith('…')).toBe(true);

    // Vorschaubild + Lizenz-Badge (getLicenseShort)
    const img = host.querySelector('img.card-img') as HTMLImageElement;
    expect(img.getAttribute('alt')).toBe('Photosynthese erklärt');
    expect(img.getAttribute('loading')).toBe('lazy');
    expect(host.querySelector('.card-license-badge')?.textContent?.trim()).toBe('CC BY-SA');

    // Metazeilen: Fach + Bildungsstufe
    expect(host.querySelector('.card-meta-fach')?.textContent).toContain('Biologie');
    expect(host.querySelector('.card-meta-stufe')?.textContent).toContain('Sekundarstufe I');
  });

  it('Sammlung ohne Bild/Quelle: Platzhalter statt Bild, keine Desc/Meta, null-Tooltip → kein title', async () => {
    const card = makeCard({
      node_type: 'collection',
      title: 'Mathe-Sammlung',
      description: '',
      publisher: '',
      disciplines: [],
      educational_contexts: [],
    });
    const host = await render(card, '#', null);

    expect(host.querySelector('.wlo-card-wrapper.is-sammlung')).not.toBeNull();
    expect(host.querySelector('.card-content-label')?.textContent?.trim()).toBe('Sammlung');
    expect(host.querySelector('.card-desc')).toBeNull();
    expect(host.querySelector('.card-source')).toBeNull();
    expect(host.querySelector('.card-meta-stufe')).toBeNull();
    expect(host.querySelector('.card-meta-fach')).toBeNull();

    // Der Medienbereich bleibt bestehen, damit bildlose Kacheln nicht flacher
    // sind als ihre Nachbarn — statt eines Fotos trägt er einen Platzhalter.
    expect(host.querySelector('.card-media')).not.toBeNull();
    expect(host.querySelector('img.card-img')).toBeNull();
    expect(host.querySelector('.card-media-fallback svg')).not.toBeNull();
    expect(host.querySelector('.card-license-badge')).toBeNull();

    // Nutzer-Rückmeldung 2026-07-31 („vorn würde reichen"): der Inhaltstyp wird
    // GENAU EINMAL bebildert — in der Metazeile. Der Platzhalter im Medienfeld
    // ist ein neutrales Bildsymbol, nicht dasselbe Glyph noch einmal groß.
    // Verglichen werden die GERENDERTEN Symbole, nicht die Quell-Konstanten:
    // der Sanitizer normalisiert das SVG, ein Vergleich gegen ICONS.* wäre
    // auch dann grün, wenn beide gleich aussähen.
    const platzhalter = host.querySelector('.card-media-fallback')?.innerHTML;
    const typSymbol = host.querySelector('.card-content-icon')?.innerHTML;
    expect(platzhalter).toBeTruthy();
    expect(platzhalter).not.toBe(typSymbol);

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

  it('Typ-Label und Typ-Titel kommen aus dem Übersetzer (C1-b3)', async () => {
    const en = createTranslator({ 'contentType.collection': 'Collection' }, DE);
    const card = makeCard({ node_type: 'collection', title: 'Mathe' });
    const host = await render(card, '#', null, en);
    expect(host.querySelector('.card-content-label')?.textContent?.trim()).toBe('Collection');
    expect(host.querySelector('.card-content-type')?.getAttribute('title')).toBe('Collection: Mathe');
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
      template: `<boerdi-wlo-card-tile [card]="card" href="#" [translate]="t">
        <div class="card-actions">Aktionen</div>
      </boerdi-wlo-card-tile>`,
    })
    class SlotHost {
      card = makeCard({ node_type: 'collection', title: 'Sammlung' });
      t = createTranslator(DE, DE);
    }

    const fixture = TestBed.createComponent(SlotHost);
    fixture.detectChanges();
    await fixture.whenStable();
    const wrapper = (fixture.nativeElement as HTMLElement).querySelector('.wlo-card-wrapper')!;
    const projected = wrapper.querySelector('.card-actions');
    expect(projected).not.toBeNull();
    expect(projected!.previousElementSibling?.classList.contains('wlo-card')).toBe(true);
  });
});
