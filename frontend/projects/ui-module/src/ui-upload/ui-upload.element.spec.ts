// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { definiere } from './ui-upload.element';

const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const DATEN = { zweck: 'bereitstellen', grenzen: { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50 } };

type Host = ElementHost & {
  antworten: ReturnType<typeof vi.fn>; vormerken: ReturnType<typeof vi.fn>; hochladen: ReturnType<typeof vi.fn>;
  ablegen: ReturnType<typeof vi.fn>;
};

function host(): Host {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), link: vi.fn(() => ({ href: '', hinweis: '' })), aktion: vi.fn(),
    beschaeftigt: vi.fn(() => false), antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(),
    ablegen: vi.fn(),
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
    // Paket U4: vor der Auswahl ist noch kein Ort gewählt
    expect(wurzel.textContent).toContain('Beim Auswählen wird nichts hochgeladen. Danach wählst du, wo die Dateien verarbeitet werden.');
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

  it('Rolle per Auswahlfeld: ein Strukturdokument erscheint in der Vormerkung', async () => {
    const { h, wurzel } = erzeuge();
    await waehle(wurzel, [datei('P/Lehr.pdf'), datei('P/b.pdf')]);
    const auswahl = wurzel.querySelector('select[aria-label="Rolle von Lehr.pdf"]') as HTMLSelectElement;
    auswahl.value = 'struktur';
    auswahl.dispatchEvent(new Event('change', { bubbles: true }));
    expect(h.vormerken.mock.calls.at(-1)?.[0].strukturdokument).toMatchObject({ name: 'Lehr.pdf' });
  });

  // Plan 2026-11-16, TG-1 (G-E4): kein Zielknopf; Paket U4: ohne wählbaren Ort ist „Nur Namen senden“
  // der Hauptknopf (statt „Senden“), und es gibt kein „Hochladen“
  it('TG-1/U4: ohne Ort nur „Nur Namen senden“ (Hauptknopf), kein Zielknopf', async () => {
    const { h, wurzel } = erzeuge();
    await waehle(wurzel, [datei('Physik/A/x.pdf')]);
    expect(knopf(wurzel, 'Als Themenbaum-Entwurf übernehmen')).toBeUndefined();
    expect(knopf(wurzel, 'Hochladen')).toBeUndefined();
    const namen = knopf(wurzel, 'Nur Namen senden (nichts hochladen)')!;
    expect(namen.classList.contains('u__haupt')).toBe(true);
    namen.click();
    expect(h.antworten.mock.calls[0][0]).toMatchObject({ aktion: 'bereitgestellt', ort: 'namen' });
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

  it('Befund 15: nur lesend ohne Antwort sagt es, dass es nicht verwendet wurde', () => {
    const { wurzel } = erzeuge({ nurLesen: true, antwort: null });
    expect(wurzel.textContent).toContain('Nicht verwendet.');
  });

  it('auf Englisch', () => {
    const { wurzel } = erzeuge({ sprache: 'en' });
    expect(knopf(wurzel, 'Choose folder')).toBeTruthy();
  });

  it('R3-b: hilft die Anmeldung beim Lesen, steht das vor der Auswahl gleich unter dem Hinweis', () => {
    // Review der Oberfläche, 8: der Name des Orts statt „lesen lassen“
    const satz = 'Dateien „Hier im Chat“ hochladen geht erst, wenn du bei WLO angemeldet bist.';
    const { wurzel } = erzeuge({}, host(), {
      ...DATEN, hinweis: 'Lade deinen Lehrplan hoch.',
      schalter: { dokument_im_chat: false, ablage_in_wlo: false, lesen_nach_anmeldung: true },
    });
    const saetze = [...wurzel.querySelectorAll('.u__hinweis')].map((p) => p.textContent);
    expect(saetze[saetze.indexOf('Lade deinen Lehrplan hoch.') + 1]).toBe(satz);
    const ohne = erzeuge({}, host(), { ...DATEN, hinweis: 'X.' }).wurzel;
    expect([...ohne.querySelectorAll('.u__hinweis')].map((p) => p.textContent)).not.toContain(satz);
  });

  it('Rückmeldung 16.11.: ohne Anmeldung nennt das Feld vor der Auswahl die Voraussetzung der Ablage', () => {
    const satz = 'Dateien „In WLO ablegen“ – in deinem persönlichen Bereich, dort entstehen Volltexte '
      + 'und Metadaten – geht, wenn du bei WLO angemeldet bist.';
    const { wurzel } = erzeuge({}, host(), {
      ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: false, ablage_nach_anmeldung: true },
    });
    expect([...wurzel.querySelectorAll('.u__hinweis')].map((p) => p.textContent)).toContain(satz);
    const angemeldet = erzeuge({}, host(), { ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: true } }).wurzel;
    expect([...angemeldet.querySelectorAll('.u__hinweis')].map((p) => p.textContent)).not.toContain(satz);
  });
});

