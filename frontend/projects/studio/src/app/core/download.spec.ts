// @vitest-environment jsdom
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { saveBlob } from './download';

interface UrlStub {
  createObjectURL: ReturnType<typeof vi.fn>;
  revokeObjectURL: ReturnType<typeof vi.fn>;
}

/**
 * jsdom 29 implements `Blob` but neither `URL.createObjectURL` nor
 * `revokeObjectURL` (probed: both `undefined`). They are a browser boundary like
 * the network, so the test provides them and asserts how they are used.
 */
function stubObjectUrl(): UrlStub {
  const stub: UrlStub = {
    createObjectURL: vi.fn(() => 'blob:studio/1'),
    revokeObjectURL: vi.fn(),
  };
  Object.assign(URL, stub);
  return stub;
}

// Die Worker laufen nicht isoliert (Angular-Vorgabe `isolate: false`): was
// diese Datei an `HTMLAnchorElement.prototype` oder `URL` ändert, sehen die
// Specs, die danach im selben Worker laufen — etwa die Navigation in
// `shell.component.spec`. Welche das sind, hängt von der Auslastung ab
// (offene Befunde §5, Audit 2026-09-29). Deshalb wird alles zurückgestellt.
const ORIGINAL_CLICK = HTMLAnchorElement.prototype.click;
const ORIGINAL_CREATE = (URL as unknown as Record<string, unknown>)['createObjectURL'];
const ORIGINAL_REVOKE = (URL as unknown as Record<string, unknown>)['revokeObjectURL'];

describe('saveBlob', () => {
  let url: UrlStub;

  afterAll(() => {
    expect(HTMLAnchorElement.prototype.click).toBe(ORIGINAL_CLICK);
    expect((URL as unknown as Record<string, unknown>)['createObjectURL']).toBe(ORIGINAL_CREATE);
    expect((URL as unknown as Record<string, unknown>)['revokeObjectURL']).toBe(ORIGINAL_REVOKE);
  });

  beforeEach(() => {
    url = stubObjectUrl();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    HTMLAnchorElement.prototype.click = ORIGINAL_CLICK;
    const urlStatics = URL as unknown as Record<string, unknown>;
    for (const [name, original] of [
      ['createObjectURL', ORIGINAL_CREATE], ['revokeObjectURL', ORIGINAL_REVOKE],
    ] as const) {
      if (original === undefined) delete urlStatics[name];
      else urlStatics[name] = original;
    }
  });

  it('lädt über einen benannten Anker herunter und lässt das Dokument sauber zurück', () => {
    const clicks: HTMLAnchorElement[] = [];
    // Firefox only follows a `download` anchor that is IN the document, so the
    // element is appended — and must be gone again afterwards.
    const inDocumentAtClick: boolean[] = [];
    HTMLAnchorElement.prototype.click = function click(this: HTMLAnchorElement) {
      clicks.push(this);
      inDocumentAtClick.push(document.body.contains(this));
    };

    saveBlob(new Blob(['x']), 'boerdi-config-backup.zip');

    expect(clicks).toHaveLength(1);
    expect(clicks[0].download).toBe('boerdi-config-backup.zip');
    expect(clicks[0].href).toContain('blob:studio/1');
    expect(inDocumentAtClick).toEqual([true]);
    expect(document.querySelectorAll('a[download]')).toHaveLength(0);
  });

  it('gibt die Objekt-URL erst im nächsten Zug frei, nicht synchron', () => {
    HTMLAnchorElement.prototype.click = function click() {};

    saveBlob(new Blob(['x']), 'snap.zip');

    // Revoking in the same task can cancel the download in Chromium: the click
    // has returned but the browser has not finished reading the URL.
    expect(url.revokeObjectURL).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(url.revokeObjectURL).toHaveBeenCalledWith('blob:studio/1');
  });
});
