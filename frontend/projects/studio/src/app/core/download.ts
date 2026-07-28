/**
 * Hand a fetched blob to the browser's download machinery (9-6 / A6).
 *
 * ALT downloaded with `window.location.href = '/api/config/backup…'`
 * (page.tsx:361, SnapshotsModal.tsx:161+252). That works for a 200, but a 404
 * navigates the whole studio away and replaces it with the raw JSON error — the
 * factory download does exactly that when no factory row exists. Fetching the
 * bytes first keeps the error on the error path (`StudioApi.blob`) and this
 * function only has to deal with a blob that already arrived.
 */

/** Milliseconds the object URL stays alive after the click. */
const REVOKE_DELAY_MS = 0;

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  // Firefox only follows a `download` anchor that is part of the document.
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Not revoked synchronously: Chromium may still be reading the URL when the
  // click handler returns, and a revoked URL cancels the download.
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_DELAY_MS);
}
