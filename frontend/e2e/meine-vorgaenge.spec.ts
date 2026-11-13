import { expect, type Page, test } from '@playwright/test';

import { chatResponse, guideModeConfig } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

/**
 * AS-Ud (Plan 2026-11-09 §5j): „Meine Vorgänge“ im echten Browser — was jsdom nicht kann: die
 * Eingabezeile mit dem zusätzlichen Knopf bei 320 px, Fokus und Esc durch die Shadow-Roots.
 */
const MIT_ANMELDUNG = { config: guideModeConfig({ mcp_auth_base: 'https://mcp.test' }) };
const VORGANG = {
  id: '0a1b2c3d-0000-4000-8000-000000000001', titel: 'Optik in Klasse 8', ablauf: 'lesen',
  status: 'wartet_person', session_id: 'bb-87654321-4321-4321-8321-cba987654321',
  geaendert: '2026-11-07T09:30:00Z',
};

async function angemeldet(page: Page): Promise<void> {
  // ein wohlgeformter Zugangsblock (Testwert) — das Widget zeigt dann „Abmelden“ und „Meine Vorgänge“
  await page.addInitScript(() => sessionStorage.setItem('boerdi.mcp-access', 'wloE2eTestBlock'));
}

/** Klasse des tatsächlich fokussierten Elements — durch die Shadow-Roots hindurch. */
function fokussiert(page: Page): Promise<string> {
  return page.evaluate(() => {
    const tief = (el: Element | null): Element | null =>
      el?.shadowRoot?.activeElement ? tief(el.shadowRoot.activeElement) : el;
    return (tief(document.activeElement) as HTMLElement | null)?.className ?? '';
  });
}

async function vorgaengeStubben(page: Page) {
  const geloescht: unknown[] = [];
  let liste = [VORGANG];
  await page.route('https://api.test/api/ui/vorgaenge/**', async (route) => {
    const pfad = new URL(route.request().url()).pathname;
    if (pfad.endsWith('/liste')) return route.fulfill({ json: { vorgaenge: liste } });
    if (pfad.endsWith('/loeschen')) {
      geloescht.push(route.request().postDataJSON());
      liste = [];
      return route.fulfill({ json: { geloescht: true } });
    }
    return route.fulfill({ json: { vorgaenge: [] } });          // /offen: nichts
  });
  return geloescht;
}

test('bei 320 px bricht die Zeile um: das Feld oben in voller Breite, die Knöpfe darunter', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await vorgaengeStubben(page);
  await w.open();
  await expect(page.locator('.btn-vorgaenge')).toBeVisible();
  await w.ohneMikrofon();
  const zeile = await page.locator('.chat-footer').evaluate((el) => {
    const kinder = Array.from(el.children).map((k) => {
      const r = k.getBoundingClientRect();
      return { klasse: (k as HTMLElement).className.split(' ')[0], breite: Math.round(r.width),
        oben: Math.round(r.top), rechts: Math.round(r.right) };
    });
    return { kinder, scroll: el.scrollWidth, client: el.clientWidth };
  });
  expect(zeile.scroll).toBeLessThanOrEqual(zeile.client);           // kein waagerechtes Scrollen
  const feld = zeile.kinder.find((k) => k.klasse === 'chat-input')!;
  const knoepfe = zeile.kinder.filter((k) => k.klasse !== 'chat-input');
  expect(feld.breite).toBeGreaterThanOrEqual(250);                  // volle Breite statt 76 px
  for (const k of knoepfe) expect(k.oben, `${k.klasse} unter dem Feld`).toBeGreaterThan(feld.oben);
  expect(new Set(knoepfe.map((k) => k.oben)).size).toBe(1);         // die Knöpfe in einer Zeile
  expect(knoepfe.at(-1)!.klasse).toBe('btn-send');                  // Senden bleibt ganz rechts
});

test('mit Mikrofon (bis 408 px): Mikrofon und Feld oben, in Sicht- wie Tab-Reihenfolge', async ({ page }) => {
  // Review AS-Ud, Befund 6: das Mikrofon steht im DOM vor dem Feld — kein `order`, das es umdreht
  await page.setViewportSize({ width: 380, height: 640 });
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await vorgaengeStubben(page);
  await page.route('https://api.test/api/speech/status', (route) => route.fulfill({ json: { enabled: true } }));
  await page.reload();                                   // der Status gilt ab dem Start
  await w.open();
  await expect(page.locator('.btn-mic')).toBeVisible();
  const lage = await page.locator('.chat-footer').evaluate((el) => {
    const box = (s: string) => el.querySelector(s)!.getBoundingClientRect();
    const mic = box('.btn-mic');
    const feld = box('.chat-input');
    const send = box('.btn-send');
    return { micOben: Math.round(mic.top + mic.height / 2), feldOben: Math.round(feld.top + feld.height / 2),
      micRechts: mic.right, feldLinks: feld.left, feld: Math.round(feld.width), sendOben: Math.round(send.top),
      scroll: el.scrollWidth, client: el.clientWidth };
  });
  expect(Math.abs(lage.micOben - lage.feldOben)).toBeLessThanOrEqual(4);   // eine Zeile
  expect(lage.micRechts).toBeLessThanOrEqual(lage.feldLinks);             // Mikrofon links vom Feld
  expect(lage.feld).toBeGreaterThanOrEqual(250);
  expect(lage.sendOben).toBeGreaterThan(lage.feldOben);                    // Knöpfe darunter
  expect(lage.scroll).toBeLessThanOrEqual(lage.client);
});

