/**
 * Studio session operations (P9-2). State lives in SessionStore.
 *
 * The auth cookie is httpOnly, so the SPA cannot read it — the only way to know
 * whether we are signed in is to ask the BFF. ALT had no such endpoint at all
 * (its middleware redirected to an HTML login page, which a fetch-based SPA can
 * only observe as "my JSON request came back as HTML"), so `GET /auth/session`
 * is new surface, added with 9-1.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApiError } from '../core/studio-api-error';
import { StudioApi } from '../core/studio-api.service';
import { SessionState, SessionStore } from './session-store';

interface SessionResponse {
  authenticated: boolean;
  open: boolean;
}

interface LoginResponse {
  ok: boolean;
  open: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(StudioApi);
  private readonly store = inject(SessionStore);

  readonly state = this.store.state;
  readonly gateOpen = this.store.gateOpen;
  readonly signedIn = this.store.signedIn;

  /**
   * Ask the BFF. Resolves to the new state; never throws.
   *
   * A 503 becomes `'disabled'`, not `'signed-out'`: it means STUDIO_PASSWORD is
   * unconfigured and the studio is closed fail-closed, so no password will ever
   * get you in and showing a login form would be a dead end.
   */
  async refresh(): Promise<SessionState> {
    try {
      const session = await this.api.get<SessionResponse>('/auth/session');
      this.store.set(session.authenticated ? 'signed-in' : 'signed-out', session.open);
    } catch (err) {
      this.store.set(
        err instanceof StudioApiError && err.isDisabled ? 'disabled' : 'signed-out',
      );
    }
    return this.store.state();
  }

  /**
   * Sign in. Resolves on success, THROWS StudioApiError otherwise — so the form
   * can tell a wrong password (401) from a locked studio (503) from too many
   * attempts (429). ALT showed the one string "Falsches Passwort" for every
   * non-2xx, a 500 included.
   */
  async login(password: string): Promise<void> {
    const resp = await this.api.post<LoginResponse>('/auth/login', { password });
    this.store.set('signed-in', resp.open);
  }

  /** Sign out. The cookie is cleared server-side; local state follows either way. */
  async logout(): Promise<void> {
    try {
      await this.api.post('/auth/logout', null);
    } finally {
      // Even on failure the user asked to leave — drop the cached state so the
      // guard re-asks instead of trusting a stale 'signed-in'.
      this.store.markSignedOut();
    }
  }
}
