/**
 * Ein Upload-Weg (Plan 2026-11-17, Paket U4, Teil b) im gebauten Widget: nach der Auswahl die Frage
 * „Wo sollen die Dateien verarbeitet werden?“ (Chips als echte Radioknöpfe), ein Knopf je Ort (Plan
 * 2026-11-20, P2: „Hier lesen“ bzw. „Weiter zur Vorschau“).
 *
 * Warum e2e: nur hier bedient der echte Browser die Radiogruppe mit den Pfeiltasten (jsdom kennt das
 * nicht), schickt die echte Ordnerauswahl je Datei als multipart mit der Rolle an
 * `POST /api/ui/dokumente` und prüft die Antwort `bereitgestellt` mit Ort chat. Dazu die Grenze
 * „Hier im Chat“ (vorab und an der Sitzungsgrenze des Servers), 320 px und 200 % Zoom.
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { expect, type Page, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const GRENZEN = {
  max_dateien: 500, max_tiefe: 8, max_mb_datei: 50, max_mb_ablage: 50,
  lokal_max_dateien: 10, lokal_max_mb_gesamt: 50, lokal_max_mb_datei: 50, lokal_aufbewahrung_h: 24,
};
const ANONYM = {
  vorauswahl: 'chat', chat: { geht: true, ueber_grenze: 'ueber_grenze_anmelden' },
  wlo: { geht: false, grund: 'nur_angemeldet' }, namen: { geht: true },
};
const ANGEMELDET = {
  vorauswahl: 'wlo', chat: { geht: true, ueber_grenze: 'ueber_grenze' }, wlo: { geht: true }, namen: { geht: true },
};

function uploadBlock(orte: Record<string, unknown>, grenzen: Record<string, unknown> = GRENZEN) {
  return {
    block_id: 'u1u2u3u4u5u6u7u8', modul: 'ui_upload', version: 1, art: 'abfragen', status: 'offen',
    daten: {
      zweck: 'bereitstellen', grenzen, orte,
      schalter: { dokument_im_chat: true, ablage_in_wlo: orte === ANGEMELDET },
    },
    text: 'Hier würde ein Auswahlfeld für einen Ordner erscheinen.', antwort: null,
  };
}

const ANGELEGT: string[] = [];

/** Lehrplan (wird Strukturdokument), zwei Inhalte, Folien (nicht lesbar). */
function ordner(): string {
  const wurzel = mkdtempSync(join(tmpdir(), 'u4-'));
  ANGELEGT.push(wurzel);
  const physik = join(wurzel, 'Physik 7');
  mkdirSync(join(physik, 'mechanik'), { recursive: true });
  writeFileSync(join(physik, 'Lehrplan_Physik.pdf'), '%PDF-1.7 plan');
  writeFileSync(join(physik, 'mechanik', 'hebel.pdf'), '%PDF-1.7 a');
  writeFileSync(join(physik, 'mechanik', 'kraft.docx'), 'PK docx');
  writeFileSync(join(physik, 'mechanik', 'folien.pptx'), 'PK pptx');
  return physik;
}

/** `voll`: ab diesem Upload (1-basiert) weist der Server mit 409 `grenze_anzahl` ab (Sitzung voll);
 *  `tor`: der erste Upload antwortet erst, wenn es offen ist. */
async function feldZeigen(page: Page, block: ReturnType<typeof uploadBlock>, voll = Infinity, tor?: Promise<void>) {
  const w = await mount(page);
  // Nach `mount`: in Playwright gewinnt die zuletzt registrierte Route.
  const hoch: { name: string; rolle: string; rumpf: string }[] = [];
  await page.route('**/api/ui/dokumente', async (route) => {
    const rumpf = route.request().postDataBuffer()?.toString('latin1') ?? '';
    const name = /filename="([^"]+)"/.exec(rumpf)?.[1] ?? '';
    const rolle = /name="rolle"\r\n\r\n([a-z]+)/.exec(rumpf)?.[1] ?? '';
    hoch.push({ name, rolle, rumpf });
    if (hoch.length === 1 && tor) await tor;
    if (hoch.length >= voll) {
      await route.fulfill({ status: 409, json: { detail: 'grenze_anzahl' }, headers: { 'Access-Control-Allow-Origin': '*' } });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      upload_id: `11111111-2222-4333-8444-55555555555${hoch.length}`, name, format: 'pdf', rolle,
      befund: { seiten: 1, woerter: 100, abschnitte: 2, gliederung_art: 'teile', warnungen: [] },
      ueberschriften_vorschau: [],
    }), headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  w.enqueue(
    chatResponse({ content: 'Wähle deinen Ordner aus.', ui: { ui_bloecke: [block] } }),
    chatResponse({ content: 'Danke, ich sehe deine Dateien.' }),
  );
  await w.open();
  await page.locator('.chat-input').fill('Ich habe Physik-Materialien');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);
  const modul = page.locator('boerdi-ui-upload');
  await modul.locator('input[webkitdirectory]').setInputFiles(ordner());
  await expect(modul.getByText('2 Ordner, 4 Dateien').first()).toBeVisible();
  return { w, modul, hoch };
}

