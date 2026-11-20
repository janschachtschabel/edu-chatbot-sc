// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import './ui-upload.element';

/**
 * Paket U3-3b (T7): `<boerdi-ui-upload>` überträgt die erfassten Dateien per Klick in den
 * persönlichen Bereich — prüfen (sha256) → Vorschau → „In WLO ablegen“ → je Datei nacheinander →
 * Ergebnisliste mit Stand als Text und Symbol, Link je Knoten → „Im Chat weitermachen“. Seit Paket U4
 * beginnt es mit Ort „In WLO ablegen und erschließen“ und (seit Plan 2026-11-20, P2) „Weiter zur Vorschau“ (hier ohne `orte` aus den
 * Schaltern abgeleitet: angemeldet mit Ablage → WLO vorgewählt).
 */
const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const DATEN = {
  zweck: 'sammlungsstruktur', grenzen: { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50, max_mb_ablage: 10 },
  schalter: { dokument_im_chat: false, ablage_in_wlo: true },
};

type Fn = ReturnType<typeof vi.fn>;
type Host = ElementHost & { antworten: Fn; vormerken: Fn; ablegen: Fn; link: Fn };

function host(): Host {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), aktion: vi.fn(), beschaeftigt: vi.fn(() => false),
    antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(), ablegen: vi.fn(),
    link: vi.fn((url: string) => ({ href: `${url}?bsid=1`, hinweis: '' })),
  } as never;
}

function datei(pfad: string, size = 100): File {
  const f = new File([new Uint8Array(size)], pfad.split('/').pop() ?? pfad, { type: 'application/pdf' });
  Object.defineProperty(f, 'webkitRelativePath', { value: pfad });
  return f;
}

const PLAN = {
  batch_token: 'tok-1234567890', layout: 'folder', ordner: 'Physik', gesamt: 200,
  eintraege: [{ index: 0, titel: 'Hebel', art: 'pdf', groesse: 100, name: 'Hebel.pdf' },
    { index: 1, titel: 'Linse', art: 'pdf', groesse: 100, name: 'Linse.pdf' }],
};

const warte = () => new Promise((r) => setTimeout(r, 0));
const knopf = (w: ShadowRoot, text: string) =>
  [...w.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

async function erzeugt(h = host(), daten: Record<string, unknown> = DATEN, kontext: Partial<ModulKontext> = {}) {
  const el = document.createElement('boerdi-ui-upload') as NachladeElement;
  el.host = h;
  el.daten = daten;
  el.kontext = { ...KONTEXT, ...kontext };
  el.beschaeftigt = false;
  document.body.appendChild(el);
  const wurzel = el.shadowRoot as ShadowRoot;
  if (!kontext.nurLesen) {
    const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [datei('Physik/Hebel.pdf'), datei('Physik/Linse.pdf'), datei('Physik/x.exe')], configurable: true });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await warte();
  }
  return { el, h, wurzel };
}

/** Antworten des Backends je Schritt; `datei` der Reihe nach. */
function backend(h: Host, dateien: Array<Record<string, unknown> | Error | DOMException> = [], plan: Record<string, unknown> = PLAN) {
  const reihe = [...dateien];
  h.ablegen.mockImplementation(async (s: { schritt: string; index?: number }) => {
    if (s.schritt === 'vorbereiten') return plan;
    if (s.schritt === 'abschluss') return { stand: 'stored', bereits: false };
    const naechste = reihe.shift() ?? { stand: 'stored', link: `https://repo.test/render/n-${s.index}` };
    // unter jsdom ist eine DOMException kein Error
    if (naechste instanceof Error || naechste instanceof DOMException) throw naechste;
    return { index: s.index, ...naechste };
  });
}

async function bisVorschau(h = host(), dateien: Array<Record<string, unknown> | Error | DOMException> = [],
  plan: Record<string, unknown> = PLAN) {
  backend(h, dateien, plan);
  const r = await erzeugt(h);
  knopf(r.wurzel, 'Weiter zur Vorschau')!.click();
  for (let i = 0; i < 10 && !knopf(r.wurzel, 'In WLO ablegen'); i++) await warte();
  return r;
}

const schritte = (h: Host) => h.ablegen.mock.calls.map((c) => (c[0] as { schritt: string; index?: number }));

beforeAll(() => {
  // jsdom liest Blobs nicht überall als ArrayBuffer; die Prüfsumme rechnet das echte `crypto.subtle`.
  if (!('arrayBuffer' in Blob.prototype)) {
    Object.defineProperty(Blob.prototype, 'arrayBuffer', { configurable: true, value: async () => new ArrayBuffer(4) });
  }
});
afterEach(() => { document.body.innerHTML = ''; });

