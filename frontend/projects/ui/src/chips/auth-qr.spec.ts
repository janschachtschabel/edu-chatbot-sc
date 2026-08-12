import { describe, expect, it } from 'vitest';

import { AUTH_QR_MARKER, isAuthQuickReply } from './auth-qr';

/**
 * Der Marker ist eine Vereinbarung mit dem Backend — er wird hier wörtlich
 * festgehalten, damit ein Umbenennen auf einer Seite auf der anderen auffällt
 * statt still den Chip verschwinden zu lassen.
 */
describe('Anmelde-Chip', () => {
  it('lautet genau __auth__', () => {
    expect(AUTH_QR_MARKER).toBe('__auth__');
  });

  it('erkennt den Marker', () => {
    expect(isAuthQuickReply('__auth__')).toBe(true);
  });

  it.each([
    ['', 'leer'],
    ['__auth__|Anmelden', 'mit angehängter Beschriftung'],
    ['__auth__ ', 'mit Leerzeichen'],
    ['__guide__|Label|https://x', 'ein Lotsen-Chip'],
    ['__action__|Label|act|{}', 'ein Aktions-Chip'],
    ['Zeig mir mehr', 'eine gewöhnliche Antwort'],
  ])('erkennt %s (%s) NICHT als Anmelde-Chip', (qr) => {
    expect(isAuthQuickReply(qr)).toBe(false);
  });
});
