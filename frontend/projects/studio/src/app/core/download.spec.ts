// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

describe('saveBlob', () => {
  let url: UrlStub;

  beforeEach(() => {
    url = stubObjectUrl();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
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
