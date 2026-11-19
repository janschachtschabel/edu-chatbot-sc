// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import './ui-upload.element';

/**
 * Review der Oberfläche zu Paket U (2026-11-19): „Hier im Chat“ an der Sitzungsgrenze, Anhalten,
 * Dubletten, gedrosselte Ansagen, Grenze je Datei, Sitzungsrest (`lokal_frei_*`, `grenze_sitzung`)
 * und ein veralteter Fehler der WLO-Übertragung.
 */
const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const GRENZEN = { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50, lokal_max_dateien: 10, lokal_max_mb_gesamt: 50, lokal_aufbewahrung_h: 24 };
const ORTE_ANONYM = {
  vorauswahl: 'chat', chat: { geht: true, ueber_grenze: 'ueber_grenze_anmelden' },
  wlo: { geht: false, grund: 'nur_angemeldet' }, namen: { geht: true },
};
const ORTE_WLO = { vorauswahl: 'wlo', chat: { geht: true, ueber_grenze: 'ueber_grenze' }, wlo: { geht: true }, namen: { geht: true } };
const ANONYM = { zweck: 'bereitstellen', grenzen: GRENZEN, orte: ORTE_ANONYM, schalter: { dokument_im_chat: true, ablage_in_wlo: false } };
const ANGEMELDET = { zweck: 'bereitstellen', grenzen: { ...GRENZEN, max_mb_ablage: 10 }, orte: ORTE_WLO,
  schalter: { dokument_im_chat: true, ablage_in_wlo: true } };

type Fn = ReturnType<typeof vi.fn>;
type Host = ElementHost & { antworten: Fn; vormerken: Fn; hochladen: Fn; ablegen: Fn };

function host(): Host {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), link: vi.fn(() => ({ href: '', hinweis: '' })), aktion: vi.fn(),
    beschaeftigt: vi.fn(() => false), antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(),
    ablegen: vi.fn(),
  } as never;
}

/** Mit festem Änderungsdatum — es gehört zum Schlüssel der Dubletten (zweites Review, 1/3). */
function datei(pfad: string, size = 100, type = 'application/pdf', lastModified = 1_700_000_000_000): File {
  const f = new File([new Uint8Array(size)], pfad.split('/').pop() ?? pfad, { type, lastModified });
  Object.defineProperty(f, 'webkitRelativePath', { value: pfad });
  return f;
}

const ID = (n: number) => `11111111-2222-4333-8444-55555555555${n}`;
const befund = (n: number) => ({ upload_id: ID(n), name: `d${n}.pdf`, format: 'pdf', rolle: 'inhalt', ueberschriften_vorschau: [],
  befund: { seiten: 1, woerter: 100, abschnitte: 2, gliederung_art: 'teile', warnungen: [] } });
const abgelehnt = (code: string, status = 409) => Object.assign(new Error('x'), { status, code });

const warte = () => new Promise((r) => setTimeout(r, 0));
const knopf = (w: ShadowRoot, text: string) =>
  [...w.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const fokus = (w: ShadowRoot) => (w.activeElement as HTMLElement | null)?.dataset['fokus'];
const radio = (w: ShadowRoot, ort: string) => w.querySelector(`input[type="radio"][data-ort="${ort}"]`) as HTMLInputElement;
const erklaerung = (w: ShadowRoot, ort: string) => w.getElementById(radio(w, ort).getAttribute('aria-describedby') ?? '-')?.textContent;

async function feld(dateien: File[], h = host(), daten: Record<string, unknown> = ANONYM, kontext: Partial<ModulKontext> = {}) {
  const el = document.createElement('boerdi-ui-upload') as NachladeElement;
  el.host = h;
  el.daten = daten;
  el.kontext = { ...KONTEXT, ...kontext };
  el.beschaeftigt = false;
  document.body.appendChild(el);
  const wurzel = el.shadowRoot as ShadowRoot;
  const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: dateien, configurable: true });
  input.dispatchEvent(new Event('change', { bubbles: true }));
  await warte();
  return { el, h, wurzel };
}

