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

import { parseProblems } from './field-problems';
import { type SaveConflict, StudioApiError } from './studio-api-error';

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

  /**
   * A GET whose version rides in `X-Config-Version` (Paket 4, D5) — for a list
   * endpoint, whose body cannot carry it. `version` is `null` when absent.
   */
  async getVersioned<T>(path: string): Promise<{ body: T; version: number | null }> {
    const response = await this.send(
      this.http.get<T>(this.url(path), { observe: 'response' }), path);
    const version = Number(response.headers.get('X-Config-Version') ?? Number.NaN);
    return { body: response.body as T, version: Number.isInteger(version) ? version : null };
  }

  /** `headers` for the few calls that must carry one — the chat probe picks the
   *  engine via `X-Boerdi-Engine` (ST-8e). The BFF still sets the key. */
  post<T>(
    path: string, body: unknown, params?: Record<string, QueryValue>,
    headers?: Record<string, string>,
  ): Promise<T> {
    return this.send(
      this.http.post<T>(this.url(path), body, { params: toParams(params), headers }), path);
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
  // ST-2e: a 422 keeps its entries with their paths, next to the joined line.
  const body: unknown = err.error;
  const problems = err.status === 422 && body && typeof body === 'object' && 'detail' in body
    ? parseProblems((body as { detail: unknown }).detail)
    : [];
  const conflict = err.status === 409 ? conflictOf(body) : null;
  return new StudioApiError(err.status, detailOf(err), path, problems, conflict);
}

/** A 409's `detail` object (Paket 4, D5) -> who saved, when, which version. */
function conflictOf(body: unknown): SaveConflict | null {
  const detail = body && typeof body === 'object' && 'detail' in body
    ? (body as { detail: unknown }).detail : null;
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const { version, updated_by, updated_at } = detail as Record<string, unknown>;
  return {
    version: typeof version === 'number' ? version : null,
    updatedBy: typeof updated_by === 'string' ? updated_by : null,
    updatedAt: typeof updated_at === 'string' ? updated_at : null,
  };
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
    // A conflict (409, Paket 4 D5) answers with an object carrying the sentence.
    const message = detail && typeof detail === 'object'
      ? (detail as { message?: unknown }).message : undefined;
    if (typeof message === 'string' && message.trim()) return message.slice(0, MAX_DETAIL);
  }
  if (typeof body === 'string' && body.trim()) return body.trim().slice(0, MAX_DETAIL);
  return (err.statusText || 'Unbekannter Fehler').slice(0, MAX_DETAIL);
}

/**
 * `{loc: ['body', 'welcome', 'quick_replies'], msg: '…'}` -> `welcome.quick_replies: …`.
 * A restore names the area of each entry (Paket 4, D3); it leads as a breadcrumb.
 */
function describeValidationError(entry: unknown): string {
  if (!entry || typeof entry !== 'object') return String(entry);
  const { loc, msg, area } = entry as { loc?: unknown; msg?: unknown; area?: unknown };
  const parts = Array.isArray(loc) ? [...loc] : [];
  // Only the LEADING segment is FastAPI's request-part envelope. `body` is also
  // a real config key — the whole markdown document of every layer doc and
  // every pattern — and filtering it everywhere left those errors nameless.
  if (parts[0] === 'body') parts.shift();
  const where = parts.join('.');
  const what = typeof msg === 'string' ? msg : 'ungültig';
  const line = where ? `${where}: ${what}` : what;
  return typeof area === 'string' && area ? `${area} › ${line}` : line;
}
