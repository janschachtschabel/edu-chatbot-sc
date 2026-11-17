/**
 * Darstellung der Strukturdokumente in `<boerdi-ui-upload>` (Paket U3-2c): Hinweis, der Knopf
 * „Lesen lassen“, Fortschritt, Befund oder Fehler. Plan 2026-11-16, TG-1 (G-E4): ein neutraler Knopf
 * statt der Ziel-Knöpfe — was mit dem Dokument geschieht, entscheiden Ablauf oder KI danach. Aus dem
 * Element gelöst, damit es bei seiner einen Aufgabe bleibt; die Knoten baut das Element (`knoten`,
 * `knopf`), damit Fokus-Schlüssel und Gestalt überall gleich sind. Fremdtext (Dateiname) nur als
 * `textContent`.
 *
 * Plan 2026-11-16, TG-3e: mehrere markierte Dokumente — der Hinweis nennt alle, Fortschritt und
 * Fehler nennen das Dokument, an dem der Ablauf steht; nach einem Fehler gibt es neben „Noch einmal“
 * „Ohne dieses weiter“ (wenn es etwas Gelesenes oder ein weiteres Dokument gibt). Mit einem Dokument
 * sieht alles aus wie vorher.
 */
import { abschnitteZusammen, type DokumentLauf, wiederholbar } from './upload-dokument';
import { fehlerSatz, liestSatz, sendetSatz } from './upload-dokument-ablauf';
import type { UploadTexte } from './upload-texte';

export interface DokumentAnsicht {
  readonly t: UploadTexte;
  readonly erlaubt: boolean;
  readonly lauf: DokumentLauf | null;
  /** Knöpfe gesperrt (ein Zug läuft oder das Dokument wird gerade gelesen). */
  readonly gesperrt: boolean;
  readonly beschaeftigt: boolean;
  /** TG-3e: kann „Ohne dieses weiter“ etwas bewirken (`DokumentAblauf.ueberspringbar`)? */
  readonly ueberspringbar?: boolean;
  knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string, text?: string): HTMLElementTagNameMap[K];
  knopf(text: string, daten: Record<string, string>, haupt?: boolean, gesperrt?: boolean): HTMLButtonElement;
}

/** Review TG-1, m4: der Hinweis mit dem Dateinamen beschreibt „Lesen lassen“ (`aria-describedby`). */
const HINWEIS_ID = 'u-strukturdokument';

function fokussierbar<T extends HTMLElement>(e: T): T {
  e.tabIndex = -1;
  e.dataset['fokus'] = 's:dokument';
  return e;
}

/** Der Hinweis zu den markierten Dokumenten — einer wie vorher, mehrere mit allen Namen. */
function hinweisText(a: DokumentAnsicht, namen: readonly string[]): string {
  const { t } = a;
  const liste = namen.join(', ');
  if (namen.length > 1) return a.erlaubt ? t.strukturLesbarMehrere(liste) : t.strukturNichtLesbarMehrere(liste);
  return a.erlaubt ? t.strukturLesbar(liste) : t.strukturNichtLesbar(liste);
}

export function dokumentTeile(a: DokumentAnsicht, namen: readonly string[]): Node[] {
  const { t, lauf } = a;
  if (!a.erlaubt) return [a.knoten('p', 'u__hinweis', hinweisText(a, namen))];
  const hinweis = a.knoten('p', 'u__hinweis', hinweisText(a, namen));
  hinweis.id = HINWEIS_ID;
  const teile: Node[] = [hinweis];
  if (lauf?.phase === 'sendet' || lauf?.phase === 'liest') {
    const prozent = lauf.phase === 'sendet' ? Math.round(lauf.anteil * 100) : 100;
    const satz = lauf.phase === 'sendet' ? sendetSatz(t, prozent, lauf.stelle) : liestSatz(t, lauf.stelle);
    const balken = a.knoten('progress', 'u__fortschritt');
    balken.max = 100;
    if (lauf.phase === 'sendet') balken.value = prozent;   // beim Lesen unbestimmt
    balken.setAttribute('aria-label', satz);
    return [...teile, balken, fokussierbar(a.knoten('p', 'u__hinweis', satz))];
  }
  if (lauf?.phase === 'fertig') {
    const mehrere = lauf.antwort.dokumente?.length ?? 0;
    const abschnitte = t.abschnitte(abschnitteZusammen(lauf.antwort));
    const leiste = a.knoten('div', 'u__knoepfe');
    // TG-1: ein neutrales „Weiter“ — es schickt dieselbe Antwort, die sonst gleich ginge; der Name
    // sagt, was gesendet wird (Review TG-1, m4)
    const weiter = a.knopf(t.weiterNachLesen, { weiter: 'dokument' }, true, a.beschaeftigt);
    weiter.setAttribute('aria-label', mehrere > 1 ? t.weiterNachLesenNameMehrere : t.weiterNachLesenName);
    leiste.append(weiter);
    const befund = mehrere > 1 ? t.gelesenMehrere(mehrere, abschnitte) : t.gelesen(abschnitte);
    return [...teile, fokussierbar(a.knoten('p', 'u__befund', befund)), leiste];
  }
  if (lauf?.phase === 'fehler') {
    // Ohne `role="alert"` (wie beim Übertragen): angesagt hat der Ablauf schon über die Status-Zeile.
    teile.push(fokussierbar(a.knoten('p', 'u__fehler', fehlerSatz(t, lauf.code, lauf.stelle))));
    const nochmal = wiederholbar(lauf.code);
    if (!nochmal && !a.ueberspringbar) return teile;
    const leiste = a.knoten('div', 'u__knoepfe');
    if (nochmal) {
      const lesen = a.knopf(t.nochmal, { dokument: 'lesen' }, true, a.gesperrt);
      lesen.setAttribute('aria-describedby', HINWEIS_ID);
      leiste.append(lesen);
    }
    if (a.ueberspringbar && lauf.stelle) {
      // TG-3e: das gescheiterte auslassen, die übrigen lesen bzw. die gelesenen schicken
      const ohne = a.knopf(t.ohneWeiter, { dokument: 'ohne' }, !nochmal, a.gesperrt);
      ohne.setAttribute('aria-label', t.ohneWeiterName(lauf.stelle.name));
      leiste.append(ohne);
    }
    return [...teile, leiste];
  }
  const leiste = a.knoten('div', 'u__knoepfe');
  const lesen = a.knopf(t.lesenLassen, { dokument: 'lesen' }, true, a.gesperrt);
  lesen.setAttribute('aria-describedby', HINWEIS_ID);
  leiste.append(lesen);
  return [...teile, leiste];
}
