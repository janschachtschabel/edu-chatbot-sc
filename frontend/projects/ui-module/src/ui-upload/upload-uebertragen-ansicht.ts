/**
 * Darstellung des Übertragens in `<boerdi-ui-upload>` (Paket U3-3b): Angebot, Prüfen, Vorschau,
 * Senden, Ergebnisliste, Fehler. Wie `upload-dokument-ansicht.ts` baut das Element die Knoten
 * (`knoten`, `knopf`), damit Fokus-Schlüssel und Gestalt gleich sind. Der Stand je Datei steht als Text
 * UND Symbol (nie nur Farbe); Links kommen vom Backend und gehen durch `host.link` (fremde Seiten mit
 * Hinweis). Fremdtext (Datei-, Ordnernamen) nur als `textContent`.
 */
import type { ElementHost } from '../_nachladen/element-vertrag';
import { type Auswahl, type Ergebnis, MAX_STAPEL, nochmalSenden, type Plan, type Stand, wiederholbarAblage, zaehlung } from './upload-uebertragen';
import type { UebertragenLauf } from './upload-uebertragen-ablauf';
import { fehlerSatz, type UebertragenTexte } from './upload-uebertragen-texte';

export interface UebertragenAnsicht {
  readonly t: UebertragenTexte;
  readonly auswahl: Auswahl<File>;
  readonly maxMb: number;
  readonly lauf: UebertragenLauf | null;
  readonly ergebnisse: readonly Ergebnis[];
  readonly anhalten: boolean;
  readonly ordnerVerweigert: boolean;
  readonly vorgangFehlt: boolean;
  /** „Im Chat weitermachen“ wartet auf den Abschluss. */
  readonly weiterLaeuft: boolean;
  /** Ein Zug läuft oder etwas anderes im Modul (Dokument) — Knöpfe gesperrt. */
  readonly gesperrt: boolean;
  readonly beschaeftigt: boolean;
  /** Der Block ist nicht mehr offen: nur der Stand, kein Antwortknopf (Querschnitts-Review M1/M2). */
  readonly nurLesen?: boolean;
  link: ElementHost['link'];
  knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string, text?: string): HTMLElementTagNameMap[K];
  knopf(text: string, daten: Record<string, string>, haupt?: boolean, gesperrt?: boolean): HTMLButtonElement;
}

const SYMBOL: Record<Stand, string> = {
  wartet: '·', sendet: '↑', stored: '✓', dropped: '!', unverified: '?', failed: '✗', abgebrochen: '–',
};

function fokussierbar<T extends HTMLElement>(e: T): T {
  e.tabIndex = -1;
  e.dataset['fokus'] = 's:ablage';
  return e;
}

function balken(a: UebertragenAnsicht, anteil: number | null, satz: string): HTMLProgressElement {
  const b = a.knoten('progress', 'u__fortschritt');
  b.max = 100;
  // Nicht `data-ablage`: das ist die Marke der Ablagefläche (Review U3-3b, Befund 3).
  b.dataset['ablageBalken'] = '';
  if (anteil !== null) b.value = Math.round(anteil * 100);    // sonst unbestimmt
  b.setAttribute('aria-label', satz);
  return b;
}

/** Die Liste in einem benannten, per Tastatur rollbaren Bereich (bis 200 Einträge; Befund 9). */
function liste(a: UebertragenAnsicht, plan: Plan): HTMLElement {
  const bereich = a.knoten('div', 'u__ergebnis');
  bereich.setAttribute('role', 'region');
  bereich.setAttribute('aria-label', a.t.liste);
  bereich.tabIndex = 0;
  const ul = a.knoten('ul', 'u__ergebnis-liste');
  for (const e of plan.eintraege) {
    const ergebnis = a.ergebnisse[e.index] ?? { stand: 'wartet' as const };
    const li = a.knoten('li', `u__eintrag u__eintrag--${ergebnis.stand}`);
    const symbol = a.knoten('span', 'u__symbol', SYMBOL[ergebnis.stand]);
    symbol.setAttribute('aria-hidden', 'true');
    const stand = ergebnis.code && ergebnis.stand === 'failed'
      ? `${a.t.stand.failed}: ${fehlerSatz(a.t, ergebnis.code)}` : a.t.stand[ergebnis.stand];
    li.append(symbol, a.knoten('span', 'u__name', e.name), a.knoten('span', 'u__zahl', stand));
    const ziel = ergebnis.link ? a.link(ergebnis.link) : null;
    if (ziel?.href) {
      const anker = a.knoten('a', 'u__link', a.t.ansehen(e.name));
      anker.href = ziel.href;
      anker.target = '_blank';
      anker.rel = 'noopener noreferrer';
      if (ziel.hinweis) anker.title = ziel.hinweis;
      li.append(anker);
    }
    ul.append(li);
  }
  bereich.append(ul);
  return bereich;
}

