/**
 * Embed contract of `<boerdi-chat>` (spec §5.5) in a real browser.
 *
 * These are the checks that unit tests structurally cannot make: the element
 * is registered by the shipped bundle, its JS API lives on the DOM node (not
 * on an Angular component), the shadow-DOM styles apply, and focus actually
 * moves. Two of them are regression guards for bugs found live in 8-5/8-6.
 */
import { expect, test } from '@playwright/test';

import { card, chatResponse } from './fixtures/backend-payloads';
import { HOST, mount } from './fixtures/harness';

/** Gerenderte Farbe → Kanäle in 0…255.
 *
 *  Zwei Formen kommen vor: `rgb(r, g, b)` mit 0…255, und — sobald `color-mix()`
 *  im Spiel ist — `color(srgb 0.93 0.88 0.91)` mit 0…1. Ein Muster nur für
 *  Ganzzahlen läse aus „0.927" die 0 heraus und meldete Schwarz. */
function kanaele(farbe: string): [number, number, number] {
  const zahlen = farbe.match(/[\d.]+/g)?.map(Number);
  if (!zahlen || zahlen.length < 3) throw new Error(`keine lesbare Farbe: ${farbe}`);
  const faktor = farbe.startsWith('color(') ? 255 : 1;
  return [zahlen[0] * faktor, zahlen[1] * faktor, zahlen[2] * faktor];
}