// ── Plan 2026-11-17, Paket U4 (Teil b): „Wo sollen sie verarbeitet werden?“ ─────────────────────

const ORTE_WLO = {
  vorauswahl: 'wlo', chat: { geht: true, ueber_grenze: 'ueber_grenze' }, wlo: { geht: true }, namen: { geht: true },
};
const ORTE_ANONYM = {
  vorauswahl: 'chat', chat: { geht: true, ueber_grenze: 'ueber_grenze_anmelden' },
  wlo: { geht: false, grund: 'nur_angemeldet' }, namen: { geht: true },
};
const GRENZEN_LOKAL = { ...DATEN.grenzen, lokal_max_dateien: 10, lokal_max_mb_gesamt: 50, lokal_aufbewahrung_h: 24 };
const ANGEMELDET = { ...DATEN, grenzen: GRENZEN_LOKAL, orte: ORTE_WLO, schalter: { dokument_im_chat: true, ablage_in_wlo: true } };
const ANONYM = { ...DATEN, grenzen: GRENZEN_LOKAL, orte: ORTE_ANONYM, schalter: { dokument_im_chat: true, ablage_in_wlo: false } };

const warte = () => new Promise((r) => setTimeout(r, 0));
const radio = (w: ShadowRoot, ort: string) => w.querySelector(`input[type="radio"][data-ort="${ort}"]`) as HTMLInputElement;
const erklaerung = (w: ShadowRoot, ort: string) =>
  w.getElementById(radio(w, ort).getAttribute('aria-describedby') ?? '-')?.textContent;
