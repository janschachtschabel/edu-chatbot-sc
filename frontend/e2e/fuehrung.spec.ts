import { expect, type Page, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { type ChatRequest, HOST, mount } from './fixtures/harness';

/**
 * AS-7 (Plan 2026-11-09 §5m): der Kernweg einer Führung im echten Browser — was jsdom nicht kann:
 * eine echte Navigation auf eine andere Seite derselben Herkunft, der Neustart des Widgets dort, der
 * Seiten-Ping beim Fortsetzen und die Ablauf-Leiste vor und nach der Ankunft.
 *
 * Der Lauf wartet schon (Wiederkehrer mit Verlauf): seine letzte Antwort trägt `ui.ablauf` mit
 * `wartet_seite` und dem Weg. Das Backend steht hier als Attrappe; den Seiten-Ping beantwortet sie
 * je nach Seite — auf der Zielseite die Ankunft, sonst nichts (wie `seite_zug.angekommen`).
 */
const SITZUNG = 'bb-12345678-1234-4123-8123-123456789abc';
const STAND = {
  id: 'probe_fuehrung', titel: 'Probe-Führung', nr: 1, von: 1, status: 'wartet_seite',
  lauf: 'a1b2', weg: { label: 'Zur Zielseite', url: '/ziel' }, teile: [],
};
const VERLAUF = [
  { role: 'user', content: 'Führung starten' },
  { role: 'assistant', content: 'Als Nächstes die Zielseite.', ui: { ablauf: STAND } },
];
const ANKUNFT = 'Angekommen – die Führung ist zu Ende.';

/** Die Seiten-Pings (`page_event: ablauf_seite`) beantworten — nach der Registrierung des Harness,
 *  damit diese Route vorgeht; alle anderen Züge fallen an den Harness zurück. */
async function seitenPingsStubben(page: Page): Promise<ChatRequest[]> {
  const pings: ChatRequest[] = [];
  await page.route('https://api.test/api/chat', async (route) => {
    const anfrage = route.request().postDataJSON() as ChatRequest;
    if (anfrage.environment?.['page_event'] !== 'ablauf_seite') return route.fallback();
    pings.push(anfrage);
    const angekommen = String(anfrage.environment?.['page'] ?? '').startsWith('/ziel');
    return route.fulfill({ json: chatResponse(angekommen
      ? { content: ANKUNFT, ui: { pattern: 'ablauf', fester_text: true } }
      : { content: '', quick_replies: [] }) });
  });
  return pings;
}

async function oeffnen(page: Page): Promise<void> {
  if (!(await page.locator('.chat-input').isVisible())) await page.locator('.boerdi-fab').first().click();
  await expect(page.locator('.chat-input')).toBeVisible();
}

test('ein Wiederkehrer mit wartender Führung sieht den Weg in der Leiste, ohne Kontext-Gruß', async ({ page }) => {
  const w = await mount(page, { url: `${HOST}/start`, session: SITZUNG, history: VERLAUF });
  const pings = await seitenPingsStubben(page);
  await w.open();
  const leiste = page.locator('boerdi-ablauf-leiste');
  await expect(leiste).toContainText('Probe-Führung');
  await expect(leiste).toContainText('wartet auf den Seitenwechsel');
  await expect(page.locator('.ablauf-leiste__weg')).toHaveText(/Zur Zielseite/);
  // der Ping fragte auf der Startseite nach — ohne Ankunft, also ohne Blase
  await expect.poll(() => pings.length).toBeGreaterThanOrEqual(1);
  expect(pings[0].environment['page']).toBe('/start');
  await expect(page.getByText(ANKUNFT)).toHaveCount(0);
  // Browser-Abnahme AS-7, L-3: kein Kontext-Gruß, solange die Führung auf ihre Seite wartet
  expect(w.chatRequests().filter((r) => String(r.environment?.['page_event'] ?? '').startsWith('context')))
    .toEqual([]);
});

test('der Weg-Knopf führt auf die Zielseite; dort kommt die Ankunft, und die Leiste geht', async ({ page }) => {
  const w = await mount(page, { url: `${HOST}/start`, session: SITZUNG, history: VERLAUF });
  const pings = await seitenPingsStubben(page);
  await w.open();
  await page.locator('.ablauf-leiste__weg').click();
  await page.waitForURL(`${HOST}/ziel`);
  await oeffnen(page);
  await expect(page.getByText(ANKUNFT)).toBeVisible();
  expect(pings.at(-1)!.environment['page']).toBe('/ziel');
  expect(pings.at(-1)!.session_id).toBe(SITZUNG);          // dieselbe Sitzung, kein neues Gespräch
  await expect(page.locator('.ablauf-leiste__weg')).toHaveCount(0);
});
