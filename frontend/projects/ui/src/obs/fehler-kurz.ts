/**
 * Fehler kurz für die Konsole (Paket 18E): Art, HTTP-Status, Fehlernummer — nie der Text.
 *
 * Die Konsole gehört der Gastseite, und ein Fehlertext kann tragen, was die Person
 * geschrieben hat oder der Server zurückgab. Die Fehlernummer reicht, um im Studio den Zug
 * zu finden; Art und Status sagen, wo es hakt.
 */

/** Zeichenvorrat der Trace-ID (`obs/trace_id` im Backend); was anders aussieht, gilt nicht
 *  als Fehlernummer — sie steht als Text in der Blase. */
const FEHLERNUMMER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

/** Ein Fehlername ist ein Bezeichner (`TypeError`, `AbortError`, `StreamHttpError`). */
const BEZEICHNER = /^[A-Za-z_$][\w$]{0,63}$/;

export function fehlernummer(roh: unknown): string {
  return typeof roh === 'string' && FEHLERNUMMER.test(roh) ? roh : '';
}

/** `TypeError`, `StreamHttpError status=429`, `StreamServerError nummer=1a2b3c4d5e6f`.
 *  Den Namen nur von echten Fehlern: ein geworfenes Objekt (etwa ein Antwortkörper) kann
 *  unter `name` alles tragen — dann steht nur sein Typ da. `DOMException` (etwa der
 *  `AbortError` eines abgebrochenen Abrufs) erbt nicht überall von `Error`. */
export function fehlerKurz(err: unknown): string {
  const echt = err instanceof Error
    || (typeof DOMException !== 'undefined' && err instanceof DOMException);
  if (!echt) return err === null ? 'null' : typeof err;
  const name = (err as Error).name;
  const teile = [BEZEICHNER.test(name) ? name : 'Error'];
  const status = (err as { status?: unknown }).status;
  if (typeof status === 'number' && Number.isInteger(status) && status >= 100 && status <= 599) {
    teile.push(`status=${status}`);
  }
  const nummer = fehlernummer((err as { nummer?: unknown }).nummer);
  if (nummer) teile.push(`nummer=${nummer}`);
  return teile.join(' ');
}
