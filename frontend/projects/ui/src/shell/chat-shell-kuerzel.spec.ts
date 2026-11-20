import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ICONS } from '../icons/icons';
import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
import { createTranslator } from '../i18n/dictionary';
import { clearAccessBlock, writeAccessBlock } from '../session/mcp-access';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Das Anmelde-Kürzel in der Fußzeile (Plan 2026-11-19, E8): ein Kreis links vom Abmelde-Knopf,
 * sobald ein Block da ist — mit den Initialen, wenn der Name bekannt ist (Anmeldung aus der
 * Sitzung der Seite), sonst mit dem Personen-Symbol. Ohne Anmeldung (Nachtrag des Nutzers) dort
 * das ausgegraute Personen-Symbol. Nicht, wo keine Anmeldung angeboten wird, nicht in der Probe.
 */

const HERKUNFT = window.location.origin;
const TAUSCH = `${HERKUNFT}/edu-sharing/services/boerdi/auth/session`;
const ICH = `${HERKUNFT}/edu-sharing/rest/iam/v1/people/-home-/-me-`;
const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';

const json = (body: unknown) => new Response(JSON.stringify(body),
  { status: 200, headers: { 'content-type': 'application/json' } });

/** Eine Seite des Repositorys, auf der Jan angemeldet ist; alles andere ist „Netz weg“. */
function seiteMitJan() {
  vi.spyOn(globalThis, 'fetch').mockImplementation((async (url: unknown) => {
    if (String(url) === ICH) return json({ person: { authorityName: 'jan' } });
    if (String(url) === TAUSCH) {
      return json({ ok: true, block: BLOCK, authority: 'jan', displayName: 'Jan Schachtschabel' });
    }
    throw new TypeError('failed to fetch');
  }) as typeof fetch);
}

function make(over: { mcpSessionUrl?: string; sizeToggleVisible?: string; en?: boolean } = {}) {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f: ComponentFixture<ChatShellComponent> = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', over.en ? createTranslator(EN, DE) : createTranslator(DE, DE));
  f.componentRef.setInput('mcpAuthBase', 'https://mcp.example.org');
  if (over.sizeToggleVisible !== undefined) {
    f.componentRef.setInput('sizeToggleVisible', over.sizeToggleVisible);
  }
  f.detectChanges();
  if (over.mcpSessionUrl) {
    f.componentRef.setInput('mcpSessionUrl', over.mcpSessionUrl);
    f.detectChanges();
  }
  return { c: f.componentInstance, f, el: f.nativeElement as HTMLElement };
}

const kuerzel = (el: HTMLElement) => el.querySelector('.konto-kuerzel') as HTMLElement | null;

beforeEach(() => { sessionStorage.clear(); clearAccessBlock(); });
afterEach(() => {
  vi.restoreAllMocks(); sessionStorage.clear(); clearAccessBlock(); TestBed.resetTestingModule();
});

