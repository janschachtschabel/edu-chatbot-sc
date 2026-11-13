// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { definiere } from './ui-fortschritt.element';

/**
 * Paket K1b: `<boerdi-ui-fortschritt>` — zeigt den Stand eines Ablauf-Auftrags, fragt selbst nach und
 * lässt das Ergebnis abholen. Geprüft: Darstellung je Stand, Ansage, Knöpfe, Fokus, nur lesen, Trennen.
 */
const KONTEXT: ModulKontext = { blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null };
const DATEN = { ablauf: 'lesen', kuerzel: '0123456789ab', text: 'Ich lasse das <b>Dokument</b> lesen.' };

type Host = ElementHost & { auftrag: ReturnType<typeof vi.fn> };

function host(staende: Array<Record<string, unknown> | Error> = []): Host {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), link: vi.fn(() => ({ href: '', hinweis: '' })), aktion: vi.fn(),
    beschaeftigt: vi.fn(() => false), antworten: vi.fn(), vormerken: vi.fn(), zweig: vi.fn(), hochladen: vi.fn(),
    ablegen: vi.fn(),
    auftrag: vi.fn(async (s: { schritt: string }) => {
      if (s.schritt === 'abholen' || s.schritt === 'abbrechen') return { gesendet: true };
      const a = staende.shift() ?? { stand: 'laeuft' };
      if (a instanceof Error) throw a;
      return a;
    }),
  } as never;
}

function erzeuge(h = host(), kontext: Partial<ModulKontext> = {}, daten: Record<string, unknown> = DATEN) {
  const el = document.createElement('boerdi-ui-fortschritt') as NachladeElement;
  el.host = h;
  el.daten = daten;
  el.kontext = { ...KONTEXT, ...kontext };
  el.beschaeftigt = false;
  document.body.appendChild(el);
  return { el, h, wurzel: el.shadowRoot as ShadowRoot };
}

const knopf = (w: ShadowRoot, text: string) =>
  [...w.querySelectorAll('button')].find((b) => !b.hidden && b.textContent?.trim() === text);
const stand = (w: ShadowRoot) => w.querySelector('.f__stand')?.textContent;
const ansage = (w: ShadowRoot) => w.querySelector('[aria-live]')?.textContent;
const schritte = (h: Host) => h.auftrag.mock.calls.map(([s]) => (s as { schritt: string }).schritt);

beforeEach(() => vi.useFakeTimers());
afterEach(() => { document.body.innerHTML = ''; vi.useRealTimers(); });

