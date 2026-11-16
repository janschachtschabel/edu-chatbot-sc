// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { definiere } from './ui-upload.element';

const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const DATEN = { zweck: 'bereitstellen', grenzen: { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50 } };

type Host = ElementHost & {
  antworten: ReturnType<typeof vi.fn>; vormerken: ReturnType<typeof vi.fn>; hochladen: ReturnType<typeof vi.fn>;
};

function host(): Host {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), link: vi.fn(() => ({ href: '', hinweis: '' })), aktion: vi.fn(),
    beschaeftigt: vi.fn(() => false), antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(),
  } as never;
}

function datei(pfad: string, size = 100, type = 'application/pdf'): File {
  const f = new File([new Uint8Array(size)], pfad.split('/').pop() ?? pfad, { type });
  Object.defineProperty(f, 'webkitRelativePath', { value: pfad });
  return f;
}

function erzeuge(kontext: Partial<ModulKontext> = {}, h = host(), daten: Record<string, unknown> = DATEN) {
  const el = document.createElement('boerdi-ui-upload') as NachladeElement;
  el.host = h;
  el.daten = daten;
  el.kontext = { ...KONTEXT, ...kontext };
  el.beschaeftigt = false;
  document.body.appendChild(el);
  return { el, h, wurzel: el.shadowRoot as ShadowRoot };
}

async function waehle(wurzel: ShadowRoot, dateien: File[]): Promise<void> {
  const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: dateien, configurable: true });
  input.dispatchEvent(new Event('change', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 0));
}

