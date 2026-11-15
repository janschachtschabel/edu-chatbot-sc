import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AUTH_QR_MARKER } from '../chips/auth-qr';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import {
  MCP_ACCESS_STORAGE_KEY, clearAccessBlock, isSignedOut, readAccessBlock, writeAccessBlock,
} from '../session/mcp-access';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Anmeldung aus der Sitzung der Seite (Plan 2026-11-15). Gepinnt wird, was still schiefgehen
 * kann: dass das Widget auf einer fremden Seite Anfragen stellt, dass es einen Gast tauscht,
 * dass der Block im Web-Speicher landet, dass ein Abmelden beim nächsten Laden vergessen ist —
 * und dass nach einem Abmelden kein Knopf mehr zurückführt.
 */

const HERKUNFT = window.location.origin;
const TAUSCH = `${HERKUNFT}/edu-sharing/services/wlo-mcp/auth/session`;
const ICH = `${HERKUNFT}/edu-sharing/rest/iam/v1/people/-home-/-me-`;
const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';
const BASIS = 'https://mcp.example.org';

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body),
  { status, headers: { 'content-type': 'application/json' } });

/** Das Repository und die Tauschstelle der Seite; alles andere ist „Netz weg“. */
function seite(person: string, tausch: () => Response = () =>
  json({ ok: true, block: BLOCK, authority: person, displayName: 'Lea Lehrerin' })) {
  const rufe: string[] = [];
  vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: unknown) => {
    rufe.push(String(url));
    if (String(url) === ICH) return json({ person: { authorityName: person } });
    if (String(url) === TAUSCH) return tausch();
    throw new TypeError('failed to fetch');
  }) as typeof fetch);
  return { rufe, anTausch: () => rufe.filter((u) => u === TAUSCH).length };
}

function make(over: { mcpSessionUrl?: string; mcpAuthBase?: string; ticket?: string } = {}) {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f: ComponentFixture<ChatShellComponent> = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('mcpAuthBase', over.mcpAuthBase ?? '');
  if (over.ticket) f.componentRef.setInput('ticket', over.ticket);
  // Wie im Betrieb: die Adresse kommt erst mit dem Config-Bündel.
  f.detectChanges();
  f.componentRef.setInput('mcpSessionUrl', over.mcpSessionUrl ?? TAUSCH);
  f.detectChanges();
  return { c: f.componentInstance, f, el: f.nativeElement as HTMLElement };
}

const knopf = (el: HTMLElement) => el.querySelector('.btn-auth') as HTMLButtonElement | null;
const texte = (c: ChatShellComponent) => c.messages().map((m) => m.content);
/** Nur die Sätze zur Anmeldung — die Shell begrüßt beim Start auch. */
const ANMELDE_SAETZE = Object.entries(DE).filter(([k]) => k.startsWith('auth.')).map(([, v]) => v);
const anmeldeSaetze = (c: ChatShellComponent) => texte(c).filter((t) => ANMELDE_SAETZE.includes(t));
/** Was ans Repository der Seite ging — die Shell fragt beim Start auch ihr eigenes Backend. */
const anRepository = (rufe: string[]) => rufe.filter((u) => u.includes('/edu-sharing/'));
const anmeldeWarnungen = (warn: { mock: { calls: unknown[][] } }) =>
  warn.mock.calls.filter(([erste]) => String(erste).startsWith('WLO-Anmeldung'));
/** Mehrere Makrotasks: eine „geschieht nicht“-Aussage soll nicht an einem einzelnen hängen. */
const ruhe = async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0)); };
/** Die Wache vor einem Abruf, wie `ChatApiClient` sie ruft — einige Sekunden nach dem letzten
 *  Tausch (eine frische Antwort der Seite fragt sie nicht noch einmal ab). */
const zugWache = (c: ChatShellComponent) => {
  const spaeter = Date.now() + 10_000;
  vi.spyOn(Date, 'now').mockReturnValue(spaeter);
  return (c as unknown as { _api: { zugWache: (() => Promise<void>) | null } })._api.zugWache!();
};

