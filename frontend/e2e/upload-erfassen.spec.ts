/**
 * Ordner erfassen (Paket U3-1a, Plan 2026-11-04 §16.5): das erste nachgeladene UI-Modul im gebauten
 * Widget.
 *
 * Warum e2e: Nur hier läuft der ganze Nachlade-Weg (Platzhalter → `<script>` mit SRI von der
 * Widget-Adresse → Custom Element im Shadow Root) und die echte Ordnerauswahl des Browsers
 * (`webkitdirectory`). Dazu der Sendeweg: Vormerkung mit der getippten Nachricht und Antwort per Knopf
 * — ohne Dateinamen.
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

function uploadBlock(blockId = 'u1u2u3u4u5u6u7u8', dokument = false) {
  return {
    block_id: blockId, modul: 'ui_upload', version: 1, art: 'abfragen', status: 'offen',
    daten: {
      zweck: 'sammlungsstruktur', grenzen: { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50 },
      ...(dokument ? { schalter: { dokument_im_chat: true, ablage_in_wlo: false } } : {}),
    },
    text: 'Hier würde ein Auswahlfeld für einen Ordner erscheinen.', antwort: null,
  };
}

/** Ein echter Ordner auf der Platte — Playwright reicht ihn an `<input webkitdirectory>` weiter. */
const ANGELEGT: string[] = [];

function ordner(): string {
  const wurzel = mkdtempSync(join(tmpdir(), 'u31-'));
  ANGELEGT.push(wurzel);
  const physik = join(wurzel, 'Physik 7');
  mkdirSync(join(physik, '01_Mechanik'), { recursive: true });
  mkdirSync(join(physik, '02_Optik'), { recursive: true });
  writeFileSync(join(physik, 'Lehrplan_Physik.pdf'), '%PDF-1.7 test');
  writeFileSync(join(physik, '01_Mechanik', 'hebel-mueller.pdf'), '%PDF-1.7 a');
  writeFileSync(join(physik, '01_Mechanik', 'kraft.docx'), 'PK docx');
  writeFileSync(join(physik, '02_Optik', 'linsen.pdf'), '%PDF-1.7 b');
  return physik;
}