/** WCAG-2-Kontrastverhältnis zweier gerenderter Farben. */
function kontrast(a: string, b: string): number {
  const leucht = (farbe: string) => {
    const [r, g, bl] = kanaele(farbe).map((c) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hell, dunkel] = [leucht(a), leucht(b)].sort((x, y) => y - x);
  return (hell + 0.05) / (dunkel + 0.05);
}

const API_METHODS = [
  'openChatbot', 'closeChatbot', 'toggleChatbot',
  'isChatbotOpen', 'resetSession', 'updateContext',
];

test('das Bundle registriert das Element und legt die 6 §5.5-Methoden auf den Knoten', async ({ page }) => {
  await mount(page);

  expect(await page.evaluate(() => !!customElements.get('boerdi-chat'))).toBe(true);
  const types = await page.evaluate((methods) => {
    const el = document.querySelector('boerdi-chat') as any;
    return methods.map((m) => typeof el[m]);
  }, API_METHODS);
  expect(types).toEqual(API_METHODS.map(() => 'function'));
});

test('die Host-Seite steuert das Panel über die JS-API', async ({ page }) => {
  await mount(page);
  const el = page.locator('boerdi-chat');

  expect(await el.evaluate((n: any) => n.isChatbotOpen())).toBe(false);
  await el.evaluate((n: any) => n.openChatbot());
  await expect(page.locator('.chat-input')).toBeVisible();
  expect(await el.evaluate((n: any) => n.isChatbotOpen())).toBe(true);

  await el.evaluate((n: any) => n.closeChatbot());
  await expect(page.locator('.chat-input')).toBeHidden();
});

test('resetSession() und updateContext() wirken wirklich, nicht nur am Typ', async ({ page }) => {
  // `element-api.ts` legt die Weiterleitung für ALLE sechs Namen an, und die
  // Komponente ruft `this.shell()?.…` — beide Methoden wären also auch dann
  // `typeof 'function'` und stillschweigend wirkungslos, wenn die Verdrahtung
  // fehlte (genau die Falle von `data-position` und `inline-result-grouping`).
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Erste Antwort.' }), chatResponse({ content: 'Zweite Antwort.' }));
  await w.open();

  await page.locator('.chat-input').fill('Erste Frage');
  await page.locator('.btn-send').click();
  await expect(page.locator('.msg-bubble')).toHaveCount(3);   // Begrüßung + Frage + Antwort

  // updateContext: der Host reicht Seiten-Wissen nach — es muss im nächsten
  // Request im page_context stehen.
  await page.locator('boerdi-chat').evaluate((n: any) => n.updateContext({ thema: 'Bruchrechnen' }));
  await page.locator('.chat-input').fill('Zweite Frage');
  await page.locator('.btn-send').click();
  await w.waitForTurns(2);
  expect(w.turnRequests()[1].environment.page_context.thema).toBe('Bruchrechnen');

  // resetSession: neue Session-ID, Verlauf wieder auf die Begrüßung.
  const before = w.turnRequests()[1].session_id;
  await page.locator('boerdi-chat').evaluate((n: any) => n.resetSession());
  await expect(page.locator('.msg-bubble')).toHaveCount(1);

  w.enqueue(chatResponse({ content: 'Dritte Antwort.' }));
  await page.locator('.chat-input').fill('Dritte Frage');
  await page.locator('.btn-send').click();
  await w.waitForTurns(3);
  expect(w.turnRequests()[2].session_id).not.toBe(before);
});

test('das Panel wird erst beim ersten Öffnen gemountet (Lazy-Mount) und bleibt dann erhalten', async ({ page }) => {
  const w = await mount(page);

  // Vor dem ersten Öffnen existiert die Shell überhaupt nicht im DOM.
  await expect(page.locator('boerdi-chat-shell')).toHaveCount(0);
  await w.open();
  await expect(page.locator('boerdi-chat-shell')).toHaveCount(1);

  // Nach dem Schließen bleibt sie gemountet (State-Erhalt, §5.5).
  await page.locator('.boerdi-close').click();
  await expect(page.locator('.chat-input')).toBeHidden();
  await expect(page.locator('boerdi-chat-shell')).toHaveCount(1);
});

test('position="top-left" verschiebt den Host — ALT-Bugfix aus 8-5 (data-position matchte nie)', async ({ page }) => {
  await mount(page, { attrs: { position: 'top-left' } });

  // `right`/`bottom` sind hier bewusst nicht geprüft: getComputedStyle löst
  // `auto` bei positionierten Elementen zum *benutzten* Pixelwert auf ("1196px").
  const style = await page.locator('boerdi-chat').evaluate((el) => {
    const s = getComputedStyle(el);
    return { position: s.position, top: s.top, left: s.left };
  });
  expect(style).toEqual({ position: 'fixed', top: '20px', left: '20px' });

  // Und der FAB liegt sichtbar in der oberen Bildschirmhälfte (das ist der
  // Effekt, der vor dem Fix ausblieb).
  const fab = await page.locator('.boerdi-fab').boundingBox();
  const viewport = page.viewportSize()!;
  expect(fab!.y).toBeLessThan(viewport.height / 2);
  expect(fab!.x).toBeLessThan(viewport.width / 2);
});

test('Escape schließt das Panel und gibt den Fokus an den FAB zurück (8-6-Live-Fix)', async ({ page }) => {
  const w = await mount(page);
  // Der Fokus wird per `afterNextRender` gesetzt, also einen Tick nach dem
  // Sichtbarwerden — deshalb gepollt statt einmalig gelesen.
  const focused = () => expect.poll(() => page.evaluate(() => {
    const shadow = (document.querySelector('boerdi-chat') as any).shadowRoot;
    return shadow.activeElement?.className ?? '';
  }));

  await w.open();
  await focused().toContain('chat-input');

  await page.keyboard.press('Escape');
  await expect(page.locator('.chat-input')).toBeHidden();

  // Beim Schließen zurück auf den FAB (sonst verliert die Tastatur die Spur).
  await focused().toContain('boerdi-fab');
});

test('zweites Embed derselben Seite wird versteckt (Single-Instance-Guard, M3)', async ({ page }) => {
  await mount(page, { duplicate: true });

  const elements = page.locator('boerdi-chat');
  await expect(elements).toHaveCount(2);
  await expect(elements.nth(0)).toBeVisible();
  expect(await elements.nth(1).evaluate((el) => getComputedStyle(el).display)).toBe('none');
});

test('Backend nicht erreichbar: FAB erscheint trotzdem und das Panel öffnet', async ({ page }) => {
  const w = await mount(page, { config: null });
  await w.open();
  await expect(page.locator('.msg-bubble').first()).toBeVisible();
});

test('bei 200 % Zoom bleibt das Panel ohne Horizontal-Scroll bedienbar (SC 1.4.4/1.4.10)', async ({ page }) => {
  // 200 % Zoom auf einem 1280×1024-Schirm entspricht einem 640×512-Viewport.
  // Ersetzt keinen Geräte-Test, misst aber den Reflow statt ihn zu behaupten.
  await page.setViewportSize({ width: 640, height: 512 });
  const w = await mount(page);
  await w.open();

  const overflow = await page.locator('.boerdi-panel').evaluate((el) => ({
    scroll: el.scrollWidth, client: el.clientWidth,
  }));
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);

  // Auch der Seiten-Body darf nicht seitlich scrollen.
  const body = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(body.scroll).toBeLessThanOrEqual(body.client);

  await expect(page.locator('.chat-input')).toBeVisible();
  await expect(page.locator('.btn-send')).toBeVisible();
});

