/**
 * Entscheidung (Paket U1-d1): das erste abfragende UI-Modul im gebauten Widget.
 *
 * Warum e2e: Der Weg geht über drei Stellen, die Unit-Tests nur einzeln sehen — das Modul (native
 * Radio-Gruppe, Tastatur), der eigene Host des Blocks (Fähigkeit `antworten`) und den Sendeweg der
 * Shell (`ui_antwort` im Rumpf, Nutzerblase = lesbare Fassung). Danach ist der Block nur lesend.
 */
import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

function frageBlock(blockId = 'a1b2c3d4e5f60718') {
  return {
    block_id: blockId, modul: 'ui_entscheidung', version: 1, art: 'abfragen', status: 'offen',
    daten: {
      frage: 'Für welche Klassenstufe?',
      optionen: [
        { id: 'klasse_5_6', label: 'Klasse 5–6' },
        { id: 'klasse_7_8', label: 'Klasse 7–8', hinweis: 'mit Vorwissen' },
      ],
    },
    text: 'Für welche Klassenstufe?\n\n1. Klasse 5–6\n2. Klasse 7–8 — mit Vorwissen',
    antwort: null,
  };
}

async function frageStellen(page: import('@playwright/test').Page) {
  const w = await mount(page);
  w.enqueue(
    chatResponse({ content: 'Kurz nachgefragt:', ui: { ui_bloecke: [frageBlock()] } }),
    chatResponse({ content: 'Gut, dann für Klasse 7–8.' }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Ein Arbeitsblatt zur Optik');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  return w;
}

test('die Frage erscheint, die Antwort geht als ui_antwort mit, der Block ist danach nur lesend', async ({ page }) => {
  const w = await frageStellen(page);
  const gruppe = page.getByRole('group', { name: 'Für welche Klassenstufe?' });
  await expect(gruppe).toBeVisible();
  const antworten = page.getByRole('button', { name: 'Antworten' });
  await expect(antworten).toBeDisabled();

  await gruppe.getByRole('radio', { name: /Klasse 7–8/ }).check();
  await antworten.click();
  await w.waitForTurns(2);

  const zug = w.turnRequests()[1];
  expect(zug.message).toBe('Klasse 7–8');
  expect(zug.action).toBeUndefined();
  expect(zug.ui_antwort).toEqual({ block_id: 'a1b2c3d4e5f60718', daten: { gewaehlt: ['klasse_7_8'] } });
  // Review U1-d1: das Widget meldet die Module seines Registers — nur dann bietet das Backend sie an.
  expect(w.turnRequests()[0].environment.ui_module).toContain('ui_entscheidung');

  await expect(page.locator('.message-row.user-row').last()).toContainText('Klasse 7–8');
  await expect(page.getByText('Gut, dann für Klasse 7–8.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Antworten' })).toHaveCount(0);
  await expect(page.locator('.ui-entscheidung__status')).toHaveText('Deine Antwort: Klasse 7–8');
  await expect(gruppe.getByRole('radio', { name: /Klasse 7–8/ })).toBeChecked();
  await expect(gruppe.getByRole('radio', { name: /Klasse 7–8/ })).toBeDisabled();
});

test('per Tastatur: Pfeiltaste wählt, Enter antwortet', async ({ page }) => {
  const w = await frageStellen(page);
  const erste = page.getByRole('radio', { name: 'Klasse 5–6' });
  // Nach jedem Zug holt das Widget den Fokus ins Eingabefeld (nach 100 ms) — erst abwarten.
  await expect(page.locator('.chat-input')).toBeFocused();
  await erste.focus();
  await page.keyboard.press('Space');
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('radio', { name: /Klasse 7–8/ })).toBeChecked();
  await page.keyboard.press('Enter');
  await w.waitForTurns(2);
  expect(w.turnRequests()[1].ui_antwort?.daten).toEqual({ gewaehlt: ['klasse_7_8'] });
});

test('bei 320 px Breite passt die Frage ohne waagerechtes Scrollen', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await frageStellen(page);
  const box = page.locator('ui-entscheidung .ui-entscheidung');
  await expect(box).toBeVisible();
  const breiten = await box.evaluate((el) => ({ innen: el.scrollWidth, aussen: el.clientWidth }));
  expect(breiten.innen).toBeLessThanOrEqual(breiten.aussen);
});