function widerruf(c: ChatShellComponent, ergebnis: boolean) {
  const api = (c as unknown as { _api: { abmelden: (block: string) => Promise<boolean> } })._api;
  return vi.spyOn(api, 'abmelden').mockResolvedValue(ergebnis);
}

beforeEach(() => { sessionStorage.clear(); clearAccessBlock(); });
afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); clearAccessBlock(); TestBed.resetTestingModule(); });

describe('Anmeldung aus der Sitzung der Seite — von selbst', () => {
  it('übernimmt die angemeldete Person, hält den Block nur im Arbeitsspeicher und nennt sie am Knopf', async () => {
    const netz = seite('lehrerin');
    const { c, f, el } = make();

    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    f.detectChanges();

    expect(readAccessBlock()).toBe(BLOCK);
    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY), 'nicht im Web-Speicher').toBeNull();
    expect(knopf(el)!.getAttribute('aria-label')).toBe('Abmelden — angemeldet als Lea Lehrerin');
    expect(anmeldeSaetze(c), 'still: kein Satz im Chat').toEqual([]);

    // Weitere Signal-Läufe stoßen keinen zweiten Tausch an.
    f.detectChanges();
    expect(netz.anTausch()).toBe(1);
  });

  it('tauscht einen Gast nicht, bietet aber „Anmelden“ an — ohne Warnung', async () => {
    const netz = seite('esguest');
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { c, f, el } = make();

    await vi.waitFor(() => expect(netz.rufe).toContain(ICH));
    await ruhe();
    f.detectChanges();

    expect(netz.anTausch()).toBe(0);
    expect(c.authButton()).toBe('signIn');
    expect(knopf(el), 'auch ohne Anmelde-Adresse').not.toBeNull();
    expect(anmeldeWarnungen(warn)).toEqual([]);
  });

  it('stellt auf einer fremden Seite keine Anfrage', async () => {
    const netz = seite('lehrerin');
    const { c } = make({ mcpSessionUrl: 'https://repository.example.org/edu-sharing/services/wlo-mcp/auth/session' });
    await ruhe();
    expect(anRepository(netz.rufe)).toEqual([]);
    expect(c.authButton()).toBe('hidden');
  });

  it('ein Ticket der Seite geht vor', async () => {
    const netz = seite('lehrerin');
    make({ ticket: 'TICKET_c001d00dfeedface0123456789abcdef01234567', mcpAuthBase: BASIS });
    await vi.waitFor(() => expect(netz.rufe).toContain(`${BASIS}/auth/ticket`));
    expect(netz.rufe).not.toContain(ICH);
    expect(netz.anTausch()).toBe(0);
  });

  it('warnt die Betreiberseite, wenn der Weg eingestellt ist, aber nicht trägt', async () => {
    seite('lehrerin', () => json({ error: 'aus' }, 404));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { c } = make();
    await vi.waitFor(() => expect(warn).toHaveBeenCalledWith(
      'WLO-Anmeldung über die Sitzung der Seite nicht gelungen:', 'unavailable'));
    expect(c.authButton()).toBe('signIn');
  });

  it('ersetzt einen mitgebrachten Block — die Seite benennt, wer hier ist', async () => {
    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');
    seite('lehrerin');
    make();
    await vi.waitFor(() => expect(readAccessBlock()).toBe(BLOCK));
    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY)).toBeNull();
  });
});