const DREI = () => [datei('P/a.pdf'), datei('P/b.pdf', 200), datei('P/c.pdf', 300)];

/** Hochladen, das erst auf `fertig[k](befund)` bzw. `scheitert[k](fehler)` antwortet. */
function haendisch(h: Host) {
  const fertig: ((b: unknown) => void)[] = [];
  const scheitert: ((f: unknown) => void)[] = [];
  h.hochladen.mockImplementation(() => new Promise((ok, nein) => { fertig.push(ok); scheitert.push(nein); }));
  return { fertig, scheitert };
}

afterEach(() => { document.body.innerHTML = ''; });

describe('Review Oberfläche 1: Sitzungsgrenze beim Hochladen „Hier im Chat“', () => {
  it('`grenze_anzahl` bei Datei 2 von 3 beendet den Lauf — „Mit den gelesenen weiter“ antwortet mit Datei 1', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1)).mockRejectedValueOnce(abgelehnt('grenze_anzahl')).mockResolvedValue(befund(3));
    const { wurzel } = await feld(DREI(), h);
    knopf(wurzel, 'Hochladen')!.click();
    for (let i = 0; i < 5; i++) await warte();
    // Datei 3 geht nicht mehr hoch: jede weitere scheiterte an derselben Grenze
    expect(h.hochladen).toHaveBeenCalledTimes(2);
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('„b.pdf“: Hier im Chat liegen für dieses Gespräch schon so viele '
      + 'Dateien, wie gehen. Mach mit den gelesenen weiter oder sende nur die Namen.');
    expect(knopf(wurzel, 'Ohne diese weiter')).toBeUndefined();
    expect(knopf(wurzel, 'Noch einmal versuchen')).toBeUndefined();
    expect(knopf(wurzel, 'Nur Namen senden (nichts hochladen)')).toBeTruthy();
    expect(wurzel.textContent).toContain('Bereits gelesene Dateien bleiben bis zu 24 Stunden nach der letzten Nutzung hier im Chat; ein daraus erstellter Entwurf bleibt im Arbeitsstand.');
    const weiter = knopf(wurzel, 'Mit den gelesenen weiter')!;
    expect(weiter.classList.contains('u__haupt')).toBe(true);
    expect(h.antworten).not.toHaveBeenCalled();
    weiter.click();
    expect(h.antworten).toHaveBeenCalledTimes(1);
    expect(h.antworten.mock.calls[0][0]).toMatchObject({ aktion: 'bereitgestellt', ort: 'chat' });
    expect(h.antworten.mock.calls[0][0].dateien).toEqual([expect.objectContaining({ upload_id: ID(1) })]);
  });

  it('an der Grenze „Nur Namen senden“ — Ort namen; ohne gelesene nennt der Satz nur diesen Weg', async () => {
    const h = host();
    h.hochladen.mockRejectedValueOnce(abgelehnt('grenze_anzahl'));
    const { wurzel } = await feld(DREI(), h);
    knopf(wurzel, 'Hochladen')!.click();
    await warte();
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('„a.pdf“: Hier im Chat liegen für dieses Gespräch schon so viele '
      + 'Dateien, wie gehen. Sende nur die Namen.');
    expect(knopf(wurzel, 'Mit den gelesenen weiter')).toBeUndefined();
    expect(wurzel.textContent).not.toContain('Bereits gelesene Dateien');
    const namen = knopf(wurzel, 'Nur Namen senden (nichts hochladen)')!;
    expect(namen.classList.contains('u__haupt')).toBe(true);
    expect(knopf(wurzel, 'Andere Auswahl')!.disabled).toBe(false);
    namen.click();
    expect(h.antworten.mock.calls[0][0]).toMatchObject({ aktion: 'bereitgestellt', ort: 'namen' });
    expect(h.hochladen).toHaveBeenCalledTimes(1);
  });

  it('`grenze_gesamt` lässt weitermachen — eine kleinere Datei passt vielleicht noch', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1)).mockRejectedValueOnce(abgelehnt('grenze_gesamt', 413)).mockResolvedValueOnce(befund(3));
    const { wurzel } = await feld(DREI(), h);
    knopf(wurzel, 'Hochladen')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('„b.pdf“: Diese Datei passt nicht mehr dazu – hier im Chat liegt für '
      + 'dieses Gespräch schon fast so viel, wie geht. Mach ohne diese weiter; eine kleinere passt vielleicht noch.');
    expect(wurzel.textContent).toContain('Bereits gelesene Dateien bleiben bis zu 24 Stunden nach der letzten Nutzung hier im Chat; ein daraus erstellter Entwurf bleibt im Arbeitsstand.');
    knopf(wurzel, 'Ohne diese weiter')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(3);
    expect(h.antworten.mock.calls[0][0].dateien.map((d: { upload_id: string }) => d.upload_id)).toEqual([ID(1), ID(3)]);
  });
});

