/**
 * The single HTTP boundary of the studio SPA (P9-2).
 *
 * Everything goes through the studio-bff at `/studio/api/*`, which gates on the
 * httpOnly cookie and injects the backend key server-side — the SPA never sees
 * or sends `X-Studio-Key`. Because the cookie is same-origin and httpOnly, no
 * `withCredentials` and no auth header are needed.
 *
 * ALT had no real client: `fetchJson` was adopted by 3 of 17 components while
 * the rest called `fetch` raw with the exact defects its own docstring listed
 * (silent `catch {}`, `r.json()` without an `ok` check, no cancellation). This
 * is the abstraction ALT intended: one place, typed errors, `HttpClient` so the
 * 401 interceptor and request cancellation work.
 */
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, firstValueFrom, throwError } from 'rxjs';

import { StudioApiError } from './studio-api-error';

/** Query values; `null`/`undefined` are dropped rather than sent as "null". */
export type QueryValue = string | number | boolean | null | undefined;

const BASE = '/studio/api';
const MAX_DETAIL = 200;

@Injectable({ providedIn: 'root' })
export class StudioApi {
  private readonly http = inject(HttpClient);

  get<T>(path: string, params?: Record<string, QueryValue>): Promise<T> {
    return this.send(this.http.get<T>(this.url(path), { params: toParams(params) }), path);
  }

  post<T>(path: string, body: unknown, params?: Record<string, QueryValue>): Promise<T> {
    return this.send(this.http.post<T>(this.url(path), body, { params: toParams(params) }), path);
  }

  put<T>(path: string, body: unknown, params?: Record<string, QueryValue>): Promise<T> {
    return this.send(this.http.put<T>(this.url(path), body, { params: toParams(params) }), path);
  }

  delete<T>(path: string, params?: Record<string, QueryValue>): Promise<T> {
    return this.send(this.http.delete<T>(this.url(path), { params: toParams(params) }), path);
  }

  /**
   * A file download (9-6). Fetched rather than navigated to: ALT set
   * `window.location.href`, so a 404 replaced the whole studio with the raw JSON
   * error. The error body arrives as a Blob here, so it is parsed separately.
   */
  async blob(path: string): Promise<Blob> {
    try {
      return await firstValueFrom(this.http.get(this.url(path), { responseType: 'blob' }));
    } catch (err) {
      throw await toBlobApiError(err as HttpErrorResponse, path);
    }
  }

  /** Multipart upload; `file` is the FastAPI parameter name on both endpoints. */
  upload<T>(path: string, file: File): Promise<T> {
    const body = new FormData();
    body.append('file', file);
    return this.send(this.http.post<T>(this.url(path), body), path);
  }

  /**
   * `path` is appended verbatim — a trailing slash is preserved on purpose:
   * `GET /api/sessions/` exists ONLY with one, and dropping it makes FastAPI
   * answer a 307 redirect instead of data (ALT needed a special case in its
   * proxy for exactly this, `[...path]/route.ts:27-35`).
   */
  private url(path: string): string {
    return BASE + path;
  }

  private send<T>(source: Observable<T>, path: string): Promise<T> {
    return firstValueFrom(
      source.pipe(catchError((err: HttpErrorResponse) => throwError(() => toApiError(err, path)))),
    );
  }
}

function toParams(params?: Record<string, QueryValue>): HttpParams {
  let out = new HttpParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== null && value !== undefined) out = out.set(key, String(value));
  }
  return out;
}

function toApiError(err: HttpErrorResponse, path: string): StudioApiError {
  if (err.status === 0) {
    return new StudioApiError(0, 'Backend nicht erreichbar.', path);
  }
  return new StudioApiError(err.status, detailOf(err), path);
}

/**
 * The same, for a request that asked for a Blob: Angular hands the error body
 * back as a Blob too, so `detailOf` would only ever see the status text and
 * "Kein Factory-Stand gesetzt" would reach the page as "Not Found".
 */
async function toBlobApiError(err: HttpErrorResponse, path: string): Promise<StudioApiError> {
  if (err.status === 0) return new StudioApiError(0, 'Backend nicht erreichbar.', path);
  const body: unknown = err.error;
  if (!(body instanceof Blob)) return toApiError(err, path);
  const text = (await body.text()).trim();
  return new StudioApiError(err.status, jsonDetail(text) || text.slice(0, MAX_DETAIL)
    || err.statusText || 'Unbekannter Fehler.', path);
}

/** `{"detail":"…"}` -> the sentence; '' for anything else (HTML, a ZIP, junk). */
function jsonDetail(text: string): string {
  if (!text.startsWith('{')) return '';
  try {
    const parsed: unknown = JSON.parse(text);
    const detail = (parsed as { detail?: unknown }).detail;
    return typeof detail === 'string' ? detail.slice(0, MAX_DETAIL) : '';
  } catch {
    return '';
  }
}

/** FastAPI answers `{detail: …}`; a proxy or gateway may answer HTML. */
function detailOf(err: HttpErrorResponse): string {
  const body: unknown = err.error;
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail.slice(0, MAX_DETAIL);
    // A validation failure answers with a LIST. Left unhandled it fell through
    // to `statusText` ("Unprocessable Content"), which names no field at all.
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map(describeValidationError).join('; ').slice(0, MAX_DETAIL);
    }
  }
  if (typeof body === 'string' && body.trim()) return body.trim().slice(0, MAX_DETAIL);
  return (err.statusText || 'Unbekannter Fehler').slice(0, MAX_DETAIL);
}

/** `{loc: ['body', 'welcome', 'quick_replies'], msg: '…'}` -> `welcome.quick_replies: …` */
function describeValidationError(entry: unknown): string {
  if (!entry || typeof entry !== 'object') return String(entry);
  const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
  const parts = Array.isArray(loc) ? [...loc] : [];
  // Only the LEADING segment is FastAPI's request-part envelope. `body` is also
  // a real config key — the whole markdown document of every layer doc and
  // every pattern — and filtering it everywhere left those errors nameless.
  if (parts[0] === 'body') parts.shift();
  const where = parts.join('.');
  const what = typeof msg === 'string' ? msg : 'ungültig';
  return where ? `${where}: ${what}` : what;
}