describe('<boerdi-ui-upload> Übertragen in WLO (U3-3b)', () => {
  it('ohne Schalter ist WLO nicht wählbar — mit Grund, ohne „Hochladen“', async () => {
    const { wurzel } = await erzeugt(host(), { ...DATEN, schalter: { ablage_in_wlo: false } });
    expect(wurzel.querySelector('h4')).toBeNull();
    expect(knopf(wurzel, 'Weiter zur Vorschau')).toBeUndefined();
    expect(wurzel.textContent).toContain('nicht wählbar – gerade ausgeschaltet');
  });

  // Paket U4: das Angebot mit eigenem Knopf ist in der Frage nach dem Ort aufgegangen
  it('Ort WLO vorgewählt: nennt, was nicht mitgeht — noch wird nichts gesendet', async () => {
    const h = host();
    const { wurzel } = await erzeugt(h);
    expect((wurzel.querySelector('input[data-ort="wlo"]') as HTMLInputElement).checked).toBe(true);
    expect(wurzel.querySelector('h4')).toBeNull();
    expect(wurzel.textContent).toContain('1 Datei hat eine Art, die WLO hier nicht annimmt');
    expect(knopf(wurzel, 'Weiter zur Vorschau')!.classList.contains('u__haupt')).toBe(true);
    expect(h.ablegen).not.toHaveBeenCalled();
  });

  it('prüfen → Vorschau mit Ziel und Namen; die Freigabe trägt Titel, sha256, Größe, Art', async () => {
    const { h, wurzel } = await bisVorschau();
    const vorbereiten = h.ablegen.mock.calls[0][0];
    expect(vorbereiten.schritt).toBe('vorbereiten');
    expect(vorbereiten.ordner).toBe('Physik');
    expect(vorbereiten.eintraege.map((e: { titel: string }) => e.titel)).toEqual(['Hebel', 'Linse']);
    expect(vorbereiten.eintraege[0]).toMatchObject({ groesse: 100, art: 'pdf', rolle: 'inhalt' });
    expect(vorbereiten.eintraege[0].sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(JSON.stringify(vorbereiten)).not.toContain('Physik/');      // keine Pfade
    expect(wurzel.textContent).toContain('neuer Ordner „Physik“');
    expect(wurzel.textContent).toContain('Hebel.pdf');
    expect(knopf(wurzel, 'Abbrechen')).toBeTruthy();
    // Die Auswahl ist jetzt fest — eine andere Rolle machte die Freigabe falsch.
    expect([...wurzel.querySelectorAll('select')].every((s) => s.disabled)).toBe(true);
  });

  it('Abbrechen in der Vorschau sendet nichts', async () => {
    const { h, wurzel } = await bisVorschau();
    knopf(wurzel, 'Abbrechen')!.click();
    expect(knopf(wurzel, 'Weiter zur Vorschau')).toBeTruthy();
    expect(wurzel.querySelector('fieldset')).not.toBeNull();
    expect(schritte(h).map((s) => s.schritt)).toEqual(['vorbereiten']);
  });

  it('überträgt nacheinander, zeigt Stand und Link, legt vorgang.json ab und merkt die Zahlen vor', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    let melde: (a: number) => void = () => undefined;
    const { wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce((s: { onFortschritt: (a: number) => void }) => {
      melde = s.onFortschritt;
      return new Promise((r) => { erste = r; });
    });
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    melde(0.5);
    expect(wurzel.textContent).toContain('Datei 1 von 2 wird übertragen … 50 %');
    expect(schritte(h).filter((s) => s.schritt === 'datei')).toHaveLength(1);      // eine zur Zeit
    erste({ index: 0, stand: 'stored', link: 'https://repo.test/render/n-0' });
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(schritte(h).map((s) => s.schritt)).toEqual(['vorbereiten', 'datei', 'datei', 'abschluss']);
    expect(wurzel.textContent).toContain('2 von 2 Dateien in WLO abgelegt.');
    const anker = wurzel.querySelector('a.u__link') as HTMLAnchorElement;
    expect(anker.href).toBe('https://repo.test/render/n-0?bsid=1');
    expect(anker.textContent).toBe('Hebel.pdf in WLO ansehen');
    expect(anker.rel).toContain('noopener');
    const symbol = wurzel.querySelector('.u__symbol') as HTMLElement;
    expect(symbol.getAttribute('aria-hidden')).toBe('true');
    expect(wurzel.querySelector('.u__eintrag')?.textContent).toContain('abgelegt');
    // Paket U4: `bereitgestellt` mit Ort wlo — je abgelegter Datei ihre Nummer i und Rolle
    expect(h.vormerken.mock.calls.at(-1)?.[0]).toMatchObject({ aktion: 'bereitgestellt', ort: 'wlo',
      dateien: [{ i: 0, rolle: 'inhalt' }, { i: 1, rolle: 'inhalt' }],
      ablage: { gesamt: 2, abgelegt: 2, vorgang_abgelegt: true, layout: 'ordner' } });
    knopf(wurzel, 'Im Chat weitermachen')!.click();
    await warte();
    const [daten, blase] = h.antworten.mock.calls[0];
    expect(blase).toBe('2 von 2 Dateien in meinen persönlichen Bereich in WLO übertragen.');
    expect(daten).toMatchObject({ aktion: 'bereitgestellt', ort: 'wlo' });
    expect(daten.dateien[0]).not.toHaveProperty('upload_id');
    expect(JSON.stringify(daten)).not.toContain('n-0');
  });

  it('ein Fehler einer Datei geht weiter; einer des Stapels hält an, der Rest bleibt „nicht gesendet“', async () => {
    const h = host();
    const { wurzel } = await bisVorschau(h, [Object.assign(new Error('x'), { status: 422, code: 'passt_nicht' })]);
    knopf(wurzel, 'In WLO ablegen')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(wurzel.textContent).toContain('nicht abgelegt: Die Datei passt nicht zur Freigabe');
    expect(wurzel.textContent).toContain('1 von 2 Dateien in WLO abgelegt.');

    document.body.innerHTML = '';
    const h2 = host();
    const r2 = await bisVorschau(h2, [Object.assign(new Error('x'), { status: 403, code: 'nur_angemeldet' })]);
    knopf(r2.wurzel, 'In WLO ablegen')!.click();
    for (let i = 0; i < 10 && !knopf(r2.wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(schritte(h2).filter((s) => s.schritt === 'datei')).toHaveLength(1);
    expect(r2.wurzel.querySelector('.u__fehler')?.textContent).toContain('bitte bei WLO anmelden');
    expect(r2.wurzel.textContent).toContain('nicht gesendet');
    expect(schritte(h2).some((s) => s.schritt === 'abschluss')).toBe(false);
  });

  it('Anhalten wirkt nach der laufenden Datei; danach gehen nur die übrigen noch einmal', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    const { wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise((r) => { erste = r; }));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    knopf(wurzel, 'Nach dieser Datei anhalten')!.click();
    expect(wurzel.textContent).toContain('Hält nach dieser Datei an');
    erste({ index: 0, stand: 'stored', link: null });
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(schritte(h).filter((s) => s.schritt === 'datei')).toHaveLength(1);
    expect(wurzel.textContent).toContain('nicht gesendet');
    backend(h);
    knopf(wurzel, 'Nicht übertragene noch einmal senden')!.click();
    for (let i = 0; i < 10 && !wurzel.textContent?.includes('2 von 2 Dateien'); i++) await warte();
    const dateien = schritte(h).filter((s) => s.schritt === 'datei');
    expect(dateien.map((s) => s.index)).toEqual([0, 1]);
    expect(wurzel.textContent).toContain('2 von 2 Dateien in WLO abgelegt.');
  });

  it('ein Fehler beim Vorbereiten sagt den Grund; darunter wieder die Frage — „Hochladen“ versucht neu', async () => {
    const h = host();
    h.ablegen.mockRejectedValueOnce(Object.assign(new Error('x'), { status: 0, code: 'netz' }));
    const { wurzel } = await erzeugt(h);
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !wurzel.querySelector('.u__fehler'); i++) await warte();
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('Keine Verbindung zum Server.');
    backend(h);
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen'); i++) await warte();
    expect(knopf(wurzel, 'In WLO ablegen')).toBeTruthy();
  });

  // ── Review U3-3b ─────────────────────────────────────────────────────────────────────

  it('Befund 1: das Layout „folder“ des MCP heißt in der Vorschau „neuer Ordner“, „flat“ flach', async () => {
    const { wurzel } = await bisVorschau();
    expect(wurzel.textContent).toContain('neuer Ordner „Physik“');
    document.body.innerHTML = '';
    const h = host();
    backend(h);
    h.ablegen.mockImplementation(async (s: { schritt: string }) =>
      s.schritt === 'vorbereiten' ? { ...PLAN, layout: 'flat' } : { stand: 'stored' });
    const r = await erzeugt(h);
    knopf(r.wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(r.wurzel, 'In WLO ablegen'); i++) await warte();
    expect(r.wurzel.textContent).toContain('ohne eigenen Ordner');
  });

  it('Befund 2: ein entferntes Element sendet nach der laufenden Datei nichts mehr', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    const { el, wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise((r) => { erste = r; }));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    el.remove();
    erste({ index: 0, stand: 'stored', link: null });
    for (let i = 0; i < 5; i++) await warte();
    expect(schritte(h).filter((s) => s.schritt === 'datei')).toHaveLength(1);
  });

  it('Befund 2: ein Abbruch (Widget geschlossen) beendet den Stapel statt als Dateifehler weiterzulaufen', async () => {
    const h = host();
    const { wurzel } = await bisVorschau(h, [new DOMException('weg', 'AbortError')]);
    knopf(wurzel, 'In WLO ablegen')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(schritte(h).filter((s) => s.schritt === 'datei')).toHaveLength(1);
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('Das Übertragen wurde abgebrochen.');
  });

  it('Befund 3: der Fortschrittsbalken ist keine Ablagefläche', async () => {
    const h = host();
    const { wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise(() => undefined));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    const balken = wurzel.querySelector('progress') as HTMLProgressElement;
    expect(balken.closest('[data-ablage]')).toBeNull();
  });

  it('Befund 4: „Im Chat weitermachen“ zweimal schnell — ein Abschluss, eine Antwort', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    const { wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise((r) => { erste = r; }));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    knopf(wurzel, 'Nach dieser Datei anhalten')!.click();
    erste({ index: 0, stand: 'stored', link: null });
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    const weiter = knopf(wurzel, 'Im Chat weitermachen')!;
    weiter.click();
    weiter.click();
    for (let i = 0; i < 10 && !h.antworten.mock.calls.length; i++) await warte();
    expect(schritte(h).filter((s) => s.schritt === 'abschluss')).toHaveLength(1);
    expect(h.antworten).toHaveBeenCalledTimes(1);
  });

  it('Befund 5: nach „Anhalten“ bleibt der Fokus im Modul', async () => {
    const h = host();
    const { wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise(() => undefined));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    const anhalten = knopf(wurzel, 'Nach dieser Datei anhalten')!;
    anhalten.focus();
    anhalten.click();
    expect((wurzel.activeElement as HTMLElement | null)?.dataset['fokus']).toBe('s:ablage');
  });

  it('Befund 7: ohne Antwort von WLO „unklar“ — und das lässt sich nachfragen', async () => {
    const h = host();
    const { wurzel } = await bisVorschau(h, [Object.assign(new Error('x'), { status: 503, code: 'nicht_erreichbar' })]);
    knopf(wurzel, 'In WLO ablegen')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(wurzel.querySelector('.u__eintrag')?.textContent).toContain('unklar');
    expect(h.vormerken.mock.calls.at(-1)?.[0]).toMatchObject({ ablage: { unklar: 1, fehler: 0, abgebrochen: 1 } });
    backend(h);
    knopf(wurzel, 'Nicht übertragene noch einmal senden')!.click();
    for (let i = 0; i < 10 && !wurzel.textContent?.includes('2 von 2 Dateien'); i++) await warte();
    expect(schritte(h).filter((s) => s.schritt === 'datei').map((s) => s.index)).toEqual([0, 0, 1]);
  });

  it('Befund 8: ein langer Ordnername geht gekürzt in die Freigabe (Backend: 120 Zeichen)', async () => {
    const h = host();
    backend(h);
    const el = document.createElement('boerdi-ui-upload') as NachladeElement;
    el.host = h;
    el.daten = DATEN;
    el.kontext = KONTEXT;
    document.body.appendChild(el);
    const wurzel = el.shadowRoot as ShadowRoot;
    const lang = 'O'.repeat(200);
    const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [datei(`${lang}/a.pdf`)], configurable: true });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await warte();
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !h.ablegen.mock.calls.length; i++) await warte();
    expect(h.ablegen.mock.calls[0][0].ordner).toHaveLength(120);
  });

  it('Befund 9: die Liste ist ein benannter, per Tastatur erreichbarer Bereich', async () => {
    const { wurzel } = await bisVorschau();
    const bereich = wurzel.querySelector('.u__ergebnis') as HTMLElement;
    expect(bereich.getAttribute('role')).toBe('region');
    expect(bereich.getAttribute('aria-label')).toBe('Dateien der Übertragung');
    expect(bereich.tabIndex).toBe(0);
  });

  it('Befund 6: nach einem Halt wegen der Anmeldung kein sinnloses Nachsenden', async () => {
    const h = host();
    const { wurzel } = await bisVorschau(h, [Object.assign(new Error('x'), { status: 403, code: 'nur_angemeldet' })]);
    knopf(wurzel, 'In WLO ablegen')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(knopf(wurzel, 'Nicht übertragene noch einmal senden')).toBeUndefined();
  });

  it('nur lesen: die Zahlen der Übertragung', async () => {
    const { wurzel } = await erzeugt(host(), DATEN, { nurLesen: true, antwort: {
      aktion: 'uebertragen', zahlen: { ordner: 1, inhalte: 2, strukturdokumente: 0 },
      ablage: { gesamt: 2, abgelegt: 1, unklar: 1, fehler: 0, abgebrochen: 0 } } });
    expect(wurzel.textContent).toContain('Übertragen: 1 von 2 in WLO abgelegt.');
  });
});