describe('Anmeldung aus der Sitzung der Seite — Abmelden und wieder anmelden', () => {
  it('Abmelden widerruft, sagt, dass WLO angemeldet bleibt, und gilt über das Neuladen hinaus', async () => {
    const netz = seite('lehrerin');
    const erste = make();
    await vi.waitFor(() => expect(erste.c.authButton()).toBe('signOut'));
    const abmelden = widerruf(erste.c, true);

    erste.c.onAuthClick();
    expect(readAccessBlock()).toBeNull();
    await vi.waitFor(() => expect(texte(erste.c)).toContain(DE['auth.signedOutSession']));
    expect(abmelden).toHaveBeenCalledWith(BLOCK);
    expect(isSignedOut()).toBe(true);
    expect(erste.c.authButton(), 'der Knopf führt zurück').toBe('signIn');

    // Neu geladen: derselbe Tab, die Sitzung der Seite lebt noch — aber kein Tausch von selbst.
    erste.f.destroy();
    TestBed.resetTestingModule();
    const zweite = make();
    await ruhe();
    expect(netz.anTausch()).toBe(1);
    expect(zweite.c.authButton()).toBe('signIn');

    // Der Klick auf „Anmelden“ nimmt wieder die Sitzung.
    zweite.c.onAuthClick();
    await vi.waitFor(() => expect(zweite.c.authButton()).toBe('signOut'));
    expect(netz.anTausch()).toBe(2);
    expect(isSignedOut()).toBe(false);
  });

  it('„Anmelden“ ohne Sitzung sagt es und bietet die Anmeldung von Hand an', async () => {
    seite('esguest');
    const { c } = make({ mcpAuthBase: BASIS });
    const start = vi.spyOn(c as unknown as { startSignIn: () => Promise<void> }, 'startSignIn')
      .mockResolvedValue(undefined);

    c.onAuthClick();
    await vi.waitFor(() => expect(texte(c)).toContain(DE['auth.sessionNone']));

    expect(start, 'kein Anmeldefenster ohne Nutzergeste').not.toHaveBeenCalled();
    const satz = c.messages().find((m) => m.content === DE['auth.sessionNone'])!;
    expect(satz.quickReplies).toEqual([AUTH_QR_MARKER]);
  });

  it('„Anmelden“ bei einer Störung sagt nicht „niemand angemeldet“, und ohne Hand-Anmeldung fehlt der Chip', async () => {
    seite('lehrerin', () => json({ code: 'upstream_error' }, 500));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { c } = make();
    await ruhe();

    c.onAuthClick();
    await vi.waitFor(() => expect(texte(c)).toContain(DE['auth.sessionFailed']));
    const satz = c.messages().find((m) => m.content === DE['auth.sessionFailed'])!;
    expect(satz.quickReplies ?? []).toEqual([]);
  });
});

describe('Anmeldung aus der Sitzung der Seite — Ablauf und Abweisung', () => {
  it('tauscht nach einer Abweisung still neu — einmal', async () => {
    const netz = seite('lehrerin');
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    const abgewiesen = () => (c as unknown as { _anmeldungAbgewiesen: () => void })._anmeldungAbgewiesen();

    abgewiesen();
    await vi.waitFor(() => expect(netz.anTausch()).toBe(2));
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    expect(anmeldeSaetze(c), 'der neue Tausch gelang: kein Satz').toEqual([]);

    // Wird auch der neue Block abgewiesen, läuft es nicht im Kreis.
    abgewiesen();
    await ruhe();
    expect(netz.anTausch()).toBe(2);
    expect(texte(c)).toContain(DE['auth.expired']);
    expect(c.authButton()).toBe('signIn');
  });

  it('endet die Sitzung der Seite, geht es ohne Anmeldung weiter — mit einem Satz', async () => {
    let person = 'lehrerin';
    const rufe: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: unknown) => {
      rufe.push(String(url));
      if (String(url) === ICH) return json({ person: { authorityName: person } });
      if (String(url) === TAUSCH) return json({ ok: true, block: BLOCK, authority: person });
      throw new TypeError('failed to fetch');
    }) as typeof fetch);
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));

    person = 'esguest';   // im Repository abgemeldet
    (c as unknown as { _anmeldungAbgewiesen: () => void })._anmeldungAbgewiesen();

    await vi.waitFor(() => expect(texte(c)).toContain(DE['auth.expired']));
    expect(readAccessBlock()).toBeNull();
    expect(c.authButton()).toBe('signIn');
  });
});

