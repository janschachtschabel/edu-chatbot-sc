/**
 * Embed contract of `<boerdi-chat>` (spec §5.5) in a real browser.
 *
 * These are the checks that unit tests structurally cannot make: the element
 * is registered by the shipped bundle, its JS API lives on the DOM node (not
 * on an Angular component), the shadow-DOM styles apply, and focus actually
 * moves. Two of them are regression guards for bugs found live in 8-5/8-6.
 */
import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { HOST, mount } from './fixtures/harness';

const API_METHODS = [
  'openChatbot', 'closeChatbot', 'toggleChatbot',
  'isChatbotOpen', 'resetSession', 'updateContext',
];

test('das Bundle registriert das Element und legt die 6 §5.5-Methoden auf den Knoten', async ({ page }) => {
  await mount(page);

  expect(await page.evaluate(() => !!customElements.get('boerdi-chat'))).toBe(true);
  const types = await page.evaluate((methods) => {
    const el = document.querySelector('boerdi-chat') as any;
    return methods.map((m) => typeof el[m]);
  }, API_METHODS);
  expect(types).toEqual(API_METHODS.map(() => 'function'));
});

test('die Host-Seite steuert das Panel über die JS-API', async ({ page }) => {
  await mount(page);
  const el = page.locator('boerdi-chat');

  expect(await el.evaluate((n: any) => n.isChatbotOpen())).toBe(false);
  await el.evaluate((n: any) => n.openChatbot());
  await expect(page.locator('.chat-input')).toBeVisible();
  expect(await el.evaluate((n: any) => n.isChatbotOpen())).toBe(true);

  await el.evaluate((n: any) => n.closeChatbot());
  await expect(page.locator('.chat-input')).toBeHidden();
});

test('resetSession() und updateContext() wirken wirklich, nicht nur am Typ', async ({ page }) => {
  // `element-api.ts` legt die Weiterleitung für ALLE sechs Namen an, und die
  // Komponente ruft `this.shell()?.…` — beide Methoden wären also auch dann
  // `typeof 'function'` und stillschweigend wirkungslos, wenn die Verdrahtung
  // fehlte (genau die Falle von `data-position` und `inline-result-grouping`).
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Erste Antwort.' }), chatResponse({ content: 'Zweite Antwort.' }));
  await w.open();

  await page.locator('.chat-input').fill('Erste Frage');
  await page.locator('.btn-send').click();
  await expect(page.locator('.msg-bubble')).toHaveCount(3);   // Begrüßung + Frage + Antwort

  // updateContext: der Host reicht Seiten-Wissen nach — es muss im nächsten
  // Request im page_context stehen.
  await page.locator('boerdi-chat').evaluate((n: any) => n.updateContext({ thema: 'Bruchrechnen' }));
  await page.locator('.chat-input').fill('Zweite Frage');
  await page.locator('.btn-send').click();
  await w.waitForChatRequests(2);
  expect(w.chatRequests()[1].environment.page_context.thema).toBe('Bruchrechnen');

  // resetSession: neue Session-ID, Verlauf wieder auf die Begrüßung.
  const before = w.chatRequests()[1].session_id;
  await page.locator('boerdi-chat').evaluate((n: any) => n.resetSession());
  await expect(page.locator('.msg-bubble')).toHaveCount(1);

  w.enqueue(chatResponse({ content: 'Dritte Antwort.' }));
  await page.locator('.chat-input').fill('Dritte Frage');
  await page.locator('.btn-send').click();
  await w.waitForChatRequests(3);
  expect(w.chatRequests()[2].session_id).not.toBe(before);
});

test('das Panel wird erst beim ersten Öffnen gemountet (Lazy-Mount) und bleibt dann erhalten', async ({ page }) => {
  const w = await mount(page);

  // Vor dem ersten Öffnen existiert die Shell überhaupt nicht im DOM.
  await expect(page.locator('boerdi-chat-shell')).toHaveCount(0);
  await w.open();
  await expect(page.locator('boerdi-chat-shell')).toHaveCount(1);

  // Nach dem Schließen bleibt sie gemountet (State-Erhalt, §5.5).
  await page.locator('.boerdi-close').click();
  await expect(page.locator('.chat-input')).toBeHidden();
  await expect(page.locator('boerdi-chat-shell')).toHaveCount(1);
});