describe('Anmelde-Kürzel', () => {
  it('zeigt „JS“ für Jan Schachtschabel, angemeldet aus der Sitzung der Seite', async () => {
    seiteMitJan();
    const { c, f, el } = make({ mcpSessionUrl: TAUSCH });
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    f.detectChanges();

    const k = kuerzel(el)!;
    expect(k.textContent?.trim()).toBe('JS');
    expect(k.getAttribute('role')).toBe('img');
    expect(k.getAttribute('aria-label')).toBe('Angemeldet als Jan Schachtschabel');
    expect(k.getAttribute('title')).toBe('Angemeldet als Jan Schachtschabel');
    expect(k.querySelector('svg'), 'kein Symbol, wenn Buchstaben da sind').toBeNull();
  });

  it('zeigt ohne Namen das Personen-Symbol und sagt nur „Angemeldet“', () => {
    // Anmeldung von Hand bzw. über das Ticket: der Weg nennt keinen Namen.
    writeAccessBlock(BLOCK);
    const k = kuerzel(make().el)!;
    expect(k.querySelector('svg')).not.toBeNull();
    expect(k.textContent?.trim()).toBe('');
    expect(k.getAttribute('aria-label')).toBe(DE['auth.signedIn']);
    expect(k.getAttribute('title')).toBe(DE['auth.signedIn']);
  });

  it('zeigt ohne Anmeldung das ausgegraute Personen-Symbol: „Nicht angemeldet“', () => {
    const { el } = make();
    const k = kuerzel(el)!;
    expect(k.classList).toContain('konto-kuerzel--aus');
    expect(k.querySelector('svg')).not.toBeNull();
    expect(k.textContent?.trim()).toBe('');
    expect(k.getAttribute('aria-label')).toBe(DE['auth.notSignedIn']);
    expect(k.getAttribute('title')).toBe(DE['auth.notSignedIn']);
  });

  it('angemeldet ist der Kreis nicht ausgegraut', () => {
    writeAccessBlock(BLOCK);
    expect(kuerzel(make().el)!.classList).not.toContain('konto-kuerzel--aus');
  });

  it('abgemeldet hat das Symbol eine andere Form als angemeldet ohne Namen (Review B, 4)', () => {
    // Nicht nur ein Farbton: abgemeldet der Umriss einer Person, angemeldet die gefüllte.
    const pfad = (svg: string) => svg.match(/ d="([^"]+)"/)![1];
    expect(pfad(ICONS.person_outline)).not.toBe(pfad(ICONS.person));
    const aus = kuerzel(make().el)!;
    expect(aus.innerHTML).toContain(pfad(ICONS.person_outline));
    TestBed.resetTestingModule();
    writeAccessBlock(BLOCK);
    const an = kuerzel(make().el)!;
    expect(an.innerHTML).toContain(pfad(ICONS.person));
    expect(an.innerHTML).not.toContain(pfad(ICONS.person_outline));
  });

  it('nach dem Abmelden bleibt kein Name stehen', async () => {
    seiteMitJan();
    const { c, f, el } = make({ mcpSessionUrl: TAUSCH });
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    const api = (c as unknown as { _api: { abmelden: (block: string) => Promise<boolean> } })._api;
    vi.spyOn(api, 'abmelden').mockResolvedValue(true);
    c.onAuthClick();
    f.detectChanges();

    const k = kuerzel(el)!;
    expect(k.textContent?.trim()).toBe('');
    expect(k.classList).toContain('konto-kuerzel--aus');
    expect(k.getAttribute('aria-label')).toBe(DE['auth.notSignedIn']);
  });

  it('fehlt, wenn diese Anlage keine Anmeldung anbietet', () => {
    const { f, el } = make();
    f.componentRef.setInput('mcpAuthBase', '');
    f.detectChanges();
    expect(kuerzel(el)).toBeNull();
    expect(el.querySelector('.chat-footer')!.classList).not.toContain('chat-footer--anmeldung');
  });

  it('meldet der Fußzeile, dass sie ein Element mehr trägt (Umbruch bei schmaler Breite)', () => {
    expect(make().el.querySelector('.chat-footer')!.classList).toContain('chat-footer--anmeldung');
  });

  it('fehlt in der Probe der Studio-Vorschau — angemeldet wie abgemeldet', () => {
    for (const angemeldet of [true, false]) {
      if (angemeldet) writeAccessBlock(BLOCK); else clearAccessBlock();
      const { c, f, el } = make();
      c.setProbe(true);
      f.detectChanges();
      expect(kuerzel(el), String(angemeldet)).toBeNull();
      TestBed.resetTestingModule();
    }
  });

  it('sitzt direkt links vom Abmelde-Knopf — auch rahmenlos', () => {
    writeAccessBlock(BLOCK);
    for (const sizeToggleVisible of ['true', 'false']) {
      const { el } = make({ sizeToggleVisible });
      const reihe = Array.from(el.querySelectorAll('.chat-footer > *'))
        .map((e) => e.className.split(' ')[0]);
      expect(reihe.indexOf('konto-kuerzel'), sizeToggleVisible).toBe(reihe.indexOf('btn-auth') - 1);
      TestBed.resetTestingModule();
    }
  });

  it('spricht Englisch, wenn das Widget Englisch spricht', async () => {
    seiteMitJan();
    const { c, f, el } = make({ mcpSessionUrl: TAUSCH, en: true });
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label')).toBe('Signed in as Jan Schachtschabel');
  });
});

/**
 * Paket B4 (Plan 2026-11-19): von Hand und per Ticket nennt das Backend den Namen in der Antwort
 * des Zuges (`auth_display_name`, aus `/auth/status`). Übernommen nur mit Block, nur für den
 * Block, mit dem der Zug hinausging, und nie über den Namen aus der Sitzung der Seite.
 */
