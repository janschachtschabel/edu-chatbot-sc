/**
 * Paket N3 (Plan 2026-11-19): die Inhalte am Punkt und die nicht zugeordneten — aufklappbar als
 * natives `<details>`/`<summary>` (Disclosure-Muster: Tab erreicht die Zusammenfassung, Enter und
 * Leertaste klappen, Vorleser sagen „zugeklappt“/„aufgeklappt“).
 *
 * Nicht im Baum: ein `treeitem` trägt keine eigenen Bedienelemente (die Pfeiltasten gehören dem
 * Baum). Die Zahl steht weiter am Eintrag (TG-3f); die Titel zeigt der gewählte Punkt unter dem
 * Baum bzw. im Detailfeld, die nicht zugeordneten stehen unter dem Baum. Titel sind Fremdtext:
 * `textContent`, `dir="auto"`. Ob aufgeklappt, merkt sich der Zustand (das Element zeichnet neu).
 */
import type { EntwurfInhalt, EntwurfKnoten } from './entwurf-regeln';
import type { EntwurfZustand } from './entwurf-zustand';

const P = 'ui-strukturentwurf';

function liste(zusammenfassung: string, inhalte: readonly EntwurfInhalt[], klasse: string, offen: boolean,
               merke: (offen: boolean) => void): HTMLDetailsElement {
  const abschnitt = document.createElement('details');
  abschnitt.className = `${P}__inhalte ${P}__${klasse}`;
  abschnitt.open = offen;
  abschnitt.addEventListener('toggle', () => merke(abschnitt.open));
  const kopf = document.createElement('summary');
  kopf.textContent = zusammenfassung;
  const ul = document.createElement('ul');
  // zweites Review, NIT 7: die Liste rollt ab ihrer Höhengrenze — per Tastatur erreichbar und benannt
  ul.tabIndex = 0;
  ul.setAttribute('aria-label', zusammenfassung);
  for (const e of inhalte) {
    const li = document.createElement('li');
    li.textContent = e.name;
    li.dir = 'auto';
    ul.append(li);
  }
  abschnitt.append(kopf, ul);
  return abschnitt;
}

/** Die Inhalte des gewählten Punkts — leer, wenn er keine trägt. */
export function inhalteDesPunkts(z: EntwurfZustand, knoten: EntwurfKnoten): Node[] {
  const inhalte = knoten.inhalte ?? [];
  if (!inhalte.length) return [];
  return [liste(z.texte.inhalteTitel(inhalte.length, z.daten.quelle === 'ordner'), inhalte, 'punktinhalte', z.inhalteOffen,
    (offen) => { z.inhalteOffen = offen; })];
}

/** Die Inhalte ohne Punkt („nicht zugeordnet: n“) — leer, wenn es keine gibt. */
export function nichtZugeordnet(z: EntwurfZustand): Node[] {
  const reste = z.reste;
  if (!reste.length) return [];
  return [liste(z.texte.nichtZugeordnet(reste.length, z.daten.quelle === 'ordner'), reste, 'reste', z.resteOffen,
    (offen) => { z.resteOffen = offen; })];
}