describe('Review Oberfläche 2: „Hier im Chat“ anhalten', () => {
  it('„Nach dieser Datei anhalten“ wirkt nach der laufenden Datei; danach „Mit den gelesenen weiter“ oder „Andere Auswahl“', async () => {
    const h = host();
    const { fertig } = haendisch(h);
    const { wurzel } = await feld(DREI(), h);
    knopf(wurzel, 'Hochladen')!.click();
    const anhalten = knopf(wurzel, 'Nach dieser Datei anhalten')!;
    anhalten.focus();
    anhalten.click();
    // der Knopf sagt, was kommt, und nimmt keinen zweiten Klick; der Fokus bleibt im Modul
    expect(knopf(wurzel, 'Hält nach dieser Datei an …')!.disabled).toBe(true);
    expect(fokus(wurzel)).toBe('s:chat');
    fertig[0](befund(1));
    await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(1);
    expect(h.antworten).not.toHaveBeenCalled();
    expect(wurzel.textContent).toContain('Angehalten – gelesen: 1 Datei.');
    expect(wurzel.textContent).toContain('Bereits gelesene Dateien bleiben bis zu 24 Stunden nach der letzten Nutzung hier im Chat; ein daraus erstellter Entwurf bleibt im Arbeitsstand.');
    expect(knopf(wurzel, 'Andere Auswahl')!.disabled).toBe(false);
    expect(knopf(wurzel, 'Nur Namen senden (nichts hochladen)')).toBeUndefined();
    knopf(wurzel, 'Mit den gelesenen weiter')!.click();
    expect(h.antworten.mock.calls[0][0].dateien).toEqual([expect.objectContaining({ upload_id: ID(1) })]);
  });

  it('angehalten und dann gescheitert: „Ohne diese weiter“ lädt nichts mehr hoch', async () => {
    const h = host();
    const { scheitert } = haendisch(h);
    const { wurzel } = await feld(DREI(), h);
    knopf(wurzel, 'Hochladen')!.click();
    knopf(wurzel, 'Nach dieser Datei anhalten')!.click();
    scheitert[0](abgelehnt('kein_text', 422));
    await warte();
    expect(wurzel.textContent).toContain('„a.pdf“: In der Datei steht kein lesbarer Text');
    knopf(wurzel, 'Ohne diese weiter')!.click();
    await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(1);
    expect(wurzel.textContent).toContain('Angehalten – gelesen: 0 Dateien.');
    // ohne gelesene führt „Nur Namen senden“ weiter
    expect(knopf(wurzel, 'Mit den gelesenen weiter')).toBeUndefined();
    expect(knopf(wurzel, 'Nur Namen senden (nichts hochladen)')).toBeTruthy();
  });

  it('ein entferntes Element (Widget zu) lädt nicht im Verborgenen weiter und antwortet nicht; zurück zeigt es den Stand', async () => {
    const h = host();
    const { fertig } = haendisch(h);
    const { el, wurzel } = await feld([datei('P/a.pdf'), datei('P/b.pdf', 200)], h);
    knopf(wurzel, 'Hochladen')!.click();
    el.remove();
    fertig[0](befund(1));
    await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(1);
    document.body.appendChild(el);
    expect(wurzel.textContent).toContain('Angehalten – gelesen: 1 Datei.');
    expect(h.antworten).not.toHaveBeenCalled();
  });

  it('entfernt während der letzten Datei: keine Antwort im Verborgenen', async () => {
    const h = host();
    const { fertig } = haendisch(h);
    const { el, wurzel } = await feld([datei('P/a.pdf')], h);
    knopf(wurzel, 'Hochladen')!.click();
    el.remove();
    fertig[0](befund(1));
    await warte();
    expect(h.antworten).not.toHaveBeenCalled();
    document.body.appendChild(el);
    knopf(wurzel, 'Mit den gelesenen weiter')!.click();
    expect(h.antworten).toHaveBeenCalledTimes(1);
  });

  it('nach einem Neustart gilt das alte Anhalten nicht mehr', async () => {
    const h = host();
    const { fertig } = haendisch(h);
    const { wurzel } = await feld([datei('P/a.pdf'), datei('P/b.pdf', 200)], h);
    knopf(wurzel, 'Hochladen')!.click();
    knopf(wurzel, 'Nach dieser Datei anhalten')!.click();
    fertig[0](befund(1));
    await warte();
    knopf(wurzel, 'Andere Auswahl')!.click();
    const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [datei('Q/x.pdf'), datei('Q/y.pdf', 200)], configurable: true });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await warte();
    knopf(wurzel, 'Hochladen')!.click();
    fertig[1](befund(2));
    await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(3);
  });

  it('auf Englisch: Anhalten und der Satz zur Frist', async () => {
    const h = host();
    const { fertig } = haendisch(h);
    const { wurzel } = await feld(DREI(), h, ANONYM, { sprache: 'en' });
    knopf(wurzel, 'Upload')!.click();
    knopf(wurzel, 'Stop after this file')!.click();
    fertig[0](befund(1));
    await warte();
    expect(wurzel.textContent).toContain('Stopped – read: 1 file.');
    expect(wurzel.textContent).toContain('Files already read stay here in the chat for up to 24 hours after last use; a draft made from them stays in your work in progress.');
    expect(knopf(wurzel, 'Continue with the files read')).toBeTruthy();
  });
});