test('position="top-left" verschiebt den Host — ALT-Bugfix aus 8-5 (data-position matchte nie)', async ({ page }) => {
  await mount(page, { attrs: { position: 'top-left' } });

  // `right`/`bottom` sind hier bewusst nicht geprüft: getComputedStyle löst
  // `auto` bei positionierten Elementen zum *benutzten* Pixelwert auf ("1196px").
  const style = await page.locator('boerdi-chat').evaluate((el) => {
    const s = getComputedStyle(el);
    return { position: s.position, top: s.top, left: s.left };
  });
  expect(style).toEqual({ position: 'fixed', top: '20px', left: '20px' });

  // Und der FAB liegt sichtbar in der oberen Bildschirmhälfte (das ist der
  // Effekt, der vor dem Fix ausblieb).
  const fab = await page.locator('.boerdi-fab').boundingBox();
  const viewport = page.viewportSize()!;
  expect(fab!.y).toBeLessThan(viewport.height / 2);
  expect(fab!.x).toBeLessThan(viewport.width / 2);
});

test('Escape schließt das Panel und gibt den Fokus an den FAB zurück (8-6-Live-Fix)', async ({ page }) => {
  const w = await mount(page);
  // Der Fokus wird per `afterNextRender` gesetzt, also einen Tick nach dem
  // Sichtbarwerden — deshalb gepollt statt einmalig gelesen.
  const focused = () => expect.poll(() => page.evaluate(() => {
    const shadow = (document.querySelector('boerdi-chat') as any).shadowRoot;
    return shadow.activeElement?.className ?? '';
  }));

  await w.open();
  await focused().toContain('chat-input');

  await page.keyboard.press('Escape');
  await expect(page.locator('.chat-input')).toBeHidden();

  // Beim Schließen zurück auf den FAB (sonst verliert die Tastatur die Spur).
  await focused().toContain('boerdi-fab');
});

test('zweites Embed derselben Seite wird versteckt (Single-Instance-Guard, M3)', async ({ page }) => {
  await mount(page, { duplicate: true });

  const elements = page.locator('boerdi-chat');
  await expect(elements).toHaveCount(2);
  await expect(elements.nth(0)).toBeVisible();
  expect(await elements.nth(1).evaluate((el) => getComputedStyle(el).display)).toBe('none');
});

test('Backend nicht erreichbar: FAB erscheint trotzdem und das Panel öffnet', async ({ page }) => {
  const w = await mount(page, { config: null });
  await w.open();
  await expect(page.locator('.msg-bubble').first()).toBeVisible();
});

test('bei 200 % Zoom bleibt das Panel ohne Horizontal-Scroll bedienbar (SC 1.4.4/1.4.10)', async ({ page }) => {
  // 200 % Zoom auf einem 1280×1024-Schirm entspricht einem 640×512-Viewport.
  // Ersetzt keinen Geräte-Test, misst aber den Reflow statt ihn zu behaupten.
  await page.setViewportSize({ width: 640, height: 512 });
  const w = await mount(page);
  await w.open();

  const overflow = await page.locator('.boerdi-panel').evaluate((el) => ({
    scroll: el.scrollWidth, client: el.clientWidth,
  }));
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);

  // Auch der Seiten-Body darf nicht seitlich scrollen.
  const body = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(body.scroll).toBeLessThanOrEqual(body.client);

  await expect(page.locator('.chat-input')).toBeVisible();
  await expect(page.locator('.btn-send')).toBeVisible();
});

test.describe('Bewegung', () => {
  const fabAnimation = (page: import('@playwright/test').Page) =>
    page.locator('.boerdi-fab').evaluate((el) => getComputedStyle(el).animationName);

  test('mit reduzierter Bewegung stehen die Endlos-Animationen still', async ({ page }) => {
    await mount(page);
    expect(await fabAnimation(page)).toBe('none');
  });

  test('ohne Präferenz bobbt der FAB wie in ALT', async ({ page }) => {
    await mount(page, { motion: 'no-preference' });
    expect(await fabAnimation(page)).toContain('boerdi-');
  });
});

test('das Widget lädt nichts von Dritt-Hosts (DSGVO-Guardrail)', async ({ page }) => {
  const seen: string[] = [];
  page.on('request', (req) => seen.push(req.url()));

  const w = await mount(page, { url: `${HOST}/` });
  await w.open();
  await expect(page.locator('.chat-input')).toBeVisible();

  // Erst beweisen, dass der Mitschnitt überhaupt läuft — sonst wäre die
  // eigentliche Zusicherung unten trivial erfüllt.
  expect(seen.length).toBeGreaterThan(1);
  const foreign = seen.filter((u) => !['host.test', 'api.test'].includes(new URL(u).host));
  expect(foreign).toEqual([]);
});