async function uploadZeigen(page: import('@playwright/test').Page, dokument = false) {
  const w = await mount(page);
  w.enqueue(
    chatResponse({ content: 'Wähle deinen Ordner aus.', ui: { ui_bloecke: [uploadBlock(undefined, dokument)] } }),
    chatResponse({ content: 'Danke, ich sehe deinen Ordner.' }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Ich habe einen Ordner mit Physik-Materialien');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  return w;
}

test.describe('ui_upload (U3-1a, nachgeladen)', () => {
  test.afterAll(() => { for (const d of ANGELEGT.splice(0)) rmSync(d, { recursive: true, force: true }); });

  test('lädt das Bündel nach, zeigt den Ordner als Baum und antwortet ohne Dateinamen', async ({ page }) => {
    const w = await uploadZeigen(page);
    const modul = page.locator('boerdi-ui-upload');
    await expect(modul.getByRole('heading', { name: 'Ordner und Dateien' })).toBeVisible();
    // das Bündel kam von der Widget-Adresse, nicht aus dem Haupt-Bündel
    expect(await page.evaluate(() => [...document.querySelectorAll('script[data-boerdi-modul]')]
      .map((s) => (s as HTMLScriptElement).integrity.startsWith('sha384-')))).toEqual([true]);

    await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
    await expect(modul.getByText('3 Ordner, 4 Dateien').first()).toBeVisible();
    // der Lehrplan in der Wurzel ist als Strukturdokument vorgeschlagen
    await expect(modul.getByLabel('Rolle von Lehrplan_Physik.pdf')).toHaveValue('struktur');

    await modul.getByRole('button', { name: 'Als Themenbaum-Entwurf übernehmen' }).click();
    await w.waitForTurns(2);
    const req = w.chatRequests().at(-1)!;
    expect(req.ui_antwort?.daten).toMatchObject({ aktion: 'ordner_als_entwurf', struktur: { name: 'Physik 7' } });
    expect(JSON.stringify(req.ui_antwort)).not.toContain('hebel-mueller');
    expect(req.message).toBe('Ordnerstruktur „Physik 7“ als Themenbaum-Entwurf übernehmen');
  });

  test('nur mit der Tastatur: Ordner aufklappen, Rolle ändern', async ({ page }) => {
    await uploadZeigen(page);
    const modul = page.locator('boerdi-ui-upload');
    await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
    const mechanik = modul.getByRole('button', { name: '01_Mechanik', exact: true });
    await mechanik.focus();
    await page.keyboard.press('Enter');
    await expect(modul.getByRole('button', { name: '01_Mechanik', exact: true })).toHaveAttribute('aria-expanded', 'true');
    await expect(modul.getByRole('button', { name: '01_Mechanik', exact: true })).toBeFocused();
    const rolle = modul.getByLabel('Rolle von kraft.docx');
    await rolle.focus();
    await rolle.selectOption('ignorieren');
    await expect(modul.getByText(/1 ignoriert/).first()).toBeVisible();
  });

  test('eine getippte Nachricht nimmt den Befund mit', async ({ page }) => {
    const w = await uploadZeigen(page);
    const modul = page.locator('boerdi-ui-upload');
    await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
    await expect(modul.getByText('3 Ordner, 4 Dateien').first()).toBeVisible();
    await page.locator('.chat-input').fill('Was hältst du davon?');
    await page.locator('.btn-send').click();
    await w.waitForTurns(2);
    expect(w.chatRequests().at(-1)!.ui_antwort?.daten).toMatchObject({ aktion: 'erfasst', zahlen: { inhalte: 3 } });
  });

  test('passt auf 320 px', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 700 });
    await uploadZeigen(page);
    const modul = page.locator('boerdi-ui-upload');
    await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
    await expect(modul.getByText('3 Ordner, 4 Dateien').first()).toBeVisible();
    const breite = await modul.evaluate((e) => ({ scroll: e.scrollWidth, client: e.clientWidth }));
    expect(breite.scroll).toBeLessThanOrEqual(breite.client + 1);
  });

  test('U3-2c: das Strukturdokument lesen lassen — nur diese Datei geht hoch, dann die Antwort mit Befund', async ({ page }) => {
    const w = await uploadZeigen(page, true);
    // Nach `mount`: in Playwright gewinnt die zuletzt registrierte Route (die Harness fängt sonst alles ab).
    const hochgeladen: string[] = [];
    await page.route('**/api/ui/dokumente', async (route) => {
      const rumpf = route.request().postDataBuffer()?.toString('latin1') ?? '';
      hochgeladen.push(rumpf);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        upload_id: '11111111-2222-4333-8444-555555555555', name: 'Lehrplan_Physik.pdf', format: 'pdf',
        befund: { seiten: 2, woerter: 400, abschnitte: 6, gliederung_art: 'nummeriert', warnungen: [] },
        ueberschriften_vorschau: ['1 Mechanik', '2 Optik'],
      }), headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    const modul = page.locator('boerdi-ui-upload');
    await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
    await expect(modul.getByLabel('Rolle von Lehrplan_Physik.pdf')).toHaveValue('struktur');

    await modul.getByRole('button', { name: 'Themenbaum aus dem Strukturdokument erstellen' }).click();
    await w.waitForTurns(2);
    expect(hochgeladen).toHaveLength(1);
    expect(hochgeladen[0]).toContain('name="block_id"');
    expect(hochgeladen[0]).toContain('filename="Lehrplan_Physik.pdf"');
    expect(hochgeladen[0]).not.toContain('hebel-mueller');
    const req = w.chatRequests().at(-1)!;
    expect(req.message).toBe('Themenbaum aus „Lehrplan_Physik.pdf“ erstellen');
    expect(req.ui_antwort?.daten).toMatchObject({
      aktion: 'dokument', dokument: { upload_id: '11111111-2222-4333-8444-555555555555', ziel: 'themenbaum',
        befund: { abschnitte: 6 }, vorschau: ['1 Mechanik', '2 Optik'] } });
    expect(JSON.stringify(req.ui_antwort)).not.toContain('hebel-mueller');
  });
});
