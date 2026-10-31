/**
 * The session signals, split out from AuthService (P9-2).
 *
 * Why its own service: the 401 interceptor must invalidate the cached state, but
 * AuthService depends on StudioApi → HttpClient, and an interceptor injecting
 * that chain builds a dependency cycle through the very client it sits inside.
 * A dependency-free store breaks the cycle — and separates "what the session is"
 * from "how to change it server-side".
 */
import { Injectable, computed, signal } from '@angular/core';

/** `locked` (Paket 19, H-3): zu viele falsche Cookies von dieser Adresse — 429 bis zum Ablauf. */
export type SessionState = 'unknown' | 'signed-in' | 'signed-out' | 'disabled' | 'locked';

@Injectable({ providedIn: 'root' })
export class SessionStore {
  private readonly _state = signal<SessionState>('unknown');
  private readonly _gateOpen = signal(false);
  private readonly _retryAfterS = signal<number | null>(null);

  readonly state = this._state.asReadonly();
  /** No STUDIO_PASSWORD configured — the gate is off (explicit dev opt-in). */
  readonly gateOpen = this._gateOpen.asReadonly();
  readonly signedIn = computed(() => this._state() === 'signed-in');
  /** Wie lange `locked` noch gilt (Sekunden aus `Retry-After`), sonst `null`. */
  readonly retryAfterS = this._retryAfterS.asReadonly();

  set(state: SessionState, gateOpen = false, retryAfterS: number | null = null): void {
    this._state.set(state);
    this._gateOpen.set(gateOpen);
    this._retryAfterS.set(retryAfterS);
  }

  markSignedOut(): void {
    this._state.set('signed-out');
  }
}
