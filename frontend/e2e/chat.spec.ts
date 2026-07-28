/**
 * Golden-UI-Smokes für den Chat-Turn (Plan-Zeile 8-7): Begrüßung, Suche mit
 * Karten, Aktions-Pill — plus der `?bsid=`-Handoff, der in 8-5 nur live
 * nachweisbar war (Shadow-DOM-Retargeting, Befund M1).
 *
 * Geprüft wird beide Richtungen: was das Widget SENDET (Request-Body) und was
 * es aus einer Antwort MACHT (gerendertes DOM).
 */
import { expect, test } from '@playwright/test';

import { card, chatResponse } from './fixtures/backend-payloads';
import { HOST, mount } from './fixtures/harness';

test('Begrüßung und Start-Quick-Replies kommen aus der Studio-Config', async ({ page }) => {
  const w = await mount(page);
  await w.open();

  await expect(page.locator('.msg-bubble').first()).toContainText('Moin! Ich bin BOERDi.');
  await expect(page.locator('.qr-btn')).toHaveText(['Was kannst du?', 'Zeig mir die Seite']);
});

test('ein getippter Turn erzeugt User-Bubble, Antwort und einen sauberen Request', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Ich helfe bei WLO-Inhalten.' }));
  await w.open();

  await page.locator('.chat-input').fill('Was kannst du?');
  await page.locator('.btn-send').click();

  await expect(page.locator('.message-row.user-row')).toContainText('Was kannst du?');
  await expect(page.locator('.msg-bubble').last()).toContainText('Ich helfe bei WLO-Inhalten.');

  await w.waitForChatRequests(1);
  const req = w.chatRequests()[0];
  expect(req.message).toBe('Was kannst du?');
  expect(req.session_id).toMatch(/^bb-[0-9a-f-]{36}$/);
  // C10: das Widget-Flag muss im page_context stehen (Backend routet Karten
  // dann in die Canvas statt in den Host-Pfad).
  expect(req.environment.page_context.widget).toBe(true);
  expect(req.environment.device).toBe('desktop');
  // M2-Regression: der Lotsen-Modus darf den Backend-Default nicht mit `false`
  // überschreiben, obwohl die Shell lazy mountet.
  expect(req.environment.guide_mode).toBe(true);
  expect(req.environment.host).toBe('host.test');
});

test('Karten landen in den Ergebnis-Boxen (Default inline-result-grouping)', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Hier sind passende Materialien.',
    cards: [card(), card({ node_id: 'n-2', title: 'Brüche kürzen' })],
  }));
  await w.open();

  await page.locator('.chat-input').fill('Bruchrechnen');
  await page.locator('.btn-send').click();

  const group = page.locator('.result-group').first();
  await expect(group).toBeVisible();
  await expect(group).toContainText('Bruchrechnen üben');
  await expect(group).toContainText('Brüche kürzen');
});

test('inline-result-grouping="false" rendert das flache Karten-Grid mit Aktionsleiste', async ({ page }) => {
  const w = await mount(page, { attrs: { 'inline-result-grouping': 'false' } });
  w.enqueue(chatResponse({
    content: 'Bitte sehr.',
    cards: [
      card(),
      // Nur Sammlungen tragen die Aktionsleiste (Inhalte/Lernpfad/Themenseite).
      card({ node_id: 'c-1', title: 'Mathe-Sammlung', node_type: 'collection' }),
    ],
  }));
  await w.open();

  await page.locator('.chat-input').fill('Bruchrechnen');
  await page.locator('.btn-send').click();

  const tile = page.locator('.cards-list .wlo-card').first();
  await expect(tile).toBeVisible();
  await expect(tile).toContainText('Bruchrechnen üben');
  await expect(tile).toContainText('Mathematik');

  const actions = page.locator('.card-actions');
  await expect(actions).toHaveCount(1);
  await expect(actions).toContainText('Inhalte');
  await expect(actions).toContainText('Lernpfad');

  // `:has()`-Rundung (offen seit 8-6): eine Karte OHNE Aktionsleiste ist rundum
  // gerundet, die MIT Leiste unten eckig, damit die Leiste bündig anschließt.
  const radius = (i: number) => page.locator('.wlo-card').nth(i)
    .evaluate((el) => getComputedStyle(el).borderBottomLeftRadius);
  expect(await radius(0)).toBe('10px');
  expect(await radius(1)).not.toBe('10px');
});

test('ein Aktions-Pill sendet action + action_params statt Text', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(
    chatResponse({
      content: 'Ich habe eine Sammlung gefunden.',
      quick_replies: ['__action__|Inhalte zeigen|browse_collection|{"collection_id":"c-1"}'],
    }),
    chatResponse({ content: 'Das ist in der Sammlung.' }),
  );
  await w.open();

  await page.locator('.chat-input').fill('Zeig mir Sammlungen');
  await page.locator('.btn-send').click();

  const pill = page.locator('.qr-btn', { hasText: 'Inhalte zeigen' });
  await expect(pill).toBeVisible();
  await pill.click();

  await w.waitForChatRequests(2);
  const req = w.chatRequests()[1];
  expect(req.action).toBe('browse_collection');
  expect(req.action_params).toEqual({ collection_id: 'c-1' });
  expect(req.message).toBe('Inhalte zeigen');
});

test('ein Link auf einen vertrauten Host bekommt beim Klick die bsid (M1)', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: `Schau hier: [Testziel](${HOST}/testziel)` }));
  await w.open();

  await page.locator('.chat-input').fill('Wo finde ich das?');
  await page.locator('.btn-send').click();

  const link = page.locator('.msg-content a', { hasText: 'Testziel' });
  await expect(link).toBeVisible();
  await link.click();

  // Der Klick-Handler schreibt die Session-ID in die URL und lässt navigieren
  // — genau das war vor dem Shadow-DOM-Retargeting-Fix tot.
  await page.waitForURL(/\/testziel\?bsid=bb-[0-9a-f-]{36}$/);
});

test('Fehler des Backends erscheinen als ehrliche Meldung im Verlauf', async ({ page }) => {
  const w = await mount(page);
  await w.open();
  // Die Queue ist leer → der Stub liefert die Default-Antwort. Für den
  // Fehlerfall wird der Endpoint hart abgeschaltet.
  await page.route((url) => url.pathname === '/api/chat/stream', (r) => r.abort('failed'));
  await page.route((url) => url.pathname === '/api/chat', (r) => r.abort('failed'));

  await page.locator('.chat-input').fill('Kaputt?');
  await page.locator('.btn-send').click();

  await expect(page.locator('.msg-bubble').last()).toContainText('Fehler');
  // Und die Eingabe ist wieder frei (kein hängender Lade-Zustand).
  await expect(page.locator('.chat-input')).toBeEnabled();
});