const knopf = (w: ShadowRoot, text: string) =>
  [...w.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

afterEach(() => { document.body.innerHTML = ''; });

describe('<boerdi-ui-upload> (U3-1a)', () => {
  it('ist definiert, Doppel-Definition wirft nicht (Pflicht aus dem Element-Vertrag)', () => {
    expect(customElements.get('boerdi-ui-upload')).toBeTruthy();
    expect(() => definiere()).not.toThrow();
  });

  it('leer: Überschrift, zwei Auswahlknöpfe, Ablagefläche mit Text, Datenschutz-Hinweis', () => {
    const { wurzel } = erzeuge();
    expect(wurzel.querySelector('h3')?.textContent).toBe('Ordner und Dateien');
    expect(knopf(wurzel, 'Ordner wählen')).toBeTruthy();
    expect(knopf(wurzel, 'Dateien wählen')).toBeTruthy();
    expect(wurzel.textContent).toContain('Ordner oder Dateien hier ablegen');
    expect(wurzel.textContent).toContain('Ordner- und Dateinamen gehen an den Chat; alle Inhalte bleiben auf deinem Gerät.');
  });

  it('nach der Auswahl: Baum mit Zahlen, Befund vorgemerkt — mit Dateien je Ordner (TG-3a)', async () => {
    const { h, wurzel } = erzeuge();
    await waehle(wurzel, [datei('Physik/Mechanik/hebel.pdf'), datei('Physik/plan.docx'), datei('Physik/.DS_Store', 5)]);
    expect(wurzel.textContent).toContain('Physik');
    expect(wurzel.textContent).toContain('2 Ordner');
    expect(wurzel.textContent).toContain('2 Dateien');
    const vorgemerkt = h.vormerken.mock.calls.at(-1)?.[0];
    expect(vorgemerkt).toMatchObject({ aktion: 'erfasst', zahlen: { inhalte: 2, ignoriert: 1 } });
    // Plan 2026-11-16, TG-3a: die Dateinamen gehen mit, die Systemdatei nicht; nie Binärdaten
    expect(vorgemerkt.struktur.kinder[0].dateiliste).toEqual([
      { i: 1, name: 'hebel.pdf', endung: 'pdf', groesse: expect.any(Number), rolle: 'inhalt' }]);
    expect(JSON.stringify(vorgemerkt)).not.toContain('DS_Store');
  });

  it('ein Ordner klappt per Knopf auf; aria-expanded sagt den Zustand', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/Sub/a.pdf'), datei('P/b.pdf')]);
    const sub = [...wurzel.querySelectorAll('button[aria-expanded]')].find((b) => b.textContent?.includes('Sub')) as HTMLButtonElement;
    expect(sub.getAttribute('aria-expanded')).toBe('false');
    expect(wurzel.textContent).not.toContain('a.pdf');
    sub.focus();          // wie per Tastatur: Fokus, dann Enter (= click)
    sub.click();
    const nachher = [...wurzel.querySelectorAll('button[aria-expanded]')].find((b) => b.textContent?.includes('Sub')) as HTMLButtonElement;
    expect(nachher.getAttribute('aria-expanded')).toBe('true');
    expect(wurzel.textContent).toContain('a.pdf');
    // der Fokus bleibt auf dem Knopf, obwohl neu gezeichnet wurde
    expect(wurzel.activeElement).toBe(nachher);
  });

  it('Rolle per Auswahlfeld: Strukturdokument setzt den Hinweis und erscheint in der Vormerkung', async () => {
    const { h, wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/Lehr.pdf'), datei('P/b.pdf')]);
    const auswahl = wurzel.querySelector('select[aria-label="Rolle von Lehr.pdf"]') as HTMLSelectElement;
    auswahl.value = 'struktur';
    auswahl.dispatchEvent(new Event('change', { bubbles: true }));
    expect(wurzel.textContent).toContain('Lesen lassen kann der Chat es hier nicht');
    expect(h.vormerken.mock.calls.at(-1)?.[0].strukturdokument).toMatchObject({ name: 'Lehr.pdf' });
  });

  // Plan 2026-11-16, TG-1 (G-E4): kein Zielknopf mehr — auch mit Unterordnern ist „Senden“ der Hauptknopf
  it('TG-1: mit Unterordnern nur „Senden“ (Hauptknopf), es antwortet mit dem Befund', async () => {
    const { h, wurzel } = erzeuge();
    await waehle(wurzel, [datei('Physik/A/x.pdf')]);
    expect(knopf(wurzel, 'Als Themenbaum-Entwurf übernehmen')).toBeUndefined();
    const senden = knopf(wurzel, 'Senden')!;
    expect(senden.classList.contains('u__haupt')).toBe(true);
    senden.click();
    expect(h.antworten).toHaveBeenCalledTimes(1);
    const [daten, text] = h.antworten.mock.calls[0];
    expect(daten).toMatchObject({ aktion: 'erfasst', struktur: { name: 'Physik' } });
    expect(text).toBe('Ordner „Physik“ erfasst: 2 Ordner, 1 Datei.');
  });

  it('solange ein Zug läuft, sind Antwort-Knöpfe gesperrt', async () => {
    const { el, wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/A/x.pdf')]);
    el.beschaeftigt = true;
    expect(knopf(wurzel, 'Senden')!.disabled).toBe(true);
    expect(knopf(wurzel, 'Andere Auswahl')!.disabled).toBe(false);
  });

  it('nur lesend: zeigt die gegebene Antwort, keine Knöpfe', () => {
    const antwort = { aktion: 'erfasst', struktur: { name: 'P', dateien: 1, alle_dateien: 3, kinder: [] },
      zahlen: { ordner: 2, dateien: 4, inhalte: 3, ignoriert: 1, strukturdokumente: 0, bytes: 10 }, strukturdokument: null, warnungen: [] };
    const { wurzel } = erzeuge({ nurLesen: true, antwort });
    expect(wurzel.textContent).toContain('Erfasst: 2 Ordner, 3 Dateien.');
    expect(wurzel.querySelectorAll('button')).toHaveLength(0);
  });

  it('Drag & Drop liest Ordner über die Einträge', async () => {
    const { h, wurzel } = erzeuge();
    const eintrag = { isFile: true, isDirectory: false, name: 'x.pdf',
      file: (ok: (f: File) => void) => ok(new File([new Uint8Array(5)], 'x.pdf', { type: 'application/pdf' })) };
    const ordner = { isFile: false, isDirectory: true, name: 'Ablage',
      createReader: () => { let n = 0; return { readEntries: (ok: (e: unknown[]) => void) => ok(n++ ? [] : [eintrag]) }; } };
    const zone = wurzel.querySelector('[data-ablage]') as HTMLElement;
    const ereignis = new Event('drop', { bubbles: true, cancelable: true }) as Event & { dataTransfer: unknown };
    ereignis.dataTransfer = { items: [{ kind: 'file', webkitGetAsEntry: () => ordner }], files: [] };
    zone.dispatchEvent(ereignis);
    await new Promise((r) => setTimeout(r, 10));
    expect(ereignis.defaultPrevented).toBe(true);
    expect(wurzel.textContent).toContain('Ablage');
    expect(h.vormerken).toHaveBeenCalled();
  });

  it('Ordnernamen erscheinen als Text, nie als HTML', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('<img src=x onerror=alert(1)>/a.pdf')]);
    expect(wurzel.querySelector('img')).toBeNull();
    expect(wurzel.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it('jeder Ignorieren-Knopf nennt seinen Ordner (Screenreader)', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/A/a.pdf'), datei('P/B/b.pdf')]);
    const namen = [...wurzel.querySelectorAll('button[data-ignorieren]')].map((b) => b.getAttribute('aria-label'));
    expect(namen).toEqual(['Alle Dateien in P ignorieren', 'Alle Dateien in A ignorieren', 'Alle Dateien in B ignorieren']);
  });

  it('„Andere Auswahl“ setzt zurück und nimmt die Vormerkung zurück', async () => {
    const { h, wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/x.pdf')]);
    knopf(wurzel, 'Andere Auswahl')!.click();
    expect(h.vormerken).toHaveBeenLastCalledWith(null);
    expect(knopf(wurzel, 'Ordner wählen')).toBeTruthy();
  });

  it('die Statuszeile sagt das Ergebnis an (aria-live)', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/x.pdf')]);
    const status = wurzel.querySelector('[aria-live="polite"]');
    expect(status?.textContent).toContain('1 Datei');
  });

  // ── Review U3-1 ─────────────────────────────────────────────────────────────

  it('Befund 2: nach der Auswahl liegt der Fokus auf dem Ergebnis, nach „Andere Auswahl“ auf „Ordner wählen“', async () => {
    const { wurzel } = erzeuge();
    knopf(wurzel, 'Ordner wählen')!.focus();
    await waehle(wurzel, [datei('P/A/x.pdf')]);
    expect((wurzel.activeElement as HTMLElement | null)?.textContent).toContain('1 Datei');
    knopf(wurzel, 'Andere Auswahl')!.focus();
    knopf(wurzel, 'Andere Auswahl')!.click();
    expect(wurzel.activeElement).toBe(knopf(wurzel, 'Ordner wählen'));
  });

  it('Befund 2: ohne Fokus im Modul (Ablegen) nimmt es der Seite den Fokus nicht', async () => {
    const fremd = document.createElement('input');
    document.body.appendChild(fremd);
    fremd.focus();
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/x.pdf')]);
    expect(document.activeElement).toBe(fremd);
  });

  it('Befund 3: der Satz der KI steht über dem Auswahlfeld', () => {
    const el = document.createElement('boerdi-ui-upload') as NachladeElement;
    el.host = host();
    el.daten = { ...DATEN, hinweis: 'Wähle den Ordner mit deinen Physik-Materialien.' };
    el.kontext = KONTEXT;
    document.body.appendChild(el);
    expect(el.shadowRoot!.textContent).toContain('Wähle den Ordner mit deinen Physik-Materialien.');
  });

  it('Befund 8: ohne Unterordner ist „Senden“ ebenso der Hauptknopf', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/a.pdf'), datei('P/b.pdf')]);
    expect(knopf(wurzel, 'Senden')!.classList.contains('u__haupt')).toBe(true);
  });

  it('Befund 9: Ablegen außerhalb der Fläche öffnet keine Datei (Vorgabe des Browsers verhindert)', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/A/x.pdf')]);
    const ereignis = new Event('drop', { bubbles: true, cancelable: true }) as Event & { dataTransfer: unknown };
    ereignis.dataTransfer = { items: [], files: [] };
    (wurzel.querySelector('h3') as HTMLElement).dispatchEvent(ereignis);
    expect(ereignis.defaultPrevented).toBe(true);
    expect(wurzel.textContent).toContain('1 Datei');     // die Erfassung bleibt
  });

  it('Befund 9: während des Lesens sind die Auswahlknöpfe gesperrt', async () => {
    const { wurzel } = erzeuge();
    const haengt = { isFile: false, isDirectory: true, name: 'Langsam',
      createReader: () => ({ readEntries: () => { /* antwortet nie */ } }) };
    const zone = wurzel.querySelector('[data-ablage]') as HTMLElement;
    const ereignis = new Event('drop', { bubbles: true, cancelable: true }) as Event & { dataTransfer: unknown };
    ereignis.dataTransfer = { items: [{ kind: 'file', webkitGetAsEntry: () => haengt }], files: [] };
    zone.dispatchEvent(ereignis);
    await new Promise((r) => setTimeout(r, 0));
    expect(knopf(wurzel, 'Ordner wählen')!.disabled).toBe(true);
  });

  it('Befund 11: der Hinweis nennt das markierte Strukturdokument', async () => {
    const { wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/A/Lehrplan.pdf'), datei('P/b.pdf')]);
    const auswahl = wurzel.querySelector('select[aria-label="Rolle von Lehrplan.pdf"]') as HTMLSelectElement | null;
    // im zugeklappten Unterordner: erst aufklappen, dann markieren
    if (!auswahl) {
      const a = [...wurzel.querySelectorAll('button[aria-expanded]')].find((b) => b.textContent?.includes('A')) as HTMLButtonElement;
      a.click();
    }
    const feld = wurzel.querySelector('select[aria-label="Rolle von Lehrplan.pdf"]') as HTMLSelectElement;
    feld.value = 'struktur';
    feld.dispatchEvent(new Event('change', { bubbles: true }));
    expect(wurzel.textContent).toContain('Strukturdokument: Lehrplan.pdf');
  });

  it('Befund 15: nur lesend ohne Antwort sagt es, dass es nicht verwendet wurde', () => {
    const { wurzel } = erzeuge({ nurLesen: true, antwort: null });
    expect(wurzel.textContent).toContain('Nicht verwendet.');
  });

  it('auf Englisch', () => {
    const { wurzel } = erzeuge({ sprache: 'en' });
    expect(knopf(wurzel, 'Choose folder')).toBeTruthy();
  });
});