describe('<boerdi-ui-upload> Übertragen — Querschnitts-Review 2026-11-06', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  const status = (w: ShadowRoot) => w.querySelector('[aria-live]')?.textContent ?? '';

  it('M1/M2: wird der Block mitten im Senden „nur lesen“, läuft der Stapel sichtbar weiter — ohne Antwortknopf', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    const { el, wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise((r) => { erste = r as (v: unknown) => void; }));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    const vorgemerkt = h.vormerken.mock.calls.length;   // der Befund des Erfassens kam schon vorher
    el.kontext = { ...KONTEXT, nurLesen: true };
    expect(wurzel.textContent).not.toContain('Nicht verwendet');
    expect(wurzel.querySelector('progress[data-ablage-balken]')).not.toBeNull();
    erste({ index: 0, stand: 'stored', link: null });
    for (let i = 0; i < 10 && !wurzel.textContent?.includes('2 von 2 Dateien'); i++) await warte();
    expect(schritte(h).filter((x) => x.schritt === 'datei')).toHaveLength(2);
    expect(wurzel.textContent).toContain('2 von 2 Dateien');
    expect(knopf(wurzel, 'Im Chat weitermachen')).toBeUndefined();
    expect(h.antworten).not.toHaveBeenCalled();
    expect(h.vormerken).toHaveBeenCalledTimes(vorgemerkt);
  });

  it('Review Q1, Befund 4: „nur lesen“ mitten im Senden — der Stapel wird trotzdem abgeschlossen', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    const { el, wurzel } = await bisVorschau(h, [Object.assign(new Error('x'), { status: 504, code: 'zu_langsam' })]);
    h.ablegen.mockImplementationOnce(() => new Promise((r) => { erste = r as (v: unknown) => void; }));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    el.kontext = { ...KONTEXT, nurLesen: true };
    erste({ index: 0, stand: 'stored', link: null });
    for (let i = 0; i < 10 && !schritte(h).some((x) => x.schritt === 'abschluss'); i++) await warte();
    // Datei 1 ist „unklar“ (nachsendbar) — ohne Antwortknopf schlösse sonst niemand den Stapel ab.
    expect(schritte(h).map((x) => x.schritt)).toContain('abschluss');
  });

  it('nur lesen ohne Übertragung: der Fokus fällt nicht auf body', async () => {
    const { el, wurzel } = await erzeugt();
    (knopf(wurzel, 'Weiter zur Vorschau') as HTMLButtonElement).focus();
    el.kontext = { ...KONTEXT, nurLesen: true };
    expect(wurzel.activeElement).not.toBeNull();
  });

  it('FE-4: die Datei-Eingaben bleiben dieselben, auch wenn ein Zug kommt und geht', () => {
    const el = document.createElement('boerdi-ui-upload') as NachladeElement;
    el.host = host();
    el.daten = DATEN;
    el.kontext = KONTEXT;
    el.beschaeftigt = false;
    document.body.appendChild(el);
    const wurzel = el.shadowRoot as ShadowRoot;
    const vorher = wurzel.querySelector('input[webkitdirectory]');
    expect(vorher).not.toBeNull();
    el.beschaeftigt = true;
    el.beschaeftigt = false;
    expect(wurzel.querySelector('input[webkitdirectory]')).toBe(vorher);
  });

  // P2: der Satz nennt den Knopf, der wirklich ablegt — „Weiter zur Vorschau“ legt noch nichts ab
  it('FE-3/U4: mit Ort WLO sagt der Datenschutz-Satz, dass die Dateien erst nach der Bestätigung dorthin gehen und bleiben', async () => {
    const { wurzel } = await erzeugt();
    expect(wurzel.textContent).not.toContain('alle Inhalte bleiben auf deinem Gerät');
    // Review P2, Befund 1: ohne `erschliessen` in den Daten nur ablegen
    expect(wurzel.textContent).toContain('„Weiter zur Vorschau“ zeigt zuerst, was abgelegt wird; erst „In WLO ablegen“ '
      + 'legt die Dateien in deinem persönlichen Bereich in WLO ab. Dort bleiben sie, bis du sie löschst');
  });

  it('FE-5: eine Fehlerzeile ist keine assertive Region, die bei jedem Zeichnen neu ansagt', async () => {
    const h = host();
    const { el, wurzel } = await bisVorschau(h, [Object.assign(new Error('x'), { status: 403, code: 'nur_angemeldet' })]);
    knopf(wurzel, 'In WLO ablegen')!.click();
    for (let i = 0; i < 10 && !wurzel.querySelector('.u__fehler'); i++) await warte();
    expect(wurzel.querySelector('[role="alert"]')).toBeNull();
    expect(status(wurzel)).toContain('anmelden');
    el.beschaeftigt = true;
    el.beschaeftigt = false;
    expect(wurzel.querySelector('[role="alert"]')).toBeNull();
  });

  it('die Vorschau versteht das Layout in beiden Wortschätzen (ordner/folder)', async () => {
    const h = host();
    backend(h);
    h.ablegen.mockImplementation(async (x: { schritt: string; index?: number }) =>
      (x.schritt === 'vorbereiten' ? { ...PLAN, layout: 'ordner' } : { index: x.index, stand: 'stored' }));
    const r = await erzeugt(h);
    knopf(r.wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(r.wurzel, 'In WLO ablegen'); i++) await warte();
    expect(r.wurzel.textContent).toContain('neuer Ordner „Physik“');
  });

  it('zeigt neben der Vorschau die eigenen letzten Ablagen (Paket M6)', async () => {
    const h = host();
    h.ablegen.mockImplementation(async (s: { schritt: string }) => s.schritt === 'vorbereiten'
      ? { ...PLAN, letzte: { ablagen: [{ titel: 'Physik', datum: 'kein Datum', lesbar: true, stored: 2, failed: 0, open: 0 }] } }
      : { stand: 'stored' });
    const r = await erzeugt(h);
    knopf(r.wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(r.wurzel, 'In WLO ablegen'); i++) await warte();
    const kasten = r.wurzel.querySelector('details.u__letzte');
    expect(kasten?.querySelector('summary')?.textContent).toBe('Deine letzte Ablage in WLO (1)');
    expect(kasten?.textContent).toContain('Physik (kein Datum) – 2 abgelegt');
    expect(kasten?.textContent).not.toContain('gescheitert');            // Nullwerte fallen weg
    expect(schritte(h).map((x) => x.schritt)).toEqual(['vorbereiten']);   // kein zusätzlicher Aufruf
  });

  it('die aufgeklappte Liste bleibt beim Neuzeichnen offen (Review M6, Befund 4)', async () => {
    const h = host();
    h.ablegen.mockImplementation(async (s: { schritt: string }) => s.schritt === 'vorbereiten'
      ? { ...PLAN, letzte: { gekappt: true, ablagen: [{ titel: 'Physik', datum: 'x', lesbar: false }] } }
      : { stand: 'stored' });
    const r = await erzeugt(h);
    knopf(r.wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(r.wurzel, 'In WLO ablegen'); i++) await warte();
    const kasten = r.wurzel.querySelector('details.u__letzte') as HTMLDetailsElement;
    expect(kasten.textContent).toContain('es können weitere fehlen');
    kasten.open = true;
    kasten.dispatchEvent(new Event('toggle'));
    r.el.beschaeftigt = true;                        // ein Neuzeichnen (Zug beginnt)
    await warte();
    expect((r.wurzel.querySelector('details.u__letzte') as HTMLDetailsElement).open).toBe(true);
  });

  it('der Fokus bleibt in der Ergebnisliste, während Dateien fertig werden (Review 2026-11-07)', async () => {
    const h = host();
    let erste: (v: unknown) => void = () => undefined;
    const { el, wurzel } = await bisVorschau(h);
    h.ablegen.mockImplementationOnce(() => new Promise((r) => { erste = r; }));
    knopf(wurzel, 'In WLO ablegen')!.click();
    await warte();
    (wurzel.querySelector('.u__ergebnis') as HTMLElement).focus();
    erste({ index: 0, stand: 'stored', link: null });
    for (let i = 0; i < 10 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect((wurzel.activeElement as HTMLElement | null)?.classList.contains('u__ergebnis')).toBe(true);
    expect(el.shadowRoot?.activeElement).not.toBeNull();
  });

  it('dieselben Werte zeichnen nicht neu (Review 2026-11-07)', async () => {
    const { el, wurzel } = await erzeugt(host());
    const vorher = wurzel.querySelector('button');
    expect(vorher).not.toBeNull();
    el.beschaeftigt = false;
    el.kontext = { ...el.kontext };
    expect(wurzel.querySelector('button')).toBe(vorher);
  });

  // W4-Anbindung: die Rolle ist Teil der Freigabe — die Vorschau nennt sie. Review P1, NIT 7: mit den
  // Namen der Rollen-Auswahl (Gliederung / Gliederung und Material), nicht „Strukturdokument“
  it('die Vorschau nennt die Gliederung in den Worten der Rollen-Auswahl', async () => {
    const plan = { ...PLAN, eintraege: [{ ...PLAN.eintraege[0], rolle: 'struktur' }, { ...PLAN.eintraege[1], rolle: 'beides' }] };
    const { wurzel } = await bisVorschau(host(), [], plan);
    const zeilen = [...wurzel.querySelectorAll('.u__eintrag')];
    expect(zeilen[0].querySelector('.u__rolle')?.textContent).toBe('Gliederung');
    expect(zeilen[1].querySelector('.u__rolle')?.textContent).toBe('Gliederung und Material');
    document.body.innerHTML = '';
    const ohne = await bisVorschau(host(), [], PLAN);
    expect(ohne.wurzel.querySelector('.u__eintrag .u__rolle')).toBeNull();
  });

  // Review W4, Befund 7: eine in der Oberfläche gesetzte Rolle kommt als `struktur` in der Freigabe an.
  it('die gewählte Rolle reist mit der Freigabe', async () => {
    const h = host();
    backend(h);
    const { wurzel } = await erzeugt(h);
    const wahl = wurzel.querySelector('select[aria-label="Rolle von Hebel.pdf"]') as HTMLSelectElement;
    wahl.value = 'struktur';
    wahl.dispatchEvent(new Event('change', { bubbles: true }));
    await warte();
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen'); i++) await warte();
    const vorbereiten = h.ablegen.mock.calls[0][0];
    expect(vorbereiten.eintraege.map((e: { rolle: string }) => e.rolle)).toEqual(['struktur', 'inhalt']);
  });
});


