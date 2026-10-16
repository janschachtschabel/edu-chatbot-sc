/**
 * Darf die Shell nach einem Zug den Fokus ins Eingabefeld zurückholen?
 * (Paket 10, Audit 2026-10-10 L-9)
 *
 * Nur, wenn er im Chat lag — oder nirgends, etwa weil das Feld während des
 * Ladens gesperrt war. Sonst risse sie ihn der Gastseite weg. Auf Touch-Geräten
 * öffnete das Zurückholen die Tastatur über der Antwort; dort nur aus dem Chat
 * heraus. `getRootNode`, weil im Shadow DOM `document.activeElement` der Wirt ist.
 */
export function fokusZurueckholen(shell: HTMLElement): boolean {
  const wurzel = shell.getRootNode() as Document | ShadowRoot;
  const imChat = !!wurzel.activeElement && shell.contains(wurzel.activeElement);
  const nirgends = !document.activeElement || document.activeElement === document.body;
  const touch = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
  return imChat || (nirgends && !touch);
}
