/**
 * Session-Boot (8-4S-e1) — die 3-Stufen-Session-Kaskade aus ALT `ngOnInit`
 * (chat.component.ts:286-305) als pure Funktion, damit `ngOnInit` schlank bleibt.
 * Löst die persistierte Session-ID (URL `?bsid=` → Cookie → localStorage) oder
 * erzeugt eine frische und schreibt sie bei `persist` in alle aktiven Storages
 * zurück (der nächste Page-Load findet sie, egal von welcher Stufe getrieben).
 *
 * Reuse: die Stufen-Resolution + der Write-Back liegen in `session/session-id.ts`
 * (security-relevant, dort gepinnt). Hier bleibt nur die Orchestrierung. Der
 * `viaBsid`-Rückgabewert ersetzt ALTs Seiteneffekt auf `_resumedViaBsid` — die
 * Shell pflegt ihr Feld daraus. KEINE Logik-Änderung.
 */
import { generateSessionId, resolvePersistedSessionId, writeSessionEverywhere } from '../session/session-id';

/** Konfiguration der Kaskade — die session-relevanten `@Input()`s der Shell. */
export interface SessionBootConfig {
  /** `[persistSession]` bereits zu bool aufgelöst (leer/false → reine Neu-ID). */
  persist: boolean;
  /** Storage-/Cookie-Schlüssel (`[sessionKey]`). */
  sessionKey: string;
  /** Cookie-Domain für Cross-Subdomain-Sharing (`[sessionCookieDomain]`). */
  cookieDomain: string;
  /** Cookie-Lebensdauer in Sekunden (`[sessionCookieMaxAge]`). */
  cookieMaxAge: number | string;
}

/** Ergebnis: die aktive ID + ob sie aus dem Storage kam (`resumed`) und ob per
 *  Cross-Origin-`?bsid=`-Handoff (`viaBsid` → `_resumedViaBsid`). */
export interface SessionBoot {
  sessionId: string;
  resumed: boolean;
  viaBsid: boolean;
}

/** Session-ID auflösen/erzeugen + bei `persist` zurückschreiben. Verbatim aus
 *  ALT `ngOnInit` 286-305 (der try/catch spiegelt ALT; `resolvePersistedSessionId`
 *  und `writeSessionEverywhere` schlucken ihre Fehler bereits intern). */
export function bootSession(cfg: SessionBootConfig): SessionBoot {
  if (!cfg.persist) {
    return { sessionId: generateSessionId(), resumed: false, viaBsid: false };
  }
  try {
    const found = resolvePersistedSessionId(cfg.sessionKey);
    const sessionId = found.id ?? generateSessionId();
    writeSessionEverywhere(sessionId, {
      sessionKey: cfg.sessionKey,
      cookieDomain: cfg.cookieDomain,
      cookieMaxAge: cfg.cookieMaxAge,
    });
    return { sessionId, resumed: !!found.id, viaBsid: found.viaBsid };
  } catch {
    return { sessionId: generateSessionId(), resumed: false, viaBsid: false };
  }
}