function angebot(a: UebertragenAnsicht, dateien: (n: number) => string): Node[] {
  const { t, auswahl: aus } = a;
  const teile: Node[] = [];
  const n = aus.kandidaten.length;
  teile.push(a.knoten('p', 'u__hinweis', n ? t.angebot(dateien(n)) : t.keine));
  const weg = t.ausgelassen(aus.ohneArt, aus.zuGross, a.maxMb);
  if (weg) teile.push(a.knoten('p', 'u__hinweis', weg));
  if (n > MAX_STAPEL) teile.push(a.knoten('p', 'u__fehler', t.zuViele(MAX_STAPEL)));
  if (n) {
    const leiste = a.knoten('div', 'u__knoepfe');
    leiste.append(a.knopf(t.pruefen, { uebertragen: 'pruefen' }, false, a.gesperrt || n > MAX_STAPEL));
    teile.push(leiste);
  }
  return teile;
}

/** Ohne `role="alert"`: die Zeile entsteht bei jedem Zeichnen neu und würde jedes Mal wieder assertiv
 *  angesagt — angesagt wird sie einmal über die bleibende Status-Zeile (Querschnitts-Review FE-5). */
function fehlerZeile(a: UebertragenAnsicht, code: string): HTMLElement {
  return fokussierbar(a.knoten('p', 'u__fehler', fehlerSatz(a.t, code)));
}

export function uebertragenTeile(a: UebertragenAnsicht, dateien: (n: number) => string): Node[] {
  const { t, lauf } = a;
  const teile: Node[] = [a.knoten('h4', 'u__titel', t.titel)];
  if (!lauf) return [...teile, ...angebot(a, dateien)];
  if (lauf.phase === 'pruefen' || lauf.phase === 'vorbereiten') {
    const satz = lauf.phase === 'pruefen' ? t.prueft(lauf.fertig, lauf.gesamt) : t.bereitet;
    const anteil = lauf.phase === 'pruefen' ? lauf.fertig / Math.max(1, lauf.gesamt) : null;
    return [...teile, balken(a, anteil, satz), fokussierbar(a.knoten('p', 'u__hinweis', satz))];
  }
  if (lauf.phase === 'fehler') {
    teile.push(fehlerZeile(a, lauf.code));
    if (wiederholbarAblage(lauf.code) || lauf.code === 'nicht_gespeichert') {
      const leiste = a.knoten('div', 'u__knoepfe');
      leiste.append(a.knopf(t.pruefen, { uebertragen: 'pruefen' }, false, a.gesperrt));
      teile.push(leiste);
    }
    return teile;
  }
  const plan = lauf.plan;
  const ziel = plan.layout === 'ordner' && !a.ordnerVerweigert ? t.zielOrdner(plan.ordner) : t.zielFlach;
  if (lauf.phase === 'vorschau') {
    const kopf = fokussierbar(a.knoten('p', 'u__befund', ziel));
    const bytes = plan.eintraege.reduce((s, e) => s + e.groesse, 0);
    const leiste = a.knoten('div', 'u__knoepfe');
    leiste.append(
      a.knopf(t.jetzt, { uebertragen: 'los' }, true, a.gesperrt),
      a.knopf(t.abbrechen, { uebertragen: 'abbrechen' }, false, false),
    );
    return [...teile, kopf, a.knoten('p', 'u__hinweis', t.umfang(dateien(plan.eintraege.length), bytes)), liste(a, plan), leiste];
  }
  if (lauf.phase === 'sendet') {
    const satz = t.sendet(lauf.position, lauf.anzahl, Math.round(lauf.anteil * 100));
    const leiste = a.knoten('div', 'u__knoepfe');
    leiste.append(a.knopf(a.anhalten ? t.haeltAn : t.anhalten, { uebertragen: 'anhalten' }, false, a.anhalten));
    return [...teile, a.knoten('p', 'u__hinweis', ziel), balken(a, lauf.anteil, satz),
      fokussierbar(a.knoten('p', 'u__hinweis', satz)), liste(a, plan), leiste];
  }
  // fertig
  const z = zaehlung(a.ergebnisse);
  const kopf = lauf.halt ? fehlerZeile(a, lauf.halt) : fokussierbar(a.knoten('p', 'u__befund', t.fertig(z.abgelegt, a.ergebnisse.length)));
  teile.push(kopf, a.knoten('p', 'u__hinweis', ziel));
  if (a.ordnerVerweigert) teile.push(a.knoten('p', 'u__hinweis', t.ordnerVerweigert));
  if (a.vorgangFehlt) teile.push(a.knoten('p', 'u__hinweis', t.vorgangFehlt));
  teile.push(liste(a, plan));
  const leiste = a.knoten('div', 'u__knoepfe');
  // Nachsenden nur, wo es helfen kann: kein Halt oder ein heilbarer (Netz, Last) — Befund 6.
  const nochmal = nochmalSenden(a.ergebnisse).length > 0 && (!lauf.halt || wiederholbarAblage(lauf.halt));
  if (nochmal) leiste.append(a.knopf(t.nochmal, { uebertragen: 'nochmal' }, false, a.gesperrt || a.weiterLaeuft));
  if (!a.nurLesen) {
    leiste.append(a.knopf(t.weiter, { uebertragen: 'weiter' }, true, a.gesperrt || a.beschaeftigt || a.weiterLaeuft));
  }
  if (leiste.childNodes.length) teile.push(leiste);
  return teile;
}
