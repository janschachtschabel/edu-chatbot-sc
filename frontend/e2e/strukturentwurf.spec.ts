/**
 * Strukturentwurf (Paket U2, Plan 2026-11-04): eine neue Gliederung im gebauten Widget.
 *
 * Warum e2e: Der Weg geht über Modul (Baum, Tastatur, Bearbeiten), den Host des Blocks (`antworten`,
 * `vormerken`) und den Sendeweg der Shell — „Übernehmen“ wie beim Auswahlfeld, und eine GETIPPTE
 * Nachricht nimmt den Stand mit (T-10). Dazu die Brücke aus dem Bestand („Als Entwurf bearbeiten“).
 */
import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const ENTWURF = {
  titel: 'Optik in Klasse 8', quelle: 'ki', fach: 'Physik',
  knoten: [
    { id: 'k1', titel: 'Ausbreitung des Lichts', kinder: [{ id: 'k1-1', titel: 'Lichtquellen' }] },
    { id: 'k2', titel: 'Reflexion' },
    { id: 'k3', titel: 'Brechung', ausstehend: true },
  ],
};

function entwurfBlock(blockId = 'e1e2e3e4e5e6e7e8') {
  return {
    block_id: blockId, modul: 'ui_strukturentwurf', version: 1, art: 'abfragen', status: 'offen',
    daten: ENTWURF, text: '**Entwurf (KI): Optik in Klasse 8**', antwort: null,
  };
}

