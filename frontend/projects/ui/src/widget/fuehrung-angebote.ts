/**
 * Führungen als Angebot unter der Begrüßung (Paket AS-7b, Plan 2026-11-09 §5m, F-7).
 *
 * Das Boot-Bündel (`GET /api/config/guide-mode`) nennt die aktiven Abläufe mit Auslöser `seite`
 * (`ablauf_seiten`: Kennung, Titel je Sprache, Pfadmuster). Passt die Seite beim Öffnen, stellt die
 * Hülle einen Start-Chip vor die Start-Chips — `ablauf_starten` per Knopf, nie ein Start von selbst
 * (ein Start ohne Zutun überraschte und verdrängte die Begrüßung). Der Abgleich läuft hier im
 * Widget: ein Ping auf jeder Seite kostete Last.
 */
import { seitePasst } from './seiten-muster';

export interface AblaufSeite {
  readonly id: string;
  readonly titel: Readonly<Record<string, string>>;
  readonly muster: readonly string[];
}

/** Höchstens so viele Angebote unter der Begrüßung. */
export const MAX_ANGEBOTE = 2;
/** Wie die Kennung eines Ablaufs im Backend (`config_models/ablauf.ID_FORM`). */
const KENNUNG = /^[a-z][a-z0-9_]{0,39}$/;

function istObjekt(wert: unknown): wert is Record<string, unknown> {
  return typeof wert === 'object' && wert !== null && !Array.isArray(wert);
}

/** Die gültigen Einträge des Feldes `ablauf_seiten` — `null`, wenn das Feld keine Liste ist. */
export function ablaufSeitenAus(roh: unknown): AblaufSeite[] | null {
  if (!Array.isArray(roh)) return null;
  return roh.flatMap((e): AblaufSeite[] => {
    if (!istObjekt(e) || typeof e['id'] !== 'string' || !KENNUNG.test(e['id'])) return [];
    const titel = e['titel'];
    const muster = e['muster'];
    if (!istObjekt(titel) || !Array.isArray(muster) || !muster.length
        || !muster.every((m) => typeof m === 'string')) return [];
    const texte = Object.fromEntries(Object.entries(titel)
      .filter(([, t]) => typeof t === 'string' && t.trim()) as [string, string][]);
    return [{ id: e['id'], titel: texte, muster: muster as string[] }];
  });
}

/** Die Start-Chips der Abläufe, deren Muster auf `pfad` passen — Titel in der Sprache, sonst
 *  Deutsch, sonst die Kennung. `|` trennt die Teile eines Chips und wird im Titel `/`. */
export function fuehrungsChips(seiten: readonly AblaufSeite[], pfad: string, sprache: string): string[] {
  return seiten
    .filter((s) => seitePasst(pfad, s.muster))
    .slice(0, MAX_ANGEBOTE)
    .map((s) => {
      const titel = (s.titel[sprache] || s.titel['de'] || s.id).replace(/\|/g, '/').trim().slice(0, 60);
      return `__action__|${titel}|ablauf_starten|${JSON.stringify({ ablauf: s.id })}`;
    });
}