test.describe('Bewegung', () => {
  const fabAnimation = (page: import('@playwright/test').Page) =>
    page.locator('.boerdi-fab').evaluate((el) => getComputedStyle(el).animationName);

  test('mit reduzierter Bewegung stehen die Endlos-Animationen still', async ({ page }) => {
    await mount(page);
    expect(await fabAnimation(page)).toBe('none');
  });

  test('ohne Präferenz bobbt der FAB wie in ALT', async ({ page }) => {
    await mount(page, { motion: 'no-preference' });
    expect(await fabAnimation(page)).toContain('boerdi-');
  });
});

test.describe('Kundenfarbe', () => {
  /** Öffnet das Widget mit gesetzter `primary-color` und einer Ergebniskarte,
   *  damit der einzige Material-Knopf („Inhalt anzeigen") sichtbar wird. Das
   *  flache Raster ist nötig, weil die Gruppen-Box einen eigenen Icon-Knopf
   *  rendert (kein Material). */
  async function knopfMitFarbe(page: import('@playwright/test').Page, farbe: string) {
    const w = await mount(page, {
      attrs: { 'primary-color': farbe, 'inline-result-grouping': 'false' },
    });
    w.enqueue(chatResponse({ content: 'Hier ist etwas.', cards: [card()] }));
    await w.open();
    await page.locator('.chat-input').fill('Zeig mir Material');
    await page.locator('.btn-send').click();

    const knopf = page.locator('.card-btn-m3').first();
    await expect(knopf).toBeVisible();
    return knopf;
  }

  test('ohne primary-color bleibt der Knopf in der Marke und lesbar', async ({ page }) => {
    // Der ausgelieferte Normalfall. Die Token-Brücke ersetzt hier Materials
    // eigene Tonwerte durch eine `color-mix`-Formel — der Kontrast muss also
    // auch OHNE Kundenfarbe halten, und die Marke (Blau) muss übrig bleiben.
    const w = await mount(page, { attrs: { 'inline-result-grouping': 'false' } });
    w.enqueue(chatResponse({ content: 'Hier ist etwas.', cards: [card()] }));
    await w.open();
    await page.locator('.chat-input').fill('Zeig mir Material');
    await page.locator('.btn-send').click();

    const stil = await page.locator('.card-btn-m3').first().evaluate((el) => {
      const s = getComputedStyle(el);
      return { flaeche: s.backgroundColor, text: s.color };
    });
    const [r, , b] = kanaele(stil.flaeche);
    expect(b, `Fläche ${stil.flaeche} ist nicht mehr blau`).toBeGreaterThan(r);
    expect(kontrast(stil.text, stil.flaeche)).toBeGreaterThanOrEqual(4.5);
  });

  test('primary-color schlägt bis in die Material-Token durch', async ({ page }) => {
    // Ohne die Token-Brücke sind die `--mat-sys-*`-Werte zur BAUZEIT aus
    // #1c4587 gebacken — der Knopf bliebe blau, egal was der Kunde setzt.
    // Deshalb eine Kundenfarbe mit umgekehrtem Farbverhältnis (Rot > Blau):
    // bleibt Blau übrig, ist die Brücke nicht da.
    const knopf = await knopfMitFarbe(page, '#7a1f5c');
    const stil = await knopf.evaluate((el) => {
      const s = getComputedStyle(el);
      return { flaeche: s.backgroundColor, text: s.color };
    });

    const [r, , b] = kanaele(stil.flaeche);
    expect(r, `Fläche ${stil.flaeche} ist nicht aus #7a1f5c abgeleitet`).toBeGreaterThan(b);
    expect(kontrast(stil.text, stil.flaeche)).toBeGreaterThanOrEqual(4.5);
  });

  test('… und behält dabei den geerbten Dunkelmodus (light-dark bleibt heil)', async ({ page }) => {
    // `color-scheme` ist vererbt: setzt die GASTSEITE dark, kippen die Token
    // des Widgets mit. Eine Brücke ohne `light-dark()` würde das stillschweigend
    // abschalten — hier gemessen statt geglaubt.
    const knopf = await knopfMitFarbe(page, '#7a1f5c');
    const hell = await knopf.evaluate((el) => getComputedStyle(el).backgroundColor);

    await page.evaluate(() => { document.documentElement.style.colorScheme = 'dark'; });
    const stil = await knopf.evaluate((el) => {
      const s = getComputedStyle(el);
      return { flaeche: s.backgroundColor, text: s.color };
    });

    expect(stil.flaeche, 'Dunkelmodus ändert die Fläche nicht').not.toBe(hell);
    const [r, , b] = kanaele(stil.flaeche);
    expect(r).toBeGreaterThan(b);
    expect(kontrast(stil.text, stil.flaeche)).toBeGreaterThanOrEqual(4.5);
  });
});

