/**
 * Themenbaum (Paket U1-e): das erste UI-Modul mit Datenquelle im gebauten Widget.
 *
 * Warum e2e: Der Baum lebt im Shadow-DOM des Widgets, und die Tastatur (wandernder tabindex, Fokus
 * je Eintrag) prüfen die Unit-Tests nur in jsdom. Dazu seit U1-h das Aufklappen im selben Baum:
 * Modul → Host des Blocks (Fähigkeit `nachladen`) → Shell → `POST /api/ui/themenbaum/zweig`
 * (gemockt), ohne Zug — vorher öffnete „Unterthemen öffnen“ einen neuen Baum als Antwort.
 */
import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { API, mount } from './fixtures/harness';

/** Zweige je Knoten (Antwort des Endpunkts) oder ein HTTP-Status für einen Fehler. */
type Zweige = Record<string, Record<string, unknown> | number>;

/** Mockt `POST /api/ui/themenbaum/zweig` (nach `mount`: die spätere Route gewinnt) und hält die
 *  Anfragen fest. */
async function zweigeMocken(page: import('@playwright/test').Page, zweige: Zweige) {
  const anfragen: Record<string, unknown>[] = [];
  await page.route(`${API}/api/ui/themenbaum/zweig`, async (route) => {
    const rumpf = route.request().postDataJSON() as Record<string, unknown>;
    anfragen.push(rumpf);
    const antwort = zweige[String(rumpf['node_id'])] ?? 502;
    if (typeof antwort === 'number') return route.fulfill({ status: antwort, json: { detail: 'nicht_geladen' } });
    return route.fulfill({ json: { daten: antwort } });
  });
  return anfragen;
}

function baumBlock(blockId = 'b7c6d5e4f3a21009') {
  return {
    block_id: blockId, modul: 'ui_themenbaum', version: 1, art: 'anzeigen', status: 'nur_anzeige',
    daten: {
      titel: 'Mathematik', wurzel_id: 'aaaa-1111', gekuerzt: true,
      knoten: [
        { id: 'bbbb-2222', titel: 'Algebra', url: 'https://wirlernenonline.de/sammlung/algebra', mehr: true,
          kinder: [{ id: 'cccc-3333', titel: 'Gleichungen', anzahl: 12 }, { id: 'dddd-4444', titel: 'Terme' }] },
        { id: 'eeee-5555', titel: 'Geometrie', anzahl: 7 },
      ],
    },
    text: '**Mathematik**\n\n- Algebra\n  - Gleichungen\n  - Terme\n- Geometrie',
    antwort: null,
  };
}

async function baumZeigen(page: import('@playwright/test').Page, zweige: Zweige = {}) {
  const w = await mount(page);
  const anfragen = await zweigeMocken(page, zweige);
  w.enqueue(chatResponse({ content: 'Hier die Themen in Mathe.', ui: { ui_bloecke: [baumBlock()] } }));
  await w.open();
  await page.locator('.chat-input').fill('Welche Themen gibt es in Mathe?');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  return { w, anfragen };
}

test('der Baum erscheint zugeklappt, ein Klick klappt auf', async ({ page }) => {
  const { w } = await baumZeigen(page);
  const baum = page.getByRole('tree', { name: 'Unterthemen von Mathematik' });
  await expect(baum).toBeVisible();
  await expect(baum.getByRole('treeitem')).toHaveCount(2);
  const algebra = baum.getByRole('treeitem', { name: 'Algebra', exact: true });
  await expect(algebra).toHaveAttribute('aria-expanded', 'false');
  await algebra.click();
  await expect(algebra).toHaveAttribute('aria-expanded', 'true');
  await expect(baum.getByRole('treeitem', { name: 'Gleichungen' })).toBeVisible();
  // Das Widget meldet das Modul — nur dann bietet das Backend es an.
  expect(w.turnRequests()[0].environment.ui_module).toContain('ui_themenbaum');
});

test('per Tastatur: Tab in den Baum, Pfeile wandern, → öffnet, ← geht zurück', async ({ page }) => {
  await baumZeigen(page);
  const baum = page.getByRole('tree');
  // Nach jedem Zug holt das Widget den Fokus ins Eingabefeld (nach 100 ms) — erst abwarten.
  await expect(page.locator('.chat-input')).toBeFocused();
  await baum.getByRole('treeitem', { name: 'Algebra', exact: true }).focus();
  await page.keyboard.press('ArrowDown');
  await expect(baum.getByRole('treeitem', { name: 'Geometrie' })).toBeFocused();
  await page.keyboard.press('Home');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await expect(baum.getByRole('treeitem', { name: 'Gleichungen' })).toBeFocused();
  await page.keyboard.press('ArrowLeft');
  await expect(baum.getByRole('treeitem', { name: 'Algebra', exact: true })).toBeFocused();
  // Wandernder tabindex: genau ein Eintrag liegt in der Tab-Folge.
  await expect(baum.locator('[role="treeitem"][tabindex="0"]')).toHaveCount(1);
});

