/**
 * Tastatur des Themenbaums nach dem WAI-ARIA-Muster „Tree View“ — als reine Regel ohne Angular
 * (Review U1 gesamt: aus der Komponente gezogen, Verhalten unverändert). Die Komponente führt die
 * Aktion aus und verbraucht die Taste (`preventDefault`), außer bei `null`.
 *
 * ↑ ↓ wechseln, Pos1/Ende springen, → öffnet bzw. geht ins erste Kind, ← schließt bzw. geht zum
 * Elternknoten, Enter/Leertaste klappen; Enter auf einem Blatt zeigt dessen Inhalte (APG:
 * Standardaktion). Tab und alles andere bleibt dem Browser.
 */
import type { Eintrag } from './themenbaum-zweige';

export type TastenAktion =
  | { readonly art: 'fokus'; readonly pfad: string }
  | { readonly art: 'aufklappen'; readonly eintrag: Eintrag }
  | { readonly art: 'zuklappen'; readonly eintrag: Eintrag }
  | { readonly art: 'umschalten'; readonly eintrag: Eintrag }
  | { readonly art: 'inhalte' }
  /** Die Taste gehört dem Baum, bewirkt hier aber nichts (etwa ↓ am Ende). */
  | { readonly art: 'nichts' };

const NICHTS: TastenAktion = { art: 'nichts' };

/** Was die Taste `taste` auf dem aktiven Eintrag (`aktiv`, Pfad) der sichtbaren `liste` bewirkt;
 *  `null`: die Taste gehört dem Browser. Ein unbekannter Pfad zählt als erster Eintrag. */
export function tastenAktion(
  taste: string, liste: readonly Eintrag[], aktiv: string, istOffen: (e: Eintrag) => boolean,
): TastenAktion | null {
  const i = Math.max(0, liste.findIndex((s) => s.pfad === aktiv));
  const jetzt = liste[i];
  if (!jetzt) return null;
  const offen = jetzt.aufklappbar && istOffen(jetzt);
  const fokus = (e: Eintrag | undefined): TastenAktion => (e ? { art: 'fokus', pfad: e.pfad } : NICHTS);
  switch (taste) {
    case 'ArrowDown': return fokus(liste[i + 1]);
    case 'ArrowUp': return i > 0 ? fokus(liste[i - 1]) : NICHTS;
    case 'Home': return fokus(liste[0]);
    case 'End': return fokus(liste[liste.length - 1]);
    case 'ArrowRight':
      if (!jetzt.aufklappbar) return NICHTS;
      if (!offen) return { art: 'aufklappen', eintrag: jetzt };
      return fokus(jetzt.kinder[0]);
    case 'ArrowLeft':
      if (offen) return { art: 'zuklappen', eintrag: jetzt };
      return jetzt.eltern !== null ? { art: 'fokus', pfad: jetzt.eltern } : NICHTS;
    case 'Enter':
      return jetzt.aufklappbar ? { art: 'umschalten', eintrag: jetzt } : { art: 'inhalte' };
    case ' ':
      return jetzt.aufklappbar ? { art: 'umschalten', eintrag: jetzt } : NICHTS;
    default:
      return null;
  }
}
