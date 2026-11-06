/**
 * Darstellung des Strukturdokuments in `<boerdi-ui-upload>` (Paket U3-2c): Hinweis, Ziel-Knöpfe
 * (eine Liste, Plan O-26), Fortschritt, Befund oder Fehler. Aus dem Element gelöst, damit es bei
 * seiner einen Aufgabe bleibt; die Knoten baut das Element (`knoten`, `knopf`), damit Fokus-Schlüssel
 * und Gestalt überall gleich sind. Fremdtext (Dateiname) nur als `textContent`.
 */
import { DOKUMENT_ZIELE, type DokumentLauf, wiederholbar } from './upload-dokument';
import { dokumentFehlerSatz, type UploadTexte } from './upload-texte';

export interface DokumentAnsicht {
  readonly t: UploadTexte;
  readonly erlaubt: boolean;
  readonly lauf: DokumentLauf | null;
  /** Knöpfe gesperrt (ein Zug läuft oder das Dokument wird gerade gelesen). */
  readonly gesperrt: boolean;
  readonly beschaeftigt: boolean;
  knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string, text?: string): HTMLElementTagNameMap[K];
  knopf(text: string, daten: Record<string, string>, haupt?: boolean, gesperrt?: boolean): HTMLButtonElement;
}

function fokussierbar<T extends HTMLElement>(e: T): T {
  e.tabIndex = -1;
  e.dataset['fokus'] = 's:dokument';
  return e;
}

export function dokumentTeile(a: DokumentAnsicht, name: string): Node[] {
  const { t, lauf } = a;
  if (!a.erlaubt) return [a.knoten('p', 'u__hinweis', t.strukturNichtLesbar(name))];
  const teile: Node[] = [a.knoten('p', 'u__hinweis', t.strukturLesbar(name))];
  if (lauf?.phase === 'sendet' || lauf?.phase === 'liest') {
    const prozent = lauf.phase === 'sendet' ? Math.round(lauf.anteil * 100) : 100;
    const satz = lauf.phase === 'sendet' ? t.sendet(prozent) : t.liestDokument;
    const balken = a.knoten('progress', 'u__fortschritt');
    balken.max = 100;
    if (lauf.phase === 'sendet') balken.value = prozent;   // beim Lesen unbestimmt
    balken.setAttribute('aria-label', satz);
    return [...teile, balken, fokussierbar(a.knoten('p', 'u__hinweis', satz))];
  }
  if (lauf?.phase === 'fertig') {
    const abschnitte = t.abschnitte(lauf.antwort.dokument?.befund.abschnitte ?? 0);
    const leiste = a.knoten('div', 'u__knoepfe');
    leiste.append(a.knopf(t.weiter[lauf.ziel], { weiter: lauf.ziel }, true, a.beschaeftigt));
    return [...teile, fokussierbar(a.knoten('p', 'u__befund', t.gelesen(abschnitte))), leiste];
  }
  if (lauf?.phase === 'fehler') {
    // Ohne `role="alert"` (wie beim Übertragen): angesagt hat der Ablauf schon über die Status-Zeile.
    teile.push(fokussierbar(a.knoten('p', 'u__fehler', dokumentFehlerSatz(t, lauf.code))));
    if (!wiederholbar(lauf.code)) return teile;
  }
  const leiste = a.knoten('div', 'u__knoepfe');
  for (const ziel of DOKUMENT_ZIELE) {
    const text = lauf?.phase === 'fehler' && lauf.ziel === ziel ? t.nochmal : t.ausDokument[ziel];
    leiste.append(a.knopf(text, { dokument: ziel }, true, a.gesperrt));
  }
  return [...teile, leiste];
}
