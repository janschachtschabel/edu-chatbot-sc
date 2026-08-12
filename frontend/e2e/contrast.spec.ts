/**
 * U4d — Kontrast-Durchgang hell **und** dunkel.
 *
 * U4b und U4c haben Kopfzeile und Ecken auf M3-Token gestellt. Damit folgt fast
 * jede Farbe des Widgets dem `color-scheme` der Gastseite — und genau das ist
 * die neue Fehlerquelle: eine Farbe, die hell gut aussieht, kann dunkel
 * unlesbar sein, ohne dass irgendein Test es merkt. Ein Durchgang von Hand
 * belegt einen Stand; dieser Lauf belegt ihn bei **jeder** Änderung.
 *
 * Der Schalter aus U4a (`theme="light|dark"`) ist hier das Messgerät: er
 * stellt beide Schemata her, ohne die Systemeinstellung des Rechners zu drehen.
 *
 * Zwei Oberflächen, weil die Karten zwei völlig verschiedene Bauteile haben:
 * die Ergebnis-Boxen (Vorgabe) und das flache Kachelraster
 * (`inline-result-grouping="false"`) samt Lizenz-Abzeichen und Blätterleiste.
 *
 * Der letzte Test ist der wichtigste: er zwingt einen zu schwachen Text ins
 * Bild und verlangt, dass der Messer ihn findet. Ohne ihn wären die anderen
 * auch dann grün, wenn die Messung gar nichts misst.
 */
import { expect, test } from '@playwright/test';

import { card, chatResponse, debugInfo } from './fixtures/backend-payloads';
import { bericht, textkontraste, verstoesse } from './fixtures/contrast';
import { mount } from './fixtures/harness';

const OBERFLAECHEN = [
  { name: 'Ergebnis-Boxen', gruppiert: 'true', anker: '.result-group' },
  { name: 'Kachelraster', gruppiert: 'false', anker: '.wlo-card' },
] as const;

/**
 * Einen Turn mit möglichst vielen Oberflächen rendern: Begrüßung, Nutzer-Blase,
 * Bot-Blase mit Markdown, Karten, Quick-Replies und das Debug-Feld. Je mehr
 * davon im Bild steht, desto mehr Farbpaare misst der Lauf.
 */
async function volleOberflaeche(
  page: import('@playwright/test').Page,
  theme: string,
  gruppiert: string,
  anker: string,
) {
  const w = await mount(page, { attrs: { theme, 'inline-result-grouping': gruppiert } });
  w.enqueue(chatResponse({
    content: '## Passende Materialien\n\nHier ist eine **Auswahl** für dich:\n\n'
      + '- Übungen zum Kürzen\n- Ein Erklärvideo\n\nMehr auf [WirLernenOnline](https://host.test/).',
    cards: [
      card(),
      card({ node_id: 'n-2', title: 'Brüche kürzen', license: 'CC_BY_SA' }),
      card({ node_id: 'n-3', title: 'Erklärvideo Bruchrechnen', node_type: 'ccm:map' }),
    ],
    quick_replies: ['Zeig mir mehr', 'Erkläre den ersten Treffer'],
    follow_up: 'Soll ich dir daraus einen Lernpfad bauen?',
    debug: debugInfo(),
  }));
  await w.open();

  await page.locator('.chat-input').fill('Bruchrechnen');
  await page.locator('.btn-send').click();
  await page.locator(anker).first().waitFor();

  // Das Debug-Feld trägt die meisten Farben, die NICHT aus einer M3-Rolle
  // kommen — ohne diesen Klick bliebe genau der Teil ungemessen.
  const debug = page.locator('.boerdi-action-btn[aria-label="Debug an"]');
  if (await debug.count()) {
    await debug.first().click();
    await page.locator('.debug-panel').first().waitFor();
  }
  return w;
}

for (const flaeche of OBERFLAECHEN) {
  for (const theme of ['light', 'dark'] as const) {
    test(`kein Text unter SC 1.4.3 — ${flaeche.name}, ${theme}`, async ({ page }) => {
      await volleOberflaeche(page, theme, flaeche.gruppiert, flaeche.anker);

      const befunde = await textkontraste(page);
      // Untergrenze gegen einen Messer, der ins Leere greift: ein leerer Lauf
      // wäre sonst der beste aller Läufe.
      expect(befunde.length, 'zu wenig gemessene Texte — rendert die Oberfläche?')
        .toBeGreaterThan(35);
      expect(befunde.filter((b) => b.unmessbar), 'Fläche nicht messbar').toEqual([]);

      const funde = verstoesse(befunde);
      expect(funde, `Kontrast zu schwach (${flaeche.name}, ${theme}):\n${bericht(funde)}`)
        .toEqual([]);
    });
  }
}

test('der Messer erkennt einen zu schwachen Text', async ({ page }) => {
  await volleOberflaeche(page, 'light', 'true', '.result-group');

  // Grau auf der hellen Blasenfläche — knapp über dem, was man noch „sieht",
  // klar unter den geforderten 4,5:1.
  await page.evaluate(() => {
    const shell = document.querySelector('boerdi-chat')!.shadowRoot!
      .querySelector('boerdi-chat-shell')!;
    const stil = document.createElement('style');
    stil.textContent = '.msg-content { color: #9a9a9a !important; }';
    (shell.shadowRoot ?? shell).appendChild(stil);
  });

  const funde = verstoesse(await textkontraste(page));
  expect(funde.length, 'der eingeschleuste Graustich blieb unbemerkt').toBeGreaterThan(0);
  expect(funde.some((f) => f.sel.includes('msg-content'))).toBe(true);
});