test.describe('ui_upload: ein Upload-Weg (Paket U4)', () => {
  test.afterAll(() => { for (const d of ANGELEGT.splice(0)) rmSync(d, { recursive: true, force: true }); });

  test('Hier im Chat: je lesbare Datei mit Rolle hochladen, eine Antwort mit Ort chat', async ({ page }) => {
    const { w, modul, hoch } = await feldZeigen(page, uploadBlock(ANONYM));
    const gruppe = modul.getByRole('group', { name: 'Wo sollen die Dateien verarbeitet werden?' });
    await expect(gruppe.getByRole('radio', { name: 'Nur hier im Chat lesen' })).toBeChecked();
    // Review P2: ohne `erschliessen` im Block nur „ablegen“; der Weg zur Anmeldung ist der Konto-Knopf
    await expect(gruppe.getByRole('radio', { name: 'In WLO ablegen', exact: true })).toBeDisabled();
    await expect(modul.getByText('nicht wählbar – melde dich über den Konto-Knopf unten an')).toBeVisible();
    // P2: ohne Anmeldung kein Häkchen
    await expect(modul.getByRole('checkbox')).toHaveCount(0);
    await expect(modul.getByText('1 Datei kann der Chat nicht lesen – davon geht nur der Name mit.')).toBeVisible();

    await modul.getByRole('button', { name: 'Hier lesen' }).click();
    await w.waitForTurns(2);
    expect(hoch.map((x) => [x.name, x.rolle])).toEqual([
      ['Lehrplan_Physik.pdf', 'struktur'], ['hebel.pdf', 'inhalt'], ['kraft.docx', 'inhalt']]);
    expect(hoch.every((x) => x.rumpf.includes('name="block_id"'))).toBe(true);
    const req = w.chatRequests().at(-1)!;
    expect(req.message).toBe('Hier im Chat bereitgestellt: 3 Dateien.');
    const daten = req.ui_antwort?.daten as { aktion: string; ort: string; dateien: { rolle: string; upload_id: string }[] };
    expect(daten).toMatchObject({ aktion: 'bereitgestellt', ort: 'chat' });
    expect(daten.dateien.map((d) => d.rolle)).toEqual(['struktur', 'inhalt', 'inhalt']);
    expect(JSON.stringify(req.ui_antwort)).not.toContain('%PDF');
  });

  test('nur mit der Tastatur: Ort per Pfeiltaste wählen, „Hier lesen“ mit Enter', async ({ page }) => {
    let oeffnen: () => void = () => undefined;
    const tor = new Promise<void>((r) => { oeffnen = r; });
    const { w, modul, hoch } = await feldZeigen(page, uploadBlock(ANGEMELDET), Infinity, tor);
    const wlo = modul.getByRole('radio', { name: 'In WLO ablegen', exact: true });
    const chat = modul.getByRole('radio', { name: 'Nur hier im Chat lesen' });
    await expect(wlo).toBeChecked();
    await wlo.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(chat).toBeChecked();
    await expect(chat).toBeFocused();
    await expect(modul.getByText('er behält nur ihren Text, bis zu 24 Stunden nach der letzten Nutzung', { exact: false })).toBeVisible();
    await page.keyboard.press('ArrowRight');
    await expect(wlo).toBeChecked();
    await page.keyboard.press('ArrowLeft');
    await modul.getByRole('button', { name: 'Hier lesen' }).focus();
    await page.keyboard.press('Enter');
    // der Fokus ging vom verschwundenen Knopf auf den Stand „Datei k von n“ — im Modul, nie auf body
    // (Review der Oberfläche, NIT 11: geprüft im Schatten-DOM)
    const fokus = () => modul.evaluate((el) => (el.shadowRoot!.activeElement as HTMLElement | null)?.dataset['fokus']);
    await expect.poll(fokus).toBe('s:chat');
    oeffnen();
    await expect.poll(() => hoch.length).toBe(3);
    await w.waitForTurns(2);
    // nach dem Zug setzt das Widget den Fokus in sein Eingabefeld
    expect(await page.evaluate(() => document.activeElement?.tagName.toLowerCase())).not.toBe('body');
  });

  test('Sitzung voll bei Datei 2: der Lauf endet, „Mit den gelesenen weiter“ antwortet mit Datei 1', async ({ page }) => {
    const { w, modul, hoch } = await feldZeigen(page, uploadBlock(ANONYM), 2);
    await modul.getByRole('button', { name: 'Hier lesen' }).click();
    await expect(modul.getByText('Mach mit den gelesenen weiter oder sende nur die Namen.', { exact: false })).toBeVisible();
    await expect(modul.getByText('Bereits gelesene Dateien bleiben bis zu 24 Stunden nach der letzten Nutzung hier im Chat', { exact: false })).toBeVisible();
    // Datei 3 ging nicht mehr hoch
    expect(hoch).toHaveLength(2);
    await expect(modul.getByRole('button', { name: 'Ohne diese weiter' })).toHaveCount(0);
    await modul.getByRole('button', { name: 'Mit den gelesenen weiter' }).click();
    await w.waitForTurns(2);
    const daten = w.chatRequests().at(-1)!.ui_antwort?.daten as { ort: string; dateien: { rolle: string }[] };
    expect(daten.ort).toBe('chat');
    expect(daten.dateien.map((d) => d.rolle)).toEqual(['struktur']);
  });

  test('über der Grenze „Nur hier im Chat lesen“: gesperrt mit Grund, „Nur die Dateinamen senden“ ist der Weg', async ({ page }) => {
    const { w, modul, hoch } = await feldZeigen(page, uploadBlock(ANONYM, { ...GRENZEN, lokal_max_dateien: 2 }));
    await expect(modul.getByRole('radio', { name: 'Nur hier im Chat lesen' })).toBeDisabled();
    await expect(modul.getByText('nicht wählbar – zu viele Dateien für hier (höchstens 2) – mit Anmeldung über WLO')).toBeVisible();
    await expect(modul.getByRole('button', { name: 'Hier lesen' })).toHaveCount(0);
    await modul.getByRole('button', { name: 'Nur die Dateinamen senden (der Inhalt bleibt auf deinem Gerät)' }).click();
    await w.waitForTurns(2);
    expect(hoch).toHaveLength(0);
    expect(w.chatRequests().at(-1)!.ui_antwort?.daten).toMatchObject({ aktion: 'bereitgestellt', ort: 'namen' });
  });

  test('passt auf 320 px — die Chips brechen um', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 760 });
    const { modul } = await feldZeigen(page, uploadBlock(ANGEMELDET));
    await expect(modul.getByRole('radio', { name: 'Nur hier im Chat lesen' })).toBeVisible();
    const ueber = await modul.evaluate((el) => {
      const r = el.shadowRoot!.querySelector('.u') as HTMLElement;
      return r.scrollWidth - r.clientWidth;
    });
    expect(ueber).toBeLessThanOrEqual(1);
    // Zielgröße der Chips (WCAG 2.5.8: mindestens 24 px)
    const hoehe = await modul.evaluate((el) => (el.shadowRoot!.querySelector('.u__chip') as HTMLElement).getBoundingClientRect().height);
    expect(hoehe).toBeGreaterThanOrEqual(24);
  });

  // WCAG 1.4.4/1.4.10: 200 % Zoom eines 1280×800-Bildschirms ist ein Fenster von 640×400 CSS-Pixeln
  test('200 % Zoom (640 × 400 CSS-Pixel): nichts läuft seitlich über, der Hauptknopf bleibt erreichbar', async ({ page }) => {
    await page.setViewportSize({ width: 640, height: 400 });
    const { modul } = await feldZeigen(page, uploadBlock(ANGEMELDET));
    const ueber = await modul.evaluate((el) => {
      const r = el.shadowRoot!.querySelector('.u') as HTMLElement;
      return r.scrollWidth - r.clientWidth;
    });
    expect(ueber).toBeLessThanOrEqual(1);
    const hochladen = modul.getByRole('button', { name: 'Weiter zur Vorschau' });
    await hochladen.scrollIntoViewIfNeeded();
    await expect(hochladen).toBeInViewport();
  });
});
