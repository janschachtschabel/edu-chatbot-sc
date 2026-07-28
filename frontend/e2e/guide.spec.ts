/**
 * Lotsen-Pfade (Plan-Zeile 8-7): Tour-Start und Kontext-Ping.
 *
 * Beide sind reine Integrationswege — die Auslöser liegen in der Hülle bzw. im
 * URL-Detektor, das Ergebnis steckt im Request-Body. Unit-Tests decken die
 * Einzelteile ab; hier wird die Kette geprüft.
 */
import { expect, test } from '@playwright/test';

import { chatResponse, guideModeConfig } from './fixtures/backend-payloads';
import { HOST, mount } from './fixtures/harness';

/** Content-Seite: `/components/render/<uuid>` → node_id + page_kind=content. */
const CONTENT_URL = `${HOST}/edu-sharing/components/render/9f8b1c2d-4e5f-6789-abcd-ef0123456789`;

test('der Tour-Chip startet die Web-Tour mit tour_action="start"', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Wir starten oben auf der Seite.',
    tour: { active: true, step: 'intro', group: 'start' },
  }));
  await w.open();

  // Der Chip-Text kommt aus welcome-config.tour_reply.
  await page.locator('.qr-btn', { hasText: 'Zeig mir die Seite' }).click();

  await w.waitForChatRequests(1);
  const req = w.chatRequests()[0];
  expect(req.environment.tour_action).toBe('start');
  await expect(page.locator('.msg-bubble').last()).toContainText('Wir starten oben auf der Seite.');
});

/** Wiederkehrer: fortgeführte Session im localStorage. */
const KNOWN_SESSION = 'bb-7c9e6679-7425-40de-944b-e07fc1f90ae7';

test('auf einer Inhaltsseite feuert der stille Kontext-Ping (page_event=context_open)', async ({ page }) => {
  const w = await mount(page, { url: CONTENT_URL, session: KNOWN_SESSION });
  w.enqueue(chatResponse({ content: 'Zu dieser Seite kann ich dir mehr sagen.' }));
  await w.open();

  await w.waitForChatRequests(1);
  const req = w.chatRequests()[0];
  expect(req.session_id).toBe(KNOWN_SESSION);
  expect(req.environment.page_event).toBe('context_open');
  // Der Detektor muss die node_id aus dem Pfad gezogen haben.
  expect(req.environment.page_context.node_id).toBe('9f8b1c2d-4e5f-6789-abcd-ef0123456789');

  // Stiller Ping: die Antwort erscheint, aber KEINE User-Bubble.
  await expect(page.locator('.msg-bubble').last()).toContainText('Zu dieser Seite kann ich dir mehr sagen.');
  await expect(page.locator('.message-row.user-row')).toHaveCount(0);
});

test('eine leere Kontext-Antwort erzeugt keine Bubble', async ({ page }) => {
  const w = await mount(page, { url: CONTENT_URL, session: KNOWN_SESSION });
  w.enqueue(chatResponse({ content: '', quick_replies: [] }));
  await w.open();

  await w.waitForChatRequests(1);
  // Nur die Begrüßung steht im Verlauf (Backend hat die Seite schon begrüßt).
  await expect(page.locator('.msg-bubble')).toHaveCount(1);
  await expect(page.locator('.msg-bubble')).toContainText('Moin! Ich bin BOERDi.');
});

/**
 * „Es wurde NICHT gepingt" lässt sich nicht durch Abwarten beweisen: der Ping
 * ginge über `setTimeout(…, 0)` (lifecycle.ts:206) raus und wäre beim Lesen
 * womöglich noch unterwegs — ein `toHaveLength(0)` direkt nach dem Rendern der
 * Begrüßung wäre ein Münzwurf. Deshalb wird stattdessen die REIHENFOLGE
 * geprüft: ein selbst getippter Turn muss der ERSTE Request sein. Ein Ping
 * würde vor ihm losgeschickt und läge damit auf Index 0.
 */
