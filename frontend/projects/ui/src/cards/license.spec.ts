import { describe, it, expect } from 'vitest';
import { getLicenseShort } from './license';

/**
 * Charakterisierung von getLicenseShort — Verbatim-Port aus ALT
 * `chat-text-utils.ts` (dort nur integrativ über die große
 * chat.component.spec.ts gedeckt). Das Kürzel steht user-sichtbar im
 * Lizenz-Badge des Vorschaubilds, darum hier vor dem Tile-Konsum gepinnt.
 * Erwartete Werte aus dem ALT-Quelltext abgeleitet (Branch-Abdeckung).
 */
describe('getLicenseShort', () => {
  it('leer/whitespace → ""', () => {
    expect(getLicenseShort('')).toBe('');
    expect(getLicenseShort('   ')).toBe('');
  });

  it('CC0 behält eigenes Kürzel (nicht PD)', () => {
    expect(getLicenseShort('CC0')).toBe('CC0');
    expect(getLicenseShort('CC0 1.0')).toBe('CC0');
  });

  it('CC-Lizenzen: Versionssuffix entfällt, Großschreibung', () => {
    expect(getLicenseShort('CC BY-SA 4.0')).toBe('CC BY-SA');
    expect(getLicenseShort('CC BY 4.0')).toBe('CC BY');
    expect(getLicenseShort('cc by')).toBe('CC BY');
  });

  it('individuelle/custom/copyright → ©', () => {
    expect(getLicenseShort('Individuelle Lizenz')).toBe('©');
    expect(getLicenseShort('Custom')).toBe('©');
    expect(getLicenseShort('Copyright 2020')).toBe('©');
  });

  it('Public Domain / gemeinfrei / PDM → PD', () => {
    expect(getLicenseShort('Public Domain')).toBe('PD');
    expect(getLicenseShort('Gemeinfrei')).toBe('PD');
    expect(getLicenseShort('PDM')).toBe('PD');
  });

  it('lange unbekannte Lizenz → "Lizenz", kurze bleibt', () => {
    expect(getLicenseShort('Sonderlizenz XYZ 2020')).toBe('Lizenz');
    expect(getLicenseShort('MIT')).toBe('MIT');
  });
});