test('die Ergebniskachel folgt dem Dunkelmodus der Gastseite (B2)', async ({ page }) => {
  // `color-scheme` ist vererbt: setzt die Gastseite dark, kippen die
  // `--mat-sys-*`-Token des Widgets mit. Die Kachel war hell-only (ALT-Erbe) —
  // in einer dunklen Gastseite stand also eine weiße Karte in dunkler Hülle.
  const w = await mount(page, { attrs: { 'inline-result-grouping': 'false' } });
  w.enqueue(chatResponse({ content: 'Hier ist etwas.', cards: [card()] }));
  await w.open();
  await page.locator('.chat-input').fill('Zeig mir Material');
  await page.locator('.btn-send').click();

  const karte = page.locator('.wlo-card-wrapper').first();
  await expect(karte).toBeVisible();
  // Die Blase MIT geprüft: eine dunkle Karte in heller Blase wäre ein halber
  // Dunkelmodus — schlechter als gar keiner (2026-07-31 im Bild gesehen).
  //
  // Über Locators, nicht über `document.querySelector`: das Widget lebt im
  // Shadow DOM, den nur Playwrights Locator durchdringt.
  const blase = page.locator('.bot-bubble').first();
  const lies = async () => ({
    flaeche: await karte.evaluate((el) => getComputedStyle(el).backgroundColor),
    titel: await karte.evaluate((el) => getComputedStyle(el.querySelector('.card-title')!).color),
    blase: await blase.evaluate((el) => getComputedStyle(el).backgroundColor),
    blasenText: await blase.evaluate((el) => getComputedStyle(el).color),
  });

  const hell = await lies();
  await page.evaluate(() => { document.documentElement.style.colorScheme = 'dark'; });
  const dunkel = await lies();

  expect(dunkel.flaeche, 'Kachelfläche ändert sich im Dunkelmodus nicht').not.toBe(hell.flaeche);
  expect(dunkel.blase, 'Blasenfläche ändert sich im Dunkelmodus nicht').not.toBe(hell.blase);
  // In BEIDEN Modi müssen Kachel-Titel und Blasentext lesbar bleiben.
  expect(kontrast(hell.titel, hell.flaeche)).toBeGreaterThanOrEqual(4.5);
  expect(kontrast(dunkel.titel, dunkel.flaeche)).toBeGreaterThanOrEqual(4.5);
  expect(kontrast(hell.blasenText, hell.blase)).toBeGreaterThanOrEqual(4.5);
  expect(kontrast(dunkel.blasenText, dunkel.blase)).toBeGreaterThanOrEqual(4.5);
});

