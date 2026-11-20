import { expect, test } from '@playwright/test';

import { chatResponse, guideModeConfig } from './fixtures/backend-payloads';
import { mount } from './fixtures/harness';

/**
 * Der Anmelde-Knopf in der Eingabezeile — seit Paket D1 (Plan 2026-11-20) der Konto-Knopf mit Menü.
 * Zwei Dinge lassen sich nur HIER
 * messen, weil jsdom kein Layout rechnet: ob die Zeile den fünften Knopf bei
 * 320 px noch trägt, und ob er per Tastatur erreichbar und sichtbar fokussiert
 * ist. Beides war im Entwurf gerechnet — hier wird es nachgesehen.
 */

/** Ohne `mcp_auth_base` gibt es den Knopf bewusst nicht. */
const MIT_ANMELDUNG = { config: guideModeConfig({ mcp_auth_base: 'https://mcp.test' }) };

async function angemeldet(page: import('@playwright/test').Page): Promise<void> {
  // ein wohlgeformter Zugangsblock (Testwert) — das Widget zeigt dann den angemeldeten Konto-Knopf
  await page.addInitScript(() => sessionStorage.setItem('boerdi.mcp-access', 'wloE2eTestBlock'));
}

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

test('bei 320 px trägt die Zeile den Konto-Knopf: kein waagerechtes Scrollen, Feld ≥ 120 px', async ({ page }) => {
  // 320 px ist die schmalste Breite, die WCAG 1.4.10 (Reflow) verlangt. Seit Paket D1 (Plan
  // 2026-11-20, E-D1) gibt es keinen eigenen Kürzel-Kreis mehr — die Grenze für den Umbruch sank
  // von 356 auf 320 px. Ob die Zeile umbricht oder nicht: kein Überlauf, das Feld bleibt bedienbar.
  await page.setViewportSize({ width: 320, height: 640 });
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();

  await expect(page.locator('.btn-auth')).toHaveAttribute('aria-label', 'Anmelden – nicht angemeldet');
  await expect(page.locator('.konto-kuerzel')).toHaveCount(0);
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
  expect(feld.breite).toBeGreaterThanOrEqual(120);
  // Die Knöpfe stehen in einer Zeile (gleiche Mitte ± 4 px), der Konto-Knopf vor Größe und Neustart.
  const mitten = rest.map((k) => k.mitte);
  expect(Math.max(...mitten) - Math.min(...mitten)).toBeLessThanOrEqual(4);
  const reihe = rest.map((k) => k.klasse);
  expect(reihe.indexOf('konto')).toBeLessThan(reihe.indexOf('btn-size'));
});