// Plan 2026-11-16, TG-3b: die Freigabe trägt je Datei ihre feste Nummer `i` aus der Auswahl — nicht
// die Stelle in der gefilterten Übertragungsliste.
describe('<boerdi-ui-upload> feste Nummer je Datei (TG-3b)', () => {
  it('eine zu große Datei fehlt in der Freigabe — die übrigen behalten ihr `i`', async () => {
    const h = host();
    backend(h);
    const el = document.createElement('boerdi-ui-upload') as NachladeElement;
    el.host = h;
    el.daten = { ...DATEN, grenzen: { ...DATEN.grenzen, max_mb_ablage: 1 } };
    el.kontext = KONTEXT;
    el.beschaeftigt = false;
    document.body.appendChild(el);
    const wurzel = el.shadowRoot as ShadowRoot;
    const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
    // sortiert nach Pfad: 0 Grosse.pdf (2 MB, über der Grenze der Ablage), 1 Hebel.pdf, 2 Linse.pdf
    Object.defineProperty(input, 'files', {
      value: [datei('Physik/Hebel.pdf'), datei('Physik/Grosse.pdf', 2 * 1024 * 1024), datei('Physik/Linse.pdf')],
      configurable: true,
    });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await warte();
    const nummern = (h.vormerken.mock.calls.at(-1)?.[0] as { struktur: { dateiliste: { name: string; i: number }[] } })
      .struktur.dateiliste.map((d) => [d.name, d.i]);
    expect(nummern).toEqual([['Grosse.pdf', 0], ['Hebel.pdf', 1], ['Linse.pdf', 2]]);
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let n = 0; n < 10 && !knopf(wurzel, 'In WLO ablegen'); n++) await warte();
    const vorbereiten = h.ablegen.mock.calls[0][0];
    expect(vorbereiten.eintraege.map((e: { titel: string; i: number }) => [e.titel, e.i]))
      .toEqual([['Hebel', 1], ['Linse', 2]]);
  });
});