describe('Review Oberfläche 3, 5, 9 und Sitzungsrest: die Wahl „Hier im Chat“', () => {
  it('3: ohne lesbare Datei gesperrt, mit eigenem Grund', async () => {
    const { wurzel } = await feld([datei('P/f.pptx', 100, 'application/vnd.ms-powerpoint')]);
    expect(radio(wurzel, 'chat').disabled).toBe(true);
    expect(erklaerung(wurzel, 'chat')).toBe('nicht wählbar – keine Datei, die der Chat lesen kann – PDF, Word, Text oder Markdown');
    expect(knopf(wurzel, 'Hochladen')).toBeUndefined();
  });

  it('5: eine Datei über der Grenze je Datei geht nicht hoch; der Hinweis nennt sie', async () => {
    const h = host();
    h.hochladen.mockResolvedValue(befund(1));
    const daten = { ...ANONYM, grenzen: { ...GRENZEN, lokal_max_mb_datei: 1 } };
    const { wurzel } = await feld([datei('P/klein.pdf'), datei('P/riesig.pdf', 2 * 1024 * 1024)], h, daten);
    expect(wurzel.textContent).toContain('1 Datei ist größer als 1 MB – davon geht nur der Name mit.');
    knopf(wurzel, 'Hochladen')!.click();
    await warte();
    expect(h.hochladen.mock.calls.map((c) => (c[0] as File).name)).toEqual(['klein.pdf']);
    // alle zu groß: gesperrt mit Grund
    document.body.innerHTML = '';
    const nur = (await feld([datei('P/riesig.pdf', 2 * 1024 * 1024)], host(), daten)).wurzel;
    expect(erklaerung(nur, 'chat')).toBe('nicht wählbar – jede Datei ist zu groß für hier (höchstens 1 MB je Datei)');
  });

  it('9: „ohne Anmeldung“ nur, wenn die Schalter es tragen', async () => {
    const mit = (await feld([datei('P/a.pdf')])).wurzel;
    expect(erklaerung(mit, 'chat')).toBe('schnell, ohne Anmeldung, bis 10 Dateien – Text bleibt bis zu 24 Stunden nach der letzten Nutzung hier');
    document.body.innerHTML = '';
    const daten = { ...ANGEMELDET, schalter: { ...ANGEMELDET.schalter, dokument_ohne_anmeldung: false } };
    const ohne = (await feld([datei('P/a.pdf')], host(), daten)).wurzel;
    expect(erklaerung(ohne, 'chat')).toBe('schnell, bis 10 Dateien – Text bleibt bis zu 24 Stunden nach der letzten Nutzung hier');
  });

  it('Sitzungsrest: `grenze_sitzung` und `lokal_frei_*` sperren mit eigenem Grund; die Erklärzeile nennt den Rest', async () => {
    const voll = { ...ANONYM, orte: { ...ORTE_ANONYM, chat: { geht: false, grund: 'grenze_sitzung' } } };
    expect(erklaerung((await feld([datei('P/a.pdf')], host(), voll)).wurzel, 'chat'))
      .toBe('nicht wählbar – hier im Chat ist für dieses Gespräch kein Platz mehr – wieder frei nach 24 Stunden ohne '
        + 'Nutzung oder mit „Arbeitsstand löschen“ – oder in WLO ablegen');
    document.body.innerHTML = '';
    const rest = { ...ANONYM, grenzen: { ...GRENZEN, lokal_frei_dateien: 1 } };
    expect(erklaerung((await feld([datei('P/a.pdf'), datei('P/b.pdf', 200)], host(), rest)).wurzel, 'chat'))
      .toBe('nicht wählbar – zu viele Dateien für hier – in diesem Gespräch geht noch 1 Datei – mit Anmeldung über WLO');
    document.body.innerHTML = '';
    const mb = { ...ANONYM, grenzen: { ...GRENZEN, lokal_frei_mb: 0.5 } };
    expect(erklaerung((await feld([datei('P/a.pdf', 1024 * 1024)], host(), mb)).wurzel, 'chat'))
      .toBe('nicht wählbar – zu viel für hier – in diesem Gespräch gehen noch 0,5 MB – mit Anmeldung über WLO');
    document.body.innerHTML = '';
    const null_ = { ...ANONYM, grenzen: { ...GRENZEN, lokal_frei_dateien: 0 } };
    expect(erklaerung((await feld([datei('P/a.pdf')], host(), null_)).wurzel, 'chat'))
      .toBe('nicht wählbar – hier im Chat ist für dieses Gespräch kein Platz mehr – wieder frei nach 24 Stunden ohne '
        + 'Nutzung oder mit „Arbeitsstand löschen“ – mit Anmeldung über WLO');
    document.body.innerHTML = '';
    const passt = { ...ANONYM, grenzen: { ...GRENZEN, lokal_frei_dateien: 3 } };
    expect(erklaerung((await feld([datei('P/a.pdf')], host(), passt)).wurzel, 'chat'))
      .toBe('schnell, ohne Anmeldung, bis 3 Dateien – Text bleibt bis zu 24 Stunden nach der letzten Nutzung hier');
  });
});