describe('Anmelde-Kürzel — Name aus der Antwort des Zuges', () => {
  type Intern = {
    _onResult: (resp: Record<string, unknown>, nachricht: string) => void;
    _api: { letzterZugBlock: string | null; abmelden: (b: string) => Promise<boolean> };
  };
  const zug = (c: ChatShellComponent, name: unknown, block: string | null = BLOCK) => {
    const intern = c as unknown as Intern;
    intern._api.letzterZugBlock = block;
    intern._onResult({ session_id: 's', content: 'ok', auth_display_name: name }, 'hallo');
  };

  it('zeigt „JS“ nach einem Zug mit Namen — Anmeldung von Hand', () => {
    writeAccessBlock(BLOCK);
    const { c, f, el } = make();
    zug(c, 'Jan Schachtschabel');
    f.detectChanges();
    const k = kuerzel(el)!;
    expect(k.textContent?.trim()).toBe('JS');
    expect(k.getAttribute('aria-label')).toBe('Angemeldet als Jan Schachtschabel');
    expect(el.querySelector('.btn-auth')!.getAttribute('aria-label'))
      .toBe('Abmelden — angemeldet als Jan Schachtschabel');
  });

  it('ein späterer Zug ohne Namen lässt ihn stehen (derselbe Block)', () => {
    writeAccessBlock(BLOCK);
    const { c, f, el } = make();
    zug(c, 'Jan Schachtschabel');
    zug(c, null);
    f.detectChanges();
    expect(kuerzel(el)!.textContent?.trim()).toBe('JS');
  });

  it('übernimmt nichts ohne Block oder für einen anderen Block', () => {
    const ohne = make();
    zug(ohne.c, 'Jan Schachtschabel', null);
    ohne.f.detectChanges();
    expect(kuerzel(ohne.el)!.getAttribute('aria-label')).toBe(DE['auth.notSignedIn']);
    TestBed.resetTestingModule();

    writeAccessBlock(BLOCK);
    const anders = make();
    zug(anders.c, 'Jan Schachtschabel', 'wlo2.ein-anderer-block');
    anders.f.detectChanges();
    expect(kuerzel(anders.el)!.getAttribute('aria-label')).toBe(DE['auth.signedIn']);
  });

  it('nimmt nur Text, gekürzt auf 120 Zeichen', () => {
    writeAccessBlock(BLOCK);
    const { c, f, el } = make();
    zug(c, 42);
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label')).toBe(DE['auth.signedIn']);
    zug(c, `  ${'Ä'.repeat(200)}  `);
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label')).toBe(`Angemeldet als ${'Ä'.repeat(120)}`);
    // Review B (NIT 9): gezählt wird nach Zeichen — kein halbes Surrogatpaar am Ende
    zug(c, '\u{1D49C}'.repeat(130));
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label'))
      .toBe(`Angemeldet als ${'\u{1D49C}'.repeat(120)}`);
  });

  it('der Name aus der Sitzung der Seite geht vor', async () => {
    seiteMitJan();
    const { c, f, el } = make({ mcpSessionUrl: TAUSCH });
    await vi.waitFor(() => expect(c.authButton()).toBe('signOut'));
    zug(c, 'Ganz Anders');
    f.detectChanges();
    expect(kuerzel(el)!.textContent?.trim()).toBe('JS');
  });

  it('nach dem Abmelden ist er weg — auch nach einer neuen Anmeldung ohne Namen', async () => {
    writeAccessBlock(BLOCK);
    const { c, f, el } = make();
    vi.spyOn((c as unknown as Intern)._api, 'abmelden').mockResolvedValue(true);
    zug(c, 'Jan Schachtschabel');
    c.onAuthClick();
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label')).toBe(DE['auth.notSignedIn']);

    // Ein neuer Block (z. B. von Hand angemeldet): ohne neuen Namen das Symbol, nicht der alte.
    writeAccessBlock('wlo2.neuer-block');
    (c as unknown as { _hasAccessBlock: { set: (v: boolean) => void } })._hasAccessBlock.set(true);
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label')).toBe(DE['auth.signedIn']);
    expect(kuerzel(el)!.textContent?.trim()).toBe('');
  });

  it('wird der Block abgewiesen, ist der Name weg', () => {
    writeAccessBlock(BLOCK);
    const { c, f, el } = make();
    zug(c, 'Jan Schachtschabel');
    const intern = c as unknown as Intern;
    intern._onResult({ session_id: 's', content: 'ok', auth_invalid: true }, 'hallo');
    f.detectChanges();
    expect(kuerzel(el)!.getAttribute('aria-label')).toBe(DE['auth.notSignedIn']);
  });
});