describe('Anmeldung aus der Sitzung der Seite — Rennen und Herkunft des Blocks', () => {
  /** Ein Tausch, der erst antwortet, wenn der Test es sagt. */
  function haltenderTausch(person = 'lehrerin') {
    let antworten!: () => void;
    const rufe: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation(((url: unknown) => {
      rufe.push(String(url));
      if (String(url) === ICH) return Promise.resolve(json({ person: { authorityName: person } }));
      if (String(url) === TAUSCH) {
        return new Promise<Response>((resolve) => {
          antworten = () => resolve(json({ ok: true, block: BLOCK, authority: person }));
        });
      }
      return Promise.reject(new TypeError('failed to fetch'));
    }) as typeof fetch);
    return { rufe, antworten: () => antworten(), bereit: () => typeof antworten === 'function' };
  }

  it('wer während des Tauschs abmeldet, bleibt abgemeldet — und der frische Block wird widerrufen', async () => {
    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');   // eine Anmeldung von Hand, noch im Tab
    const netz = haltenderTausch();
    const { c } = make();
    const abmelden = widerruf(c, true);
    await vi.waitFor(() => expect(netz.bereit()).toBe(true));

    c.onAuthClick();   // „Abmelden“, während der Tausch läuft
    expect(abmelden).toHaveBeenCalledWith('wlo2.YWx0.aXY.Y3Q');
    netz.antworten();
    await vi.waitFor(() => expect(abmelden).toHaveBeenCalledWith(BLOCK));

    expect(readAccessBlock()).toBeNull();
    expect(c.authButton()).toBe('signIn');
  });

  it('ein Klick auf „Anmelden“ während des stillen Tauschs hängt sich an ihn', async () => {
    const netz = haltenderTausch();
    const { c } = make();
    await vi.waitFor(() => expect(netz.bereit()).toBe(true));

    c.onAuthClick();
    await ruhe();
    netz.antworten();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    expect(netz.rufe.filter((u) => u === TAUSCH), 'ein Tausch, nicht zwei').toHaveLength(1);
  });

  it('eine Anmeldung von Hand auf derselben Seite bekommt den Hinweis vor dem Ablauf', async () => {
    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');
    seite('esguest');
    const { c } = make({ mcpAuthBase: BASIS });
    await ruhe();
    const frist = (c as unknown as { _frist: { planen: (iso: string) => void } })._frist;

    frist.planen(new Date(Date.now() + 5 * 60_000).toISOString());   // läuft in fünf Minuten ab
    await vi.waitFor(() => expect(texte(c)).toContain(DE['auth.expiresSoon']));
  });

  it('ein Block aus der Sitzung bekommt den Hinweis nicht — er wird still erneuert', async () => {
    seite('lehrerin');
    const { c } = make({ mcpAuthBase: BASIS });
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    const frist = (c as unknown as { _frist: { planen: (iso: string) => void; vergessen: () => void } })._frist;

    frist.planen(new Date(Date.now() + 5 * 60_000).toISOString());
    await ruhe();
    expect(texte(c)).not.toContain(DE['auth.expiresSoon']);
    frist.vergessen();
  });

  it('bricht die Person das Anmeldefenster ab, behält der Knopf den Namen', async () => {
    seite('lehrerin');
    const { c, f, el } = make({ mcpAuthBase: BASIS });
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    vi.spyOn(c as unknown as { startSignIn: () => Promise<void> }, 'startSignIn').mockResolvedValue(undefined);

    (c as unknown as { _signInAndRefresh: () => void })._signInAndRefresh();   // alter `__auth__`-Chip
    await ruhe();
    f.detectChanges();
    expect(knopf(el)!.getAttribute('aria-label')).toBe('Abmelden — angemeldet als Lea Lehrerin');
  });
});

