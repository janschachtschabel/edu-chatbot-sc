/**
 * Querschnitts-Review 2026-11-06, M1/M2: zwei Module zugleich — `ui_upload` überträgt, `ui_fortschritt`
 * holt währenddessen ein fertiges Auftragsergebnis ab. Das Abholen ist kein Zug der Person: es schließt
 * die offene Frage des Uploads nicht (`automatisch: true`), und der Stapel läuft zu Ende.
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { expect, type Page, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const ANGELEGT: string[] = [];

function ordner(): string {
  const wurzel = mkdtempSync(join(tmpdir(), 'qr-'));
  ANGELEGT.push(wurzel);
  const physik = join(wurzel, 'Physik 7');
  mkdirSync(physik, { recursive: true });
  writeFileSync(join(physik, 'hebel.pdf'), '%PDF-1.7 a');
  writeFileSync(join(physik, 'linse.pdf'), '%PDF-1.7 bb');
  return physik;
}

const BLOECKE = [
  {
    block_id: 'u1u2u3u4u5u6u7u8', modul: 'ui_upload', version: 1, art: 'abfragen', status: 'offen',
    daten: {
      zweck: 'sammlungsstruktur', grenzen: { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50, max_mb_ablage: 10 },
      schalter: { dokument_im_chat: false, ablage_in_wlo: true },
    },
    text: 'Ordner wählen', antwort: null,
  },
  {
    block_id: 'f1f2f3f4f5f6f7f8', modul: 'ui_fortschritt', version: 1, art: 'anzeigen',
    daten: { ablauf: 'lesen', kuerzel: '0123456789ab', text: 'Ich lasse das Dokument lesen.' },
    text: 'Ich lasse das Dokument lesen.', antwort: null,
  },
];

/** Ablage mit angehaltener erster Datei — sie geht erst weiter, wenn `weiter()` gerufen wird. */
async function ablage(page: Page) {
  let weiter: () => void = () => undefined;
  const gate = new Promise<void>((r) => { weiter = r; });
  const dateien: string[] = [];
  await page.route('**/api/ui/ablage/*', async (route) => {
    const schritt = new URL(route.request().url()).pathname.split('/').pop() ?? '';
    if (schritt === 'datei') {
      const index = /name="index"\r\n\r\n(\d+)/.exec(route.request().postDataBuffer()?.toString('latin1') ?? '')?.[1] ?? '';
      dateien.push(index);
      if (index === '0') await gate;
      return route.fulfill({ json: { index: Number(index), stand: 'stored', node_id: `n-${index}`, link: null,
        ordner_verweigert: false, bereits: false } });
    }
    if (schritt === 'abschluss') return route.fulfill({ json: { stand: 'stored', bereits: false } });
    const json = route.request().postDataJSON() as { ordner: string; eintraege: { titel: string; art: string; groesse: number }[] };
    return route.fulfill({ json: { batch_token: 'tok-1234567890', layout: 'ordner', ordner: json.ordner,
      gesamt: 0, eintraege: json.eintraege.map((e, index) => ({ index, ...e, name: `${e.titel}.${e.art}` })) } });
  });
  await page.route('**/api/ui/auftrag/stand', (route) => route.fulfill({ json: { stand: 'fertig' } }));
  return { weiter: () => weiter(), dateien };
}

test.describe('ui_upload und ui_fortschritt zugleich (Querschnitts-Review M1)', () => {
  test.afterAll(() => { for (const d of ANGELEGT.splice(0)) rmSync(d, { recursive: true, force: true }); });

  test('das Abholen während einer Übertragung schließt die Frage des Uploads nicht', async ({ page }) => {
    const w = await mount(page);
    const { weiter, dateien } = await ablage(page);
    w.enqueue(
      chatResponse({ content: 'Wähle deinen Ordner. Nebenbei lese ich das Dokument.', ui: { ui_bloecke: BLOECKE } }),
      chatResponse({ content: 'Gelesen.' }),
    );
    await w.open();
    await page.locator('.chat-input').fill('Leg meine Physik-Sachen ab');
    await page.locator('.btn-send').click();
    await w.waitForTurns(1);

    const upload = page.locator('boerdi-ui-upload');
    await upload.locator('input[webkitdirectory]').setInputFiles(ordner());
    await upload.getByRole('button', { name: 'Übertragen vorbereiten …' }).click();
    await upload.getByRole('button', { name: 'Jetzt übertragen' }).click();
    await expect.poll(() => dateien.length).toBe(1);

    // Während die erste Datei hängt: das Ergebnis des Auftrags wird abgeholt.
    await page.locator('boerdi-ui-fortschritt').getByRole('button', { name: 'Jetzt prüfen' }).click();
    await w.waitForTurns(2);
    const abholen = w.chatRequests().at(-1)!;
    expect(abholen.action).toBe('ablauf_auftrag_pruefen');
    expect(abholen.action_params).toEqual({ ablauf: 'lesen', automatisch: true });
    await expect(page.getByText('Gelesen.')).toBeVisible();

    weiter();
    await expect(upload.getByText('2 von 2 Dateien in WLO abgelegt.').first()).toBeVisible();
    expect(dateien).toEqual(['0', '1']);
    await expect(upload.getByText('Nicht verwendet')).toHaveCount(0);
    // Die Frage ist noch offen: die Person kann mit den Zahlen im Chat weitermachen.
    await expect(upload.getByRole('button', { name: 'Im Chat weitermachen' })).toBeEnabled();
  });

  test('bei reduzierter Bewegung steht der unbestimmte Balken still', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const w = await mount(page);
    await page.route('**/api/ui/auftrag/stand', (route) => route.fulfill({ json: { stand: 'laeuft' } }));
    w.enqueue(chatResponse({ content: 'Läuft.', ui: { ui_bloecke: [BLOECKE[1]] } }));
    await w.open();
    await page.locator('.chat-input').fill('Lies');
    await page.locator('.btn-send').click();
    await w.waitForTurns(1);
    const balken = page.locator('boerdi-ui-fortschritt').locator('progress');
    await expect(balken).toBeVisible();
    expect(await balken.evaluate((b) => getComputedStyle(b).appearance)).toBe('none');
  });
});