// ── Paket U3-2c: ein Strukturdokument lesen lassen ──────────────────────────────

const MIT_DOKUMENT = { ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: false } };
const BEFUND = {
  upload_id: '11111111-2222-4333-8444-555555555555', name: 'Lehr.pdf', format: 'pdf',
  befund: { seiten: 3, woerter: 900, abschnitte: 5, gliederung_art: 'ueberschriften', warnungen: ['gekuerzt'],
            zeichen: 5000, sprache: 'de', gekuerzt: true },
  ueberschriften_vorschau: ['Mechanik', 'Optik'],
};

async function markiert(h = host(), daten: Record<string, unknown> = MIT_DOKUMENT) {
  const r = erzeuge({}, h, daten);
  await waehle(r.wurzel, [datei('P/Lehr.pdf'), datei('P/b.pdf')]);
  const auswahl = r.wurzel.querySelector('select[aria-label="Rolle von Lehr.pdf"]') as HTMLSelectElement;
  auswahl.value = 'struktur';
  auswahl.dispatchEvent(new Event('change', { bubbles: true }));
  return r;
}

const warte = () => new Promise((r) => setTimeout(r, 0));

describe('<boerdi-ui-upload> Strukturdokument lesen (U3-2c)', () => {
  it('ohne Schalter kein Knopf, sondern ein ehrlicher Hinweis', async () => {
    const { wurzel } = await markiert(host(), DATEN);
    expect(knopf(wurzel, 'Lesen lassen')).toBeUndefined();
    expect(wurzel.textContent).toContain('Lesen lassen kann der Chat es hier nicht');
  });

  it('lädt nur das Strukturdokument hoch, zeigt den Fortschritt und antwortet mit dem Befund', async () => {
    const h = host();
    let melde: (anteil: number) => void = () => undefined;
    let fertig: (befund: unknown) => void = () => undefined;
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => { melde = f; return new Promise((r) => { fertig = r; }); });
    const { wurzel } = await markiert(h);
    expect(wurzel.textContent).toContain('Zum Lesen wird es hochgeladen');
    knopf(wurzel, 'Lesen lassen')!.click();
    expect((h.hochladen.mock.calls[0][0] as File).name).toBe('Lehr.pdf');
    melde(0.4);
    expect(wurzel.textContent).toContain('Wird hochgeladen … 40 %');
    expect((wurzel.querySelector('progress') as HTMLProgressElement).value).toBe(40);
    expect(knopf(wurzel, 'Andere Auswahl')!.disabled).toBe(true);
    melde(1);
    expect(wurzel.textContent).toContain('Das Dokument wird gelesen');
    fertig(BEFUND);
    await warte();
    const [daten, blase] = h.antworten.mock.calls[0];
    expect(blase).toBe('Dokument „Lehr.pdf“ lesen lassen');
    expect(daten).toMatchObject({ aktion: 'dokument', dokument: {
      upload_id: BEFUND.upload_id, name: 'Lehr.pdf', format: 'pdf', vorschau: ['Mechanik', 'Optik'] } });
    // TG-1: kein Ziel mehr — was mit dem Dokument geschieht, klären Ablauf oder KI danach
    expect(daten.dokument).not.toHaveProperty('ziel');
    // nur die Felder des Antwort-Schemas — `zeichen`, `sprache`, `gekuerzt` bleiben draußen
    expect(daten.dokument.befund).toEqual({ seiten: 3, woerter: 900, abschnitte: 5, gliederung_art: 'ueberschriften', warnungen: ['gekuerzt'] });
  });

  it('ein endgültiger Fehler sagt den Grund, ohne neuen Versuch', async () => {
    const h = host();
    h.hochladen.mockRejectedValue(Object.assign(new Error('x'), { status: 400, code: 'kein_text' }));
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    expect(wurzel.querySelector('.u__fehler')?.textContent).toContain('kein lesbarer Text');
    expect(knopf(wurzel, 'Noch einmal versuchen')).toBeUndefined();
    expect(h.antworten).not.toHaveBeenCalled();
  });

  it('nach einem Netzfehler geht es noch einmal; 429 heißt kurz warten', async () => {
    const h = host();
    h.hochladen.mockRejectedValueOnce(Object.assign(new Error('x'), { status: 0, code: 'netz' }))
      .mockRejectedValueOnce(Object.assign(new Error('x'), { status: 429, code: 'fehler' }))
      .mockResolvedValueOnce(BEFUND);
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('Keine Verbindung zum Server');
    knopf(wurzel, 'Noch einmal versuchen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('Zu viele Anfragen');
    knopf(wurzel, 'Noch einmal versuchen')!.click();
    await warte();
    expect(h.antworten).toHaveBeenCalledTimes(1);
  });

  it('läuft gerade ein Zug, wartet der Befund auf den Knopf — ohne neues Hochladen', async () => {
    const h = host();
    h.hochladen.mockResolvedValue(BEFUND);
    const { el, wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    el.beschaeftigt = true;
    await warte();
    expect(h.antworten).not.toHaveBeenCalled();
    expect(wurzel.textContent).toContain('Gelesen: 5 Abschnitte');
    expect(knopf(wurzel, 'Weiter')!.disabled).toBe(true);
    el.beschaeftigt = false;
    knopf(wurzel, 'Weiter')!.click();
    expect(h.antworten).toHaveBeenCalledTimes(1);
    expect(h.hochladen).toHaveBeenCalledTimes(1);
  });

  it('ein unbrauchbarer Befund gilt als Fehler', async () => {
    const h = host();
    h.hochladen.mockResolvedValue({ name: 'x' });
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('Das Dokument ließ sich nicht lesen.');
    expect(h.antworten).not.toHaveBeenCalled();
  });

  it('R3-b: hilft die Anmeldung beim Lesen, steht das gleich unter dem Hinweis', () => {
    const { wurzel } = erzeuge({}, host(), {
      ...DATEN, hinweis: 'Lade deinen Lehrplan hoch.',
      schalter: { dokument_im_chat: false, ablage_in_wlo: false, lesen_nach_anmeldung: true },
    });
    const saetze = [...wurzel.querySelectorAll('.u__hinweis')].map((p) => p.textContent);
    const i = saetze.indexOf('Lade deinen Lehrplan hoch.');
    expect(i).toBeGreaterThanOrEqual(0);
    expect(saetze[i + 1]).toBe('Ein Dokument lesen lassen geht erst, wenn du bei WLO angemeldet bist.');
    const ohne = erzeuge({}, host(), { ...DATEN, hinweis: 'X.' }).wurzel;
    expect([...ohne.querySelectorAll('.u__hinweis')].map((p) => p.textContent))
      .not.toContain('Ein Dokument lesen lassen geht erst, wenn du bei WLO angemeldet bist.');
  });

  it('Rückmeldung 16.11.: ohne Anmeldung nennt das Feld die Voraussetzung der Ablage', () => {
    const satz = 'Dateien in deinen persönlichen Bereich in WLO übertragen – dort entstehen Volltexte '
      + 'und Metadaten – geht, wenn du bei WLO angemeldet bist.';
    const { wurzel } = erzeuge({}, host(), {
      ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: false, ablage_nach_anmeldung: true },
    });
    expect([...wurzel.querySelectorAll('.u__hinweis')].map((p) => p.textContent)).toContain(satz);
    const angemeldet = erzeuge({}, host(), {
      ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: true },
    }).wurzel;
    expect([...angemeldet.querySelectorAll('.u__hinweis')].map((p) => p.textContent))
      .not.toContain(satz);
  });

  it('Datenschutz-Hinweis sagt, dass nur ein Strukturdokument hochgeladen wird', () => {
    const { wurzel } = erzeuge({}, host(), MIT_DOKUMENT);
    expect(wurzel.textContent).toContain('erst hochgeladen, wenn du es lesen lässt');
  });

  it('nur lesend nach dem Lesen: Name und Abschnitte', () => {
    const antwort = { aktion: 'dokument', zahlen: { ordner: 1, inhalte: 1, strukturdokumente: 1, ignoriert: 0 },
      dokument: { name: 'Lehr.pdf', befund: { abschnitte: 5 } } };
    const { wurzel } = erzeuge({ nurLesen: true, antwort: antwort as never });
    expect(wurzel.textContent).toContain('Gelesen: Lehr.pdf, 5 Abschnitte.');
  });

  it('Review 3: während des Hochladens sind Rollen und „ignorieren“ gesperrt — das Modul bleibt bedienbar', async () => {
    const h = host();
    let fertig: (befund: unknown) => void = () => undefined;
    h.hochladen.mockImplementation(() => new Promise((r) => { fertig = r; }));
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    expect([...wurzel.querySelectorAll('select')].every((s) => s.disabled)).toBe(true);
    expect([...wurzel.querySelectorAll('button[data-ignorieren]')].every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    fertig(BEFUND);
    await warte();
    expect(h.antworten).toHaveBeenCalledTimes(1);
  });

  it('Review 9: ein Fortschrittsschritt zeichnet nicht neu (der Fokus bleibt, nur Balken und Satz)', async () => {
    const h = host();
    let melde: (anteil: number) => void = () => undefined;
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => { melde = f; return new Promise(() => undefined); });
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    const balken = wurzel.querySelector('progress');
    melde(0.25);
    melde(0.5);
    expect(wurzel.querySelector('progress')).toBe(balken);
    expect(balken!.value).toBe(50);
    expect(wurzel.textContent).toContain('Wird hochgeladen … 50 %');
  });

  it('Review 8: die Rumpf-Grenze (413 mit Text) heißt „zu groß“, ohne neuen Versuch', async () => {
    const h = host();
    h.hochladen.mockRejectedValue(Object.assign(new Error('x'), { status: 413, code: 'fehler' }));
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('Das Dokument ist zu groß.');
    expect(knopf(wurzel, 'Noch einmal versuchen')).toBeUndefined();
  });
});

