/**
 * Darstellung von „Hier im Chat“ in `<boerdi-ui-upload>` (Plan 2026-11-17, Paket U4) — löst die
 * Ansicht „Lesen lassen“ (U3-2c, TG-3e) ab: Fortschritt „Datei k von n“ mit „Nach dieser Datei
 * anhalten“, Fehler je Datei als eigener Satz mit „Noch einmal versuchen“ (wo es hilft) und „Ohne diese
 * weiter“, das Ende (Sitzungsgrenze, angehalten) mit „Mit den gelesenen weiter“ bzw. „Nur Namen
 * senden“, und — wenn gerade ein Zug läuft — die fertige Antwort mit „Weiter“. Nach einem Fehler oder
 * Ende mit gelesenen Dateien sagt ein Satz, wie lange sie hier bleiben. Die Knoten baut das Element
 * (`knoten`, `knopf`); Fremdtext (Dateiname) nur als `textContent`.
 */
import { type ChatLauf, wiederholbar } from './upload-chat';
import { fehlerSatz, sendetSatz } from './upload-chat-ablauf';
import type { UploadTexte } from './upload-texte';

export interface ChatAnsicht {
  readonly t: UploadTexte;
  readonly lauf: ChatLauf;
  /** „Nach dieser Datei anhalten“ ist gedrückt. */
  readonly anhalten: boolean;
  /** Wie lange gelesene Dateien hier bleiben (`grenzen.lokal_aufbewahrung_h`). */
  readonly aufbewahrungH: number;
  /** Knöpfe gesperrt (ein Zug läuft). */
  readonly beschaeftigt: boolean;
  knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string, text?: string): HTMLElementTagNameMap[K];
  knopf(text: string, daten: Record<string, string>, haupt?: boolean, gesperrt?: boolean): HTMLButtonElement;
}

const FEHLER_ID = 'u-chat-fehler';

function beschrieben(b: HTMLButtonElement): HTMLButtonElement {
  b.setAttribute('aria-describedby', FEHLER_ID);
  return b;
}

function fokussierbar<T extends HTMLElement>(e: T): T {
  e.tabIndex = -1;
  e.dataset['fokus'] = 's:chat';
  return e;
}

export function chatTeile(a: ChatAnsicht): Node[] {
  const { t, lauf } = a;
  const teile: Node[] = [a.knoten('h4', 'u__titel', t.ort.chat)];
  if (lauf.phase === 'sendet' || lauf.phase === 'liest') {
    const prozent = lauf.phase === 'sendet' ? Math.round(lauf.anteil * 100) : 100;
    const satz = lauf.phase === 'sendet' ? sendetSatz(t, prozent, lauf.stelle) : t.liestDatei(lauf.stelle.nr, lauf.stelle.von);
    const balken = a.knoten('progress', 'u__fortschritt');
    balken.max = 100;
    balken.dataset['chatBalken'] = '';
    if (lauf.phase === 'sendet') balken.value = prozent;   // beim Lesen unbestimmt
    // Festes Label; den Wert (Prozent) meldet das Element selbst (zweites Review, 12)
    balken.setAttribute('aria-label', t.dateiVon(lauf.stelle.nr, lauf.stelle.von));
    // Wie beim Übertragen: eine halb gesendete Datei abzubrechen ließe offen, ob sie angekommen ist
    const leiste = a.knoten('div', 'u__knoepfe');
    leiste.append(a.knopf(a.anhalten ? t.haeltAn : t.anhalten, { chat: 'anhalten' }, false, a.anhalten));
    return [...teile, balken, fokussierbar(a.knoten('p', 'u__hinweis', satz)), leiste];
  }
  if (lauf.phase === 'fertig') {
    // Nur sichtbar, solange ein Zug läuft: dieselbe Antwort, die sonst gleich ginge
    const weiter = a.knopf(t.weiterNachLesen, { chat: 'weiter' }, true, a.beschaeftigt);
    weiter.setAttribute('aria-label', t.weiterNachLesenName);
    const leiste = a.knoten('div', 'u__knoepfe');
    leiste.append(weiter);
    return [...teile, fokussierbar(a.knoten('p', 'u__befund', t.gelesenWartet(lauf.antwort.dateien?.length ?? 0))), leiste];
  }
  const gelesen = lauf.bisher.length;
  const frist = gelesen ? [a.knoten('p', 'u__hinweis', t.bleibenHier(a.aufbewahrungH))] : [];
  const leiste = a.knoten('div', 'u__knoepfe');
  if (lauf.phase === 'halt') {
    const satz = lauf.grund === 'grenze'
      ? `${fehlerSatz(t, lauf.code, lauf.stelle)} ${gelesen ? t.weiterOderNamen : t.nurNamenRest}`
      : t.angehalten(t.dateien(gelesen));
    const zeile = fokussierbar(a.knoten('p', lauf.grund === 'grenze' ? 'u__fehler' : 'u__befund', satz));
    zeile.id = FEHLER_ID;
    if (gelesen) leiste.append(beschrieben(a.knopf(t.mitGelesenen, { chat: 'gelesene' }, true, a.beschaeftigt)));
    // „Nur Namen senden“, wo der Satz es nennt — und angehalten ohne gelesene (sonst bliebe nur „Andere Auswahl“)
    if (lauf.grund === 'grenze' || !gelesen) leiste.append(beschrieben(a.knopf(t.nurNamen, { namen: '1' }, !gelesen, a.beschaeftigt)));
    return [...teile, zeile, ...frist, leiste];
  }
  // Ohne `role="alert"`: angesagt hat der Ablauf schon über die bleibende Status-Zeile.
  // Die Knöpfe beschreibt der Fehlersatz mit dem Dateinamen (`aria-describedby`) — ein eigener Name
  // enthielte die sichtbare Beschriftung nicht (WCAG 2.5.3).
  const fehler = fokussierbar(a.knoten('p', 'u__fehler', fehlerSatz(t, lauf.code, lauf.stelle)));
  fehler.id = FEHLER_ID;
  const nochmal = wiederholbar(lauf.code);
  if (nochmal) leiste.append(beschrieben(a.knopf(t.nochmal, { chat: 'nochmal' }, true, a.beschaeftigt)));
  leiste.append(beschrieben(a.knopf(t.ohneWeiter, { chat: 'ohne' }, !nochmal, a.beschaeftigt)));
  return [...teile, fehler, ...frist, leiste];
}
