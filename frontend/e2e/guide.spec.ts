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

  await w.waitForTurns(1);
  const req = w.turnRequests()[0];
  expect(req.environment.tour_action).toBe('start');
  await expect(page.locator('.msg-bubble').last()).toContainText('Wir starten oben auf der Seite.');
});

/** Wiederkehrer: fortgeführte Session im localStorage. */
const KNOWN_SESSION = 'bb-7c9e6679-7425-40de-944b-e07fc1f90ae7';

test('ein echter Wiederkehrer (History vorhanden) pingt als context_open', async ({ page }) => {
  // EK7: das Ping-Event richtet sich nach der UNTERHALTUNG. Erst eine
  // Nutzer-Nachricht in der wiederhergestellten History macht den Ping zur
  // Fortsetzung — und pinnt zugleich die Reihenfolge: Restore VOR Ping.
  const w = await mount(page, {
    url: CONTENT_URL, session: KNOWN_SESSION,
    history: [
      { role: 'user', content: 'Was ist das hier?' },
      { role: 'assistant', content: 'Ein Arbeitsblatt zur Optik.' },
    ],
    pingReply: chatResponse({ content: 'Zu dieser Seite kann ich dir mehr sagen.' }),
  });
  await w.open();

  await w.waitForChatRequests(1);
  const req = w.chatRequests()[0];
  expect(req.session_id).toBe(KNOWN_SESSION);
  expect(req.environment.page_event).toBe('context_open');
  // Beleg der Reihenfolge: die restaurierte User-Bubble stand vor dem Ping da.
  await expect(page.locator('.message-row.user-row')).toHaveCount(1);
});

test('auf einer Inhaltsseite feuert der stille Kontext-Ping — geleerte History gilt als Erstlade-Fall', async ({ page }) => {
  // `pingReply` statt `enqueue`: die Warteschlange gehört den echten Zügen,
  // ein Ping bedient sich dort nicht (sonst schnappte er die Antwort weg).
  //
  // EK7 (2026-08-21, Live-Befund Prüftisch): OHNE Nutzer-Nachricht ist jeder
  // Kontext-Ping der Erstlade-Fall — als `context_open` gesendet, fiele er im
  // Backend ins Streu-Ping-Gate (leere History → bewusste Stille), und genau
  // das hat live die Erschließungs-Begrüßung verschluckt. Der Pin hielt bis
  // dahin den alten Draht-Vertrag fest, nicht eine Produktanforderung.
  const w = await mount(page, {
    url: CONTENT_URL, session: KNOWN_SESSION,
    pingReply: chatResponse({ content: 'Zu dieser Seite kann ich dir mehr sagen.' }),
  });
  await w.open();

  await w.waitForChatRequests(1);
  const req = w.chatRequests()[0];
  expect(req.session_id).toBe(KNOWN_SESSION);
  expect(req.environment.page_event).toBe('context_open_initial');
  // Der Detektor muss die node_id aus dem Pfad gezogen haben.
  expect(req.environment.page_context.node_id).toBe('9f8b1c2d-4e5f-6789-abcd-ef0123456789');

  // Stiller Ping: die Antwort erscheint, aber KEINE User-Bubble.
  await expect(page.locator('.msg-bubble').last()).toContainText('Zu dieser Seite kann ich dir mehr sagen.');
  await expect(page.locator('.message-row.user-row')).toHaveCount(0);
});

test('eine leere Kontext-Antwort erzeugt keine Bubble', async ({ page }) => {
  // Leere Ping-Antwort ist die Vorgabe der Harness — kein `enqueue` nötig.
  const w = await mount(page, { url: CONTENT_URL, session: KNOWN_SESSION });
  await w.open();

  await w.waitForChatRequests(1);
  // Nur die Begrüßung steht im Verlauf (Backend hat die Seite schon begrüßt).
  await expect(page.locator('.msg-bubble')).toHaveCount(1);
  await expect(page.locator('.msg-bubble')).toContainText('Moin! Ich bin BOERDi.');
});