// ── Plan 2026-11-16, TG-1: zielneutral — kein Knopf und kein Text nennt einen Themenbaum ─────────

describe('<boerdi-ui-upload> zielneutral (TG-1)', () => {
  const THEMENBAUM = /themenbaum|topic.?tree/i;
  const sichtbar = (w: ShadowRoot) => [w.textContent ?? '',
    ...[...w.querySelectorAll('[aria-label]')].map((e) => e.getAttribute('aria-label') ?? '')].join(' ');

  for (const sprache of ['de', 'en'] as const) {
    it(`${sprache}: leer, erfasst mit Unterordnern und Strukturdokument, gelesen — nirgends ein Themenbaum`, async () => {
      const h = host();
      h.hochladen.mockResolvedValue(BEFUND);
      const daten = { ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: true } };
      const { el, wurzel } = erzeuge({ sprache }, h, daten);
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      await waehle(wurzel, [datei('P/Lehr.pdf'), datei('P/A/b.pdf')]);
      const rolle = wurzel.querySelector('select[data-datei]') as HTMLSelectElement;
      rolle.value = 'struktur';
      rolle.dispatchEvent(new Event('change', { bubbles: true }));
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      const lesen = [...wurzel.querySelectorAll('button[data-dokument]')] as HTMLButtonElement[];
      expect(lesen).toHaveLength(1);
      expect(lesen[0].textContent).toBe(sprache === 'de' ? 'Lesen lassen' : 'Read document');
      lesen[0].click();
      el.beschaeftigt = true;     // ein Zug läuft: der Befund wartet auf „Weiter“
      await warte();
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      expect(knopf(wurzel, sprache === 'de' ? 'Weiter' : 'Continue')).toBeTruthy();
    });
  }

  // Review TG-1, m5: ist ein lesbares Strukturdokument markiert und Lesen erlaubt, ist „Lesen lassen“
  // der Hauptknopf — sonst „Senden“
  it('m5: mit lesbarem Strukturdokument ist „Lesen lassen“ der Hauptknopf, sonst „Senden“', async () => {
    const { wurzel } = await markiert();
    expect(knopf(wurzel, 'Lesen lassen')!.classList.contains('u__haupt')).toBe(true);
    expect(knopf(wurzel, 'Senden')!.classList.contains('u__haupt')).toBe(false);
    const ohne = (await markiert(host(), DATEN)).wurzel;     // Lesen nicht erlaubt
    expect(knopf(ohne, 'Senden')!.classList.contains('u__haupt')).toBe(true);
  });

  // Zweites Review TG-1, NIT 10: nach einem endgültigen Lesefehler gibt es kein „Lesen lassen“ mehr —
  // dann ist „Senden“ wieder der Hauptknopf (eine Leiste ohne Hauptknopf wäre ein toter Weg)
  it('n10: nach einem endgültigen Lesefehler ist „Senden“ der Hauptknopf', async () => {
    const h = host();
    h.hochladen.mockRejectedValue(Object.assign(new Error('x'), { status: 400, code: 'kein_text' }));
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    expect(knopf(wurzel, 'Lesen lassen')).toBeUndefined();
    expect(knopf(wurzel, 'Senden')!.classList.contains('u__haupt')).toBe(true);
  });

  it('n10: nach einem Fehler mit neuem Versuch bleibt „Noch einmal versuchen“ der Hauptknopf', async () => {
    const h = host();
    h.hochladen.mockRejectedValue(Object.assign(new Error('x'), { status: 0, code: 'netz' }));
    const { wurzel } = await markiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    expect(knopf(wurzel, 'Noch einmal versuchen')!.classList.contains('u__haupt')).toBe(true);
    expect(knopf(wurzel, 'Senden')!.classList.contains('u__haupt')).toBe(false);
  });

  // Review TG-1, m4: die Knöpfe nennen, worauf sie wirken
  it('m4: „Lesen lassen“ beschreibt der Hinweis mit dem Dateinamen, „Weiter“ sagt, was gesendet wird', async () => {
    const h = host();
    h.hochladen.mockResolvedValue(BEFUND);
    const { el, wurzel } = await markiert(h);
    const lesen = knopf(wurzel, 'Lesen lassen')!;
    const hinweis = wurzel.getElementById(lesen.getAttribute('aria-describedby') ?? '-');
    expect(hinweis?.textContent).toContain('Lehr.pdf');
    lesen.click();
    el.beschaeftigt = true;
    await warte();
    expect(knopf(wurzel, 'Weiter')!.getAttribute('aria-label')).toBe('Weiter: gelesenes Dokument an den Chat');
  });

  it('die Lehrplan-Automatik merkt das Strukturdokument vor, liest aber nicht von selbst', async () => {
    const h = host();
    const { wurzel } = erzeuge({}, h, MIT_DOKUMENT);
    await waehle(wurzel, [datei('P/Lehrplan_Physik.pdf'), datei('P/b.pdf')]);
    expect(h.vormerken.mock.calls.at(-1)?.[0].strukturdokument).toMatchObject({ name: 'Lehrplan_Physik.pdf' });
    expect(knopf(wurzel, 'Lesen lassen')).toBeTruthy();
    expect(h.hochladen).not.toHaveBeenCalled();
    expect(h.antworten).not.toHaveBeenCalled();
  });
});


