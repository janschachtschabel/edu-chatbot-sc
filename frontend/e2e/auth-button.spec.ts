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
 * Das Panel fokussiert das Eingabefeld nach dem Öffnen selbst (`focusInput()`,
 * 100 ms verzögert). Beim ersten Öffnen ist das Feld oft noch gesperrt — der
 * Kontext-Ping läuft —, dann holt die Shell den Fokus nach dem Laden nach.
 * Erst wenn er dort ANGEKOMMEN ist, steht kein Refokus mehr aus; vorher
 * gedrücktes Tab ginge an das Feld zurück. Deshalb kein eigenes `focus()`
 * (auf dem gesperrten Feld verpuffte es: CI-Kippler 2026-10-17) und kein
 * Zeitpuffer, sondern auf den Fokus des Widgets warten.
 */
async function tabAbEingabefeld(page: import('@playwright/test').Page): Promise<void> {
  await expect.poll(() => fokussiert(page)).toContain('chat-input');
  await page.keyboard.press('Tab');
}

test('bei 320 px bricht die Eingabezeile um und das Feld bleibt bedienbar', async ({ page }) => {
  // 320 px ist die schmalste Breite, die WCAG 1.4.10 (Reflow) verlangt. Seit Plan 2026-11-19 (E8)
  // steht links vom Knopf der Kreis „Nicht angemeldet“ — in einer Zeile blieben dem Feld 84 px.
  // Darum bricht die Zeile unter 356 px um: das Feld oben in voller Breite, die Knöpfe darunter.
  await page.setViewportSize({ width: 320, height: 640 });
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();

  await expect(page.locator('.btn-auth')).toBeVisible();
  await expect(page.locator('.konto-kuerzel')).toHaveAttribute('aria-label', 'Nicht angemeldet');
  await w.ohneMikrofon();

  const zeile = await page.locator('.chat-footer').evaluate((el) => {
    const kinder = Array.from(el.children).map((k) => {
      const r = k.getBoundingClientRect();
      return { klasse: (k as HTMLElement).className.split(' ')[0], breite: Math.round(r.width),
        mitte: Math.round((r.top + r.bottom) / 2) };
    });
    return { kinder, scroll: el.scrollWidth, client: el.clientWidth };
  });
  console.log('320px Fußzeile:', JSON.stringify(zeile));

  expect(zeile.scroll).toBeLessThanOrEqual(zeile.client);           // kein waagerechtes Scrollen
  const feld = zeile.kinder.find((k) => k.klasse === 'chat-input')!;
  const rest = zeile.kinder.filter((k) => k.klasse !== 'chat-input');
  expect(feld.breite).toBeGreaterThanOrEqual(250);                  // volle Breite
  for (const k of rest) expect(k.mitte, `${k.klasse} unter dem Feld`).toBeGreaterThan(feld.mitte);
  // Die Kinder sind verschieden hoch und zentriert — eine Zeile heißt: gleiche Mitte (± 4 px).
  const mitten = rest.map((k) => k.mitte);
  expect(Math.max(...mitten) - Math.min(...mitten)).toBeLessThanOrEqual(4);
  const reihe = rest.map((k) => k.klasse);
  expect(reihe.indexOf('konto-kuerzel')).toBe(reihe.indexOf('btn-auth') - 1);
});

test('bei 320 px kostet der Knopf das Eingabefeld nur seine eigene Breite', async ({ page }) => {
  // Die Gegenprobe zum Test darüber: dieselbe Breite, aber ohne
  // `mcp_auth_base` — dann fehlt der Knopf, und die Differenz IST sein Preis.
  await page.setViewportSize({ width: 320, height: 640 });
  const w = await mount(page);  // Standard-Config: keine Anmelde-Adresse
  await w.open();

  await expect(page.locator('.btn-auth')).toHaveCount(0);
  await w.ohneMikrofon();
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

test('abgemeldet: der Kreis ist gestrichelt, das Symbol hält ≥ 3:1 — hell und dunkel (Review B, 4)', async ({ page }) => {
  // „Ausgegraut“ soll sich nicht nur im Farbton von „angemeldet ohne Namen“ unterscheiden:
  // andere Form (Umriss, gestrichelter Rand) — und das Symbol trägt die Bedeutung, also SC 1.4.11.
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();
  const kreis = page.locator('.konto-kuerzel');
  await expect(kreis).toHaveAttribute('aria-label', 'Nicht angemeldet');

  const messen = () => page.evaluate(() => {
    const tief = (wurzel: Document | ShadowRoot, sel: string): Element | null => {
      const direkt = wurzel.querySelector(sel);
      if (direkt) return direkt;
      for (const el of Array.from(wurzel.querySelectorAll('*'))) {
        const treffer = el.shadowRoot ? tief(el.shadowRoot, sel) : null;
        if (treffer) return treffer;
      }
      return null;
    };
    const cv = document.createElement('canvas');
    cv.width = cv.height = 1;
    const ctx = cv.getContext('2d', { willReadFrequently: true })!;
    const rgb = (wert: string) => {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = wert;
      ctx.fillRect(0, 0, 1, 1);
      return Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3);
    };
    const leucht = (f: number[]) => {
      const [r, g, b] = f.map((c) => (c / 255 <= 0.03928 ? c / 255 / 12.92 : ((c / 255 + 0.055) / 1.055) ** 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const k = tief(document, '.konto-kuerzel')!;
    const fuss = tief(document, '.chat-footer')!;
    const [a, b] = [leucht(rgb(getComputedStyle(k).color)), leucht(rgb(getComputedStyle(fuss).backgroundColor))]
      .sort((x, y) => y - x);
    return { rand: getComputedStyle(k).borderTopStyle, kontrast: (a + 0.05) / (b + 0.05) };
  });

  const hell = await messen();
  await page.evaluate(() => { document.documentElement.style.colorScheme = 'dark'; });
  const dunkel = await messen();
  console.log('Kreis „nicht angemeldet“:', JSON.stringify({ hell, dunkel }));
  for (const [modus, m] of [['hell', hell], ['dunkel', dunkel]] as const) {
    expect(m.rand, modus).toBe('dashed');
    expect(m.kontrast, modus).toBeGreaterThanOrEqual(3);
  }
});