async function entwurfZeigen(page: import('@playwright/test').Page) {
  const w = await mount(page);
  w.enqueue(
    chatResponse({ content: 'Hier ist ein Entwurf zur Optik.', ui: { ui_bloecke: [entwurfBlock()] } }),
    chatResponse({ content: 'Gut, damit arbeite ich weiter.' }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Entwirf eine Gliederung zur Optik');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  return w;
}

test('bearbeiten per Tastatur, dann übernehmen: der Stand geht als ui_antwort mit', async ({ page }) => {
  const w = await entwurfZeigen(page);
  await expect(page.locator('.ui-strukturentwurf__marke')).toHaveText('Entwurf (KI)');
  const baum = page.getByRole('tree', { name: /Optik in Klasse 8/ });
  await expect(baum.getByRole('treeitem')).toHaveCount(3);
  await expect(page.locator('.chat-input')).toBeFocused();       // Fokus nach dem Zug abwarten

  await baum.getByRole('treeitem', { name: 'Ausbreitung des Lichts' }).focus();
  await page.keyboard.press('Alt+Shift+ArrowDown');
  await expect(page.getByRole('status').filter({ hasText: 'nach unten verschoben' })).toHaveCount(1);
  await expect(baum.getByRole('treeitem', { name: 'Ausbreitung des Lichts' })).toBeFocused();
  await page.keyboard.press('F2');
  const titelFeld = page.getByRole('textbox', { name: 'Titel' });
  await expect(titelFeld).toBeFocused();
  // Review BU-2, Befund 5: Taste für Taste mit dem Cursor in der Mitte — das Element zeichnet bei jeder
  // Eingabe neu; Feld, Wert und Cursor müssen stehen bleiben.
  await titelFeld.fill('Licht Schatten');
  await page.keyboard.press('Home');
  for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowRight');
  await titelFeld.pressSequentially(' und');
  await expect(titelFeld).toHaveValue('Licht und Schatten');
  await expect(baum.getByRole('treeitem', { name: 'Licht und Schatten' })).toHaveCount(1);
  await page.keyboard.press('Enter');
  await expect(baum.getByRole('treeitem', { name: 'Licht und Schatten' })).toBeFocused();

  await page.getByRole('button', { name: 'Übernehmen' }).click();
  await w.waitForTurns(2);
  const zug = w.turnRequests()[1];
  expect(zug.message).toBe('Entwurf „Optik in Klasse 8“ übernommen (4 Punkte).');
  expect(zug.ui_antwort.block_id).toBe('e1e2e3e4e5e6e7e8');
  expect(zug.ui_antwort.daten).toMatchObject({ uebernommen: true, bearbeitet: true });
  expect(zug.ui_antwort.daten.knoten.map((k: { titel: string }) => k.titel))
    .toEqual(['Reflexion', 'Licht und Schatten', 'Brechung']);
  expect(w.turnRequests()[0].environment.ui_module).toContain('ui_strukturentwurf');

  await expect(page.locator('.ui-strukturentwurf__status')).toHaveText('Übernommen.');
  await expect(page.getByRole('button', { name: 'Übernehmen' })).toHaveCount(0);
  // Review U2, Befund 4, im echten Browser (Review BU-2, Befund 5): der Knopf verschwindet, die
  // Statuszeile hat den Fokus.
  await expect(page.locator('.ui-strukturentwurf__status')).toBeFocused();
});

test('Esc im Titelfeld führt in den Baum und schließt das Chat-Fenster nicht (Review U2, Befund 2)', async ({ page }) => {
  await entwurfZeigen(page);
  await expect(page.locator('.chat-input')).toBeFocused();
  const reflexion = page.getByRole('treeitem', { name: 'Reflexion' });
  await reflexion.focus();
  await page.keyboard.press('F2');
  await expect(page.getByRole('textbox', { name: 'Titel' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(reflexion).toBeFocused();
  await expect(page.locator('.chat-input')).toBeVisible();
});

test('eine getippte Nachricht nimmt den offenen Entwurf mit (T-10)', async ({ page }) => {
  const w = await entwurfZeigen(page);
  await page.getByRole('button', { name: 'Löschen' }).click();
  await page.locator('.chat-input').fill('Bitte die Brechung vertiefen');
  await page.locator('.btn-send').click();
  await w.waitForTurns(2);
  const zug = w.turnRequests()[1];
  expect(zug.message).toBe('Bitte die Brechung vertiefen');
  expect(zug.ui_antwort.daten).toMatchObject({ uebernommen: false, bearbeitet: true });
  expect(zug.ui_antwort.daten.knoten).toHaveLength(2);
  await expect(page.locator('.ui-strukturentwurf__status')).toHaveText('Mit deiner Nachricht gesendet.');
});

test('aus dem Bestand: „Als Entwurf bearbeiten“ schickt die Direktaktion', async ({ page }) => {
  const w = await mount(page);
  const wurzel = 'aaaa1111-0000-4000-8000-000000000000';
  w.enqueue(
    chatResponse({ content: 'Hier sind die Themen.', ui: { ui_bloecke: [{
      block_id: 'a0a0a0a0a0a0a0a0', modul: 'ui_themenbaum', version: 1, art: 'anzeigen', status: 'nur_anzeige',
      daten: { titel: 'Mathematik', wurzel_id: wurzel, entwurf_moeglich: true, knoten: [{ id: 'bbbb-1', titel: 'Algebra' }] },
      text: '- Algebra', antwort: null,
    }] } }),
    chatResponse({ content: 'Die Gliederung als Entwurf.', ui: { ui_bloecke: [entwurfBlock('f1f2f3f4f5f6f7f8')] } }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Themen in Mathe');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  await expect(page.locator('.ui-themenbaum__marke')).toHaveText('Aus WLO');
  await page.getByRole('button', { name: 'Als Entwurf bearbeiten' }).click();
  await w.waitForTurns(2);
  const zug = w.turnRequests()[1];
  expect(zug.action).toBe('edit_collection_as_draft');
  expect(zug.action_params).toEqual({ collection_id: wurzel, title: 'Mathematik' });
  await expect(page.locator('.ui-strukturentwurf__marke')).toHaveText('Entwurf (KI)');
});

test('320 px: kein waagerechtes Scrollen, Felder und Knöpfe bleiben erreichbar', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await entwurfZeigen(page);
  const box = page.locator('.ui-strukturentwurf');
  await expect(box).toBeVisible();
  const ueber = await box.evaluate((el) => el.scrollWidth - el.clientWidth);
  expect(ueber).toBeLessThanOrEqual(1);
  const seite = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(seite).toBeLessThanOrEqual(1);
  await expect(page.getByRole('textbox', { name: 'Titel' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Übernehmen' })).toBeVisible();
});