describe('Anmeldung aus der Sitzung der Seite — Wache vor jedem Zug (SA-13)', () => {
  /** Eine Seite, deren angemeldete Person der Test wechseln kann. */
  function wechselSeite(start: string) {
    const stand = { person: start as string | null };
    const rufe: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: unknown) => {
      rufe.push(String(url));
      if (stand.person === null) throw new TypeError('failed to fetch');
      if (String(url) === ICH) return json({ person: { authorityName: stand.person } });
      if (String(url) === TAUSCH) {
        return json({ ok: true, block: stand.person === 'lehrerin' ? BLOCK : 'wlo2.bmV1.aXY.Y3Q',
          authority: stand.person, displayName: stand.person === 'lehrerin' ? 'Lea Lehrerin' : 'Ben Redakteur' });
      }
      throw new TypeError('failed to fetch');
    }) as typeof fetch);
    return { stand, anTausch: () => rufe.filter((u) => u === TAUSCH).length,
      anIch: () => rufe.filter((u) => u === ICH).length };
  }

  it('dieselbe Person: der Block bleibt, es wird nicht neu getauscht', async () => {
    const netz = wechselSeite('lehrerin');
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));

    await zugWache(c);
    expect(readAccessBlock()).toBe(BLOCK);
    expect(netz.anTausch()).toBe(1);
    expect(netz.anIch(), 'einmal beim Tausch, einmal vor dem Zug').toBe(2);
  });

  it('eine andere Person auf derselben Seite: neu tauschen, der Knopf nennt sie', async () => {
    const netz = wechselSeite('lehrerin');
    const { c, f, el } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));

    netz.stand.person = 'redakteur';   // ohne Neuladen umgemeldet
    await zugWache(c);
    f.detectChanges();

    expect(readAccessBlock(), 'der Zug geht mit dem Block der neuen Person').toBe('wlo2.bmV1.aXY.Y3Q');
    expect(knopf(el)!.getAttribute('aria-label')).toBe('Abmelden — angemeldet als Ben Redakteur');
    expect(anmeldeSaetze(c)).toEqual([]);
  });

  it('abgemeldet im Repository: der Block fällt vor dem Zug weg, mit einem Satz', async () => {
    const netz = wechselSeite('lehrerin');
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));

    netz.stand.person = 'esguest';
    await zugWache(c);

    expect(readAccessBlock()).toBeNull();
    expect(c.authButton()).toBe('signIn');
    expect(texte(c)).toContain(DE['auth.expired']);
    expect(netz.anTausch(), 'für einen Gast kein Tausch').toBe(1);
  });

  it('antwortet das Repository nicht, ist das kein Urteil: der Block bleibt', async () => {
    const netz = wechselSeite('lehrerin');
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));

    netz.stand.person = null;   // Netz weg
    await zugWache(c);
    expect(readAccessBlock()).toBe(BLOCK);
    expect(anmeldeSaetze(c)).toEqual([]);
  });

  it('eine Anmeldung von Hand ist nicht ihr Fall', async () => {
    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');   // von Hand angemeldet, die Seite zeigt einen Gast
    const netz = wechselSeite('esguest');
    const { c } = make({ mcpAuthBase: BASIS });
    await ruhe();
    const vorher = netz.anIch();

    netz.stand.person = 'lehrerin';
    await zugWache(c);
    expect(netz.anIch()).toBe(vorher);
    expect(readAccessBlock()).toBe('wlo2.YWx0.aXY.Y3Q');
  });

  it('wer sich nach dem Laden im Repository anmeldet, ist beim nächsten Zug auch im Chat angemeldet', async () => {
    const netz = wechselSeite('esguest');
    const { c, f, el } = make();
    await vi.waitFor(() => expect(netz.anIch()).toBe(1));
    await ruhe();
    expect(c.authButton()).toBe('signIn');

    netz.stand.person = 'lehrerin';   // Anmeldung im Repository, ohne Neuladen
    await zugWache(c);
    f.detectChanges();

    expect(readAccessBlock()).toBe(BLOCK);
    expect(knopf(el)!.getAttribute('aria-label')).toBe('Abmelden — angemeldet als Lea Lehrerin');
  });

  it('ein Gast kostet je Zug eine Frage, aber keinen Tausch', async () => {
    const netz = wechselSeite('esguest');
    const { c } = make();
    await vi.waitFor(() => expect(netz.anIch()).toBe(1));
    await ruhe();

    await zugWache(c);
    expect(netz.anIch()).toBe(2);
    expect(netz.anTausch()).toBe(0);
    expect(anmeldeSaetze(c)).toEqual([]);
  });

  it('nach „Abmelden“ im Chat tut sie nichts — bis „Anmelden“ es aufhebt', async () => {
    const netz = wechselSeite('lehrerin');
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    widerruf(c, true);
    c.onAuthClick();   // Abmelden
    await ruhe();
    const vorher = { ich: netz.anIch(), tausch: netz.anTausch() };

    await zugWache(c);
    expect(netz.anIch()).toBe(vorher.ich);
    expect(netz.anTausch()).toBe(vorher.tausch);
    expect(readAccessBlock()).toBeNull();
  });

  it('eine neu gebaute Instanz erbt den Block aus der Sitzung nicht — sie tauscht neu', async () => {
    // Review 2026-11-15: bis das Config-Bündel den Weg nennt, hängt die Wache an keinem Abruf;
    // ein geerbter Block ginge so lange ungeprüft hinaus, auch wenn die Seite inzwischen jemand
    // anderen zeigt.
    const netz = wechselSeite('lehrerin');
    const erste = make();
    await vi.waitFor(() => expect(erste.c.authButton()).toBe('signOut'));
    erste.f.destroy();
    TestBed.resetTestingModule();
    expect(readAccessBlock(), 'der Block liegt noch im Arbeitsspeicher des Moduls').toBe(BLOCK);

    // Die Gastseite baut `<boerdi-chat>` neu; das Config-Bündel ist noch nicht da.
    TestBed.configureTestingModule({ imports: [ChatShellComponent], providers: [provideZonelessChangeDetection()] });
    const f = TestBed.createComponent(ChatShellComponent);
    f.componentRef.setInput('translate', createTranslator(DE, DE));
    f.detectChanges();
    expect(readAccessBlock(), 'schon vor dem Config-Bündel weg').toBeNull();
    expect(f.componentInstance.authButton()).toBe('hidden');

    // Mit dem Bündel tauscht sie selbst — für die Person, die die Seite JETZT zeigt.
    netz.stand.person = 'redakteur';
    f.componentRef.setInput('mcpSessionUrl', TAUSCH);
    f.detectChanges();
    await vi.waitFor(() => expect(readAccessBlock()).toBe('wlo2.bmV1.aXY.Y3Q'));
  });

  it('ein Block von Hand überlebt den Neubau der Instanz', async () => {
    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');
    wechselSeite('esguest');
    const { c } = make({ mcpAuthBase: BASIS });
    await ruhe();
    expect(readAccessBlock()).toBe('wlo2.YWx0.aXY.Y3Q');
    expect(c.authButton()).toBe('signOut');
  });

  it('ein Abruf während des Tauschs wartet auf ihn, statt die Seite ein zweites Mal zu fragen', async () => {
    let antworten!: () => void;
    const rufe: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation(((url: unknown) => {
      rufe.push(String(url));
      if (String(url) === ICH) return Promise.resolve(json({ person: { authorityName: 'lehrerin' } }));
      if (String(url) === TAUSCH) {
        return new Promise<Response>((resolve) => {
          antworten = () => resolve(json({ ok: true, block: BLOCK, authority: 'lehrerin' }));
        });
      }
      return Promise.reject(new TypeError('failed to fetch'));
    }) as typeof fetch);
    const { c } = make();
    await vi.waitFor(() => expect(antworten).toBeTypeOf('function'));

    let fertig = false;
    void (c as unknown as { _api: { zugWache: () => Promise<void> } })._api.zugWache().then(() => { fertig = true; });
    await ruhe();
    expect(fertig, 'der Abruf wartet auf den laufenden Tausch').toBe(false);
    expect(rufe.filter((u) => u === ICH), 'keine zweite Frage').toHaveLength(1);

    antworten();
    await vi.waitFor(() => expect(fertig).toBe(true));
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('scheitert der Tausch beim Laden an der Einrichtung, versucht es kein Abruf von selbst wieder', async () => {
    // Review 2026-11-15: sonst kostete ein nicht eingehängter Pfad bei jedem Zug drei Abrufe,
    // und hinter einem gemeinsamen Anschluss das Anmelde-Budget der Adresse am MCP-Server.
    const rufe: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: unknown) => {
      rufe.push(String(url));
      if (String(url) === ICH) return json({ person: { authorityName: 'lehrerin' } });
      if (String(url) === TAUSCH) return json({ error: 'aus' }, 404);
      throw new TypeError('failed to fetch');
    }) as typeof fetch);
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { c } = make();
    await vi.waitFor(() => expect(rufe.filter((u) => u === TAUSCH)).toHaveLength(1));
    await ruhe();

    await zugWache(c);
    await zugWache(c);
    expect(rufe.filter((u) => u === TAUSCH), 'kein weiterer Tausch').toHaveLength(1);

    // Der Klick auf „Anmelden“ versucht es trotzdem.
    c.onAuthClick();
    await vi.waitFor(() => expect(rufe.filter((u) => u === TAUSCH)).toHaveLength(2));
  });

  it('eine Abweisung des Servers trifft nur den Block, mit dem der Zug hinausging', async () => {
    const netz = wechselSeite('lehrerin');
    const { c } = make();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    const api = (c as unknown as { _api: { letzterZugBlock: string | null } })._api;
    const abgewiesen = () => (c as unknown as { _zugAbgewiesen: () => void })._zugAbgewiesen();

    // Der Zug ging mit Leas Block hinaus; inzwischen hat die Wache für Ben getauscht.
    api.letzterZugBlock = BLOCK;
    netz.stand.person = 'redakteur';
    await zugWache(c);
    expect(readAccessBlock()).toBe('wlo2.bmV1.aXY.Y3Q');
    abgewiesen();
    expect(readAccessBlock(), 'Bens gültiger Block bleibt').toBe('wlo2.bmV1.aXY.Y3Q');

    // Kein Block mehr da (die Wache hat ihn verworfen und es gesagt): kein zweiter Satz.
    netz.stand.person = 'esguest';
    await zugWache(c);
    const saetze = anmeldeSaetze(c).length;
    abgewiesen();
    await ruhe();
    expect(anmeldeSaetze(c).length).toBe(saetze);

    // Der Regelfall bleibt: derselbe Block, abgewiesen → weg.
    netz.stand.person = 'lehrerin';
    c.onAuthClick();
    await vi.waitFor(() => expect(readAccessBlock()).toBe(BLOCK));
    api.letzterZugBlock = BLOCK;
    abgewiesen();
    await vi.waitFor(() => expect(netz.anTausch(), 'still neu getauscht').toBe(4));
  });

  it('ist für beide Wege angemeldet — auch aus dem Klick auf „Anmelden“', async () => {
    // Abgemeldet geladen: der stille Tausch läuft nicht, die Wache hängt trotzdem am Abruf.
    sessionStorage.setItem('boerdi.mcp-signed-out', '1');
    wechselSeite('lehrerin');
    const { c } = make();
    await ruhe();
    const api = (c as unknown as { _api: { zugWache: unknown } })._api;
    expect(api.zugWache).toBeTypeOf('function');

    c.onAuthClick();
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
  });
});
