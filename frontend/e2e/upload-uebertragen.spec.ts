/**
 * Übertragen in den persönlichen Bereich (Paket U3-3b, Plan U3-3 T8) im gebauten Widget, mit
 * gemocktem Backend (`/api/ui/ablage/*`).
 *
 * Warum e2e: nur hier rechnet der echte Browser die Prüfsummen (`crypto.subtle`), schickt die echte
 * Ordnerauswahl als multipart und zeigt den Link über den Link-Weg der Shell. Dazu: ein Fehler in der
 * Mitte, Abbrechen, nur Tastatur, 320 px.
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { expect, type Page, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

function uploadBlock() {
  return {
    block_id: 'u1u2u3u4u5u6u7u8', modul: 'ui_upload', version: 1, art: 'abfragen', status: 'offen',
    daten: {
      zweck: 'sammlungsstruktur', grenzen: { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50, max_mb_ablage: 10 },
      schalter: { dokument_im_chat: false, ablage_in_wlo: true },
    },
    text: 'Hier würde ein Auswahlfeld für einen Ordner erscheinen.', antwort: null,
  };
}

const ANGELEGT: string[] = [];

function ordner(): string {
  const wurzel = mkdtempSync(join(tmpdir(), 'u33-'));
  ANGELEGT.push(wurzel);
  const physik = join(wurzel, 'Physik 7');
  // klein geschrieben: die Erfassung sortiert nach Pfad, so bleibt `hebel.pdf` vorn.
  mkdirSync(join(physik, 'optik'), { recursive: true });
  writeFileSync(join(physik, 'hebel.pdf'), '%PDF-1.7 a');
  writeFileSync(join(physik, 'optik', 'linsen.pdf'), '%PDF-1.7 bb');
  writeFileSync(join(physik, 'optik', 'notiz.txt'), 'Text');
  return physik;
}

interface Aufruf { schritt: string; json?: Record<string, unknown>; index?: string; groesse?: number }

/** Das Backend der Ablage: Vorschau aus der Freigabe, je Datei `stored` (oder `fehler` je Index). */
async function ablageBackend(page: Page, fehler: Record<number, { status: number; detail: string }> = {}) {
  const aufrufe: Aufruf[] = [];
  await page.route('**/api/ui/ablage/*', async (route) => {
    const schritt = new URL(route.request().url()).pathname.split('/').pop() ?? '';
    if (schritt === 'datei') {
      const rumpf = route.request().postDataBuffer()?.toString('latin1') ?? '';
      const index = /name="index"\r\n\r\n(\d+)/.exec(rumpf)?.[1] ?? '';
      aufrufe.push({ schritt, index, groesse: rumpf.length });
      const f = fehler[Number(index)];
      if (f) return route.fulfill({ status: f.status, json: { detail: f.detail } });
      return route.fulfill({ json: { index: Number(index), stand: 'stored', node_id: `n-${index}`,
        link: `https://repo.test/edu-sharing/components/render/n-${index}`, ordner_verweigert: false, bereits: false } });
    }
    const json = route.request().postDataJSON() as Record<string, unknown>;
    aufrufe.push({ schritt, json });
    if (schritt === 'abschluss') return route.fulfill({ json: { stand: 'stored', bereits: false } });
    const eintraege = (json['eintraege'] as { titel: string; art: string; groesse: number }[])
      .map((e, index) => ({ index, titel: e.titel, art: e.art, groesse: e.groesse, name: `${e.titel}.${e.art}` }));
    return route.fulfill({ json: { batch_token: 'tok-1234567890', layout: 'folder', ordner: json['ordner'],
      gesamt: eintraege.reduce((s, e) => s + e.groesse, 0), eintraege } });
  });
  return aufrufe;
}