// ── Plan 2026-11-16, TG-3e: mehrere Strukturdokumente ───────────────────────────────────────────

function befund(n: number, name: string, abschnitte = 3) {
  return { ...BEFUND, upload_id: `11111111-2222-4333-8444-55555555555${n}`, name,
           befund: { ...BEFUND.befund, abschnitte } };
}

async function zweiMarkiert(h = host(), namen = ['A.pdf', 'B.pdf']) {
  const r = erzeuge({}, h, MIT_DOKUMENT);
  await waehle(r.wurzel, [...namen.map((n) => datei(`P/${n}`)), datei('P/inhalt.pdf')]);
  for (const name of namen) {
    const auswahl = r.wurzel.querySelector(`select[aria-label="Rolle von ${name}"]`) as HTMLSelectElement;
    auswahl.value = 'struktur';
    auswahl.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return r;
}

describe('<boerdi-ui-upload> mehrere Strukturdokumente (TG-3e)', () => {
  it('zwei markierte bleiben beide markiert, der Hinweis nennt beide', async () => {
    const h = host();
    const { wurzel } = await zweiMarkiert(h);
    const rollen = [...wurzel.querySelectorAll('select')].map((s) => (s as HTMLSelectElement).value);
    expect(rollen.filter((r) => r === 'struktur')).toHaveLength(2);
    expect(wurzel.textContent).toContain('Strukturdokumente: A.pdf, B.pdf.');
    expect(h.vormerken.mock.calls.at(-1)?.[0].zahlen.strukturdokumente).toBe(2);
  });

  it('ein sechstes lässt sich nicht als Strukturdokument wählen', async () => {
    const namen = ['a.pdf', 'b.pdf', 'c.pdf', 'd.pdf', 'e.pdf'];
    const { wurzel } = await zweiMarkiert(host(), namen);
    const option = wurzel.querySelector('select[aria-label="Rolle von inhalt.pdf"] option[value="struktur"]') as HTMLOptionElement;
    expect(option.disabled).toBe(true);
    const markiert = wurzel.querySelector('select[aria-label="Rolle von a.pdf"] option[value="struktur"]') as HTMLOptionElement;
    expect(markiert.disabled).toBe(false);
  });

  it('liest nacheinander, zeigt „Dokument n von m“ und antwortet einmal mit allen', async () => {
    const h = host();
    const melder: ((a: number) => void)[] = [];
    const fertig: ((b: unknown) => void)[] = [];
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => {
      melder.push(f);
      return new Promise((r) => { fertig.push(r); });
    });
    const { wurzel } = await zweiMarkiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    melder[0](0.5);
    expect(wurzel.textContent).toContain('Dokument 1 von 2 wird hochgeladen … 50 %');
    melder[0](1);
    expect(wurzel.textContent).toContain('Dokument 1 von 2 wird gelesen');
    fertig[0](befund(1, 'A.pdf', 3));
    await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(2);
    expect((h.hochladen.mock.calls[1][0] as File).name).toBe('B.pdf');
    expect(wurzel.textContent).toContain('Dokument 2 von 2 wird hochgeladen');
    expect(h.antworten).not.toHaveBeenCalled();
    fertig[1](befund(2, 'B.pdf', 4));
    await warte();
    const [daten, blase] = h.antworten.mock.calls[0];
    expect(blase).toBe('2 Dokumente lesen lassen');
    expect(daten.dokument.name).toBe('A.pdf');
    expect(daten.dokumente.map((d: { name: string }) => d.name)).toEqual(['A.pdf', 'B.pdf']);
  });

  it('ein Fehler nennt das Dokument; „Noch einmal“ liest es erneut, die gelesenen bleiben', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1, 'A.pdf'))
      .mockRejectedValueOnce(Object.assign(new Error('x'), { status: 0, code: 'netz' }))
      .mockResolvedValueOnce(befund(2, 'B.pdf'));
    const { wurzel } = await zweiMarkiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    await warte();
    expect(wurzel.querySelector('.u__fehler')?.textContent).toBe('„B.pdf“: Keine Verbindung zum Server.');
    knopf(wurzel, 'Noch einmal versuchen')!.click();
    await warte();
    expect(h.hochladen).toHaveBeenCalledTimes(3);           // A nicht noch einmal
    expect(h.antworten.mock.calls[0][0].dokumente).toHaveLength(2);
  });

  it('„Ohne dieses weiter“ lässt ein unlesbares aus und schickt die übrigen', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1, 'A.pdf'))
      .mockRejectedValueOnce(Object.assign(new Error('x'), { status: 400, code: 'kein_text' }));
    const { wurzel } = await zweiMarkiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    await warte();
    await warte();
    expect(knopf(wurzel, 'Noch einmal versuchen')).toBeUndefined();
    const ohne = knopf(wurzel, 'Ohne dieses weiter')!;
    expect(ohne.getAttribute('aria-label')).toBe('Ohne „B.pdf“ weiterlesen');
    expect(ohne.classList.contains('u__haupt')).toBe(true);
    expect(knopf(wurzel, 'Senden')!.classList.contains('u__haupt')).toBe(false);
    ohne.click();
    await warte();
    const [daten, blase] = h.antworten.mock.calls[0];
    expect(blase).toBe('Dokument „A.pdf“ lesen lassen');      // eins gelesen: wie vorher
    expect(daten.dokumente).toBeUndefined();
  });

  it('läuft ein Zug, nennt der Befund die Zahl der Dokumente', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1, 'A.pdf', 3)).mockResolvedValueOnce(befund(2, 'B.pdf', 4));
    const { el, wurzel } = await zweiMarkiert(h);
    knopf(wurzel, 'Lesen lassen')!.click();
    el.beschaeftigt = true;
    await warte();
    await warte();
    expect(wurzel.textContent).toContain('Gelesen: 2 Dokumente, 7 Abschnitte');
    expect(knopf(wurzel, 'Weiter')!.getAttribute('aria-label')).toBe('Weiter: gelesene Dokumente an den Chat');
  });

  it('nur lesend nach dem Lesen: Zahl der Dokumente und alle Abschnitte', () => {
    const a = befund(1, 'A.pdf', 3);
    const dok = (b: typeof a) => ({ upload_id: b.upload_id, name: b.name, format: 'pdf', befund: b.befund, vorschau: [] });
    const { wurzel } = erzeuge({ nurLesen: true, antwort: {
      aktion: 'dokument', dokument: dok(a), dokumente: [dok(a), dok(befund(2, 'B.pdf', 4))],
      zahlen: { ordner: 1, dateien: 2, inhalte: 0, ignoriert: 0, strukturdokumente: 2, bytes: 1 } } });
    expect(wurzel.textContent).toContain('Gelesen: 2 Dokumente, 7 Abschnitte.');
  });

  it('auf Englisch', async () => {
    const h = host();
    h.hochladen.mockImplementation(() => new Promise(() => undefined));
    const r = erzeuge({ sprache: 'en' }, h, MIT_DOKUMENT);
    await waehle(r.wurzel, [datei('P/A.pdf'), datei('P/B.pdf')]);
    for (const name of ['A.pdf', 'B.pdf']) {
      const auswahl = r.wurzel.querySelector(`select[aria-label="Role of ${name}"]`) as HTMLSelectElement;
      auswahl.value = 'struktur';
      auswahl.dispatchEvent(new Event('change', { bubbles: true }));
    }
    expect(r.wurzel.textContent).toContain('Structure documents: A.pdf, B.pdf.');
    knopf(r.wurzel, 'Read document')!.click();
    expect(r.wurzel.textContent).toContain('Uploading document 1 of 2 … 0 %');
  });
});
