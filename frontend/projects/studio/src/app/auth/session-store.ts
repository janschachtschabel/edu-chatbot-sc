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

export type SessionState = 'unknown' | 'signed-in' | 'signed-out' | 'disabled';

@Injectable({ providedIn: 'root' })
export class SessionStore {
  private readonly _state = signal<SessionState>('unknown');
  private readonly _gateOpen = signal(false);

  readonly state = this._state.asReadonly();
  /** No STUDIO_PASSWORD configured — the gate is off (explicit dev opt-in). */
  readonly gateOpen = this._gateOpen.asReadonly();
  readonly signedIn = computed(() => this._state() === 'signed-in');

  set(state: SessionState, gateOpen = false): void {
    this._state.set(state);
    this._gateOpen.set(gateOpen);
  }

  markSignedOut(): void {
    this._state.set('signed-out');
  }
}
