/**
 * Trefferliste (Paket U1-c2a/b): die WLO-Treffer als UI-Modul im gebauten Widget (Boxen und Kacheln).
 * `cards` bleibt in der Antwort (Entscheid „Blöcke zusätzlich“); gezeigt wird genau einmal.
 */
import { expect, test } from '@playwright/test';

import { luecke, textkante, TOLERANZ_PX } from './fixtures/abstaende';
import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const KARTEN = [
  { node_id: 'c1', title: 'Sammlung Optik', node_type: 'collection', url: 'https://wirlernenonline.de/c1' },
  { node_id: 'm1', title: 'Video: Licht', node_type: 'content', url: 'https://wirlernenonline.de/m1' },
];
const META = { tool_name: 'search_wlo_content', search_term: 'Optik', search_url: 'https://wirlernenonline.de/suche?q=Optik' };

test('Treffer genau einmal — aus dem Modul, mit Such-Absprung', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Hier ist, was ich gefunden habe.',
    cards: KARTEN,
    query_metas: [META],
    ui: {
      pattern: 'M05 (Suche)',
      ui_bloecke: [{
        block_id: 'b0000006', modul: 'ui_trefferliste', version: 1, art: 'anzeigen', status: 'nur_anzeige',
        daten: { karten: KARTEN, such_metas: [META], seiten: null, typ_fokus: '' },
        text: '- [Sammlung Optik](https://wirlernenonline.de/c1)',
      }],
    },
  }));
  await w.open();
  await page.locator('.chat-input').fill('Optik');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);

  const letzte = page.locator('.message-row').last();
  await expect(letzte.locator('boerdi-result-groups')).toHaveCount(1);
  await expect(letzte.locator('ui-trefferliste boerdi-result-groups')).toHaveCount(1);
  await expect(letzte).toContainText('Sammlung Optik');
  await expect(letzte).toContainText('Video: Licht');
  await expect(letzte.locator('ui-trefferliste boerdi-search-cta')).toHaveCount(1);
});

test('Kacheln: eine Kachelliste aus dem Modul, „mehr anzeigen“ deckt auf', async ({ page }) => {
  const viele = Array.from({ length: 8 }, (_, i) => ({
    node_id: `k${i}`, title: `Material ${i}`, node_type: 'content', url: `https://wirlernenonline.de/k${i}`,
  }));
  const w = await mount(page, { attrs: { 'show-cards': 'always' } });
  w.enqueue(chatResponse({
    content: 'Hier ist, was ich gefunden habe.',
    cards: viele,
    ui: {
      pattern: 'M05 (Suche)',
      ui_bloecke: [{
        block_id: 'b0000008', modul: 'ui_trefferliste', version: 1, art: 'anzeigen', status: 'nur_anzeige',
        daten: { karten: viele, such_metas: [], seiten: null, typ_fokus: '' }, text: '',
      }],
    },
  }));
  await w.open();
  await page.locator('.chat-input').fill('Optik');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);

  const letzte = page.locator('.message-row').last();
  await expect(letzte.locator('boerdi-card-list')).toHaveCount(1);
  await expect(letzte.locator('ui-trefferliste .wlo-card-wrapper')).toHaveCount(5);
  await letzte.locator('.pagination-bar button').first().click();
  await expect(letzte.locator('ui-trefferliste .wlo-card-wrapper')).toHaveCount(8);
});

// ── Senkrechter Rhythmus (2026-11-03) ──────────────────────────────────────────────────────────
// Die Trefferboxen sind die bisherigen (`boerdi-result-groups`); hier nur gemessen, damit sie im
// Takt der Linkbox bleiben (linkbox.spec.ts vergleicht beide direkt): Überschrift → erster Treffer
// wie Treffer → Treffer, sichtbarer Weißraum zwischen Textzeilen (fixtures/abstaende.ts).
test('Rhythmus: Überschrift → erster Treffer wie Treffer → Treffer', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Hier ist, was ich gefunden habe.',
    cards: KARTEN,
    ui: {
      pattern: 'M05 (Suche)',
      ui_bloecke: [{
        block_id: 'b0000006', modul: 'ui_trefferliste', version: 1, art: 'anzeigen', status: 'nur_anzeige',
        daten: { karten: [...KARTEN, { node_id: 'm2', title: 'Arbeitsblatt: Spiegel', node_type: 'content', url: 'https://wirlernenonline.de/m2' }],
          such_metas: [], seiten: null, typ_fokus: '' },
        text: '',
      }],
    },
  }));
  await w.open();
  await page.locator('.chat-input').fill('Optik');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);

  // Die Materialbox hat zwei Treffer (Video, Arbeitsblatt) — Zeilen mit Volltext-Knopf.
  const gruppe = page.locator('ui-trefferliste .result-group--material');
  const kopf = await textkante(gruppe.locator('.result-group__heading'));
  const titel = gruppe.locator('.result-group__item-title');
  await expect(titel).toHaveCount(2);
  const [t1, t2] = [await textkante(titel.nth(0)), await textkante(titel.nth(1))];
  const m = { kopfZuEintrag: luecke(kopf, t1), eintragZuEintrag: luecke(t1, t2) };
  test.info().annotations.push({ type: 'abstaende', description: JSON.stringify(m) });
  expect(Math.abs(m.kopfZuEintrag - m.eintragZuEintrag), JSON.stringify(m)).toBeLessThanOrEqual(TOLERANZ_PX);
});