// Plan 2026-11-20, P2: das Häkchen geht mit dem Vorbereiten; der letzte Klick — der, der ablegt (in P3 die
// Zustimmung zum Flow) — heißt danach, was der Server festhielt
describe('<boerdi-ui-upload> Häkchen beim Ablegen (P2)', () => {
  const haken = (w: ShadowRoot) => w.querySelector('input[type="checkbox"][data-erschliessen]') as HTMLInputElement;
  // Review P2, Befund 1: das Häkchen sieht nur ein Ablauf-Schritt vor (`erschliessen` gesetzt)
  const MIT_HAKEN = { ...DATEN, erschliessen: true };

  it('gesetzt: `erschliessen: true` geht mit; hält der Server es fest, heißt der Knopf „In WLO ablegen und erschließen“', async () => {
    const h = host();
    backend(h, [], { ...PLAN, erschliessen: true });
    const { wurzel } = await erzeugt(h, MIT_HAKEN);
    expect(haken(wurzel).checked).toBe(true);
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen und erschließen'); i++) await warte();
    expect(h.ablegen.mock.calls[0][0]).toMatchObject({ schritt: 'vorbereiten', erschliessen: true });
    expect(knopf(wurzel, 'In WLO ablegen und erschließen')!.classList.contains('u__haupt')).toBe(true);
    expect(knopf(wurzel, 'In WLO ablegen')).toBeUndefined();
  });

  it('abgewählt: `erschliessen: false`, der Knopf heißt „In WLO ablegen“', async () => {
    const h = host();
    backend(h, [], { ...PLAN, erschliessen: false });
    const { wurzel } = await erzeugt(h, MIT_HAKEN);
    const x = haken(wurzel);
    x.checked = false;
    x.dispatchEvent(new Event('change', { bubbles: true }));
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen'); i++) await warte();
    expect(h.ablegen.mock.calls[0][0]).toMatchObject({ schritt: 'vorbereiten', erschliessen: false });
    expect(knopf(wurzel, 'In WLO ablegen')).toBeTruthy();
  });

  it('ohne Flow (`ohne_erschliessung`) geht `erschliessen: false` mit, auch wenn die Daten es vorgeben', async () => {
    const h = host();
    backend(h);
    const daten = { ...DATEN, erschliessen: true, orte: { vorauswahl: 'wlo', chat: { geht: false, grund: 'aus' },
      wlo: { geht: true, hinweis: 'ohne_erschliessung' }, namen: { geht: true } } };
    const { wurzel } = await erzeugt(h, daten);
    expect(haken(wurzel)).toBeNull();
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen'); i++) await warte();
    expect(h.ablegen.mock.calls[0][0]).toMatchObject({ erschliessen: false });
  });

  it('ohne `erschliessen` in den Daten (freier Chat): kein Häkchen, `erschliessen: false`, der Knopf heißt „In WLO ablegen“', async () => {
    const h = host();
    backend(h);
    const { wurzel } = await erzeugt(h);
    expect(haken(wurzel)).toBeNull();
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen'); i++) await warte();
    expect(h.ablegen.mock.calls[0][0]).toMatchObject({ schritt: 'vorbereiten', erschliessen: false });
    expect(knopf(wurzel, 'In WLO ablegen und erschließen')).toBeUndefined();
  });

  // Review P2, Befund 2: in der Vorschau gilt, was der Server festhielt — Satz und Knopf sagen dasselbe
  it('in der Vorschau folgt der Datenschutz-Satz dem Wert des Servers, nicht dem Häkchen', async () => {
    const h = host();
    backend(h, [], { ...PLAN, erschliessen: false });
    const { wurzel } = await erzeugt(h, MIT_HAKEN);
    expect(haken(wurzel).checked).toBe(true);
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen'); i++) await warte();
    expect(h.ablegen.mock.calls[0][0]).toMatchObject({ erschliessen: true });
    expect(wurzel.textContent).toContain('erst „In WLO ablegen“ legt die Dateien');
    expect(wurzel.textContent).toContain('Metadaten erzeugt WLO dabei nicht.');
    expect(wurzel.textContent).not.toContain('erst „In WLO ablegen und erschließen“');
  });

  it('die Antwort nennt, was der Server zum Häkchen festhielt (`ablage.erschliessen`)', async () => {
    const h = host();
    backend(h, [], { ...PLAN, erschliessen: true });
    const { wurzel } = await erzeugt(h, MIT_HAKEN);
    knopf(wurzel, 'Weiter zur Vorschau')!.click();
    for (let i = 0; i < 10 && !knopf(wurzel, 'In WLO ablegen und erschließen'); i++) await warte();
    knopf(wurzel, 'In WLO ablegen und erschließen')!.click();
    for (let i = 0; i < 20 && !knopf(wurzel, 'Im Chat weitermachen'); i++) await warte();
    expect(h.vormerken.mock.calls.at(-1)?.[0]).toMatchObject({ ort: 'wlo', ablage: { erschliessen: true } });
  });
});

