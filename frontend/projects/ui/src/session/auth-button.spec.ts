import { describe, expect, it } from 'vitest';

import { authButtonState } from './auth-button';

const BASIS = 'https://mcp.example.org';

describe('authButtonState', () => {
  it('bietet die Anmeldung an, wenn eine Adresse da ist und niemand angemeldet', () => {
    expect(authButtonState(BASIS, false)).toBe('signIn');
  });

  it('bietet das Abmelden an, sobald ein Zugangsblock im Speicher liegt', () => {
    expect(authButtonState(BASIS, true)).toBe('signOut');
  });

  it('verschwindet, wenn diese Anlage keine Anmeldung anbietet', () => {
    // Ein Knopf, der nur scheitern kann, ist schlechter als keiner.
    expect(authButtonState('', false)).toBe('hidden');
  });

  it('wertet eine Adresse aus Leerzeichen wie „nicht gesetzt"', () => {
    // Spiegelbildlich zu `runSignIn`, das die Basis ebenfalls trimmt.
    expect(authButtonState('   ', false)).toBe('hidden');
    expect(authButtonState('\t\n', false)).toBe('hidden');
  });

  it('lässt das Abmelden AUCH ohne Adresse zu', () => {
    // Zwei erreichbare Fälle, in denen beides zusammentrifft:
    // (1) Beim Neuladen des Tabs — `mcpAuthBase` beginnt leer und wird erst
    //     nach dem Config-Abruf gesetzt, der Block liegt aber schon im
    //     `sessionStorage` (das den Reload überlebt).
    // (2) Wenn der Betrieb `mcp_auth_base` abschaltet, während ein Tab noch
    //     einen Block hält.
    // Ohne diesen Zweig bliebe die Person angemeldet, ohne je wieder anonym
    // werden zu können — und Abmelden kann, anders als Anmelden, nicht
    // scheitern: es räumt nur den lokalen Speicher.
    expect(authButtonState('', true)).toBe('signOut');
  });
});