test('Aufklappen lädt die Unterthemen in denselben Baum — ohne Zug, Fokus bleibt', async ({ page }) => {
  const { w, anfragen } = await baumZeigen(page, {
    // Die volle Liste unter Algebra; Terme ist darin gekürzt („weitere“) und lädt beim Aufklappen.
    'bbbb-2222': { knoten: [{ id: 'cccc-3333', titel: 'Gleichungen' },
      { id: 'dddd-4444', titel: 'Terme', mehr: true, kinder: [{ id: 'x1', titel: 'Klammern' }] }] },
    'dddd-4444': { knoten: [{ id: 'x1', titel: 'Klammern', kinder: [{ id: 'x2', titel: 'Ausmultiplizieren' }] }, { id: 'x3', titel: 'Faktorisieren' }] },
  });
  const baum = page.getByRole('tree');
  await expect(page.locator('.chat-input')).toBeFocused();
  await baum.getByRole('treeitem', { name: 'Algebra', exact: true }).focus();
  await page.keyboard.press('ArrowRight');                // Algebra auf („weitere“ → volle Liste)
  await page.keyboard.press('ArrowRight');                // Gleichungen
  await page.keyboard.press('ArrowDown');                 // Terme
  const terme = baum.getByRole('treeitem', { name: 'Terme' });
  await expect(page.getByRole('status').filter({ hasText: 'Unterthemen von Algebra geladen' })).toHaveCount(1);
  await expect(terme).toHaveAttribute('aria-expanded', 'false');
  await page.keyboard.press('ArrowRight');                // Terme auf → lädt die volle Liste
  const klammern = baum.getByRole('treeitem', { name: 'Klammern' });
  await expect(klammern).toBeVisible();
  await expect(klammern).toHaveAttribute('aria-level', '3');
  await expect(klammern).toHaveAttribute('aria-setsize', '2');
  await expect(terme).not.toHaveAttribute('aria-busy', 'true');
  await expect(terme).toBeFocused();
  await expect(page.getByRole('status').filter({ hasText: 'Unterthemen von Terme geladen' })).toHaveCount(1);
  // Kein Zug, kein zweiter Baum; die Anfrage trägt nur Sitzung und Knoten.
  await expect(page.getByRole('tree')).toHaveCount(1);
  expect(w.turnRequests()).toHaveLength(1);
  expect(anfragen.map((a) => a['node_id'])).toEqual(['bbbb-2222', 'dddd-4444']);
  expect(anfragen[1]['session_id']).toBe(w.turnRequests()[0].session_id);
  expect(Object.keys(anfragen[1]).sort()).toEqual(['node_id', 'session_id']);
});

test('ein Fehler steht am Knoten, „Erneut laden“ versucht es noch einmal', async ({ page }) => {
  const zweige: Zweige = { 'bbbb-2222': 502 };
  const { anfragen } = await baumZeigen(page, zweige);
  const algebra = page.getByRole('treeitem', { name: 'Algebra', exact: true });
  await algebra.click();
  await expect(algebra.getByText('nicht geladen')).toBeVisible();
  // Die mitgelieferten Kinder bleiben sichtbar.
  await expect(page.getByRole('treeitem', { name: 'Gleichungen' })).toBeVisible();
  zweige['bbbb-2222'] = { knoten: [{ id: 'zz-1', titel: 'Bruchterme' }] };
  await page.getByRole('group', { name: 'Aktionen für Algebra' }).getByRole('button', { name: 'Erneut laden' }).click();
  await expect(page.getByRole('treeitem', { name: 'Bruchterme' })).toBeVisible();
  await expect(algebra).toBeFocused();
  expect(anfragen).toHaveLength(2);
});

test('bei 320 px Breite passt der Baum ohne waagerechtes Scrollen', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await baumZeigen(page);
  const box = page.locator('ui-themenbaum .ui-themenbaum');
  await expect(box).toBeVisible();
  const breiten = await box.evaluate((el) => ({ innen: el.scrollWidth, aussen: el.clientWidth }));
  expect(breiten.innen).toBeLessThanOrEqual(breiten.aussen);
});

// Review U1-h, Befund 5: bis zur tiefsten Ebene (8) bleibt dem Titel Platz — die Einrückung je
// Ebene schrumpft mit der Breite des Baums.
test('bei 320 px passt auch ein tief aufgeklappter Zweig (Ebene 8, lange Titel)', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  const lang = (n: number) => `Ebene ${n}: Gleichungssysteme mit mehreren Unbekannten und Parametern`;
  // Jeder Abruf bringt einen Knoten mit einem Kind (zwei Ebenen); das Kind lädt beim Aufklappen.
  const zweig = (n: number) => ({ knoten: [{ id: `x${n}`, titel: lang(n), kinder: [{ id: `x${n + 1}`, titel: lang(n + 1) }] }] });
  await baumZeigen(page, { 'bbbb-2222': zweig(2), 'x3': zweig(4), 'x5': zweig(6), 'x7': zweig(8) });
  const baum = page.getByRole('tree');
  await baum.getByRole('treeitem', { name: 'Algebra', exact: true }).click();
  for (let n = 2; n <= 7; n += 1) {
    await baum.getByRole('treeitem', { name: lang(n), exact: true }).click();
  }
  const tiefster = baum.locator('[aria-level="8"]');
  await expect(tiefster).toBeVisible();
  await expect(tiefster).toHaveAccessibleName(lang(8));
  await expect(baum.locator('[aria-level="9"]')).toHaveCount(0);
  const titel = await tiefster.locator(':scope > .ui-themenbaum__zeile > .ui-themenbaum__titel')
    .evaluate((el) => el.getBoundingClientRect().width);
  expect(titel).toBeGreaterThanOrEqual(120);
  const box = page.locator('ui-themenbaum .ui-themenbaum');
  const breiten = await box.evaluate((el) => ({ innen: el.scrollWidth, aussen: el.clientWidth }));
  expect(breiten.innen).toBeLessThanOrEqual(breiten.aussen);
  const seite = await page.evaluate(() => ({ innen: document.documentElement.scrollWidth, aussen: document.documentElement.clientWidth }));
  expect(seite.innen).toBeLessThanOrEqual(seite.aussen);
});
