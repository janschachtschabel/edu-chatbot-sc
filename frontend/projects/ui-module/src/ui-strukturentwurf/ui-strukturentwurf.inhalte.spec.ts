// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ModulKontext } from '../_vertrag/ui-block';
import { alsJson, type EntwurfDaten } from './entwurf-export';
import manifest from './manifest.json';
import { definiere, ELEMENT, UiStrukturentwurfElement } from './ui-strukturentwurf.element';

/**
 * Paket N3 (Plan 2026-11-19): die Zuordnung Datei → Punkt im Entwurf aus Materialien. Der Baum
 * zeigt je Punkt die Zahl (TG-3f); die Titel stehen aufklappbar (natives `<details>`, Disclosure)
 * beim gewählten Punkt, die nicht zugeordneten unter dem Baum. Nichts davon ist im Baumeintrag
 * selbst bedienbar — der bleibt ein `treeitem` ohne verschachtelte Knöpfe.
 */
const KONTEXT: ModulKontext = {
  blockId: 'b0000001', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
};

let h = host();

function host() {
  return {
    antworten: vi.fn(), vormerken: vi.fn(), herunterladen: vi.fn(), beschaeftigt: vi.fn(() => false),
    drucken: vi.fn(), link: vi.fn(), aktion: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(), ablegen: vi.fn(), auftrag: vi.fn(),
  };
}

function render(daten: EntwurfDaten, kontext: Partial<ModulKontext> = {}): ShadowRoot {
  h = host();
  definiere();
  const knoten = document.createElement(ELEMENT) as UiStrukturentwurfElement;
  knoten.host = h as never;
  knoten.daten = daten as unknown as Record<string, unknown>;
  knoten.kontext = { ...KONTEXT, ...kontext };
  document.body.appendChild(knoten);
  return knoten.shadowRoot as ShadowRoot;
}

const NODE = '11111111-2222-3333-4444-555555555555';
const AUS_MATERIALIEN = {
  titel: 'Erdkunde', quelle: 'ki', quelle_block: 'bauswahl1', knoten: [
    { id: 'k1', titel: 'Vulkane', inhalte: [{ i: 0, name: 'Aufbau eines Schichtvulkans', node_id: NODE },
                                            { i: 1, name: 'Der Ausbruch des Vesuv' }] },
    { id: 'k2', titel: 'Klima' },
  ],
  nicht_zugeordnet: [{ i: 5, name: 'Bruchrechnung' }, { i: 6, name: 'Present Perfect', node_id: NODE }],
} as unknown as EntwurfDaten;

const items = (el: ShadowRoot) => [...el.querySelectorAll<HTMLElement>('[role="treeitem"]')];
const offenbar = (el: ShadowRoot) => [...el.querySelectorAll<HTMLDetailsElement>('details.ui-strukturentwurf__inhalte')];
const zusammenfassung = (d: HTMLDetailsElement) => d.querySelector('summary')?.textContent?.trim();
const namen = (d: HTMLDetailsElement) => [...d.querySelectorAll('li')].map((li) => li.textContent);