function waehleOrt(w: ShadowRoot, ort: string): void {
  const r = radio(w, ort);
  r.focus();
  r.checked = true;
  r.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('<boerdi-ui-upload> Wo verarbeiten? (Paket U4)', () => {
  it('nach der Auswahl: Frage als Gruppe, zwei Chips mit Erklärzeile, Vorauswahl aus `orte`', async () => {
    const { wurzel } = erzeuge({}, host(), ANGEMELDET);
    expect(wurzel.querySelector('fieldset')).toBeNull();          // leer: noch keine Frage
    await waehle(wurzel, [datei('P/a.pdf'), datei('P/b.pdf')]);
    expect(wurzel.querySelector('fieldset > legend')?.textContent).toBe('Wo sollen sie verarbeitet werden?');
    const radios = [...wurzel.querySelectorAll('input[type="radio"]')] as HTMLInputElement[];
    expect(radios.map((r) => [r.value, r.name, r.checked, r.disabled])).toEqual([
      ['chat', 'u-ort', false, false], ['wlo', 'u-ort', true, false]]);
    expect(radios.map((r) => r.closest('label')?.textContent)).toEqual(['Hier im Chat', 'In WLO ablegen und erschließen']);
    expect(erklaerung(wurzel, 'chat')).toBe('schnell, ohne Anmeldung, bis 10 Dateien – Text bleibt bis zu 24 Stunden nach der letzten Nutzung hier');
    expect(erklaerung(wurzel, 'wlo')).toBe('alle Dateien, mit WLO-Anmeldung – Titel, Beschreibung, Fach und Stufe entstehen in WLO im Hintergrund');
    // ein Hauptknopf; „Nur Namen senden“ daneben
    expect(knopf(wurzel, 'Hochladen')!.classList.contains('u__haupt')).toBe(true);
    expect(knopf(wurzel, 'Nur Namen senden (nichts hochladen)')!.classList.contains('u__haupt')).toBe(false);
    expect(knopf(wurzel, 'Senden')).toBeUndefined();
    expect(knopf(wurzel, 'Lesen lassen')).toBeUndefined();
    expect(knopf(wurzel, 'Übertragen vorbereiten …')).toBeUndefined();
    expect(wurzel.textContent).toContain('in deinem persönlichen Bereich in WLO ab; dort bleiben sie, bis du sie löschst');
  });

  it('gesperrt bleibt sichtbar, mit dem Grund als Text; ohne Anmeldung ist „Hier im Chat“ vorgewählt', async () => {
    const { wurzel } = erzeuge({}, host(), ANONYM);
    await waehle(wurzel, [datei('P/a.pdf')]);
    expect(radio(wurzel, 'wlo').disabled).toBe(true);
    expect(erklaerung(wurzel, 'wlo')).toBe('nicht wählbar – braucht eine WLO-Anmeldung');
    expect(radio(wurzel, 'chat').checked).toBe(true);
    expect(wurzel.textContent).toContain('er behält nur ihren Text, bis zu 24 Stunden nach der letzten Nutzung');
  });

  it('WLO ohne Erschließung sagt es; ein Ablauf kann einen Ort ausschließen', async () => {
    const daten = { ...ANGEMELDET, orte: { ...ORTE_WLO, wlo: { geht: true, hinweis: 'ohne_erschliessung' },
      chat: { geht: false, grund: 'ablauf' } } };
    const { wurzel } = erzeuge({}, host(), daten);
    await waehle(wurzel, [datei('P/a.pdf')]);
    expect(erklaerung(wurzel, 'wlo')).toBe('alle Dateien, mit WLO-Anmeldung – nur ablegen; Angaben werden gerade nicht erzeugt');
    expect(erklaerung(wurzel, 'chat')).toBe('nicht wählbar – in diesem Ablauf nicht vorgesehen');
    expect(wurzel.textContent).not.toContain('erzeugt daraus Titel');
  });

  it('über der Grenze: „Hier im Chat“ gesperrt mit Grund, ohne Ort ist „Nur Namen senden“ der Hauptknopf', async () => {
    const daten = { ...ANONYM, grenzen: { ...GRENZEN_LOKAL, lokal_max_dateien: 2 } };
    const { h, wurzel } = erzeuge({}, host(), daten);
    await waehle(wurzel, [datei('P/a.pdf'), datei('P/b.pdf'), datei('P/c.pdf')]);
    expect(radio(wurzel, 'chat').disabled).toBe(true);
    expect(erklaerung(wurzel, 'chat')).toBe('nicht wählbar – zu viele Dateien für hier (höchstens 2) – mit Anmeldung über WLO');
    expect(knopf(wurzel, 'Hochladen')).toBeUndefined();
    const namen = knopf(wurzel, 'Nur Namen senden (nichts hochladen)')!;
    expect(namen.classList.contains('u__haupt')).toBe(true);
    // eine Datei ignorieren → wieder unter der Grenze, „Hier im Chat“ geht wieder
    const rolle = wurzel.querySelector('select[aria-label="Rolle von c.pdf"]') as HTMLSelectElement;
    rolle.value = 'ignorieren';
    rolle.dispatchEvent(new Event('change', { bubbles: true }));
    expect(radio(wurzel, 'chat').disabled).toBe(false);
    expect(radio(wurzel, 'chat').checked).toBe(true);
    expect(knopf(wurzel, 'Hochladen')).toBeTruthy();
    expect(h.hochladen).not.toHaveBeenCalled();
  });

  it('über der Menge (MB) nennt es die Menge; angemeldet wechselt die Vorauswahl zu WLO', async () => {
    const daten = { ...ANGEMELDET, orte: { ...ORTE_WLO, vorauswahl: 'chat' }, grenzen: { ...GRENZEN_LOKAL, lokal_max_mb_gesamt: 1 } };
    const { wurzel } = erzeuge({}, host(), daten);
    await waehle(wurzel, [datei('P/a.pdf', 800_000), datei('P/b.pdf', 800_000)]);
    expect(erklaerung(wurzel, 'chat')).toBe('nicht wählbar – zu viel für hier (höchstens 1 MB zusammen)');
    expect(radio(wurzel, 'wlo').checked).toBe(true);
  });

  it('die Person wählt per Radioknopf; Fokus bleibt, Datenschutz-Satz und Hinweise folgen dem Ort', async () => {
    const { wurzel } = erzeuge({}, host(), ANGEMELDET);
    await waehle(wurzel, [datei('P/a.pdf'), datei('P/folien.pptx', 100, 'application/vnd.ms-powerpoint')]);
    expect(wurzel.textContent).not.toContain('kann der Chat nicht lesen');
    waehleOrt(wurzel, 'chat');
    expect(radio(wurzel, 'chat').checked).toBe(true);
    expect(radio(wurzel, 'wlo').checked).toBe(false);
    expect(wurzel.activeElement).toBe(radio(wurzel, 'chat'));
    expect(radio(wurzel, 'chat').closest('label')!.classList.contains('u__chip--an')).toBe(true);
    expect(wurzel.textContent).toContain('1 Datei kann der Chat nicht lesen – davon geht nur der Name mit.');
    expect(wurzel.textContent).toContain('er behält nur ihren Text');
  });

  it('„Nur Namen senden“ antwortet mit Ort namen — nichts wird hochgeladen', async () => {
    const { h, wurzel } = erzeuge({}, host(), ANGEMELDET);
    await waehle(wurzel, [datei('Physik/A/x.pdf')]);
    knopf(wurzel, 'Nur Namen senden (nichts hochladen)')!.click();
    const [daten, text] = h.antworten.mock.calls[0];
    expect(daten).toMatchObject({ aktion: 'bereitgestellt', ort: 'namen', struktur: { name: 'Physik' } });
    expect(daten).not.toHaveProperty('dateien');
    expect(text).toBe('Nur die Namen gesendet – „Physik“: 2 Ordner, 1 Datei.');
    expect(h.hochladen).not.toHaveBeenCalled();
    expect(h.ablegen).not.toHaveBeenCalled();
  });

  it('solange ein Zug läuft, sind Chips, „Hochladen“ und „Nur Namen senden“ gesperrt', async () => {
    const { el, wurzel } = erzeuge({}, host(), ANGEMELDET);
    await waehle(wurzel, [datei('P/a.pdf')]);
    el.beschaeftigt = true;
    expect(knopf(wurzel, 'Hochladen')!.disabled).toBe(true);
    expect(knopf(wurzel, 'Nur Namen senden (nichts hochladen)')!.disabled).toBe(true);
    expect(radio(wurzel, 'chat').disabled).toBe(true);
    expect(knopf(wurzel, 'Andere Auswahl')!.disabled).toBe(false);
  });

  it('ohne `orte` (älteres Backend) aus den Schaltern; ohne Schalter gehen nur die Namen', async () => {
    const { wurzel } = erzeuge({}, host(), { ...DATEN, schalter: { dokument_im_chat: true, ablage_in_wlo: false } });
    await waehle(wurzel, [datei('P/a.pdf')]);
    expect(radio(wurzel, 'chat').checked).toBe(true);
    expect(erklaerung(wurzel, 'wlo')).toBe('nicht wählbar – gerade ausgeschaltet');
    const ohne = erzeuge().wurzel;
    await waehle(ohne, [datei('P/a.pdf')]);
    expect(knopf(ohne, 'Hochladen')).toBeUndefined();
    expect(ohne.textContent).toContain('alle Inhalte bleiben auf deinem Gerät');
  });

  it('auf Englisch: Frage, Chips und Knöpfe', async () => {
    const { wurzel } = erzeuge({ sprache: 'en' }, host(), ANONYM);
    await waehle(wurzel, [datei('P/a.pdf')]);
    expect(wurzel.querySelector('legend')?.textContent).toBe('Where should they be processed?');
    expect(radio(wurzel, 'chat').closest('label')?.textContent).toBe('Here in the chat');
    expect(erklaerung(wurzel, 'wlo')).toBe('not available – needs a WLO sign-in');
    expect(knopf(wurzel, 'Upload')).toBeTruthy();
    expect(knopf(wurzel, 'Send names only (upload nothing)')).toBeTruthy();
  });
});

// ── Paket U4: „Hier im Chat“ — je lesbare Datei hochladen, nacheinander ─────────────────────────

const ID = (n: number) => `11111111-2222-4333-8444-55555555555${n}`;
const befundVon = (n: number, rolle = 'inhalt') => ({
  upload_id: ID(n), name: `d${n}.pdf`, format: 'pdf', rolle, ueberschriften_vorschau: [],
  befund: { seiten: 1, woerter: 100, abschnitte: 2, gliederung_art: 'teile', warnungen: [] },
  ...(rolle === 'inhalt' ? { angaben: { titel: 'T', beschreibung: 'B', schlagworte: [] } } : {}),
});

/** Ein Feld ohne Anmeldung mit Lehrplan (Strukturdokument), einem Inhalt und Folien (nicht lesbar). */
async function bereit(h = host(), daten: Record<string, unknown> = ANONYM) {
  const r = erzeuge({}, h, daten);
  await waehle(r.wurzel, [datei('P/Lehrplan.pdf'), datei('P/blatt.docx'), datei('P/folien.pptx', 100, 'application/vnd.ms-powerpoint')]);
  return r;
}

describe('<boerdi-ui-upload> Hier im Chat (Paket U4)', () => {
  it('lädt jede lesbare Datei mit ihrer Rolle hoch, „Datei k von n“, und antwortet einmal mit Ort chat', async () => {
    const h = host();
    const melder: ((a: number) => void)[] = [];
    const fertig: ((b: unknown) => void)[] = [];
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => {
      melder.push(f);
      return new Promise((r) => fertig.push(r));
    });
    const { wurzel } = await bereit(h);
    // die Lehrplan-Automatik hat den Lehrplan als Strukturdokument vorgemerkt
    expect((wurzel.querySelector('select[aria-label="Rolle von Lehrplan.pdf"]') as HTMLSelectElement).value).toBe('struktur');
    knopf(wurzel, 'Hochladen')!.focus();
    knopf(wurzel, 'Hochladen')!.click();
    expect(h.hochladen).toHaveBeenCalledTimes(1);
    const [erste, , rolle] = h.hochladen.mock.calls[0] as [File, unknown, string];
    expect([erste.name, rolle]).toEqual(['Lehrplan.pdf', 'struktur']);
    // der Fokus geht vom verschwundenen Knopf auf den Stand, nie auf body
    expect((wurzel.activeElement as HTMLElement | null)?.dataset['fokus']).toBe('s:chat');
    melder[0](0.4);
    expect(wurzel.textContent).toContain('Datei 1 von 2 wird hochgeladen … 40 %');
    expect((wurzel.querySelector('progress') as HTMLProgressElement).value).toBe(40);
    expect(knopf(wurzel, 'Andere Auswahl')!.disabled).toBe(true);
    expect(knopf(wurzel, 'Hochladen')).toBeUndefined();
    melder[0](1);
    expect(wurzel.textContent).toContain('Datei 1 von 2 wird gelesen');
    fertig[0](befundVon(1, 'struktur'));
    await warte();
    const [zweite, , rolle2] = h.hochladen.mock.calls[1] as [File, unknown, string];
    expect([zweite.name, rolle2]).toEqual(['blatt.docx', 'inhalt']);
    fertig[1](befundVon(2));
    await warte();
    // Folien (pptx) gehen nicht hoch
    expect(h.hochladen).toHaveBeenCalledTimes(2);
    expect(h.antworten).toHaveBeenCalledTimes(1);
    const [daten, blase] = h.antworten.mock.calls[0];
    expect(blase).toBe('Hier im Chat bereitgestellt: 2 Dateien.');
    expect(daten).toMatchObject({ aktion: 'bereitgestellt', ort: 'chat' });
    const i = (name: string) => (daten.struktur.dateiliste as { i: number; name: string }[]).find((d) => d.name === name)!.i;
    expect(daten.dateien).toEqual([
      { i: i('Lehrplan.pdf'), rolle: 'struktur', upload_id: ID(1) }, { i: i('blatt.docx'), rolle: 'inhalt', upload_id: ID(2) }]);
    // nie Angaben oder Text des Backends in der Antwort
    expect(JSON.stringify(daten)).not.toContain('beschreibung');
  });

  // Review der Oberfläche, 1: `grenze_anzahl` beendet den Lauf (ui-upload-chat.element.spec.ts); hier
  // eine Datei, die der Chat nicht verarbeitet — ohne neuen Versuch, mit „Ohne diese weiter“
  it('ein Fehler je Datei als eigener Satz; ohne Aussicht kein neuer Versuch, „Ohne diese weiter“', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befundVon(1, 'struktur'))
      .mockRejectedValueOnce(Object.assign(new Error('x'), { status: 422, code: 'abgewiesen' }));
    const { wurzel } = await bereit(h);
    knopf(wurzel, 'Hochladen')!.click();
    await warte();
    await warte();
    const fehler = wurzel.querySelector('.u__fehler') as HTMLElement;
    expect(fehler.textContent).toBe('„blatt.docx“: Diese Datei kann der Chat nicht verarbeiten.');
    expect(knopf(wurzel, 'Noch einmal versuchen')).toBeUndefined();
    const ohne = knopf(wurzel, 'Ohne diese weiter')!;
    expect(ohne.classList.contains('u__haupt')).toBe(true);
    expect(wurzel.getElementById(ohne.getAttribute('aria-describedby') ?? '-')).toBe(fehler);
    expect(h.antworten).not.toHaveBeenCalled();
    ohne.click();
    await warte();
    expect(h.antworten.mock.calls[0][0].dateien).toEqual([expect.objectContaining({ upload_id: ID(1) })]);
  });

  it('nach einem Netzfehler „Noch einmal versuchen“ mit derselben Datei; 429 heißt kurz warten', async () => {
    const h = host();
    h.hochladen.mockRejectedValueOnce(Object.assign(new Error('x'), { status: 0, code: 'netz' }))
      .mockRejectedValueOnce(Object.assign(new Error('x'), { status: 429, code: 'fehler' }))
      .mockResolvedValueOnce(befundVon(1, 'struktur'))
      .mockResolvedValueOnce(befundVon(2));
    const { wurzel } = await bereit(h);
    knopf(wurzel, 'Hochladen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('„Lehrplan.pdf“: Keine Verbindung zum Server.');
    knopf(wurzel, 'Noch einmal versuchen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('Zu viele Anfragen');
    knopf(wurzel, 'Noch einmal versuchen')!.click();
    await warte();
    await warte();
    expect((h.hochladen.mock.calls.map((c) => (c[0] as File).name))).toEqual(['Lehrplan.pdf', 'Lehrplan.pdf', 'Lehrplan.pdf', 'blatt.docx']);
    expect(h.antworten).toHaveBeenCalledTimes(1);
  });

  it('läuft gerade ein Zug, wartet die Antwort auf „Weiter“ — vorgemerkt, ohne neues Hochladen', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befundVon(1, 'struktur')).mockResolvedValueOnce(befundVon(2));
    const { el, wurzel } = await bereit(h);
    knopf(wurzel, 'Hochladen')!.click();
    el.beschaeftigt = true;
    await warte();
    await warte();
    expect(h.antworten).not.toHaveBeenCalled();
    expect(h.vormerken.mock.calls.at(-1)?.[0]).toMatchObject({ aktion: 'bereitgestellt', ort: 'chat' });
    expect(wurzel.textContent).toContain('Gelesen: 2 Dateien. Bitte warten, bis die Antwort da ist.');
    const weiter = knopf(wurzel, 'Weiter')!;
    expect(weiter.disabled).toBe(true);
    expect(weiter.getAttribute('aria-label')).toBe('Weiter: gelesene Dateien an den Chat');
    el.beschaeftigt = false;
    knopf(wurzel, 'Weiter')!.click();
    expect(h.antworten).toHaveBeenCalledTimes(1);
    expect(h.hochladen).toHaveBeenCalledTimes(2);
  });

  it('ein unbrauchbarer Befund gilt als Fehler; 413 ohne Code heißt „zu groß“ ohne neuen Versuch', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce({ name: 'x' });
    const { wurzel } = await bereit(h);
    knopf(wurzel, 'Hochladen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('„Lehrplan.pdf“: Die Datei ließ sich nicht lesen.');
    h.hochladen.mockRejectedValueOnce(Object.assign(new Error('x'), { status: 413, code: 'fehler' }));
    knopf(wurzel, 'Noch einmal versuchen')!.click();
    await warte();
    expect(wurzel.textContent).toContain('Die Datei ist zu groß.');
    expect(knopf(wurzel, 'Noch einmal versuchen')).toBeUndefined();
  });

  it('während des Hochladens ruhen Rollen und „Ignorieren“; ein Fortschrittsschritt zeichnet nicht neu', async () => {
    const h = host();
    let melde: (anteil: number) => void = () => undefined;
    h.hochladen.mockImplementation((_d: File, f: (a: number) => void) => { melde = f; return new Promise(() => undefined); });
    const { wurzel } = await bereit(h);
    knopf(wurzel, 'Hochladen')!.click();
    expect([...wurzel.querySelectorAll('select')].every((s) => s.disabled)).toBe(true);
    expect([...wurzel.querySelectorAll('button[data-ignorieren]')].every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    const balken = wurzel.querySelector('progress');
    melde(0.25);
    melde(0.5);
    expect(wurzel.querySelector('progress')).toBe(balken);
    expect(balken!.value).toBe(50);
  });

  it('nur lesend: die Antwort je Ort — und ältere Antworten wie damals', () => {
    const zahlen = { ordner: 1, dateien: 3, inhalte: 2, ignoriert: 0, strukturdokumente: 1, bytes: 1 };
    const chat = erzeuge({ nurLesen: true, antwort: { aktion: 'bereitgestellt', ort: 'chat', zahlen,
      dateien: [{ i: 0, rolle: 'inhalt', upload_id: ID(1) }, { i: 1, rolle: 'struktur', upload_id: ID(2) }] } as never }).wurzel;
    expect(chat.textContent).toContain('Hier im Chat bereitgestellt: 2 Dateien.');
    document.body.innerHTML = '';
    const namen = erzeuge({ nurLesen: true, antwort: { aktion: 'bereitgestellt', ort: 'namen', zahlen } as never }).wurzel;
    expect(namen.textContent).toContain('Nur Namen gesendet: 1 Ordner, 3 Dateien.');
    document.body.innerHTML = '';
    const alt = erzeuge({ nurLesen: true, antwort: { aktion: 'dokument', zahlen,
      dokument: { name: 'Lehr.pdf', befund: { abschnitte: 5 } } } as never }).wurzel;
    expect(alt.textContent).toContain('Gelesen: Lehr.pdf, 5 Abschnitte.');
  });
});