test('ab 364 px bleibt es auch angemeldet eine Zeile mit mindestens 120 px Feld', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 640 });
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await vorgaengeStubben(page);
  await w.open();
  await w.ohneMikrofon();
  const oben = await page.locator('.chat-footer').evaluate((el) =>
    Array.from(el.children).map((k) => Math.round(k.getBoundingClientRect().top + k.getBoundingClientRect().height / 2)));
  expect(Math.max(...oben) - Math.min(...oben)).toBeLessThanOrEqual(4);
  const feld = await page.locator('.chat-input').evaluate((el) => el.getBoundingClientRect().width);
  expect(feld).toBeGreaterThanOrEqual(120);
});

test('per Tastatur: öffnen, nachfragen, löschen, mit Esc schließen — der Fokus geht mit', async ({ page }) => {
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  const geloescht = await vorgaengeStubben(page);
  await w.open();

  const knopf = page.locator('.btn-vorgaenge');
  await expect(knopf).toHaveAttribute('aria-expanded', 'false');
  await knopf.focus();
  await page.keyboard.press('Enter');
  await expect(knopf).toHaveAttribute('aria-expanded', 'true');
  const panel = page.getByRole('region', { name: 'Meine Vorgänge in anderen Gesprächen' });
  await expect(panel).toContainText('Optik in Klasse 8');
  await expect(panel).toContainText('Wartet auf dich');
  await expect.poll(() => fokussiert(page)).toContain('meine-vorgaenge__titel');

  await panel.getByRole('button', { name: '„Optik in Klasse 8“ löschen' }).focus();
  await page.keyboard.press('Enter');
  await expect(panel).toContainText('„Optik in Klasse 8“ löschen? Die gesammelten Daten gehen verloren');
  await expect.poll(() => fokussiert(page)).toContain('meine-vorgaenge__ja');
  await page.keyboard.press('Enter');
  await expect(panel.getByRole('status').filter({ hasText: '„Optik in Klasse 8“ gelöscht.' })).toHaveCount(1);
  await expect(panel).toContainText('In anderen Gesprächen ist nichts offen.');
  expect(geloescht).toEqual([{ session_id: expect.stringMatching(/^bb-/), vorgang: VORGANG.id }]);
  await expect.poll(() => fokussiert(page)).toContain('meine-vorgaenge__titel');

  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await expect(page.locator('.chat-input')).toBeVisible();      // das Chat-Fenster bleibt offen
  await expect.poll(() => fokussiert(page)).toContain('btn-vorgaenge');
});

test('Q-4: 320 × 360 px mit Leiste, offener Liste und wartendem Vorgang — das Eingabefeld bleibt sichtbar', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 360 });
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await page.route('https://api.test/api/ui/vorgaenge/**', async (route) => {
    const pfad = new URL(route.request().url()).pathname;
    if (pfad.endsWith('/liste')) return route.fulfill({ json: { vorgaenge: [VORGANG, { ...VORGANG, id: '0a1b2c3d-0000-4000-8000-000000000002', titel: 'Zweiter' }] } });
    return route.fulfill({ json: { vorgaenge: [{ ...VORGANG, status: 'wartet_person' }] } });   // /offen: der Hinweis
  });
  w.enqueue(chatResponse({ content: 'Weiter im Ablauf.', ui: { pattern: 'ABLAUF', ablauf: {
    id: 'lesen', titel: 'Dokument lesen und gliedern', nr: 2, von: 4, status: 'wartet_freigabe', lauf: 'a1',
    teile: [{ name: 'a', text: 'Erster Teil' }, { name: 'b', text: 'Zweiter Teil' }] } } }));
  await w.open();
  await page.locator('.chat-input').fill('weiter');
  await page.locator('.btn-send').click();
  await expect(page.locator('boerdi-ablauf-leiste section')).toBeVisible();
  await page.locator('.btn-vorgaenge').click();
  await expect(page.locator('boerdi-meine-vorgaenge section')).toContainText('Zweiter');
  await expect(page.locator('.chat-input')).toBeInViewport();
  await expect(page.locator('.btn-send')).toBeInViewport();
  // Q-18: solange die Liste offen ist, ruht der Hinweis — die Liste nennt denselben Vorgang
  await expect(page.locator('.fortsetzen-hinweis')).toHaveCount(0);
  const bereich = await page.locator('.ueber-eingabe').evaluate((el) => ({ hoch: el.clientHeight, inhalt: el.scrollHeight }));
  expect(bereich.inhalt).toBeGreaterThan(bereich.hoch);             // der Bereich scrollt selbst
});