async function waehle(el: ShadowRoot, item: HTMLElement) {
  item.focus();
  item.dispatchEvent(new FocusEvent('focusin', { bubbles: true, composed: true }));
  item.click();
  await Promise.resolve();
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('ui_strukturentwurf: Zuordnung Datei → Punkt (N3)', () => {
  it('nennt die nicht zugeordneten unter dem Baum, zugeklappt, mit ihren Titeln', () => {
    const el = render(AUS_MATERIALIEN);
    const rest = offenbar(el).find((d) => d.classList.contains('ui-strukturentwurf__reste'))!;
    expect(zusammenfassung(rest)).toBe('Nicht zugeordnet: 2 Materialien');
    expect(rest.open).toBe(false);
    expect(namen(rest)).toEqual(['Bruchrechnung', 'Present Perfect']);
    expect(rest.closest('[role="tree"]')).toBeNull();
  });

  it('zeigt beim gewählten Punkt seine Inhalte aufklappbar — nicht im Baumeintrag', async () => {
    const el = render(AUS_MATERIALIEN);
    await waehle(el, items(el)[0]);
    const punkt = offenbar(el).find((d) => d.classList.contains('ui-strukturentwurf__punktinhalte'))!;
    expect(zusammenfassung(punkt)).toBe('Inhalte dieses Punkts: 2 Materialien');
    expect(namen(punkt)).toEqual(['Aufbau eines Schichtvulkans', 'Der Ausbruch des Vesuv']);
    expect(items(el)[0].querySelector('details, button, summary')).toBeNull();
    await waehle(el, items(el)[1]);
    expect(offenbar(el).some((d) => d.classList.contains('ui-strukturentwurf__punktinhalte'))).toBe(false);
  });

  it('nur lesend genauso', async () => {
    const el = render(AUS_MATERIALIEN, { nurLesen: true });
    await waehle(el, items(el)[0]);
    const texte = offenbar(el).map(zusammenfassung);
    expect(texte).toContain('Nicht zugeordnet: 2 Materialien');
    expect(texte).toContain('Inhalte dieses Punkts: 2 Materialien');
  });

  it('auf Englisch', async () => {
    const el = render(AUS_MATERIALIEN, { sprache: 'en' });
    await waehle(el, items(el)[0]);
    const texte = offenbar(el).map(zusammenfassung);
    expect(texte).toContain('Not assigned: 2 materials');
    expect(texte).toContain('Content of this item: 2 materials');
  });

  it('aufgeklappt bleibt aufgeklappt, auch nach dem Neuzeichnen', async () => {
    const el = render(AUS_MATERIALIEN);
    const rest = () => el.querySelector<HTMLDetailsElement>('details.ui-strukturentwurf__reste')!;
    rest().open = true;
    rest().dispatchEvent(new Event('toggle'));
    await waehle(el, items(el)[1]);
    expect(rest().open).toBe(true);
  });

  it('ohne nicht zugeordnete kein Abschnitt', () => {
    const el = render({ ...AUS_MATERIALIEN, nicht_zugeordnet: undefined } as unknown as EntwurfDaten);
    expect(el.querySelector('details.ui-strukturentwurf__reste')).toBeNull();
  });

  it('die Antwort und der Export behalten nicht_zugeordnet und die node_ids', () => {
    const el = render(AUS_MATERIALIEN);
    [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === 'Übernehmen')!.click();
    const [daten] = h.antworten.mock.calls[0];
    expect(daten.nicht_zugeordnet).toEqual(AUS_MATERIALIEN.nicht_zugeordnet);
    expect(daten.knoten[0].inhalte[0].node_id).toBe(NODE);
    const json = JSON.parse(alsJson(AUS_MATERIALIEN));
    expect(json.nicht_zugeordnet).toEqual(AUS_MATERIALIEN.nicht_zugeordnet);
    expect(json.knoten[0].inhalte[0].node_id).toBe(NODE);
  });

  it('der Baum zählt Materialien (aus Ordnern bleiben es Dateien)', () => {
    const el = render(AUS_MATERIALIEN);
    const vulkane = items(el)[0];
    const id = (vulkane.getAttribute('aria-describedby') ?? '').split(' ')[0];
    expect(el.querySelector(`#${id}`)?.textContent).toBe('2 Materialien');
  });

  // ── Review N3 ──────────────────────────────────────────────────────────────────────────────

  it('MINOR 9: Löschen schiebt die Inhalte des Punkts (und seiner Unterpunkte) nach „nicht zugeordnet“', async () => {
    const daten = {
      ...AUS_MATERIALIEN, knoten: [
        { ...AUS_MATERIALIEN.knoten[0], kinder: [{ id: 'k1-1', titel: 'Ätna', inhalte: [{ i: 9, name: 'Ätna heute' }] }] },
        AUS_MATERIALIEN.knoten[1],
      ],
    } as unknown as EntwurfDaten;
    const el = render(daten);
    const vulkane = items(el)[0];
    await waehle(el, vulkane);
    vulkane.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true, composed: true }));
    const rest = el.querySelector<HTMLDetailsElement>('details.ui-strukturentwurf__reste')!;
    expect(zusammenfassung(rest)).toBe('Nicht zugeordnet: 5 Materialien');
    expect(namen(rest)).toEqual(['Bruchrechnung', 'Present Perfect', 'Aufbau eines Schichtvulkans',
      'Der Ausbruch des Vesuv', 'Ätna heute']);
    [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.trim() === 'Übernehmen')!.click();
    const [antwort] = h.antworten.mock.calls[0];
    expect(antwort.nicht_zugeordnet.map((e: { i: number }) => e.i)).toEqual([5, 6, 0, 1, 9]);
    expect(antwort.nicht_zugeordnet[2].node_id).toBe(NODE);
  });

  it('MINOR 9: Rückgängig holt sie zurück; ein Material an zwei Punkten bleibt beim anderen', async () => {
    const doppelt = {
      ...AUS_MATERIALIEN, knoten: [AUS_MATERIALIEN.knoten[0],
        { id: 'k2', titel: 'Klima', inhalte: [{ i: 1, name: 'Der Ausbruch des Vesuv' }] }],
    } as unknown as EntwurfDaten;
    const el = render(doppelt);
    const vulkane = items(el)[0];
    await waehle(el, vulkane);
    vulkane.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true, composed: true }));
    const rest = () => el.querySelector<HTMLDetailsElement>('details.ui-strukturentwurf__reste')!;
    expect(namen(rest())).toEqual(['Bruchrechnung', 'Present Perfect', 'Aufbau eines Schichtvulkans']);
    const klima = items(el)[0];
    klima.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true, composed: true }));
    expect(namen(rest())).toEqual(['Bruchrechnung', 'Present Perfect']);
  });

  it('NIT 10: gekürzte Inhalte eines Entwurfs aus Materialien haben einen eigenen Satz', () => {
    const el = render({ ...AUS_MATERIALIEN, gekuerzt: true } as unknown as EntwurfDaten);
    const hinweis = el.querySelector('.ui-strukturentwurf__hinweis')?.textContent ?? '';
    expect(hinweis).toContain('Materialien');
    expect(hinweis).not.toContain('Sammlung in WLO');
  });

  it('NIT 12: die Listen sind in der Höhe begrenzt und rollen', async () => {
    const { STIL } = await import('./ui-strukturentwurf.stil.generated');
    expect(STIL).toMatch(/__inhalte ul\{[^}]*max-block-size/);
    expect(STIL).toMatch(/__inhalte ul\{[^}]*overflow-y:auto/);
  });

  it('zweites Review, NIT 6: aus Ordnern heißen sie „Dateien“', async () => {
    const el = render({ ...AUS_MATERIALIEN, quelle: 'ordner' } as unknown as EntwurfDaten);
    await waehle(el, items(el)[0]);
    const texte = offenbar(el).map(zusammenfassung);
    expect(texte).toContain('Nicht zugeordnet: 2 Dateien');
    expect(texte).toContain('Inhalte dieses Punkts: 2 Dateien');
  });

  it('zweites Review, NIT 7: die rollbare Liste ist per Tastatur erreichbar und benannt', async () => {
    const el = render(AUS_MATERIALIEN);
    await waehle(el, items(el)[0]);
    for (const d of offenbar(el)) {
      const ul = d.querySelector('ul')!;
      expect(ul.tabIndex).toBe(0);
      expect(ul.getAttribute('aria-label')).toBe(zusammenfassung(d));
    }
  });

  it('das Manifest kennt nicht_zugeordnet in Eingabe und Antwort', () => {
    for (const teil of [manifest.eingabe, manifest.antwort] as unknown as
      { properties: Record<string, { items?: { $ref?: string }; maxItems?: number }> }[]) {
      expect(teil.properties['nicht_zugeordnet'].items?.$ref).toBe('#/$defs/inhalt');
      expect(teil.properties['nicht_zugeordnet'].maxItems).toBe(500);
    }
  });
});
