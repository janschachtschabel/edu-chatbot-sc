/**
 * Schreib-Abnahme (Plan 2026-08-11, S2/S3): der Kasten, der zeigt, WAS in WLO
 * geschrieben würde.
 *
 * Warum e2e und nicht nur Unit-Tests: Der ganze Zweck dieser Scheibe ist, dass
 * der Nutzer den Text des MCP-Servers **selbst sieht** statt der Nacherzählung
 * des Modells. Unit-Tests belegen, dass das Backend das richtige Feld füllt —
 * ob es beim Menschen ankommt, belegt nur die gerenderte Seite.
 */
import { expect, test } from '@playwright/test';

import { chatResponse } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

/** Wortlaut des Servers (``previewReply``/``renderChangeSet``), gekürzt. */
const VORSCHAU = [
  'Bitte prüfen — bisher wurde nichts geändert:',
  'Legt die Sammlung „Bruchrechnung Klasse 6" an',
  'Titel: (leer) → „Bruchrechnung Klasse 6"',
  'Fach: „Mathematik" → „Mathematik, Physik"',
  '',
  'Soll ich das so ausführen? Wenn etwas nicht stimmt, sag mir, was anders sein soll.',
].join('\n');

test('die Vorschau erreicht den Nutzer wörtlich, nicht nacherzählt', async ({ page }) => {
  const w = await mount(page);
  w.enqueue(chatResponse({
    // Was das Modell sagt: EIN einordnender Satz — mehr soll es seit S4 nicht.
    content: 'Ich würde folgendes anlegen:',
    inline_documents: [{
      kind: 'schreib_vorschau',
      title: 'Änderung zur Abnahme',
      content: VORSCHAU,
      meta: {},
    }],
    quick_replies: ['Ja, so ausführen'],
  }));
  await w.open();

  await page.locator('.chat-input').fill('Leg eine Sammlung Bruchrechnung Klasse 6 an');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);

  const kasten = page.locator('.inline-document');
  await expect(kasten).toHaveCount(1);
  await expect(kasten.locator('.inline-document__title')).toHaveText('Änderung zur Abnahme');

  // Der Kern: JEDE Änderungszeile steht da — nicht eine Auswahl, die ein
  // Zusammenfasser getroffen hat. Genau die Vollständigkeit war der Auftrag.
  await expect(kasten).toContainText('bisher wurde nichts geändert');
  await expect(kasten).toContainText('Titel: (leer) → „Bruchrechnung Klasse 6"');
  await expect(kasten).toContainText('Fach: „Mathematik" → „Mathematik, Physik"');

  // Die Frage hat zwei Ausgänge, und beide sind erreichbar: der Satz im Fuß
  // lädt zum Ändern ein, der Chip ist die kürzeste Zustimmung.
  await expect(kasten).toContainText('sag mir, was anders sein soll');
  await expect(page.locator('.qr-btn', { hasText: 'Ja, so ausführen' })).toBeVisible();

  // Und der Begleittext bleibt daneben stehen — der Kasten ERSETZT die Worte
  // des Bots nicht, er belegt sie (Nutzer-Entscheid 2026-08-11).
  await expect(page.locator('.msg-bubble').last()).toContainText('Ich würde folgendes anlegen:');
});

test('der Zustimmungs-Chip sendet genau seinen Text als nächste Nachricht', async ({ page }) => {
  // Die zweite Hälfte des Wegs: Der Klick muss als gewöhnliche Nutzer-Nachricht
  // ankommen — daran hängt, dass das Modell im FOLGEZUG dasselbe Werkzeug mit
  // denselben Argumenten aufruft und die Bestätigung greift.
  const w = await mount(page);
  w.enqueue(chatResponse({
    content: 'Ich würde folgendes anlegen:',
    inline_documents: [{ kind: 'schreib_vorschau', title: 'Änderung zur Abnahme',
      content: VORSCHAU, meta: {} }],
    quick_replies: ['Ja, so ausführen'],
  }));
  w.enqueue(chatResponse({ content: 'Die Sammlung ist angelegt.' }));
  await w.open();

  await page.locator('.chat-input').fill('Leg eine Sammlung an');
  await page.locator('.btn-send').click();
  await w.waitForTurns(1);

  await page.locator('.qr-btn', { hasText: 'Ja, so ausführen' }).click();
  await w.waitForTurns(2);

  expect(w.turnRequests()[1].message).toBe('Ja, so ausführen');
});
