// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import './ui-upload.element';
import { orteAus } from './upload-orte';
import { texte } from './upload-texte';

/**
 * Plan 2026-11-19, Paket C: Texterkennung „Hier im Chat“. Der Server sagt im Ort `chat`, ob gescannte
 * PDF per Texterkennung gelesen werden (`texterkennung`). Das Feld nennt dann vor dem Hochladen den
 * Datenschutz-Satz, zeigt während eines langen Lesens einer PDF einen Hinweis und sagt danach, welche
 * Dateien per Texterkennung gelesen wurden (Warnung `ocr` im Befund).
 */
const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const GRENZEN = { max_dateien: 500, max_tiefe: 8, max_mb_datei: 50, lokal_max_dateien: 10, lokal_max_mb_gesamt: 50, lokal_aufbewahrung_h: 24 };
const orte = (texterkennung: boolean) => ({
  vorauswahl: 'chat', chat: { geht: true, ueber_grenze: 'ueber_grenze', ...(texterkennung ? { texterkennung: true } : {}) },
  wlo: { geht: false, grund: 'nur_angemeldet' }, namen: { geht: true },
});
const daten = (texterkennung = true) => ({ zweck: 'bereitstellen', grenzen: GRENZEN, orte: orte(texterkennung),
  schalter: { dokument_im_chat: true, ablage_in_wlo: false } });

type Fn = ReturnType<typeof vi.fn>;
type Host = ElementHost & { antworten: Fn; hochladen: Fn };

function host(): Host {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), link: vi.fn(() => ({ href: '', hinweis: '' })), aktion: vi.fn(),
    beschaeftigt: vi.fn(() => false), antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(),
    ablegen: vi.fn(),
  } as never;
}

function datei(pfad: string, type = 'application/pdf'): File {
  const f = new File([new Uint8Array(100)], pfad.split('/').pop() ?? pfad, { type, lastModified: 1_700_000_000_000 });
  Object.defineProperty(f, 'webkitRelativePath', { value: pfad });
  return f;
}

const ID = (n: number) => `11111111-2222-4333-8444-55555555555${n}`;
const befund = (n: number, warnungen: string[] = []) => ({ upload_id: ID(n), name: `d${n}.pdf`, format: 'pdf', rolle: 'inhalt',
  ueberschriften_vorschau: [], befund: { seiten: 1, woerter: 100, abschnitte: 2, gliederung_art: 'teile', warnungen } });
const warte = () => new Promise((r) => setTimeout(r, 0));
const knopf = (w: ShadowRoot, text: string) =>
  [...w.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

async function feld(dateien: File[], h: Host, d: Record<string, unknown> = daten()) {
  const el = document.createElement('boerdi-ui-upload') as NachladeElement;
  el.host = h;
  el.daten = d;
  el.kontext = KONTEXT;
  el.beschaeftigt = false;
  document.body.appendChild(el);
  const wurzel = el.shadowRoot as ShadowRoot;
  const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: dateien, configurable: true });
  input.dispatchEvent(new Event('change', { bubbles: true }));
  await warte();
  return wurzel;
}

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = '';
});