test('der Konto-Knopf ist so groß wie „Vollbild“ — abgemeldet wie angemeldet (E-D1)', async ({ page }) => {
  for (const mitBlock of [false, true]) {
    if (mitBlock) await angemeldet(page);
    const w = await mount(page, MIT_ANMELDUNG);
    await w.open();
    if (mitBlock) await expect(page.locator('.btn-auth')).toHaveAttribute('aria-haspopup', 'menu');
    const masse = await page.locator('.chat-footer').evaluate((el) => {
      const box = (s: string) => {
        const r = el.querySelector(s)!.getBoundingClientRect();
        return [Math.round(r.width), Math.round(r.height)];
      };
      return { konto: box('.btn-auth'), vollbild: box('.btn-size') };
    });
    console.log(`Konto-Knopf ${mitBlock ? 'angemeldet' : 'abgemeldet'}:`, JSON.stringify(masse));
    expect(masse.konto).toEqual(masse.vollbild);
    expect(masse.konto[0]).toBeGreaterThanOrEqual(24);                // SC 2.5.8
  }
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

/** Kontrast von `sel` (Vordergrund) gegen die Fläche von `grund` — durch die Shadow-Roots hindurch,
 *  über ein 1×1-Canvas (versteht `color-mix()`), dazu der Randstil von `sel`. */
function kontrast(page: import('@playwright/test').Page, sel: string, grund: string) {
  return page.evaluate(([vorne, hinten]) => {
    const tief = (wurzel: Document | ShadowRoot, s: string): Element | null => {
      const direkt = wurzel.querySelector(s);
      if (direkt) return direkt;
      for (const el of Array.from(wurzel.querySelectorAll('*'))) {
        const treffer = el.shadowRoot ? tief(el.shadowRoot, s) : null;
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
    const k = tief(document, vorne)!;
    const g = tief(document, hinten)!;
    const [a, b] = [leucht(rgb(getComputedStyle(k).color)), leucht(rgb(getComputedStyle(g).backgroundColor))]
      .sort((x, y) => y - x);
    return { rand: getComputedStyle(k).borderTopStyle, kontrast: (a + 0.05) / (b + 0.05) };
  }, [sel, grund] as const);
}

/** Den Endzustand messen: die Fußzeilen-Knöpfe haben Übergänge (nach dem Umschalten des Farbschemas,
 *  nach neuen Initialen). Der Übergang ist dafür aus — zwei gleiche Messungen hintereinander bewiesen
 *  auf dem langsamen CI-Rechner nichts (beide im selben Bild, mitten im Übergang). */
async function eingeschwungen(page: import('@playwright/test').Page, sel: string, grund: string) {
  await page.locator(sel).evaluate((el) => { (el as HTMLElement).style.transition = 'none'; });
  return kontrast(page, sel, grund);
}

const dunkel = (page: import('@playwright/test').Page) =>
  page.evaluate(() => { document.documentElement.style.colorScheme = 'dark'; });

test('abgemeldet: der Knopf ist gestrichelt, das Symbol hält ≥ 3:1 — hell und dunkel (Review B, 4)', async ({ page }) => {
  // „Ausgegraut“ soll sich nicht nur im Farbton von „angemeldet ohne Namen“ unterscheiden:
  // andere Form (Umriss, gestrichelter Rand) — und das Symbol trägt die Bedeutung, also SC 1.4.11.
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();
  await expect(page.locator('.btn-auth')).toHaveAttribute('aria-label', 'Anmelden – nicht angemeldet');

  const hell = await kontrast(page, '.btn-auth', '.chat-footer');
  await dunkel(page);
  const nacht = await eingeschwungen(page, '.btn-auth', '.chat-footer');
  console.log('Konto-Knopf „nicht angemeldet“:', JSON.stringify({ hell, dunkel: nacht }));
  for (const [modus, m] of [['hell', hell], ['dunkel', nacht]] as const) {
    expect(m.rand, modus).toBe('dashed');
    expect(m.kontrast, modus).toBeGreaterThanOrEqual(3);
  }
});

test('angemeldet: Initialen ≥ 4,5:1, das Symbol ohne Namen ≥ 3:1 — hell und dunkel', async ({ page }) => {
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();
  const konto = page.locator('.btn-auth');
  await expect(konto).toHaveAttribute('aria-label', 'Konto – angemeldet');
  const symbol = [await kontrast(page, '.btn-auth', '.btn-auth')];

  // Der Name kommt mit der Antwort eines Zuges (B4) — dann die Initialen.
  w.enqueue({ ...chatResponse(), auth_display_name: 'Jan Schachtschabel' });
  await page.locator('.chat-input').fill('hallo');
  await page.locator('.btn-send').click();
  await expect(konto).toHaveText('JS');
  await expect(konto).toHaveAttribute('aria-label', 'Konto – angemeldet als Jan Schachtschabel');
  const initialen = [await eingeschwungen(page, '.btn-auth', '.btn-auth')];
  await dunkel(page);
  initialen.push(await eingeschwungen(page, '.btn-auth', '.btn-auth'));
  console.log('Konto-Knopf angemeldet:', JSON.stringify({ symbol, initialen }));
  expect(symbol[0].kontrast).toBeGreaterThanOrEqual(3);
  for (const m of initialen) expect(m.kontrast).toBeGreaterThanOrEqual(4.5);
});

test('angemeldet: das Menü per Tastatur — Enter, Esc, Pfeil runter, Klick daneben, Abmelden', async ({ page }) => {
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();
  const konto = page.locator('.btn-auth');
  await expect(konto).toHaveAttribute('aria-haspopup', 'menu');
  await expect(konto).toHaveAttribute('aria-expanded', 'false');

  await konto.focus();
  await page.keyboard.press('Enter');
  const menue = page.getByRole('menu', { name: 'Angemeldet' });
  await expect(menue).toBeVisible();
  await expect(konto).toHaveAttribute('aria-expanded', 'true');
  await expect.poll(() => fokussiert(page)).toContain('konto-menue__eintrag');

  await page.keyboard.press('Escape');
  await expect(menue).toHaveCount(0);
  await expect(page.locator('.chat-input')).toBeVisible();          // das Chat-Fenster bleibt offen
  await expect.poll(() => fokussiert(page)).toContain('btn-auth');

  await page.keyboard.press('ArrowDown');
  await expect(menue).toBeVisible();
  await page.locator('.chat-input').click();                        // daneben
  await expect(menue).toHaveCount(0);

  await konto.click();
  await page.getByRole('menuitem', { name: 'Abmelden' }).click();
  await expect(konto).toHaveAttribute('aria-label', 'Anmelden – nicht angemeldet');
  await expect(konto).not.toHaveAttribute('aria-haspopup', 'menu');
  await expect(menue).toHaveCount(0);
});

test('bei 320 px bleibt das Menü ganz im Widget', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await angemeldet(page);
  const w = await mount(page, MIT_ANMELDUNG);
  await w.open();
  await page.locator('.btn-auth').click();
  await expect(page.getByRole('menu')).toBeVisible();
  const lage = await page.locator('.chat-wrapper').evaluate((el) => {
    const w = el.getBoundingClientRect();
    const m = el.querySelector('.konto-menue')!.getBoundingClientRect();
    return { wl: w.left, wr: w.right, ml: m.left, mr: m.right, mt: m.top, wt: w.top };
  });
  console.log('Menü bei 320 px:', JSON.stringify(lage));
  expect(lage.ml).toBeGreaterThanOrEqual(lage.wl);
  expect(lage.mr).toBeLessThanOrEqual(lage.wr);
  expect(lage.mt).toBeGreaterThanOrEqual(lage.wt);
});
