/**
 * Pfadmuster für Führungen im Widget (Paket AS-7b, Plan 2026-11-09 §5m, F-3/F-7).
 *
 * Dieselbe Regel wie im Backend (`backend/src/boerdi/domain/seiten_muster.py`): `*` ist der einzige
 * Platzhalter, sonst zählt jedes Zeichen wörtlich; verglichen wird der normalisierte Pfad (ohne Host,
 * Anfrage und Anker, klein, ohne Schrägstrich am Ende); ein Muster auf `/*` passt auch auf seinen
 * Stamm. Der Vergleich ist linear (kein `RegExp` aus Mustern) — die Specs spiegeln die Fälle des
 * Backends, damit Widget und Server gleich entscheiden.
 */

/** So viel einer Seite wird verglichen (wie `MAX_SEITE` im Backend). */
export const MAX_SEITE = 1000;

/** `https://host/A/?x#y` → `/a`; leer → `/`. */
export function normalisierterPfad(seite: string | null | undefined): string {
  let s = (seite || '/').slice(0, 2 * MAX_SEITE).trim();
  s = s.replace(/^https?:\/\/[^/]+/i, '');
  s = s.split('?', 1)[0].split('#', 1)[0].trim().toLowerCase();
  if (!s.startsWith('/')) s = `/${s}`;
  // wie Pythons ``rstrip('/')`` im Backend — „//“ wird zum leeren Pfad (Review AS-7b, Befund 5)
  if (s.length > 1) s = s.replace(/\/+$/, '');
  return s.slice(0, MAX_SEITE);
}

/** Wie `_ERLAUBT` im Backend: Pfad-Zeichen und `*` — kein `?`, keine Klammern. */
// ohne Komma: der Regel-Editor trennt Muster an Kommas (Querschnitts-Review AS-7, Befund 9)
const ERLAUBT = /^\/[A-Za-z0-9._~%!$&'()+;=:@/*-]*$/;

function gueltig(muster: string): boolean {
  return typeof muster === 'string' && muster.length <= 200 && ERLAUBT.test(muster.trim());
}

function passtEins(pfad: string, muster: string): boolean {
  if (muster.endsWith('/*') && pfad === (muster.slice(0, -2) || '/')) return true;
  const teile = muster.split('*');
  if (teile.length === 1) return pfad === muster;
  const anfang = teile[0];
  const ende = teile[teile.length - 1];
  if (pfad.length < anfang.length + ende.length || !pfad.startsWith(anfang) || !pfad.endsWith(ende)) {
    return false;
  }
  let pos = anfang.length;
  const grenze = pfad.length - ende.length;
  for (const stueck of teile.slice(1, -1)) {
    if (!stueck) continue;
    const treffer = pfad.indexOf(stueck, pos);
    if (treffer < 0 || treffer + stueck.length > grenze) return false;
    pos = treffer + stueck.length;
  }
  return true;
}

/** Passt die Seite zu einem der Muster? Ungültige Muster passen nie. */
export function seitePasst(seite: string | null | undefined, muster: readonly string[]): boolean {
  const pfad = normalisierterPfad(seite);
  return muster.some((m) => gueltig(m) && passtEins(pfad, normalisierterPfad(m)));
}