describe('Paket C: Texterkennung im Upload-Feld', () => {
  it('der Ort chat übernimmt `texterkennung` nur, wenn der Server sie meldet', () => {
    expect(orteAus(daten(true)).chat.texterkennung).toBe(true);
    expect(orteAus(daten(false)).chat.texterkennung).toBeUndefined();
    expect(orteAus({ orte: { ...orte(false), chat: { geht: true, texterkennung: 'ja' } } }).chat.texterkennung).toBeUndefined();
  });

  it('Datenschutz: mit Texterkennung sagt das Feld vor dem Hochladen, dass Seiten als Bild an das KI-Modell gehen', async () => {
    const mit = await feld([datei('P/scan.pdf')], host());
    expect(mit.textContent).toContain('Gescannte Seiten gehen als Bild an das KI-Modell.');
    document.body.innerHTML = '';
    const ohne = await feld([datei('P/scan.pdf')], host(), daten(false));
    expect(ohne.textContent).not.toContain('Gescannte Seiten');
  });

  it('danach: die Blase nennt, wie viele per Texterkennung gelesen wurden', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1, ['ocr'])).mockResolvedValueOnce(befund(2));
    const w = await feld([datei('P/scan.pdf'), datei('P/text.pdf')], h);
    knopf(w, 'Hochladen')!.click();
    for (let i = 0; i < 5; i++) await warte();
    expect(h.antworten).toHaveBeenCalledTimes(1);
    expect(h.antworten.mock.calls[0][1]).toBe('Hier im Chat bereitgestellt: 2 Dateien, davon 1 per Texterkennung gelesen.');
    // die Antwort an den Chat trägt nur Nummer, Rolle und Kennung
    expect(Object.keys(h.antworten.mock.calls[0][0].dateien[0]).sort()).toEqual(['i', 'rolle', 'upload_id']);
  });

  it('ohne Texterkennung bleibt die Blase wie bisher', async () => {
    const h = host();
    h.hochladen.mockResolvedValueOnce(befund(1));
    const w = await feld([datei('P/text.pdf')], h);
    knopf(w, 'Hochladen')!.click();
    for (let i = 0; i < 5; i++) await warte();
    expect(h.antworten.mock.calls[0][1]).toBe('Hier im Chat bereitgestellt: 1 Datei.');
  });

  it('während des Lesens einer PDF erscheint nach 5 s der Hinweis zur Texterkennung — und wird angesagt', async () => {
    vi.useFakeTimers();
    const h = host();
    let fertig: (b: unknown) => void = () => undefined;
    h.hochladen.mockImplementation((_d: File, fortschritt: (a: number) => void) => {
      fortschritt(1);                         // gesendet — jetzt liest der Server
      return new Promise((ok) => { fertig = ok; });
    });
    const w = await feldMitUhr([datei('P/scan.pdf')], h);
    knopf(w, 'Hochladen')!.click();
    await vi.advanceTimersByTimeAsync(4000);
    expect(w.textContent).not.toContain('Texterkennung');
    await vi.advanceTimersByTimeAsync(1500);
    const satz = 'Bei gescannten Seiten läuft eine Texterkennung – das kann bis zu anderthalb Minuten dauern.';
    expect(w.textContent).toContain(satz);
    expect(w.querySelector('[aria-live]')?.textContent).toBe(satz);
    fertig(befund(1, ['ocr']));
    await vi.advanceTimersByTimeAsync(10);
    expect(h.antworten).toHaveBeenCalledTimes(1);
  });

  it('kein Hinweis zum langen Lesen ohne Texterkennung oder bei anderen Dateien als PDF', async () => {
    vi.useFakeTimers();
    for (const [d, f] of [[daten(false), datei('P/scan.pdf')], [daten(true), datei('P/notiz.docx', 'application/msword')]] as const) {
      const h = host();
      h.hochladen.mockImplementation((_d: File, fortschritt: (a: number) => void) => {
        fortschritt(1);
        return new Promise(() => undefined);
      });
      const w = await feldMitUhr([f], h, d);
      knopf(w, 'Hochladen')!.click();
      await vi.advanceTimersByTimeAsync(6000);
      expect(w.textContent).not.toContain('Texterkennung läuft');
      document.body.innerHTML = '';
    }
  });

  it('Texte de/en', () => {
    expect(texte('en').datenschutzOcr).toBe('Scanned pages go to the AI model as images.');
    // Review 11: ehrlich zur Frist (80 s Texterkennung plus Moderation)
    expect(texte('en').texterkennungLaeuft).toBe('For scanned pages, text recognition is running – this can take up to a minute and a half.');
    // Review 12: eigene Form, wenn alle per Texterkennung gelesen sind
    expect(texte('de').blaseChat(1, 0)).toBe('Hier im Chat bereitgestellt: 1 Datei.');
    expect(texte('de').blaseChat(1, 1)).toBe('Hier im Chat bereitgestellt: 1 Datei, per Texterkennung gelesen.');
    expect(texte('de').blaseChat(3, 3)).toBe('Hier im Chat bereitgestellt: 3 Dateien, alle per Texterkennung gelesen.');
    expect(texte('de').blaseChat(2, 1)).toBe('Hier im Chat bereitgestellt: 2 Dateien, davon 1 per Texterkennung gelesen.');
    expect(texte('en').blaseChat(1, 1)).toBe('Provided here in the chat: 1 file, read by text recognition.');
    expect(texte('en').blaseChat(2, 2)).toBe('Provided here in the chat: 2 files, all read by text recognition.');
    expect(texte('en').blaseChat(3, 1)).toBe('Provided here in the chat: 3 files, 1 of them read by text recognition.');
    // Review 3: die Grenze der Sitzung hat einen eigenen Satz
    expect(texte('de').chatFehler.grenze_ocr).toBe('Für dieses Gespräch sind schon so viele gescannte Seiten gelesen, wie gehen. Text-PDFs gehen weiter.');
    expect(texte('en').chatFehler.grenze_ocr).toBe('This conversation has used up its scanned pages. PDFs with text still work.');
  });
});

/** Wie `feld`, aber mit falscher Uhr: das Warten danach über die Uhr statt über `setTimeout`. */
async function feldMitUhr(dateien: File[], h: Host, d: Record<string, unknown> = daten()) {
  const el = document.createElement('boerdi-ui-upload') as NachladeElement;
  el.host = h;
  el.daten = d;
  el.kontext = KONTEXT;
  el.beschaeftigt = false;
  document.body.appendChild(el);
  const wurzel = el.shadowRoot as ShadowRoot;
  const input = wurzel.querySelector('input[webkitdirectory]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: dateien, configurable: true });
  input.dispatchEvent(new Event('change', { bubbles: true }));
  await vi.advanceTimersByTimeAsync(0);
  return wurzel;
}