// ── Plan 2026-11-16, TG-1: zielneutral — kein Knopf und kein Text nennt einen Themenbaum ─────────

describe('<boerdi-ui-upload> zielneutral (TG-1)', () => {
  const THEMENBAUM = /themenbaum|topic.?tree/i;
  const sichtbar = (w: ShadowRoot) => [w.textContent ?? '',
    ...[...w.querySelectorAll('[aria-label]')].map((e) => e.getAttribute('aria-label') ?? '')].join(' ');

  for (const sprache of ['de', 'en'] as const) {
    it(`${sprache}: leer, erfasst mit Strukturdokument, Ort gewählt, gelesen — nirgends ein Themenbaum`, async () => {
      const h = host();
      h.hochladen.mockResolvedValueOnce(befundVon(1, 'struktur')).mockResolvedValueOnce(befundVon(2));
      const { el, wurzel } = erzeuge({ sprache }, h, ANGEMELDET);
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      await waehle(wurzel, [datei('P/Lehrplan.pdf'), datei('P/A/b.pdf')]);
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      waehleOrt(wurzel, 'chat');
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      knopf(wurzel, sprache === 'de' ? 'Hochladen' : 'Upload')!.click();
      el.beschaeftigt = true;     // ein Zug läuft: die Antwort wartet auf „Weiter“
      await warte();
      await warte();
      expect(sichtbar(wurzel)).not.toMatch(THEMENBAUM);
      expect(knopf(wurzel, sprache === 'de' ? 'Weiter' : 'Continue')).toBeTruthy();
    });
  }

  it('die Lehrplan-Automatik merkt das Strukturdokument vor, lädt aber nicht von selbst', async () => {
    const h = host();
    const { wurzel } = erzeuge({}, h, ANONYM);
    await waehle(wurzel, [datei('P/Lehrplan_Physik.pdf'), datei('P/b.pdf')]);
    expect(h.vormerken.mock.calls.at(-1)?.[0].strukturdokument).toMatchObject({ name: 'Lehrplan_Physik.pdf' });
    expect(knopf(wurzel, 'Hochladen')).toBeTruthy();
    expect(h.hochladen).not.toHaveBeenCalled();
    expect(h.antworten).not.toHaveBeenCalled();
  });
});

