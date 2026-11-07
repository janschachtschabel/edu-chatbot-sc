/**
 * Zugangsblock des MCP-Servers, im Browser gehalten (C5-b).
 *
 * Wer sich beim WLO-MCP-Server anmeldet, bekommt einen **Zugangsblock**
 * (`wlo2.…`). Das Widget hält ihn und schickt ihn je Chat-Anfrage als Kopfzeile
 * mit; das Backend reicht ihn nur an den MCP-Server durch und **speichert ihn
 * nirgends**.
 *
 * ⚠️ Security-relevant. Drei Entscheidungen, jede gegen `docs/AUTH.md` des
 * MCP-Servers gemessen (2026-08-10) — sie sehen wie Kleinigkeiten aus und sind
 * es nicht:
 *
 * 1. **`sessionStorage`, nicht `localStorage`.** Der Block verschlüsselt ein
 *    WLO-Passwort (AUTH.md §1: edu-sharing hat kein Token zu vergeben) und hat
 *    **kein Ablaufdatum im Token** (§5b: kein `refresh_token`, kein `expires_in`;
 *    seit 07.11.2026 laufen Widget- und Ticket-Blöcke nur in der Erlaubnisliste
 *    des Servers nach 12 h ab — `session/anmelde-frist.ts`). Er
 *    darf deshalb nicht neben der Sitzungskennung liegen, die absichtlich
 *    langlebig ist und über `?bsid=` durch URLs wandert. Mit dem Tab zu sterben
 *    ist hier ein Merkmal, kein Mangel.
 * 2. **Kein Cookie.** Ein Cookie ginge automatisch an jede Anfrage derselben
 *    Domain; diese Berechtigung soll nur an den Chat-Endpunkt gehen.
 * 3. **Nicht die `Authorization`-Kopfzeile.** Die bedeutet „berechtige mich
 *    gegenüber DIESEM Server"; der Block gilt dem MCP-Server dahinter.
 *
 * Die Prüfung hier ist Bequemlichkeit, nicht Schutz: das Backend prüft
 * dieselbe Form noch einmal (`services/mcp/auth.set_turn_auth_block`), und der
 * MCP-Server entscheidet als Einziger, ob der Block wirklich gilt. Sie fängt
 * den häufigen Fall früh ab — mitkopiertes „Bearer " (AUTH.md §5a: genau dafür
 * hat die `/auth`-Seite zwei Kopier-Knöpfe) — und hält fremde Zugangsdaten aus
 * unserem Speicher heraus.
 */

/** Schlüssel im `sessionStorage`. */
export const MCP_ACCESS_STORAGE_KEY = 'boerdi.mcp-access';

/** Kopfzeile, unter der der Block ans Backend reist (dort `_ACCESS_BLOCK_HEADER`). */
export const MCP_ACCESS_HEADER = 'WLO-Access-Block';

/** Obergrenze — ein echter Block liegt bei ~1000 Zeichen (RSA-2048 + AES-GCM). */
const MAX_LENGTH = 4096;

/**
 * Form-Prüfung, spiegelbildlich zum Backend.
 *
 * Präfix `wlo` deckt `wlo2.…` und `wlo-anon.v1` ab und überlebt ein künftiges
 * `wlo3.`; der Zeichenvorrat ist base64url plus Trennpunkte und schliesst
 * Leerzeichen und Steuerzeichen aus.
 */
export function isWellFormedAccessBlock(block: string | null | undefined): boolean {
  if (!block || typeof block !== 'string') return false;
  return block.length <= MAX_LENGTH && /^wlo[A-Za-z0-9._~+/=-]*$/.test(block);
}

/** Der hinterlegte Block — `null`, wenn keiner da oder er unbrauchbar ist. */
export function readAccessBlock(): string | null {
  try {
    const roh = sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY);
    // Auch beim LESEN prüfen: fremder Code auf der Gastgeberseite teilt sich
    // diesen Speicher und könnte dort etwas anderes ablegen.
    return isWellFormedAccessBlock(roh) ? roh : null;
  } catch {
    return null; // Speicher gesperrt (privater Modus) — dann eben anonym.
  }
}

/** Hinterlege den Block. Gibt zurück, ob er angenommen wurde. */
export function writeAccessBlock(block: string): boolean {
  if (!isWellFormedAccessBlock(block)) return false;
  try {
    sessionStorage.setItem(MCP_ACCESS_STORAGE_KEY, block);
    return true;
  } catch {
    return false;
  }
}

/**
 * Nach einem ausdrücklichen „Abmelden“ (Plan 2026-11-07, R2/CB-9) tauscht das Widget in diesem
 * Tab kein Seiten-Ticket mehr von selbst — sonst wäre die Person nach dem nächsten Laden wieder
 * angemeldet. Eine Anmeldung von Hand hebt den Merker auf. `sessionStorage` wie der Block: er
 * stirbt mit dem Tab.
 */
export const MCP_SIGNED_OUT_STORAGE_KEY = 'boerdi.mcp-signed-out';

export function markSignedOut(): void {
  try {
    sessionStorage.setItem(MCP_SIGNED_OUT_STORAGE_KEY, '1');
  } catch {
    /* ignore */
  }
}

export function clearSignedOut(): void {
  try {
    sessionStorage.removeItem(MCP_SIGNED_OUT_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function isSignedOut(): boolean {
  try {
    return sessionStorage.getItem(MCP_SIGNED_OUT_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

/** Den Block aus dem Tab entfernen. Den Zugang am Server beendet erst der Widerruf über das
 *  Backend (`ChatApiService.abmelden`, Plan 2026-11-07, R2). */
export function clearAccessBlock(): void {
  try {
    sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Die Kopfzeilen für eine Chat-Anfrage — leeres Objekt, wenn niemand angemeldet
 * ist.
 *
 * Bewusst leer statt leerer Kopfzeile: das Backend meldet einen vorgelegten,
 * aber unbrauchbaren Wert als Warnung, und ein anonymer Zug ist keine Warnung.
 */
export function accessBlockHeaders(): Record<string, string> {
  const block = readAccessBlock();
  return block ? { [MCP_ACCESS_HEADER]: block } : {};
}
