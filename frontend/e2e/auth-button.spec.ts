import { expect, test } from '@playwright/test';

import { guideModeConfig } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

/**
 * Der Anmelde-Knopf in der Eingabezeile. Zwei Dinge lassen sich nur HIER
 * messen, weil jsdom kein Layout rechnet: ob die Zeile den fünften Knopf bei
 * 320 px noch trägt, und ob er per Tastatur erreichbar und sichtbar fokussiert
 * ist. Beides war im Entwurf gerechnet — hier wird es nachgesehen.
 */

/** Ohne `mcp_auth_base` gibt es den Knopf bewusst nicht. */
const MIT_ANMELDUNG = { config: guideModeConfig({ mcp_auth_base: 'https://mcp.test' }) };

/** Klasse des tatsächlich fokussierten Elements — durch die Shadow-Roots hindurch. */
function fokussiert(page: import('@playwright/test').Page): Promise<string> {
  return page.evaluate(() => {
    const tief = (el: Element | null): Element | null =>
      el?.shadowRoot?.activeElement ? tief(el.shadowRoot.activeElement) : el;
    return (tief(document.activeElement) as HTMLElement | null)?.className ?? '';
  });
}

/**
 * Das Panel refokussiert das Eingabefeld 100 ms nach dem Öffnen
 * (`focusInput()`). Wer vorher Tab drückt, verliert den Fokus wieder an das
 * Feld — erst abwarten, dann tabben.
 */
async function tabAbEingabefeld(page: import('@playwright/test').Page): Promise<void> {
  await page.locator('.chat-input').focus();
  await expect.poll(() => fokussiert(page)).toContain('chat-input');
  await page.waitForTimeout(200);
  await page.keyboard.press('Tab');
}

test('bei 320 px bricht die Eingabezeile nicht um und das Feld bleibt bedienbar', async ({ page }) => {
  // 320 px ist die schmalste Breite, die WCAG 1.4.10 (Reflow) verlangt.
  await page.setViewportSize({ width: 320, height: 640 });
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();

  await expect(page.locator('.btn-auth')).toBeVisible();

  const zeile = await page.locator('.chat-footer').evaluate((el) => {
    const rahmen = el.getBoundingClientRect();
    const kinder = Array.from(el.children).map((k) => {
      const r = k.getBoundingClientRect();
      return {
        klasse: (k as HTMLElement).className.split(' ')[0],
        breite: Math.round(r.width),
        mitteAb: Math.round(Math.abs((r.top + r.bottom) / 2 - (rahmen.top + rahmen.bottom) / 2)),
      };
    });
    return { kinder, scroll: el.scrollWidth, client: el.clientWidth };
  });
  console.log('320px Fußzeile:', JSON.stringify(zeile));

  // Ein Umbruch hieße: ein Kind sitzt nicht mehr auf der Mittellinie der
  // Fußzeile. NICHT über `offsetTop` prüfen — die Kinder sind verschieden hoch
  // und zentriert, ihre Oberkanten liegen also planmäßig 2 px auseinander.
  for (const k of zeile.kinder) {
    expect(k.mitteAb, `${k.klasse} sitzt nicht auf der Zeilenmitte`).toBeLessThanOrEqual(4);
  }
  expect(zeile.scroll).toBeLessThanOrEqual(zeile.client);

  // Das Eingabefeld ist das Einzige, das schrumpft — es muss benutzbar bleiben.
  const feld = zeile.kinder.find((k) => k.klasse === 'chat-input')!;
  expect(feld.breite).toBeGreaterThanOrEqual(120);
});

test('bei 320 px kostet der Knopf das Eingabefeld nur seine eigene Breite', async ({ page }) => {
  // Die Gegenprobe zum Test darüber: dieselbe Breite, aber ohne
  // `mcp_auth_base` — dann fehlt der Knopf, und die Differenz IST sein Preis.
  await page.setViewportSize({ width: 320, height: 640 });
  const w = await mount(page);  // Standard-Config: keine Anmelde-Adresse
  await w.open();

  await expect(page.locator('.btn-auth')).toHaveCount(0);
  const ohne = await page.locator('.chat-footer').evaluate((el) => ({
    feld: Math.round(el.querySelector('.chat-input')!.getBoundingClientRect().width),
    scroll: el.scrollWidth, client: el.clientWidth,
  }));
  console.log('320px ohne Anmelde-Knopf:', JSON.stringify(ohne));

  // Der Knopf kostet 36 px + 8 px Abstand. Was er NICHT tun darf: die Zeile
  // erst zum Überlaufen bringen — deshalb steht hier dieselbe Messung wie
  // oben, damit die beiden Zahlen vergleichbar sind statt nur behauptet.
  expect(ohne.scroll).toBeLessThanOrEqual(ohne.client);
  expect(ohne.feld).toBeGreaterThanOrEqual(120);
});

test('der Knopf liegt in der Tab-Reihenfolge direkt hinter dem Eingabefeld', async ({ page }) => {
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();

  await tabAbEingabefeld(page);
  expect(await fokussiert(page)).toContain('btn-auth');
});

test('der fokussierte Knopf ist sichtbar hervorgehoben (SC 2.4.7)', async ({ page }) => {
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();

  await tabAbEingabefeld(page);  // Tastatur-Fokus, damit `:focus-visible` greift

  const ring = await page.locator('.btn-auth').evaluate((el) => {
    const s = getComputedStyle(el);
    return { style: s.outlineStyle, width: s.outlineWidth, schatten: s.boxShadow };
  });
  console.log('Fokus-Ring:', JSON.stringify(ring));
  const sichtbar = (ring.style !== 'none' && ring.width !== '0px') || ring.schatten !== 'none';
  expect(sichtbar, `kein sichtbarer Fokus: ${JSON.stringify(ring)}`).toBe(true);
});