/** Erst einbinden, dann die Route der Ablage: Playwright fragt die zuletzt registrierte Route zuerst. */
async function bisVorschau(page: Page, fehler: Record<number, { status: number; detail: string }> = {}) {
  const w = await mount(page);
  const aufrufe = await ablageBackend(page, fehler);
  w.enqueue(
    chatResponse({ content: 'Wähle deinen Ordner aus.', ui: { ui_bloecke: [uploadBlock()] } }),
    chatResponse({ content: 'Schön, die Dateien liegen in deinem Bereich.' }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Ich will meine Physik-Materialien in WLO ablegen');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  const modul = page.locator('boerdi-ui-upload');
  await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
  await expect(modul.getByText('3 Dateien kannst du in deinen persönlichen Bereich in WLO übertragen', { exact: false }).first()).toBeVisible();
  return { w, modul, aufrufe };
}

test.describe('ui_upload Übertragen in WLO (U3-3b)', () => {
  test.afterAll(() => { for (const d of ANGELEGT.splice(0)) rmSync(d, { recursive: true, force: true }); });

  test('Ordner → Vorschau → Übertragen → Ergebnis mit Link → im Chat weiter, ohne Kennungen', async ({ page }) => {
    const { w, modul, aufrufe } = await bisVorschau(page);
    await modul.getByRole('button', { name: 'Übertragen vorbereiten …' }).click();
    await expect(modul.getByText('neuer Ordner „Physik 7“', { exact: false }).first()).toBeVisible();
    const freigabe = aufrufe[0].json!;
    expect(freigabe['ordner']).toBe('Physik 7');
    const eintraege = freigabe['eintraege'] as { titel: string; sha256: string }[];
    expect(eintraege.map((e) => e.titel)).toEqual(['hebel', 'linsen', 'notiz']);
    // die echte Prüfsumme des Browsers: sha256("%PDF-1.7 a")
    expect(eintraege[0].sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(JSON.stringify(freigabe)).not.toContain('optik/');

    await modul.getByRole('button', { name: 'Jetzt übertragen' }).click();
    await expect(modul.getByText('3 von 3 Dateien in WLO abgelegt.').first()).toBeVisible();
    expect(aufrufe.map((a) => a.schritt)).toEqual(['vorbereiten', 'datei', 'datei', 'datei', 'abschluss']);
    expect(aufrufe.filter((a) => a.schritt === 'datei').map((a) => a.index)).toEqual(['0', '1', '2']);
    const link = modul.getByRole('link', { name: 'hebel.pdf in WLO ansehen' });
    await expect(link).toHaveAttribute('href', /^https:\/\/repo\.test\/edu-sharing\/components\/render\/n-0/);

    await modul.getByRole('button', { name: 'Im Chat weitermachen' }).click();
    await w.waitForTurns(2);
    const req = w.chatRequests().at(-1)!;
    expect(req.message).toBe('3 von 3 Dateien in meinen persönlichen Bereich in WLO übertragen.');
    expect(req.ui_antwort?.daten).toMatchObject({ aktion: 'uebertragen',
      ablage: { gesamt: 3, abgelegt: 3, vorgang_abgelegt: true } });
    expect(JSON.stringify(req.ui_antwort)).not.toContain('n-0');
    expect(JSON.stringify(req.ui_antwort)).not.toContain('hebel');
  });

  test('ein Fehler in der Mitte: die anderen Dateien gehen weiter', async ({ page }) => {
    const { modul, aufrufe } = await bisVorschau(page, { 1: { status: 422, detail: 'passt_nicht' } });
    await modul.getByRole('button', { name: 'Übertragen vorbereiten …' }).click();
    await modul.getByRole('button', { name: 'Jetzt übertragen' }).click();
    await expect(modul.getByText('2 von 3 Dateien in WLO abgelegt.').first()).toBeVisible();
    await expect(modul.getByText('nicht abgelegt: Die Datei passt nicht zur Freigabe', { exact: false }).first()).toBeVisible();
    expect(aufrufe.filter((a) => a.schritt === 'datei')).toHaveLength(3);
  });

  test('Abbrechen in der Vorschau sendet keine Datei', async ({ page }) => {
    const { modul, aufrufe } = await bisVorschau(page);
    await modul.getByRole('button', { name: 'Übertragen vorbereiten …' }).click();
    await modul.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(modul.getByRole('button', { name: 'Übertragen vorbereiten …' })).toBeVisible();
    expect(aufrufe.map((a) => a.schritt)).toEqual(['vorbereiten']);
  });

  test('nur mit der Tastatur', async ({ page }) => {
    const { modul } = await bisVorschau(page);
    await modul.getByRole('button', { name: 'Übertragen vorbereiten …' }).focus();
    await page.keyboard.press('Enter');
    // Der Fokus geht auf die Vorschau, nicht verloren (body).
    await expect(modul.locator('[data-fokus="s:ablage"]')).toBeFocused();
    await expect(modul.locator('[data-fokus="s:ablage"]')).toContainText('neuer Ordner „Physik 7“');
    await modul.getByRole('button', { name: 'Jetzt übertragen' }).focus();
    await page.keyboard.press('Space');
    await expect(modul.getByText('3 von 3 Dateien in WLO abgelegt.').first()).toBeVisible();
    // Review U3-3b, Befund 10: wohin der Fokus nach dem Senden geht — auf das Ergebnis, nie auf body.
    await expect(modul.locator('[data-fokus="s:ablage"]')).toBeFocused();
    await expect(modul.locator('[data-fokus="s:ablage"]')).toContainText('3 von 3 Dateien');
    // Befund 9: der nächste Tab-Halt ist der rollbare Bereich der Liste.
    await page.keyboard.press('Tab');
    await expect(modul.getByRole('region', { name: 'Dateien der Übertragung' })).toBeFocused();
  });

  test('passt auf 320 px', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    const { modul } = await bisVorschau(page);
    await modul.getByRole('button', { name: 'Übertragen vorbereiten …' }).click();
    await modul.getByRole('button', { name: 'Jetzt übertragen' }).click();
    await expect(modul.getByText('3 von 3 Dateien in WLO abgelegt.').first()).toBeVisible();
    const ueber = await modul.evaluate((el) => {
      const r = el.shadowRoot!.querySelector('.u') as HTMLElement;
      return r.scrollWidth - r.clientWidth;
    });
    expect(ueber).toBeLessThanOrEqual(1);
  });
});
