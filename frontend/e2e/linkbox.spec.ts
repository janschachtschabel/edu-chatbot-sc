/**
 * Linkbox (Paket U1-c1): die Webseiten einer Antwort als UI-Modul im gebauten Widget.
 *
 * Das Backend liefert `web_links` weiter (Entscheid: Blöcke zusätzlich) und dazu den Block.
 * Das Widget zeigt dann genau EINE Webseiten-Box — die des Moduls, nach den Trefferboxen.
 */
import { expect, test } from '@playwright/test';

import { luecke, textkante } from './fixtures/abstaende';
import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const LINKS = [
  { title: 'WirLernenOnline', url: 'https://wirlernenonline.de/' },
  { title: 'Bildungsserver', url: 'https://www.bildungsserver.de/' },
];

const LINKBOX = {
  block_id: 'b0000004', modul: 'ui_linkbox', version: 1, art: 'anzeigen', status: 'nur_anzeige',
  daten: { links: LINKS.map((l) => ({ titel: l.title, url: l.url })) },
  text: LINKS.map((l) => `- [${l.title}](${l.url})`).join('\n'),
};

test('genau eine Webseiten-Box — die Linkbox, nach den Treffern', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Hier ist, was ich gefunden habe.',
    cards: [{ node_id: 'c1', title: 'Sammlung Optik', node_type: 'collection', url: 'https://wirlernenonline.de/c1' }],
    web_links: LINKS,
    ui: { pattern: 'M05', ui_bloecke: [LINKBOX] },
  }));
  await w.open();
  await page.locator('.chat-input').fill('Optik');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);

  const boxen = page.locator('.result-group--web');
  await expect(boxen).toHaveCount(1);
  await expect(page.locator('ui-linkbox .result-group--web')).toHaveCount(1);
  const links = page.locator('ui-linkbox a.result-group__item');
  await expect(links).toHaveCount(2);
  await expect(links.first()).toHaveAttribute('target', '_blank');
  await expect(links.first()).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(links.nth(1)).toContainText('Bildungsserver');

  // Nach den Trefferboxen, wie die bisherige Box.
  const vorher = await page.locator('boerdi-result-groups').last().evaluate((gruppen) => {
    const linkbox = gruppen.ownerDocument.querySelector('ui-linkbox')
      ?? (gruppen.getRootNode() as ShadowRoot).querySelector('ui-linkbox');
    return !!linkbox && !!(gruppen.compareDocumentPosition(linkbox) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(vorher).toBe(true);
});

test('nach dem Neuladen: die Linkbox aus dem Verlauf, keine zweite Box', async ({ page }) => {
  // Der Verlauf liefert `ui` je Nachricht mit `web_links` UND dem abgeleiteten Block — die
  // bisherige Box fiele ohne Tor auf `ui.web_links` zurück und stünde doppelt da.
  const w = await mount(page, {
    session: 'bb-11111111-2222-3333-4444-555555555555',
    history: [
      { role: 'user', content: 'Optik' },
      { role: 'assistant', content: 'Hier ist, was ich gefunden habe.',
        ui: { pattern: 'M05 (Suche)', web_links: LINKS, ui_bloecke: [LINKBOX] } },
    ],
  });
  await w.open();
  await expect(page.locator('.message-row.user-row')).toHaveCount(1);
  await expect(page.locator('.result-group--web')).toHaveCount(1);
  await expect(page.locator('ui-linkbox a.result-group__item')).toHaveCount(2);
});

// ── Senkrechter Rhythmus (2026-11-03) ──────────────────────────────────────────────────────────
// Sichtbarer Weißraum zwischen Textzeilen (fixtures/abstaende.ts): Überschrift → erster Link wie
// Link → Link — in der Linkbox und in der Trefferbox darüber (beide stehen zusammen, gleicher Stil).
const KARTEN = [
  { node_id: 'c1', title: 'Sammlung Optik', node_type: 'collection', url: 'https://wirlernenonline.de/c1' },
  { node_id: 'c2', title: 'Sammlung Licht', node_type: 'collection', url: 'https://wirlernenonline.de/c2' },
];
const TREFFER = {
  block_id: 'b0000006', modul: 'ui_trefferliste', version: 1, art: 'anzeigen', status: 'nur_anzeige',
  daten: { karten: KARTEN, such_metas: [], seiten: null, typ_fokus: '' }, text: '',
};

/** Überschrift → erster Eintrag und Eintrag → Eintrag in einer `.result-group`. */
async function gruppenRhythmus(gruppe: import('@playwright/test').Locator) {
  const kopf = await textkante(gruppe.locator('.result-group__heading'));
  const titel = gruppe.locator('.result-group__item-title');
  const [t1, t2] = [await textkante(titel.nth(0)), await textkante(titel.nth(1))];
  return { kopfZuEintrag: luecke(kopf, t1), eintragZuEintrag: luecke(t1, t2) };
}

for (const breite of [1280, 320]) {
  test(`Rhythmus (${breite} px): Überschrift → erster Link wie Link → Link, wie in der Trefferbox`, async ({ page }) => {
    await page.setViewportSize({ width: breite, height: 800 });
    const w = await mount(page);
    w.enqueue(chatResponse({
      content: 'Hier ist, was ich gefunden habe.', cards: KARTEN, web_links: LINKS,
      ui: { pattern: 'M05 (Suche)', ui_bloecke: [TREFFER, LINKBOX] },
    }));
    await w.open();
    await page.locator('.chat-input').fill('Optik');
    await page.locator('.btn-send').click();
    await w.waitForTurns(1);

    const linkbox = await gruppenRhythmus(page.locator('ui-linkbox .result-group'));
    const treffer = await gruppenRhythmus(page.locator('ui-trefferliste .result-group').first());
    const m = { linkbox, treffer };
    test.info().annotations.push({ type: 'abstaende', description: JSON.stringify(m) });
    const zeig = JSON.stringify(m);

    // Überschrift → erster Link wie Link → Link (±3 px, wie bei den anderen Modulen). Vorher
    // 9,7 gegen 6,1 px; seit dem Entscheid des Nutzers (2026-11-03) steht die Überschrift im
    // geteilten Partial `ui/src/grouping/_result-group.scss` 2 px statt 4 px über dem ersten Eintrag.
    expect(Math.abs(linkbox.kopfZuEintrag - linkbox.eintragZuEintrag), zeig).toBeLessThanOrEqual(3);
    expect(Math.abs(linkbox.kopfZuEintrag - treffer.kopfZuEintrag), zeig).toBeLessThanOrEqual(1);
    expect(Math.abs(linkbox.eintragZuEintrag - treffer.eintragZuEintrag), zeig).toBeLessThanOrEqual(1);
  });
}
