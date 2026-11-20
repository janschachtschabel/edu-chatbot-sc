/**
 * Plan 2026-11-19, A6 (E7): „Gelesener Text“ — die Rückkontrolle beim Entwurf aus einem Dokument. Je
 * Dokument ein natives `<details>` unter dem Kopf (Disclosure-Muster wie die Inhalte, N3: Tab
 * erreicht die Zusammenfassung, Enter und Leertaste klappen, Vorleser sagen „zugeklappt“/
 * „aufgeklappt“), eingeklappt; aufgeklappt Weg, Abschnittstitel und Anfang des gelesenen Texts.
 *
 * Name, Titel und Anfang sind Fremdtext: `textContent`, `dir="auto"`. Ob aufgeklappt, merkt sich der
 * Zustand (das Element zeichnet neu). Nur Anzeige — `gelesen` geht nicht in die Antwort.
 */
import type { EntwurfGelesen } from './entwurf-export';
import { el } from './entwurf-zeichnen';
import type { EntwurfZustand } from './entwurf-zustand';

const P = 'ui-strukturentwurf';

function abschnitt(z: EntwurfZustand, g: EntwurfGelesen, nr: number): HTMLDetailsElement {
  const t = z.texte;
  const box = el('details', `${P}__gelesen`);
  box.open = z.gelesenOffen.has(nr);
  box.addEventListener('toggle', () => {
    const offen = new Set(z.gelesenOffen);
    if (box.open) offen.add(nr);
    else offen.delete(nr);
    z.gelesenOffen = offen;
  });
  // Review A, NIT 14: der Name ist Fremdtext — isoliert (<bdi>); „anzeigen“ sagt der Zustand
  // (Vorleser: „zugeklappt“). NIT 15: `data-fokus`, damit der Fokus das Neuzeichnen übersteht.
  const [vor, nach] = t.gelesenTitel(g.zeichen);
  const kopf = el('summary', '', vor);
  kopf.dataset['fokus'] = `gelesen-${nr}`;
  kopf.append(el('bdi', '', g.name), nach);
  box.append(kopf, el('p', `${P}__gelesen-weg`, t.gelesenWeg[g.weg] ?? ''));
  if (g.abschnitte.length) {
    const ul = el('ul', `${P}__gelesen-abschnitte`);
    ul.setAttribute('aria-label', t.gelesenAbschnitte);
    for (const titel of g.abschnitte) {
      const li = el('li', '', titel);
      li.dir = 'auto';
      ul.append(li);
    }
    box.append(ul);
  }
  // Der Anfang rollt ab seiner Höhengrenze — per Tastatur erreichbar und benannt (wie die Inhalte);
  // Review A, MINOR 8: als Bereich (`role="region"`), ein <p> trägt keinen Namen.
  const anfang = el('div', `${P}__gelesen-anfang`, g.anfang);
  anfang.dir = 'auto';
  anfang.tabIndex = 0;
  anfang.setAttribute('role', 'region');
  anfang.dataset['fokus'] = `gelesen-anfang-${nr}`;
  anfang.setAttribute('aria-label', t.gelesenAnfang(g.name));
  box.append(anfang);
  return box;
}

/** Je gelesenem Dokument ein eingeklappter Abschnitt — leer ohne `gelesen`. */
export function gelesenAbschnitte(z: EntwurfZustand): Node[] {
  return (z.daten.gelesen ?? []).map((g, nr) => abschnitt(z, g, nr));
}
