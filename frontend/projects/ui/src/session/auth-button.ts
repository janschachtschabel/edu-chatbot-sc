/**
 * Was der Anmelde-Knopf in der Eingabezeile zeigen soll.
 *
 * Rein, ohne DOM und ohne Angular: die Shell fragt nur, was sie zeichnen soll,
 * und der Zustand hängt an genau zwei Dingen — bietet diese Anlage die
 * Anmeldung überhaupt an, und liegt schon ein Zugangsblock im Speicher.
 *
 * Zwei Entscheidungen stecken darin:
 *
 * 1. **Ohne Anmelde-Adresse kein Knopf.** `runSignIn` bricht ohne Basis ab und
 *    sagt „diese Installation bietet die WLO-Anmeldung nicht an" — ein Knopf,
 *    der nur das erreichen kann, ist schlechter als keiner. Das ist zugleich
 *    der Ausschalter für Anlagen, die die Anmeldung nicht anbieten wollen.
 * 2. **Ein vorhandener Block schlägt die fehlende Adresse.** Abmelden kann,
 *    anders als Anmelden, nicht scheitern — es räumt nur `sessionStorage`.
 *    Und beides trifft erreichbar zusammen: `mcpAuthBase` beginnt leer und
 *    wird erst nach dem Config-Abruf gesetzt (`guide-boot.load`), während der
 *    Block das Neuladen des Tabs überlebt. Ohne diesen Vorrang wäre eine
 *    angemeldete Person nach jedem Reload kurz ohne Knopf — und dauerhaft
 *    ohne, sobald der Betrieb `mcp_auth_base` abschaltet.
 */

export type AuthButtonState = 'hidden' | 'signIn' | 'signOut';

/**
 * @param mcpAuthBase Herkunft des MCP-Servers; leer (auch nur Leerzeichen)
 *   heisst „keine Anmeldung angeboten" — dieselbe Prüfung wie in `runSignIn`.
 * @param hasBlock Ob ein brauchbarer Zugangsblock hinterlegt ist
 *   (`readAccessBlock() !== null`).
 */
export function authButtonState(mcpAuthBase: string, hasBlock: boolean): AuthButtonState {
  if (hasBlock) return 'signOut';
  return (mcpAuthBase || '').trim() ? 'signIn' : 'hidden';
}
