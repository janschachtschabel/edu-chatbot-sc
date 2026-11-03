/**
 * Entscheidung (Paket U1-d1): das erste abfragende UI-Modul im gebauten Widget.
 *
 * Warum e2e: Der Weg geht über drei Stellen, die Unit-Tests nur einzeln sehen — das Modul (native
 * Radio-Gruppe, Tastatur), der eigene Host des Blocks (Fähigkeit `antworten`) und den Sendeweg der
 * Shell (`ui_antwort` im Rumpf, Nutzerblase = lesbare Fassung). Danach ist der Block nur lesend.
 */
import { expect, test } from '@playwright/test';

import { boxkante, luecke, textkante, TOLERANZ_PX } from './fixtures/abstaende';
import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

const FRAGE = {
  frage: 'Für welche Klassenstufe?',
  optionen: [
    { id: 'klasse_5_6', label: 'Klasse 5–6' },
    { id: 'klasse_7_8', label: 'Klasse 7–8', hinweis: 'mit Vorwissen' },
  ],
};

function frageBlock(daten: Record<string, unknown> = FRAGE, blockId = 'a1b2c3d4e5f60718') {
  return {
    block_id: blockId, modul: 'ui_entscheidung', version: 1, art: 'abfragen', status: 'offen',
    daten,
    text: 'Für welche Klassenstufe?\n\n1. Klasse 5–6\n2. Klasse 7–8 — mit Vorwissen',
    antwort: null,
  };
}

async function frageStellen(page: import('@playwright/test').Page, daten: Record<string, unknown> = FRAGE) {
  const w = await mount(page);
  w.enqueue(
    chatResponse({ content: 'Kurz nachgefragt:', ui: { ui_bloecke: [frageBlock(daten)] } }),
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

// ── Senkrechter Rhythmus (2026-11-03) ────────────────────────────────────────────────────────────
// Rückmeldung: „der Abstand vom Text (Frage) zur ersten Option etwa so groß wie von Option 1 zu
// Option 2“. Gemessen am sichtbaren Weißraum zwischen den Textzeilen (fixtures/abstaende.ts), in
// voller Breite und bei 320 px. Daten wie die Beispiele im manifest.json.

const EINZELWAHL = {
  frage: 'Für welche Klassenstufe soll das Arbeitsblatt sein?',
  optionen: [
    { id: 'klasse_5_6', label: 'Klasse 5–6' },
    { id: 'klasse_7_8', label: 'Klasse 7–8' },
    { id: 'klasse_9_10', label: 'Klasse 9–10' },
  ],
};

const MEHRFACH = {
  frage: 'Welche Formate passen für deine Stunde?',
  optionen: [
    { id: 'video', label: 'Video', hinweis: 'kurze Erklärfilme bis 10 Minuten' },
    { id: 'arbeitsblatt', label: 'Arbeitsblatt', hinweis: 'zum Ausdrucken' },
    { id: 'interaktiv', label: 'Interaktive Übung' },
  ],
  mehrfach: true,
  freitext: true,
};

for (const breite of [1280, 320]) {
  test(`Rhythmus Einzelwahl (${breite} px): Frage → erste Möglichkeit wie Möglichkeit → Möglichkeit`, async ({ page }) => {
    await page.setViewportSize({ width: breite, height: 800 });
    await frageStellen(page, EINZELWAHL);
    const box = page.locator('ui-entscheidung');
    const frage = await textkante(box.locator('.ui-entscheidung__frage'));
    const texte = box.locator('.ui-entscheidung__text');
    const [o1, o2, o3] = [await textkante(texte.nth(0)), await textkante(texte.nth(1)), await textkante(texte.nth(2))];
    const m = { frageZuOption: luecke(frage, o1), option1zu2: luecke(o1, o2), option2zu3: luecke(o2, o3) };
    test.info().annotations.push({ type: 'abstaende', description: JSON.stringify(m) });

    expect(Math.abs(m.frageZuOption - m.option1zu2), JSON.stringify(m)).toBeLessThanOrEqual(TOLERANZ_PX);
    expect(Math.abs(m.option1zu2 - m.option2zu3), JSON.stringify(m)).toBeLessThanOrEqual(TOLERANZ_PX);
    // WCAG 2.5.8: die ganze Zeile ist Ziel und bleibt mindestens 24 px hoch.
    for (const zeile of await box.locator('.ui-entscheidung__option').all()) {
      expect((await boxkante(zeile)).unten - (await boxkante(zeile)).oben).toBeGreaterThanOrEqual(24);
    }
  });

  test(`Rhythmus Mehrfachwahl mit Hinweisen und Freitext (${breite} px)`, async ({ page }) => {
    await page.setViewportSize({ width: breite, height: 800 });
    await frageStellen(page, MEHRFACH);
    const box = page.locator('ui-entscheidung');
    const frage = await textkante(box.locator('.ui-entscheidung__frage'));
    const anleitung = await textkante(box.locator('.ui-entscheidung__anleitung'));
    const texte = box.locator('.ui-entscheidung__text');
    const [o1, o2, o3] = [await textkante(texte.nth(0)), await textkante(texte.nth(1)), await textkante(texte.nth(2))];
    const freitextLabel = await textkante(box.locator('.ui-entscheidung__freitext-label'));
    const feld = await boxkante(box.locator('.ui-entscheidung__freitext'));
    const knopf = await boxkante(box.locator('.ui-entscheidung__senden'));
    const m = {
      frageZuAnleitung: luecke(frage, anleitung),
      anleitungZuOption: luecke(anleitung, o1),
      option1zu2: luecke(o1, o2),
      option2zu3: luecke(o2, o3),
      optionZuFreitext: luecke(o3, freitextLabel),
      labelZuFeld: luecke(freitextLabel, feld),
      feldZuKnopf: luecke(feld, knopf),
    };
    test.info().annotations.push({ type: 'abstaende', description: JSON.stringify(m) });
    const zeig = JSON.stringify(m);

    // Möglichkeiten mit und ohne Hinweis stehen gleich weit auseinander …
    expect(Math.abs(m.option1zu2 - m.option2zu3), zeig).toBeLessThanOrEqual(TOLERANZ_PX);
    // … der Kopf (Frage + Anleitung) steht so weit von der ersten wie die Möglichkeiten voneinander,
    expect(Math.abs(m.anleitungZuOption - m.option1zu2), zeig).toBeLessThanOrEqual(TOLERANZ_PX);
    // die Anleitung gehört zur Frage (nicht weiter weg als die Möglichkeiten voneinander),
    expect(m.frageZuAnleitung, zeig).toBeLessThanOrEqual(m.option1zu2);
    // die Ergänzung beginnt im selben Takt nach der letzten Möglichkeit,
    expect(Math.abs(m.optionZuFreitext - m.option1zu2), zeig).toBeLessThanOrEqual(TOLERANZ_PX);
    // ihr Label sitzt dichter am Feld als an den Möglichkeiten — es gehört zum Feld.
    expect(m.labelZuFeld, zeig).toBeLessThan(m.optionZuFreitext);
  });
}
