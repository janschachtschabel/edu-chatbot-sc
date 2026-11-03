/**
 * Linkbox (Paket U1-c1): die Webseiten einer Antwort als UI-Modul im gebauten Widget.
 *
 * Das Backend liefert `web_links` weiter (Entscheid: Blöcke zusätzlich) und dazu den Block.
 * Das Widget zeigt dann genau EINE Webseiten-Box — die des Moduls, nach den Trefferboxen.
 */
import { expect, test } from '@playwright/test';

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
