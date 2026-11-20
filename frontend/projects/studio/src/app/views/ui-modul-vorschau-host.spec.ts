import { describe, expect, it, vi } from 'vitest';

import { VorschauModulHost } from './ui-modul-vorschau-host';

/**
 * Review der Oberfläche zu Paket U, NIT 12: die Vorschau gibt je Datei eine eigene `upload_id` —
 * sonst sähe die Antwort von „Hier im Chat“ mit mehreren Dateien aus wie lauter Dubletten.
 */
describe('VorschauModulHost.hochladen', () => {
  const host = () => new VorschauModulHost(vi.fn(), (t) => t, () => ({}) as never);

  it('je Datei eine eigene, gültige upload_id (UUID v4) und die Rolle wie das Backend', async () => {
    const h = host();
    const a = await h.hochladen(new File(['a'], 'a.pdf'), undefined, 'inhalt');
    const b = await h.hochladen(new File(['b'], 'b.pdf'));
    expect(a['upload_id']).not.toBe(b['upload_id']);
    for (const id of [a['upload_id'], b['upload_id']]) {
      expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    }
    expect([a['rolle'], b['rolle']]).toEqual(['inhalt', 'struktur']);
    expect(a['angaben']).toBeTruthy();
    expect(b['angaben']).toBeUndefined();
  });
});

// Plan 2026-11-20, P2: die Vorschau hält das Häkchen „Metadaten von WLO erzeugen lassen“ fest, wie es kam — der
// Knopf, der ablegt, heißt so wie im Betrieb
describe('VorschauModulHost.ablegen', () => {
  it('vorbereiten gibt erschliessen zurück, wie es kam', async () => {
    const h = new VorschauModulHost(vi.fn(), (t) => t, () => ({}) as never);
    const eintraege = [{ titel: 'a', sha256: 'a'.repeat(64), groesse: 1, art: 'pdf' }];
    expect((await h.ablegen({ schritt: 'vorbereiten', ordner: 'P', eintraege, erschliessen: true }))['erschliessen']).toBe(true);
    expect((await h.ablegen({ schritt: 'vorbereiten', ordner: 'P', eintraege }))['erschliessen']).toBe(false);
  });
});
