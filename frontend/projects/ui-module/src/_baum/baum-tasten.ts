/**
 * Gemeinsamer Baum-Kern (Paket U2, Plan 2026-11-04 T-1): Tastatur nach dem WAI-ARIA-Muster
 * „Tree View“ — als reine Regel ohne Angular, für Bestand (`ui-themenbaum`) und Entwurf
 * (`ui-strukturentwurf`). Seit U2 hier statt in `ui-themenbaum/themenbaum-tasten.ts` (Verhalten
 * unverändert). Die Komponente führt die Aktion aus und verbraucht die Taste (`preventDefault`),
 * außer bei `null`.
 *
 * ↑ ↓ wechseln, Pos1/Ende springen, → öffnet bzw. geht ins erste Kind, ← schließt bzw. geht zum
 * Elternknoten, Enter/Leertaste klappen; Enter auf einem Blatt ist die Standardaktion des
 * Moduls (`inhalte`). Tab und alles andere bleibt dem Browser.
 *
 * Kein Modul-Ordner (kein `ui-`-Präfix): das Register übergeht `_baum/`.
 */

/** Was die Regel von einem sichtbaren Eintrag braucht. `pfad` = Positionen ab der Wurzel. */
export interface BaumEintrag {
  readonly pfad: string;
  readonly eltern: string | null;
  /** Hat Kinder oder kann sie laden — dann trägt der Eintrag `aria-expanded`. */
  readonly aufklappbar: boolean;
  /** Nur bei offenen Einträgen gefüllt. */
  readonly kinder: readonly BaumEintrag[];
}

export type TastenAktion<E extends BaumEintrag = BaumEintrag> =
  | { readonly art: 'fokus'; readonly pfad: string }
  | { readonly art: 'aufklappen'; readonly eintrag: E }
  | { readonly art: 'zuklappen'; readonly eintrag: E }
  | { readonly art: 'umschalten'; readonly eintrag: E }
  | { readonly art: 'inhalte' }
  /** Die Taste gehört dem Baum, bewirkt hier aber nichts (etwa ↓ am Ende). */
  | { readonly art: 'nichts' };

const NICHTS = { art: 'nichts' } as const;

/** Was die Taste `taste` auf dem aktiven Eintrag (`aktiv`, Pfad) der sichtbaren `liste` bewirkt;
 *  `null`: die Taste gehört dem Browser. Ein unbekannter Pfad zählt als erster Eintrag. */
export function tastenAktion<E extends BaumEintrag>(
  taste: string, liste: readonly E[], aktiv: string, istOffen: (e: E) => boolean,
): TastenAktion<E> | null {
  const i = Math.max(0, liste.findIndex((s) => s.pfad === aktiv));
  const jetzt = liste[i];
  if (!jetzt) return null;
  const offen = jetzt.aufklappbar && istOffen(jetzt);
  const fokus = (e: BaumEintrag | undefined): TastenAktion<E> => (e ? { art: 'fokus', pfad: e.pfad } : NICHTS);
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

/** Alle sichtbaren Einträge in Lesereihenfolge — Grundlage der Pfeiltasten. */
export function flach<E extends { readonly kinder: readonly E[] }>(baum: readonly E[]): E[] {
  return baum.flatMap((e) => [e, ...flach(e.kinder)]);
}