/**
 * Beide Tests hier hielten bis 2026-08-11 das ALT-Verhalten fest: „der
 * Erstbesucher bekommt keine proaktive Kontext-Begrüßung", und „eine Seite ohne
 * IDs pingt gar nicht". Die Seitenkontext-Erweiterung hat **beides bewusst
 * geändert** (Nutzer-Entscheid: „Auch beim ersten Laden melden? Ja — mit der
 * Auflage, dass Begrüßung und Kontextmeldung zu EINER Nachricht verschmelzen").
 * Die Tests pinnen deshalb jetzt die neue Absicht statt der alten.
 */

test('eine Seite ohne IDs pingt trotzdem — der Hostname genügt, das Backend entscheidet', async ({ page }) => {
  // Das Widget kennt „eigene Startseite" vs. „fremde Seite" nicht; beide
  // heißen für den Erkenner `other`. Es fragt also, statt selbst zu urteilen.
  const w = await mount(page, { url: `${HOST}/impressum`, session: KNOWN_SESSION });
  await w.open();

  await w.waitForChatRequests(1);
  const ping = w.chatRequests()[0];
  // EK7: Session ohne Nutzer-Nachricht (Harness-History ist leer) → Erstlade-
  // Event. Der Kern dieses Tests ist unverändert: es pingt trotz fehlender IDs.
  expect(ping.environment.page_event).toBe('context_open_initial');
  expect(ping.environment.page_context.page_host).toBe('host.test');
  expect(ping.environment.page_context.node_id).toBeUndefined();
});

test('eine FRISCHE Session pingt beim ersten Laden — und bleibt bei EINER Nachricht', async ({ page }) => {
  // Eigenes Ereignis `context_open_initial`: das Backend darf den Erstaufruf
  // von der Fortsetzung unterscheiden. Antwortet es leer (Vorgabe der
  // Harness), kommt die normale Begrüßung — nie beides und nie gar nichts.
  const w = await mount(page, { url: CONTENT_URL });
  await w.open();

  await w.waitForChatRequests(1);
  expect(w.chatRequests()[0].environment.page_event).toBe('context_open_initial');
  await expect(page.locator('.msg-bubble')).toHaveCount(1);
  await expect(page.locator('.msg-bubble')).toContainText('Moin! Ich bin BOERDi.');
});

test('spricht der Ping beim ersten Laden, IST er die Begrüßung — keine zweite Blase', async ({ page }) => {
  // Die Auflage des Nutzers: Begrüßung und Kontextmeldung verschmelzen.
  const w = await mount(page, {
    url: CONTENT_URL,
    pingReply: chatResponse({ content: 'Zu dieser Seite kann ich dir mehr sagen.' }),
  });
  await w.open();

  await expect(page.locator('.msg-bubble')).toHaveCount(1);
  await expect(page.locator('.msg-bubble')).toContainText('Zu dieser Seite kann ich dir mehr sagen.');
  await expect(page.locator('.msg-bubble')).not.toContainText('Moin! Ich bin BOERDi.');
});

test('SPA-Navigation auf eine Inhaltsseite löst den Ping aus (URL-Watcher, 1,5 s)', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Diese Seite kenne ich.' }));
  await w.open();

  await page.evaluate((url) => history.pushState({}, '', url), CONTENT_URL);

  // Der Watcher pollt alle 1,5 s — der Default-Timeout von 5 s wäre auf einem
  // ausgelasteten Runner die knappste Marge der ganzen Suite.
  // Index 0 ist der Erstaufruf-Ping; der SPA-Ping ist der zweite. EK7: die
  // Unterhaltung hat auch nach der Navigation noch keine Nutzer-Nachricht,
  // also bleibt es der Erstlade-Fall — als `context_open` schwiege das Backend
  // (leere History), und die SPA-Begrüßung fiele aus. Den Fortsetzungs-Fall
  // (context_open nach echtem Turn) pinnt der Wiederkehrer-Test oben.
  await w.waitForChatRequests(2, 15_000);
  const req = w.chatRequests()[1];
  expect(req.environment.page_event).toBe('context_open_initial');
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

  await w.waitForTurns(1);
  // Ohne `tour_reply` ist derselbe Text nur eine gewöhnliche Nachricht.
  expect(w.turnRequests()[0].environment.tour_action).toBeUndefined();
  expect(w.turnRequests()[0].message).toBe('Zeig mir die Seite');
});