async function expectNoPingBefore(page: import('@playwright/test').Page, w: Awaited<ReturnType<typeof mount>>) {
  await page.locator('.chat-input').fill('Hallo');
  await page.locator('.btn-send').click();
  await w.waitForChatRequests(1);
  const first = w.chatRequests()[0];
  expect(first.message).toBe('Hallo');
  expect(first.environment.page_event).toBeUndefined();
}

test('eine fortgeführte Session auf einer Seite ohne Kontext pingt nicht', async ({ page }) => {
  const w = await mount(page, { url: `${HOST}/impressum`, session: KNOWN_SESSION });
  await w.open();
  await expectNoPingBefore(page, w);
});

test('eine FRISCHE Session pingt nie — auch auf einer Inhaltsseite (ALT-Verhalten)', async ({ page }) => {
  // Pinnt eine Grenze, die leicht als Bug missverstanden wird: ALT ruft
  // `_maybeSendContextPing()` nur aus `_afterResume()` (chat.component.ts:738)
  // und `onSpaContextChange()` (752) — der Erstbesucher bekommt keine proaktive
  // Kontext-Begrüßung. Bewusst als IST-Verhalten festgehalten, nicht geändert.
  const w = await mount(page, { url: CONTENT_URL });
  await w.open();
  await expectNoPingBefore(page, w);
});

test('SPA-Navigation auf eine Inhaltsseite löst den Ping aus (URL-Watcher, 1,5 s)', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Diese Seite kenne ich.' }));
  await w.open();

  await page.evaluate((url) => history.pushState({}, '', url), CONTENT_URL);

  // Der Watcher pollt alle 1,5 s — der Default-Timeout von 5 s wäre auf einem
  // ausgelasteten Runner die knappste Marge der ganzen Suite.
  await w.waitForChatRequests(1, 15_000);
  const req = w.chatRequests()[0];
  expect(req.environment.page_event).toBe('context_open');
  expect(req.environment.page_context.node_id).toBe('9f8b1c2d-4e5f-6789-abcd-ef0123456789');
});

test('die Kopfzeilen-Nav kommt aus der Studio-Config und trägt die bsid', async ({ page }) => {
  const w = await mount(page);
  await w.open();

  const nav = page.locator('.boerdi-header-actions a').first();
  await expect(nav).toHaveAttribute('title', 'Fachportale');
  // Vertrauter Host → Session-Handoff im Link.
  await expect(nav).toHaveAttribute('href', /\/fachportale\?bsid=bb-[0-9a-f-]{36}$/);
});

test('ein Bot-navigate zeigt das Lotsen-Banner statt heimlich zu springen', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Ich bringe dich hin.',
    page_action: { action: 'navigate', payload: { url: `${HOST}/fachportal/mathematik`, label: 'Fachportal Mathematik' } },
  }));
  await w.open();

  await page.locator('.chat-input').fill('Bring mich zum Fachportal');
  await page.locator('.btn-send').click();

  const banner = page.locator('.boerdi-nav-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('Fachportal Mathematik');
  // Kein automatischer Sprung: die Seite steht noch.
  expect(new URL(page.url()).pathname).toBe('/');
});

test('ohne Tour-Chip in der Config startet kein Tour-Turn', async ({ page }) => {
  const w = await mount(page, {
    config: guideModeConfig({
      welcome: { greeting: 'Hallo!', quick_replies: ['Zeig mir die Seite'], tour_reply: '' },
    }),
  });
  w.enqueue(chatResponse({ content: 'Das ist eine normale Antwort.' }));
  await w.open();

  await page.locator('.qr-btn', { hasText: 'Zeig mir die Seite' }).click();

  await w.waitForChatRequests(1);
  // Ohne `tour_reply` ist derselbe Text nur eine gewöhnliche Nachricht.
  expect(w.chatRequests()[0].environment.tour_action).toBeUndefined();
  expect(w.chatRequests()[0].message).toBe('Zeig mir die Seite');
});
