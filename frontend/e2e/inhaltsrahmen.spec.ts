/**
 * Inhaltsrahmen (Paket U1-b): das erste UI-Modul im gebauten Widget — Box, Drucken, Download.
 *
 * Warum e2e: Der Download (Blob, `a.download`) und das Druckfenster (`window.open`) wirken erst
 * im echten Browser; Unit-Tests belegen nur, dass der Host gerufen wird.
 */
import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const DATEN = {
  titel: 'Lernpfad Bruchrechnung',
  art: 'lernpfad',
  markdown: '1. Brüche erkennen\n2. Brüche kürzen\n3. Brüche addieren',
};

function rahmenBlock(blockId = 'b0000001') {
  return {
    block_id: blockId, modul: 'ui_inhaltsrahmen', version: 1, art: 'anzeigen',
    daten: DATEN, text: DATEN.markdown, status: 'nur_anzeige',
  };
}

async function frage(page: import('@playwright/test').Page, w: Awaited<ReturnType<typeof mount>>, n: number) {
  await page.locator('.chat-input').fill(`Frage ${n}`);
  await page.locator('.btn-send').click();
  await w.waitForTurns(n);
}

test('der Inhaltsrahmen zeigt Titel und Inhalt, Download liefert die Markdown-Datei', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Hier ist der Lernpfad.', ui: { ui_bloecke: [rahmenBlock()] } }));
  await w.open();
  await frage(page, w, 1);

  const box = page.locator('ui-inhaltsrahmen .inline-document');
  await expect(box).toHaveCount(1);
  await expect(box.locator('.inline-document__title')).toHaveText(DATEN.titel);
  await expect(box.locator('.inline-document__body li')).toHaveCount(3);

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    box.getByRole('button', { name: 'Als Markdown herunterladen' }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('lernpfad-bruchrechnung.md');
  const inhalt = readFileSync(await download.path(), 'utf8');
  expect(inhalt).toBe(`# ${DATEN.titel}\n\n${DATEN.markdown}\n`);
});

test('Drucken öffnet die Druckansicht mit dem Titel', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Hier ist der Lernpfad.', ui: { ui_bloecke: [rahmenBlock()] } }));
  await w.open();
  await frage(page, w, 1);

  const [fenster] = await Promise.all([
    page.waitForEvent('popup'),
    page.getByRole('button', { name: 'Als PDF drucken / speichern' }).click(),
  ]);
  await expect(fenster.locator('h1')).toHaveText(DATEN.titel);
  await expect(fenster.locator('body')).toContainText('Brüche kürzen');
  await fenster.close();
});

test('Drucken und Herunterladen gehen per Tastatur', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Hier ist der Lernpfad.', ui: { ui_bloecke: [rahmenBlock()] } }));
  await w.open();
  await frage(page, w, 1);

  const drucken = page.getByRole('button', { name: 'Als PDF drucken / speichern' });
  const laden = page.getByRole('button', { name: 'Als Markdown herunterladen' });
  // Nach jedem Zug holt das Widget den Fokus ins Eingabefeld (nach 100 ms) — erst abwarten.
  await expect(page.locator('.chat-input')).toBeFocused();
  await drucken.focus();
  await expect(drucken).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(laden).toBeFocused();
  const [download] = await Promise.all([page.waitForEvent('download'), page.keyboard.press('Enter')]);
  expect(download.suggestedFilename()).toBe('lernpfad-bruchrechnung.md');
});
