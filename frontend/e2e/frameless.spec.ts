/**
 * Rahmenloser Einbau (U1, `embed-mode="frameless"`) in einem SCHMALEN
 * Container — der Fall, den ein Browser-Plugin baut: eine Seitenleiste von
 * ~440 px, darin eine eigene Kopfleiste und darunter der Chat in einem
 * Flex-Platz (`docs/browser-plugin-einbindung.md` §2).
 *
 * Warum hier und nicht im Unit-Test: der Bruch entstand aus einer Media-Query
 * plus Layout. jsdom wertet die eine nicht aus und rechnet das andere nicht —
 * ein Unit-Test hätte die Regel höchstens im Stylesheet-Text wiedererkennen
 * können, also die Schreibweise geprüft statt die Wirkung.
 *
 * Beide Tests laufen bewusst im SELBEN schmalen Viewport: der eine sichert,
 * dass das Widget im Platz bleibt, der andere, dass das Vollbild des
 * schwebenden Modus dabei nicht mit verloren geht.
 */
import { expect, test } from '@playwright/test';

import { mount } from './fixtures/harness';

// Schmal wie eine Plugin-Seitenleiste, jedenfalls unter den 480 px, ab denen die
// Vollbild-Regel des schwebenden Modus greift. Die Plugin-Entwickler nennen
// 440 px Vorgabe und 340 px Minimum — ihr `panel-host.js` liegt nicht in diesem
// Repositorium, die Zahlen sind also gemeldet und nicht hier nachgelesen.
test.use({ viewport: { width: 440, height: 720 } });

/** Gerenderte Geometrie eines Elements, in Viewport-Koordinaten. */
const kasten = (page: import('@playwright/test').Page, ort: string) =>
  page.locator(ort).first().evaluate((el) => {
    const r = el.getBoundingClientRect();
    return {
      top: r.top, bottom: r.bottom, height: r.height,
      left: r.left, right: r.right, width: r.width,
    };
  });

test('rahmenlos bleibt das Panel auch bei schmaler Weite in seinem Platz', async ({ page }) => {
  const w = await mount(page, { frameless: true });
  await w.open();

  const lage = await page.locator('.boerdi-panel').evaluate((el) => getComputedStyle(el).position);
  const panel = await kasten(page, '.boerdi-panel');
  const kopf = await kasten(page, '.wirt-kopf');
  const platz = await kasten(page, '.wirt-platz');

  // `soft`, damit ein Rückfall URSACHE und WIRKUNG in einem Lauf nennt: sonst
  // stoppt der Bericht an der ersten Zeile und die Frage „was hat der Nutzer
  // gesehen?" bleibt offen. Fehlschlagen tut der Test trotzdem.
  //
  // Die Ursache: `position: fixed; inset: 0` aus der 480-px-Regel überlebte den
  // rahmenlosen Modus, weil dessen Block width/height/max-*/radius zurücksetzt,
  // position/inset aber nicht.
  expect.soft(lage, 'Panel ist aus dem Fluss gerissen').toBe('static');

  // Und die Wirkung, die den Fehler erst teuer macht: das Panel legte sich über
  // die Kopfleiste der Gastanwendung.
  expect.soft(panel.top, 'Panel überdeckt die Leiste der Gastanwendung')
    .toBeGreaterThanOrEqual(kopf.bottom);

  // `inset: 0` pinnt VIER Seiten, also beide Achsen prüfen. Der Platz im Wirt
  // ist dafür absichtlich schmaler als das Fenster (`margin-inline`) — sonst
  // könnten diese zwei Zeilen einen waagerechten Ausbruch nicht sehen.
  expect.soft(panel.left, 'Panel steht links außerhalb seines Platzes')
    .toBeGreaterThanOrEqual(platz.left);
  expect.soft(panel.right, 'Panel steht rechts außerhalb seines Platzes')
    .toBeLessThanOrEqual(platz.right);

  // Es füllt seinen Platz — nicht mehr (kein Ausbruch) und nicht weniger (die
  // Prozentmaße greifen, sonst bliebe Luft im Kasten).
  expect.soft(Math.abs(panel.height - platz.height), 'Panel füllt die Höhe nicht genau')
    .toBeLessThan(1);
  expect.soft(Math.abs(panel.width - platz.width), 'Panel füllt die Breite nicht genau')
    .toBeLessThan(1);
});

test('im schwebenden Modus bleibt das Vollbild bei schmaler Weite erhalten', async ({ page }) => {
  // Der Gegen-Test zum Fix: die 480-px-Regel ist für DIESEN Modus gemacht und
  // muss dort unverändert greifen. Ohne diesen Test wäre „im Container bleiben"
  // auch dadurch erreichbar, dass die Regel ganz entfällt.
  const w = await mount(page);
  await w.open();

  const stil = await page.locator('.boerdi-panel').evaluate((el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { position: s.position, radius: s.borderTopLeftRadius, breite: r.width, top: r.top };
  });
  const sicht = page.viewportSize()!;

  expect(stil.position).toBe('fixed');
  expect(stil.top).toBe(0);
  expect(stil.breite).toBe(sicht.width);
  expect(stil.radius).toBe('0px');
});
