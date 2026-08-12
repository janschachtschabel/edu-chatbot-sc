import { describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
import { createTranslator } from '../i18n/dictionary';
import type { SignInResult } from './mcp-oauth';
import { OAUTH_CALLBACK_PATH, callbackUrl, runSignIn, signInMessageKey } from './sign-in-flow';

const t = createTranslator(DE, DE);

function ctx(over: Partial<Parameters<typeof runSignIn>[0]> = {}) {
  const gesagt: string[] = [];
  const basis = {
    mcpAuthBase: () => 'https://mcp.example.org',
    apiUrl: () => '',
    origin: () => 'https://gastgeber.example',
    say: (s: string) => { gesagt.push(s); },
    translate: t,
    signInImpl: async (): Promise<SignInResult> => ({ ok: true }),
    ...over,
  };
  return { ctx: basis, gesagt };
}

describe('Ausgang → Satz', () => {
  it.each([
    [{ ok: true } as SignInResult, 'auth.done'],
    [{ ok: false, reason: 'denied' } as SignInResult, 'auth.denied'],
    [{ ok: false, reason: 'popup-blocked' } as SignInResult, 'auth.popupBlocked'],
    [{ ok: false, reason: 'unavailable' } as SignInResult, 'auth.unavailable'],
    [{ ok: false, reason: 'timeout' } as SignInResult, 'auth.timeout'],
    [{ ok: false, reason: 'exchange-failed' } as SignInResult, 'auth.failed'],
  ])('%o → %s', (ergebnis, schluessel) => {
    expect(signInMessageKey(ergebnis)).toBe(schluessel);
  });

  it('jeder Schlüssel steht in BEIDEN Katalogen', () => {
    // Ein fehlender Schlüssel käme als Schlüsselname in die Blase — sichtbar,
    // aber sinnlos. Der Rückfall des Wörterbuchs verdeckt hier nichts.
    const alle = ['auth.done', 'auth.denied', 'auth.popupBlocked',
                  'auth.unavailable', 'auth.timeout', 'auth.failed', 'auth.signIn'];
    for (const k of alle) {
      expect(DE[k], `DE fehlt ${k}`).toBeTruthy();
      expect(EN[k], `EN fehlt ${k}`).toBeTruthy();
    }
  });
});

describe('Rückkehr-Adresse', () => {
  it('nimmt die Backend-Adresse, wenn es eine gibt', () => {
    expect(callbackUrl('https://api.example/', 'https://gastgeber.example'))
      .toBe(`https://api.example${OAUTH_CALLBACK_PATH}`);
  });

  it('fällt auf die eigene Herkunft zurück', () => {
    expect(callbackUrl('', 'https://gastgeber.example'))
      .toBe(`https://gastgeber.example${OAUTH_CALLBACK_PATH}`);
  });

  it('hängt keinen doppelten Schrägstrich an', () => {
    expect(callbackUrl('https://api.example///', '')).not.toContain('//widget');
  });
});

describe('Vorgang', () => {
  it('ohne Server-Adresse öffnet er kein Fenster', async () => {
    const vorgang = vi.fn();
    const { ctx: c, gesagt } = ctx({ mcpAuthBase: () => '', signInImpl: vorgang });
    await runSignIn(c);
    expect(vorgang).not.toHaveBeenCalled();
    expect(gesagt).toEqual([DE['auth.unavailable']]);
  });

  it('reicht Herkunft und Rückkehr-Adresse durch', async () => {
    const vorgang = vi.fn(async (): Promise<SignInResult> => ({ ok: true }));
    const { ctx: c } = ctx({ signInImpl: vorgang });
    await runSignIn(c);
    expect(vorgang).toHaveBeenCalledWith(
      'https://mcp.example.org',
      `https://gastgeber.example${OAUTH_CALLBACK_PATH}`,
    );
  });

  it('sagt den Erfolg an', async () => {
    const { ctx: c, gesagt } = ctx();
    await runSignIn(c);
    expect(gesagt).toEqual([DE['auth.done']]);
  });

  it('sagt eine Ablehnung als Entscheidung an, nicht als Panne', async () => {
    const { ctx: c, gesagt } = ctx({
      signInImpl: async (): Promise<SignInResult> => ({ ok: false, reason: 'denied' }),
    });
    await runSignIn(c);
    expect(gesagt).toEqual([DE['auth.denied']]);
    expect(gesagt[0]).not.toBe(DE['auth.failed']);
  });

  it('ein geworfener Fehler wird zum Satz, nicht zur stillen Zusage', async () => {
    // Echter Fall: `crypto.subtle` fehlt auf unsicherer Herkunft (http://) und
    // wirft. Ohne Auffangen sähe die Person gar nichts — der Chip täte
    // scheinbar nichts, der Fehler landete nur in der Konsole.
    const { ctx: c, gesagt } = ctx({
      signInImpl: async () => { throw new Error('crypto.subtle fehlt'); },
    });
    await expect(runSignIn(c)).resolves.toBeUndefined();
    expect(gesagt).toEqual([DE['auth.failed']]);
  });

  it('spricht die eingestellte Sprache', async () => {
    const { ctx: c, gesagt } = ctx({ translate: createTranslator(EN, DE) });
    await runSignIn(c);
    expect(gesagt).toEqual([EN['auth.done']]);
  });
});