describe('<boerdi-ui-upload> nach der Ablage (zweites Review P4–P6, MINOR 1)', () => {
  /** Bis „Im Chat weitermachen“: legt die Dateien in WLO ab (`dateien`: Antworten je Datei). */
  async function abgelegt(dateien: Array<Record<string, unknown> | Error> = [], sprache: 'de' | 'en' = 'de') {
    const h = host();
    backend(h, dateien);
    const r = await erzeugt(h, DATEN, { sprache });
    const [vorschau, ablegen, weiter] = sprache === 'de'
      ? ['Weiter zur Vorschau', 'In WLO ablegen', 'Im Chat weitermachen']
      : ['Continue to preview', 'Store in WLO', 'Continue in the chat'];
    knopf(r.wurzel, vorschau)!.click();
    for (let i = 0; i < 10 && !knopf(r.wurzel, ablegen); i++) await warte();
    knopf(r.wurzel, ablegen)!.click();
    for (let i = 0; i < 10 && !knopf(r.wurzel, weiter); i++) await warte();
    return { ...r, h };
  }

  it('liegen Dateien in WLO, ist „Andere Auswahl“ gesperrt — mit Grund, und ein Klick setzt nichts zurück', async () => {
    const { h, wurzel } = await abgelegt();
    const zurueck = knopf(wurzel, 'Andere Auswahl')!;
    expect(zurueck.disabled).toBe(true);
    const grund = wurzel.getElementById(zurueck.getAttribute('aria-describedby') ?? '');
    expect(grund?.textContent).toBe('Die Dateien liegen schon in WLO.');
    expect(knopf(wurzel, 'Im Chat weitermachen')!.disabled).toBe(false);
    zurueck.dataset['zurueck'] = '1';
    zurueck.disabled = false;      // auch ein erzwungener Klick setzt die Auswahl nicht zurück
    zurueck.click();
    await warte();
    expect(h.vormerken).not.toHaveBeenCalledWith(null);
    expect(knopf(wurzel, 'Im Chat weitermachen')).toBeTruthy();
  });

  it('auf Englisch nennt der Grund dasselbe', async () => {
    const { wurzel } = await abgelegt([], 'en');
    const zurueck = knopf(wurzel, 'Choose again')!;
    expect(zurueck.disabled).toBe(true);
    expect(wurzel.getElementById(zurueck.getAttribute('aria-describedby') ?? '')?.textContent)
      .toBe('The files are already in WLO.');
  });

  it('ist nichts abgelegt, bleibt „Andere Auswahl“ frei — ohne den Grund', async () => {
    const fehler = () => Object.assign(new Error('x'), { status: 422, code: 'passt_nicht' });
    const { wurzel } = await abgelegt([fehler(), fehler()]);
    const zurueck = knopf(wurzel, 'Andere Auswahl')!;
    expect(zurueck.disabled).toBe(false);
    expect(zurueck.hasAttribute('aria-describedby')).toBe(false);
    expect(wurzel.textContent).not.toContain('Die Dateien liegen schon in WLO.');
  });
});
