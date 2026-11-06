// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { erzeugeLader, type NachladeIndex, zuruecksetzenFuerTests } from './nachladen';

const INDEX: NachladeIndex = {
  ui_probe: { datei: 'ui-probe.0123abcd.js', integritaet: 'sha384-AAAA' },
};

function skripte(): HTMLScriptElement[] {
  return [...document.head.querySelectorAll('script[data-boerdi-modul]')] as HTMLScriptElement[];
}

afterEach(() => {
  zuruecksetzenFuerTests();
  skripte().forEach((s) => s.remove());
  vi.useRealTimers();
  delete (window as unknown as { trustedTypes?: unknown }).trustedTypes;
});

describe('erzeugeLader (U3-0)', () => {
  it('lädt das Bündel von der Widget-Adresse mit SRI und ohne Zugangsdaten', async () => {
    const laden = erzeugeLader(() => 'https://api.example.org/api', INDEX);
    const fertig = laden('ui_probe');
    const [s] = skripte();
    expect(s.src).toBe('https://api.example.org/widget/module/ui-probe.0123abcd.js');
    expect(s.integrity).toBe('sha384-AAAA');
    expect(s.crossOrigin).toBe('anonymous');
    expect(s.dataset['boerdiModul']).toBe('ui_probe');
    s.dispatchEvent(new Event('load'));
    await expect(fertig).resolves.toBeUndefined();
  });

  it('nimmt eine relative API-Basis (Dev-Proxy) wie die Shell', async () => {
    const laden = erzeugeLader(() => '/api', INDEX);
    void laden('ui_probe').catch(() => {});
    expect(skripte()[0].getAttribute('src')).toBe('/widget/module/ui-probe.0123abcd.js');
  });

  it('lädt jedes Modul nur einmal, auch bei vielen Blöcken', () => {
    const laden = erzeugeLader(() => '/api', INDEX);
    const a = laden('ui_probe');
    const b = laden('ui_probe');
    expect(a).toBe(b);
    expect(skripte()).toHaveLength(1);
  });

  it('lehnt ab, wenn das Modul nicht im Index steht (Bündel nicht gebaut)', async () => {
    const laden = erzeugeLader(() => '/api', INDEX);
    await expect(laden('ui_fehlt')).rejects.toThrow(/ui_fehlt/);
    expect(skripte()).toHaveLength(0);
  });

  it('lehnt ab, wenn das Skript nicht lädt (Netz, SRI, CSP) — ein neuer Versuch lädt neu', async () => {
    const laden = erzeugeLader(() => '/api', INDEX);
    const erster = laden('ui_probe');
    skripte()[0].dispatchEvent(new Event('error'));
    await expect(erster).rejects.toThrow();
    expect(skripte()).toHaveLength(0);
    void laden('ui_probe').catch(() => {});
    expect(skripte()).toHaveLength(1);
  });

  it('gibt nach der Frist auf', async () => {
    vi.useFakeTimers();
    const laden = erzeugeLader(() => '/api', INDEX, { fristMs: 1000 });
    const fertig = laden('ui_probe');
    vi.advanceTimersByTime(1001);
    await expect(fertig).rejects.toThrow(/Frist/);
  });

  it('zwei Widgets auf einer Seite laden ein Modul nur einmal (ein Skript, ein Versprechen)', () => {
    const a = erzeugeLader(() => '/api', INDEX)('ui_probe');
    const b = erzeugeLader(() => '/api', INDEX)('ui_probe');
    expect(a).toBe(b);
    expect(skripte()).toHaveLength(1);
  });

  it('ein schon geladenes Modul hängt kein zweites Skript ein', async () => {
    const laden = erzeugeLader(() => '/api', INDEX);
    const erster = laden('ui_probe');
    skripte()[0].dispatchEvent(new Event('load'));
    await erster;
    await laden('ui_probe');
    expect(skripte()).toHaveLength(1);
  });

  it('Trusted Types: eine Richtlinie je Seite, auch bei zwei Widgets und neuer API-Basis', () => {
    const createPolicy = vi.fn((_name: string, regeln: { createScriptURL: (u: string) => string }) => ({
      createScriptURL: (u: string) => regeln.createScriptURL(u),
    }));
    (window as unknown as { trustedTypes: unknown }).trustedTypes = { createPolicy };
    let basis = '/api';
    void erzeugeLader(() => basis, INDEX)('ui_probe').catch(() => {});
    basis = 'https://anderes.example/api';
    const zweiter = erzeugeLader(() => basis, { ui_zwei: { datei: 'ui-zwei.0123abcd.js', integritaet: 'sha384-B' } });
    void zweiter('ui_zwei').catch(() => {});
    expect(createPolicy).toHaveBeenCalledTimes(1);
    expect(skripte().map((s) => s.getAttribute('src'))).toEqual([
      '/widget/module/ui-probe.0123abcd.js', 'https://anderes.example/widget/module/ui-zwei.0123abcd.js',
    ]);
  });

  it('nutzt Trusted Types, wenn die Seite sie verlangt — die Adresse muss zur Widget-Basis passen', () => {
    const createScriptURL = vi.fn((u: string) => ({ toString: () => u }));
    const createPolicy = vi.fn((_name: string, regeln: { createScriptURL: (u: string) => string }) => ({
      createScriptURL: (u: string) => createScriptURL(regeln.createScriptURL(u)),
    }));
    (window as unknown as { trustedTypes: unknown }).trustedTypes = { createPolicy };
    const laden = erzeugeLader(() => '/api', INDEX);
    void laden('ui_probe').catch(() => {});
    expect(createPolicy).toHaveBeenCalledWith('boerdi-ui-module', expect.any(Object));
    expect(createScriptURL).toHaveBeenCalledWith('/widget/module/ui-probe.0123abcd.js');
    const regeln = createPolicy.mock.calls[0][1];
    expect(() => regeln.createScriptURL('https://boese.example/x.js')).toThrow();
    expect(() => regeln.createScriptURL('https://boese.example/widget/module/../x.js')).toThrow();
    // Querschnitts-Review FE-7: eine API unter einem Präfix lädt von dort.
    expect(regeln.createScriptURL('https://x.example/boerdi/widget/module/ui-probe.0123abcd.js'))
      .toBe('https://x.example/boerdi/widget/module/ui-probe.0123abcd.js');
    expect(() => regeln.createScriptURL('https://x.example/widget/module/ui-probe.js')).toThrow();
    expect(() => regeln.createScriptURL('https://x.example/boerdi/widget/modul/ui-probe.0123abcd.js')).toThrow();
  });
});