// ── Plan 2026-11-16, TG-3e: mehrere Strukturdokumente ───────────────────────────────────────────

async function zweiMarkiert(h = host(), namen = ['A.pdf', 'B.pdf']) {
  const r = erzeuge({}, h, ANONYM);
  await waehle(r.wurzel, [...namen.map((n) => datei(`P/${n}`)), datei('P/inhalt.pdf')]);
  for (const name of namen) {
    const auswahl = r.wurzel.querySelector(`select[aria-label="Rolle von ${name}"]`) as HTMLSelectElement;
    auswahl.value = 'struktur';
    auswahl.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return r;
}

describe('<boerdi-ui-upload> mehrere Strukturdokumente (TG-3e)', () => {
  it('zwei markierte bleiben beide markiert und gehen beide mit ihrer Rolle hoch', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befundVon(1, 'struktur')).mockResolvedValueOnce(befundVon(2, 'struktur'))
      .mockResolvedValueOnce(befundVon(3));
    const { wurzel } = await zweiMarkiert(h);
    const rollen = [...wurzel.querySelectorAll('select')].map((s) => (s as HTMLSelectElement).value);
    expect(rollen.filter((r) => r === 'struktur')).toHaveLength(2);
    expect(h.vormerken.mock.calls.at(-1)?.[0].zahlen.strukturdokumente).toBe(2);
    knopf(wurzel, 'Hochladen')!.click();
    for (let k = 0; k < 4; k++) await warte();
    expect(h.hochladen.mock.calls.map((c) => c[2])).toEqual(['struktur', 'struktur', 'inhalt']);
    expect(h.antworten.mock.calls[0][0].dateien.map((d: { rolle: string }) => d.rolle)).toEqual(['struktur', 'struktur', 'inhalt']);
  });

  it('ein sechstes lässt sich nicht als Strukturdokument wählen (Antwort-Schema: höchstens fünf)', async () => {
    const namen = ['a.pdf', 'b.pdf', 'c.pdf', 'd.pdf', 'e.pdf'];
    const { wurzel } = await zweiMarkiert(host(), namen);
    const option = wurzel.querySelector('select[aria-label="Rolle von inhalt.pdf"] option[value="struktur"]') as HTMLOptionElement;
    expect(option.disabled).toBe(true);
    const markiert = wurzel.querySelector('select[aria-label="Rolle von a.pdf"] option[value="struktur"]') as HTMLOptionElement;
    expect(markiert.disabled).toBe(false);
  });
});