describe('<boerdi-ui-fortschritt> (K1b)', () => {
  it('ist definiert, Doppel-Definition wirft nicht', () => {
    expect(customElements.get('boerdi-ui-fortschritt')).toBeTruthy();
    expect(() => definiere()).not.toThrow();
  });

  it('läuft: Überschrift, Balken, „Jetzt prüfen“ — der Satz steht in der Blase darüber, nicht doppelt (Befund 7)', () => {
    const { wurzel } = erzeuge();
    expect(wurzel.querySelector('h3')?.textContent).toBe('Auftrag im Hintergrund');
    expect(wurzel.textContent).not.toContain('Dokument');
    expect(wurzel.querySelector('b')).toBeNull();
    expect((wurzel.querySelector('progress') as HTMLProgressElement).hidden).toBe(false);
    expect(stand(wurzel)).toBe('Läuft noch …');
    expect(knopf(wurzel, 'Jetzt prüfen')).toBeTruthy();
    expect(wurzel.querySelector('.f')?.getAttribute('aria-labelledby')).toBe('f-titel');
  });

  it('fertig → abgeholt, angesagt; Uhrzeit der letzten Prüfung', async () => {
    const { wurzel, h } = erzeuge(host([{ stand: 'fertig' }]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(schritte(h)).toEqual(['stand', 'abholen']);
    expect(stand(wurzel)).toBe('Erledigt – die Antwort steht im Chat.');
    expect(ansage(wurzel)).toBe('Erledigt – die Antwort steht im Chat.');
    expect(knopf(wurzel, 'Jetzt prüfen')).toBeUndefined();
    expect((wurzel.querySelector('progress') as HTMLProgressElement).hidden).toBe(true);
  });

  it('nach einer Prüfung, die noch läuft: „Zuletzt geprüft um …“', async () => {
    const { wurzel } = erzeuge();
    await vi.advanceTimersByTimeAsync(5_000);
    const zeit = wurzel.querySelector('.f__zeit') as HTMLElement;
    expect(zeit.hidden).toBe(false);
    expect(zeit.textContent).toMatch(/^Zuletzt geprüft um \d{2}:\d{2} Uhr\.$/);
  });

  it('„Jetzt prüfen“ fragt sofort; während der Frage ist er gesperrt (aria-disabled, behält den Fokus)', async () => {
    const h = host();
    let loesen: (v: unknown) => void = () => undefined;
    h.auftrag.mockImplementationOnce(() => new Promise((r) => { loesen = r as (v: unknown) => void; }));
    const { wurzel } = erzeuge(h);
    const jetzt = knopf(wurzel, 'Jetzt prüfen') as HTMLButtonElement;
    jetzt.focus();
    jetzt.click();
    expect(h.auftrag).toHaveBeenCalledTimes(1);
    expect(jetzt.getAttribute('aria-disabled')).toBe('true');
    expect(stand(wurzel)).toBe('Der Stand wird geprüft …');
    jetzt.click();
    expect(h.auftrag).toHaveBeenCalledTimes(1);
    expect(wurzel.activeElement).toBe(jetzt);
    loesen({ stand: 'laeuft' });
    await vi.advanceTimersByTimeAsync(0);
    expect(jetzt.getAttribute('aria-disabled')).toBe('false');
  });

  it('verschwindet der fokussierte Knopf, geht der Fokus auf den Rahmen — nie auf body', async () => {
    const { wurzel } = erzeuge(host([{ stand: 'fertig' }]));
    (knopf(wurzel, 'Jetzt prüfen') as HTMLButtonElement).focus();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(wurzel.activeElement).toBe(wurzel.querySelector('.f'));
  });

  it('409 (alter Block im Verlauf) → abgeschlossen, keine Knöpfe', async () => {
    const { wurzel } = erzeuge(host([Object.assign(new Error('x'), { status: 409 })]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(stand(wurzel)).toBe('Dieser Auftrag ist abgeschlossen.');
    expect([...wurzel.querySelectorAll('button')].every((b) => b.hidden)).toBe(true);
  });

  it('403 → Hinweis auf die Anmeldung', async () => {
    const { wurzel } = erzeuge(host([Object.assign(new Error('x'), { status: 403 })]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(stand(wurzel)).toBe('Den Stand sehe ich nur, solange du in WLO angemeldet bist.');
  });

  it('R1-e: 403 abgewiesen → eigener Satz, nicht „nur angemeldet“', async () => {
    const { wurzel } = erzeuge(host([Object.assign(new Error('x'), { status: 403, code: 'abgewiesen' })]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(stand(wurzel)).toBe('Den Stand dieses Auftrags darf ich mit deiner Anmeldung nicht abrufen – melde dich neu an und starte den Ablauf noch einmal.');
  });

  it('503 → Störung sichtbar, es geht weiter', async () => {
    const { wurzel, h } = erzeuge(host([Object.assign(new Error('x'), { status: 503 })]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(stand(wurzel)).toBe('Den Stand kann ich gerade nicht abrufen – ich versuche es weiter.');
    await vi.advanceTimersByTimeAsync(10_000);
    expect(h.auftrag).toHaveBeenCalledTimes(2);
    expect(stand(wurzel)).toBe('Läuft noch …');
  });

  it('während eines Zugs wartet das Abholen; danach erst neu fragen, dann abholen (Befund 1)', async () => {
    const { el, h } = erzeuge(host([{ stand: 'fertig' }, { stand: 'fertig' }]));
    el.beschaeftigt = true;
    await vi.advanceTimersByTimeAsync(5_000);
    expect(schritte(h)).toEqual(['stand']);
    el.beschaeftigt = false;
    await vi.advanceTimersByTimeAsync(0);
    expect(schritte(h)).toEqual(['stand', 'stand', 'abholen']);
  });

  it('Befund 3: eine Störung wird angesagt — auch nach „Jetzt prüfen“ im Handbetrieb', async () => {
    const { wurzel } = erzeuge(host([Object.assign(new Error('x'), { status: 503 })]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(ansage(wurzel)).toBe('Den Stand kann ich gerade nicht abrufen – ich versuche es weiter.');
    await vi.advanceTimersByTimeAsync(31 * 60_000);
    expect(stand(wurzel)).toBe('Ich frage nicht mehr von selbst nach. Mit „Jetzt prüfen“ siehst du den Stand.');
  });

  it('Befund 3: scheitert „Jetzt prüfen“ im Handbetrieb, steht und klingt es', async () => {
    const h = host();
    const { wurzel } = erzeuge(h);
    await vi.advanceTimersByTimeAsync(31 * 60_000);
    h.auftrag.mockImplementationOnce(async () => { throw Object.assign(new Error('x'), { status: 503 }); });
    (knopf(wurzel, 'Jetzt prüfen') as HTMLButtonElement).click();
    await vi.advanceTimersByTimeAsync(0);
    const satz = 'Den Stand kann ich gerade nicht abrufen – versuch es gleich noch einmal mit „Jetzt prüfen“.';
    expect(stand(wurzel)).toBe(satz);
    expect(ansage(wurzel)).toBe(satz);
  });

  it('nicht gesendet → „Ergebnis abholen“; ein Klick versucht es erneut', async () => {
    const h = host([{ stand: 'fehler' }]);
    h.auftrag.mockImplementation(async (s: { schritt: string }) =>
      (s.schritt === 'abholen' ? { gesendet: false } : { stand: 'fehler' }));
    const { wurzel } = erzeuge(h);
    await vi.advanceTimersByTimeAsync(5_000);
    expect(stand(wurzel)).toBe('Der Auftrag ist nicht gelungen – gleich steht im Chat, wie es weitergeht.');
    const abholen = knopf(wurzel, 'Ergebnis abholen') as HTMLButtonElement;
    expect(abholen).toBeTruthy();
    h.auftrag.mockImplementation(async (s: { schritt: string }) =>
      (s.schritt === 'abholen' ? { gesendet: true } : { stand: 'fehler' }));
    abholen.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(stand(wurzel)).toBe('Erledigt – die Antwort steht im Chat.');
  });

  it('nur lesen: kein Nachfragen, kein Knopf', async () => {
    const { wurzel, h } = erzeuge(host(), { nurLesen: true });
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(h.auftrag).not.toHaveBeenCalled();
    expect(stand(wurzel)).toBe('Dieser Auftrag wird hier nicht mehr verfolgt.');
    expect([...wurzel.querySelectorAll('button')].every((b) => b.hidden)).toBe(true);
  });

  it('entfernt: keine Frage mehr', async () => {
    const { el, h } = erzeuge();
    el.remove();
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(h.auftrag).not.toHaveBeenCalled();
  });

  it('englisch', () => {
    const { wurzel } = erzeuge(host(), { sprache: 'en' });
    expect(wurzel.querySelector('h3')?.textContent).toBe('Job in the background');
    expect(knopf(wurzel, 'Check now')).toBeTruthy();
  });

  it('ohne gültige Daten: abgeschlossen, keine Frage', async () => {
    const { wurzel, h } = erzeuge(host(), {}, { ablauf: 'lesen', kuerzel: 'job-1', text: 'x' });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(h.auftrag).not.toHaveBeenCalled();
    expect(stand(wurzel)).toBe('Dieser Auftrag ist abgeschlossen.');
  });

  it('K2b: „Auftrag abbrechen“ schickt den Abbruch (das Backend fragt nach) und fragt weiter', async () => {
    const { h, wurzel } = erzeuge();
    knopf(wurzel, 'Auftrag abbrechen')?.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(h.auftrag).toHaveBeenCalledWith({ schritt: 'abbrechen', ablauf: 'lesen' });
    await vi.advanceTimersByTimeAsync(5_000);
    expect(schritte(h)).toEqual(['abbrechen', 'stand']);
  });

  it('K2b: kein Abbruch im Verlauf (nur lesen), während eines Zugs und nach dem Ende', async () => {
    expect(knopf(erzeuge(host(), { nurLesen: true }).wurzel, 'Auftrag abbrechen')).toBeUndefined();
    const beschaeftigt = erzeuge();
    beschaeftigt.el.beschaeftigt = true;
    expect(knopf(beschaeftigt.wurzel, 'Auftrag abbrechen')).toBeUndefined();
    const ende = erzeuge(host([Object.assign(new Error('x'), { status: 409 })]));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(knopf(ende.wurzel, 'Auftrag abbrechen')).toBeUndefined();
  });
});