describe('Review Oberfläche 4, 6, 7: Fehler der Übertragung, Dubletten, Ansagen', () => {
  it('4: ein Fehler der WLO-Übertragung steht nicht mehr da, wenn „Hier im Chat“ beginnt', async () => {
    const h = host();
    h.ablegen.mockRejectedValue(abgelehnt('nicht_erreichbar', 503));
    h.hochladen.mockImplementation(() => new Promise(() => undefined));
    const { wurzel } = await feld([datei('P/a.pdf')], h, ANGEMELDET);
    knopf(wurzel, 'Hochladen')!.click();
    // die Frage kommt nach dem Fehler beim Vorbereiten zurück, der Fehler steht darüber
    for (let i = 0; i < 20 && !radio(wurzel, 'chat'); i++) await warte();
    const alt = wurzel.querySelector('.u__wlo')?.textContent ?? '';
    expect(alt).not.toBe('');
    const chat = radio(wurzel, 'chat');
    chat.checked = true;
    chat.dispatchEvent(new Event('change', { bubbles: true }));
    knopf(wurzel, 'Hochladen')!.focus();
    knopf(wurzel, 'Hochladen')!.click();
    expect(h.hochladen).toHaveBeenCalledTimes(1);
    expect(wurzel.querySelectorAll('.u__wlo')).toHaveLength(1);
    expect(wurzel.textContent).not.toContain(alt);
    expect(fokus(wurzel)).toBe('s:chat');
  });

  it('6: inhaltsgleiche Dateien (Name und Größe) gehen einmal hoch — dieselbe `upload_id` für beide', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1)).mockResolvedValueOnce(befund(2));
    const { wurzel } = await feld([datei('P/a/blatt.pdf', 100), datei('P/b/blatt.pdf', 100), datei('P/c.pdf', 300)], h);
    knopf(wurzel, 'Hochladen')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(2);
    const daten = h.antworten.mock.calls[0][0];
    const liste = daten.struktur.kinder.flatMap((k: { dateiliste: { i: number; name: string }[] }) => k.dateiliste)
      .concat(daten.struktur.dateiliste ?? []) as { i: number; name: string }[];
    const blaetter = liste.filter((d) => d.name === 'blatt.pdf').map((d) => d.i);
    expect(blaetter).toHaveLength(2);
    expect(daten.dateien).toEqual(expect.arrayContaining([
      { i: blaetter[0], rolle: 'inhalt', upload_id: ID(1) }, { i: blaetter[1], rolle: 'inhalt', upload_id: ID(1) },
      expect.objectContaining({ upload_id: ID(2) })]));
    expect(daten.dateien).toHaveLength(3);
    // gleicher Name, andere Größe: zwei Dateien
    document.body.innerHTML = '';
    const h2 = host();
    h2.hochladen.mockResolvedValueOnce(befund(1)).mockResolvedValueOnce(befund(2));
    const zwei = (await feld([datei('P/a/blatt.pdf', 100), datei('P/b/blatt.pdf', 101)], h2)).wurzel;
    knopf(zwei, 'Hochladen')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(h2.hochladen).toHaveBeenCalledTimes(2);
    // gleicher Name und gleiche Größe, aber ein anderes Änderungsdatum: zwei Dateien
    document.body.innerHTML = '';
    const h3 = host();
    h3.hochladen.mockResolvedValueOnce(befund(1)).mockResolvedValueOnce(befund(2));
    const drei = (await feld([datei('P/a/blatt.pdf', 100), datei('P/b/blatt.pdf', 100, 'application/pdf', 1)], h3)).wurzel;
    knopf(drei, 'Hochladen')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(h3.hochladen).toHaveBeenCalledTimes(2);
  });

  it('zweites Review, 1: dieselbe Datei in zwei Rollen geht getrennt hoch — je Rolle eine eigene `upload_id`', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1)).mockResolvedValueOnce(befund(2));
    // die Lehrplan-Automatik macht nur die Datei in der Wurzel zum Strukturdokument; die Kopie bleibt Inhalt
    const { wurzel } = await feld([datei('P/Lehrplan.pdf', 100), datei('P/Material/Lehrplan.pdf', 100)], h);
    knopf(wurzel, 'Hochladen')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(h.hochladen.mock.calls.map((c) => c[2])).toEqual(['struktur', 'inhalt']);
    const dateien = h.antworten.mock.calls[0][0].dateien as { rolle: string; upload_id: string }[];
    // wie `upload_bereitgestellt._dubletten_grund`: dieselbe Kennung nur bei gleicher Rolle — hier zwei
    expect(dateien.map((d) => [d.rolle, d.upload_id])).toEqual([['struktur', ID(1)], ['inhalt', ID(2)]]);
  });

  it('zweites Review, 7: 403 `ort_nicht_erlaubt` beendet den Lauf wie die Sitzungsgrenze', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1)).mockRejectedValueOnce(abgelehnt('ort_nicht_erlaubt', 403));
    const { wurzel } = await feld(DREI(), h);
    knopf(wurzel, 'Hochladen')!.click();
    for (let i = 0; i < 4; i++) await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(2);
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('„b.pdf“: In diesem Ablauf ist „Hier im Chat“ nicht '
      + 'vorgesehen. Mach mit den gelesenen weiter oder sende nur die Namen.');
    expect(knopf(wurzel, 'Ohne diese weiter')).toBeUndefined();
    expect(knopf(wurzel, 'Mit den gelesenen weiter')).toBeTruthy();
  });

  it('zweites Review, 12: der Balken trägt ein festes Label „Datei k von n“; „wird gelesen“ auch nach einem Weitermachen', async () => {
    const h = host();
    const melder: ((a: number) => void)[] = [];
    const ergebnis: { ok: (b: unknown) => void; nein: (f: unknown) => void }[] = [];
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => {
      melder.push(f);
      return new Promise((ok, nein) => ergebnis.push({ ok, nein }));
    });
    const { wurzel } = await feld([...DREI(), datei('P/d.pdf', 400)], h);
    knopf(wurzel, 'Hochladen')!.click();
    const balken = () => wurzel.querySelector('progress') as HTMLProgressElement;
    expect(balken().getAttribute('aria-label')).toBe('Datei 1 von 4');
    melder[0](0.5);
    expect(balken().getAttribute('aria-label')).toBe('Datei 1 von 4');
    expect(balken().value).toBe(50);
    ergebnis[0].nein(abgelehnt('kein_text', 422));
    await warte();
    const status = wurzel.querySelector('[aria-live]') as HTMLElement;
    knopf(wurzel, 'Ohne diese weiter')!.click();
    expect(status.textContent).toContain('Datei 2 von 4 wird hochgeladen');
    melder[1](1);
    // Datei 2 von 4 ist sonst nicht dran (erste, jede zehnte, letzte) — nach dem Weitermachen schon
    expect(status.textContent).toBe('Datei 2 von 4 wird gelesen …');
  });

  it('7: die Statuszeile sagt nicht jede Datei an — die erste, jede zehnte, die letzte (wie beim Übertragen)', async () => {
    const h = host();
    const { wurzel } = await feld(DREI(), h);
    const status = wurzel.querySelector('[aria-live]') as HTMLElement;
    const angesagt: string[] = [];
    new MutationObserver(() => angesagt.push(status.textContent ?? '')).observe(status, { childList: true, characterData: true, subtree: true });
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => { f(1); return Promise.resolve(befund(1)); });
    knopf(wurzel, 'Hochladen')!.click();
    for (let i = 0; i < 6; i++) await warte();
    expect(angesagt.some((s) => s.includes('Datei 1 von 3'))).toBe(true);
    expect(angesagt.some((s) => s.includes('Datei 3 von 3'))).toBe(true);
    expect(angesagt.some((s) => s.includes('Datei 2 von 3'))).toBe(false);
  });
});