test('auch die Hülle folgt dem Dunkelmodus — Panel, Fußzeile, Eingabe, Ergebnisbox (B2)', async ({ page }) => {
  // Ergänzt den Kachel-Test oben um die HÜLLE. Die Kachel allein reichte nicht:
  // beim Bild-Abgleich am 2026-07-31 stand eine korrekt gekippte Kachel in einem
  // weißen Panel mit weißer Fußzeile — der halbe Dunkelmodus, den der Kachel-Test
  // gerade verhindern sollte, eine Ebene höher.
  //
  // Bewusst OHNE `inline-result-grouping: false`: das ist die AUSGELIEFERTE
  // Voreinstellung. Die Ergebnisse erscheinen dann als `.result-group`-Boxen,
  // nicht als Kachelraster — die Fläche also, die Nutzer normalerweise sehen.
  const w = await mount(page);
  w.enqueue(chatResponse({ content: 'Hier ist etwas.', cards: [card()] }));
  await w.open();
  await page.locator('.chat-input').fill('Zeig mir Material');
  await page.locator('.btn-send').click();

  const box = page.locator('.result-group').first();
  await expect(box).toBeVisible();

  const flaeche = (ort: string) =>
    page.locator(ort).first().evaluate((el) => getComputedStyle(el).backgroundColor);
  const schrift = (ort: string) =>
    page.locator(ort).first().evaluate((el) => getComputedStyle(el).color);
  const lies = async () => ({
    panel: await flaeche('.boerdi-panel'),
    fuss: await flaeche('.chat-footer'),
    eingabe: await flaeche('.chat-input'),
    eingabeText: await schrift('.chat-input'),
    box: await flaeche('.result-group'),
    boxText: await schrift('.result-group__item'),
  });

  const hell = await lies();
  await page.evaluate(() => { document.documentElement.style.colorScheme = 'dark'; });
  const dunkel = await lies();

  expect(dunkel.panel, 'Panel-Fläche kippt nicht').not.toBe(hell.panel);
  expect(dunkel.fuss, 'Fußzeile kippt nicht').not.toBe(hell.fuss);
  expect(dunkel.eingabe, 'Eingabefeld kippt nicht').not.toBe(hell.eingabe);
  expect(dunkel.box, 'Ergebnisbox kippt nicht').not.toBe(hell.box);

  // Kippen allein genügt nicht — lesbar muss es in beiden Modi bleiben.
  expect(kontrast(hell.eingabeText, hell.eingabe)).toBeGreaterThanOrEqual(4.5);
  expect(kontrast(dunkel.eingabeText, dunkel.eingabe)).toBeGreaterThanOrEqual(4.5);
  expect(kontrast(hell.boxText, hell.box)).toBeGreaterThanOrEqual(4.5);
  expect(kontrast(dunkel.boxText, dunkel.box)).toBeGreaterThanOrEqual(4.5);
});

test('das Widget lädt nichts von Dritt-Hosts (DSGVO-Guardrail)', async ({ page }) => {
  const seen: string[] = [];
  page.on('request', (req) => seen.push(req.url()));

  const w = await mount(page, { url: `${HOST}/` });
  await w.open();
  await expect(page.locator('.chat-input')).toBeVisible();

  // Erst beweisen, dass der Mitschnitt überhaupt läuft — sonst wäre die
  // eigentliche Zusicherung unten trivial erfüllt.
  expect(seen.length).toBeGreaterThan(1);
  const foreign = seen.filter((u) => !['host.test', 'api.test'].includes(new URL(u).host));
  expect(foreign).toEqual([]);
});
