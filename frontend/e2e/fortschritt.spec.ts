/**
 * `ui_fortschritt` (Paket K1b) im gebauten Widget, mit gemocktem Backend (`/api/ui/auftrag/stand`).
 *
 * Warum e2e: nur hier lädt das echte Bündel nach (SRI), fragt mit der echten Uhr nach und schickt das
 * Abholen über den echten Zug-Weg der Shell (Direktaktion `ablauf_auftrag_pruefen`, ohne Nutzerblase).
 */
import { expect, type Page, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const KUERZEL = '0123456789ab';

function fortschrittBlock() {
  return {
    block_id: 'f1f2f3f4f5f6f7f8', modul: 'ui_fortschritt', version: 1, art: 'anzeigen',
    daten: { ablauf: 'lesen', kuerzel: KUERZEL, text: 'Ich lasse das Dokument lesen.' },
    text: 'Ich lasse das Dokument lesen.', antwort: null,
  };
}

/** Das Backend des Stands: die Antworten der Reihe nach, danach „läuft“. */
async function standBackend(page: Page, antworten: Array<{ status?: number; json: Record<string, unknown> }>) {
  const fragen: Record<string, unknown>[] = [];
  await page.route('**/api/ui/auftrag/stand', async (route) => {
    fragen.push(route.request().postDataJSON() as Record<string, unknown>);
    const a = antworten.shift() ?? { json: { stand: 'laeuft' } };
    return route.fulfill({ status: a.status ?? 200, json: a.json });
  });
  return fragen;
}

/** Erst einbinden, dann die Route: Playwright fragt die zuletzt registrierte Route zuerst. */
async function mitFortschritt(page: Page, antworten: Array<{ status?: number; json: Record<string, unknown> }>) {
  const w = await mount(page);
  const fragen = await standBackend(page, antworten);
  w.enqueue(
    chatResponse({ content: 'Ich lasse das Dokument lesen.', ui: { ui_bloecke: [fortschrittBlock()] },
      quick_replies: ['__action__|Stand prüfen|ablauf_auftrag_pruefen|{"ablauf": "lesen"}'] }),
    chatResponse({ content: 'Gelesen.' }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Lies mein Dokument');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  const modul = page.locator('boerdi-ui-fortschritt');
  await expect(modul.getByText('Läuft noch …').first()).toBeVisible();
  return { w, modul, fragen };
}

test.describe('ui_fortschritt (K1b)', () => {
  test('„Jetzt prüfen“ → fertig → abgeholt im Zug, ohne Nutzerblase und ohne Job-ID', async ({ page }) => {
    const { w, modul, fragen } = await mitFortschritt(page, [{ json: { stand: 'fertig' } }]);
    await modul.getByRole('button', { name: 'Jetzt prüfen' }).click();
    await w.waitForTurns(2);
    const req = w.chatRequests().at(-1)!;
    expect(req.action).toBe('ablauf_auftrag_pruefen');
    // Querschnitts-Review M1: automatisch — das Backend schließt dabei keine offene Frage.
    expect(req.action_params).toEqual({ ablauf: 'lesen', automatisch: true });
    expect(fragen[0]).toMatchObject({ ablauf: 'lesen', kuerzel: KUERZEL });
    await expect(modul.getByText('Erledigt – die Antwort steht im Chat.').first()).toBeVisible();
    await expect(page.getByText('Gelesen.')).toBeVisible();
    await expect(page.locator('.message-row.user-row', { hasText: 'Stand prüfen' })).toHaveCount(0);
  });

  test('fragt von selbst nach (erste Frage nach 5 s) und zeigt die Uhrzeit', async ({ page }) => {
    const { modul, fragen } = await mitFortschritt(page, []);
    await expect(modul.getByText(/Zuletzt geprüft um \d{2}:\d{2} Uhr\./)).toBeVisible({ timeout: 12_000 });
    expect(fragen).toHaveLength(1);
  });

  test('ein alter Block (409) hört auf zu fragen', async ({ page }) => {
    const { modul, fragen } = await mitFortschritt(page, [{ status: 409, json: { detail: 'kein_auftrag' } }]);
    await modul.getByRole('button', { name: 'Jetzt prüfen' }).click();
    await expect(modul.getByText('Dieser Auftrag ist abgeschlossen.').first()).toBeVisible();
    await expect(modul.getByRole('button')).toHaveCount(0);
    expect(fragen).toHaveLength(1);
  });

  test('nur mit der Tastatur, auf 320 px', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    const { w, modul } = await mitFortschritt(page, [{ json: { stand: 'fertig' } }]);
    const jetzt = modul.getByRole('button', { name: 'Jetzt prüfen' });
    await jetzt.focus();
    await page.keyboard.press('Enter');
    await w.waitForTurns(2);
    // Der Knopf verschwindet — der Fokus bleibt im Modul (Rahmen), nie auf body.
    await expect(modul.locator('.f')).toBeFocused();
    const breite = await modul.evaluate((el) => el.getBoundingClientRect().width);
    expect(breite).toBeLessThanOrEqual(320);
  });
});
