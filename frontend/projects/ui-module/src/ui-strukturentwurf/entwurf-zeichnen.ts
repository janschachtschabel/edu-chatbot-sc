/**
 * Die Teile des Strukturentwurfs als DOM (Paket BU-2; bis dahin das Template der Komponente,
 * Klassen und ARIA unverändert). Fremdtext steht immer als `textContent`; kein `innerHTML`, auch nicht
 * für die eigenen Symbole (Trusted Types, Querschnitts-Review Q-3).
 *
 * Bedienung: Knöpfe tragen `data-tat` (die Bearbeitung) und `data-fokus` (damit der Fokus nach dem
 * Neuzeichnen zurückfindet), Felder `data-feld`, Baumeinträge `data-id`. Das Element hört an einer
 * Stelle zu (`ui-strukturentwurf.element.ts`).
 *
 * Der Baum wird abgeglichen statt neu gebaut ({@link BaumZeichner}): ein Eintrag bleibt dasselbe
 * Element, solange es seinen Punkt gibt — sonst ersetzte der Fokus beim Mausdruck den Eintrag,
 * und der folgende Klick fiele ins Leere; Vorleser sagten den Eintrag nach jedem Aufklappen neu an.
 */
import type { EntwurfEintrag } from './entwurf-ansicht';
import { strukturHinweise } from './entwurf-pruefung';
import { BESCHREIBUNG_ZEICHEN, TITEL_ZEICHEN } from './entwurf-regeln';
import { PFEIL, SYMBOL, svgSymbol, type Zeichen } from './entwurf-symbole';
import type { EntwurfZustand } from './entwurf-zustand';

const P = 'ui-strukturentwurf';

/** Kennung im Shadow Root: `se-<block>-<teil>` wie zuvor. */
export type Kennung = (teil: string) => string;

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, klasse = '', text = ''): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (text) e.textContent = text;
  return e;
}

function knopf(text: string, tat: string, klasse = `${P}__knopf`): HTMLButtonElement {
  const b = el('button', klasse, text);
  b.type = 'button';
  b.dataset['tat'] = tat;
  b.dataset['fokus'] = tat;
  return b;
}

function symbol(zeichen: Zeichen): HTMLSpanElement {
  const s = el('span', 'bb-icon');
  s.append(svgSymbol(zeichen));                         // kein innerHTML (Trusted Types, Q-3)
  return s;
}

/** Kopf, Angaben, Kürzungshinweis und „Alles auf-/zuklappen“ — alles vor dem Baum. */
export function vorDemBaum(z: EntwurfZustand, k: Kennung): Node[] {
  const t = z.texte;
  const d = z.daten;
  const kopf = el('div', `${P}__kopf`);
  kopf.id = k('kopf');
  const icon = symbol(SYMBOL);
  icon.setAttribute('aria-hidden', 'true');
  kopf.append(icon, el('span', `${P}__marke`, t.marke[d.quelle] ?? ''), ` ${d.titel}`);
  const angaben = el('p', `${P}__neben ${P}__angaben`);
  if (d.fach) angaben.append(el('span', '', `${t.fach}: ${d.fach}`));
  if (d.bildungsstufe) angaben.append(el('span', '', `${t.stufe}: ${d.bildungsstufe}`));
  angaben.append(el('span', '', t.punkte(z.zahl)));
  const teile: Node[] = [kopf, angaben];
  if (d.gekuerzt) teile.push(el('p', `${P}__hinweis`, d.quelle === 'ordner' ? t.gekuerztOrdner : t.gekuerzt));
  if (z.struktur.length && z.hatKinder) {
    teile.push(knopf(z.allesOffen ? t.allesZu : t.allesAuf, 'alles', `${P}__knopf ${P}__alles`));
  }
  return teile;
}

/** R4: Hinweise nach dem Leitfaden — zugeklappt, nach jeder Bearbeitung neu gerechnet; ob der
 *  Abschnitt offen ist, merkt sich der Zustand (das Element zeichnet neu). */
function hinweise(z: EntwurfZustand): Node[] {
  const liste = strukturHinweise(z.struktur);
  if (!liste.length) return [];
  const t = z.texte;
  const abschnitt = el('details', `${P}__hinweise`);
  abschnitt.open = z.hinweiseOffen;
  abschnitt.addEventListener('toggle', () => { z.hinweiseOffen = abschnitt.open; });
  const ul = el('ul');
  for (const h of liste) ul.append(el('li', '', t.strukturHinweis(h)));
  // Querschnitts-Review, Befund 5: die Überschrift zählt ALLE Hinweise, auch die nicht gezeigten
  const letzter = liste.at(-1);
  const gesamt = letzter?.code === 'weitere' ? liste.length - 1 + letzter.anzahl : liste.length;
  abschnitt.append(el('summary', '', t.hinweiseTitel(gesamt)), ul);
  return [abschnitt];
}

/** Leer-Hinweis, Statuszeile und Leiste bzw. Leseansicht des aktiven Punkts. */
export function nachDemBaum(z: EntwurfZustand, k: Kennung): Node[] {
  const t = z.texte;
  const teile: Node[] = [];
  if (!z.struktur.length) teile.push(el('p', `${P}__leer`, t.leer));
  if (z.status) {
    const s = el('p', `${P}__status`, z.status);
    s.tabIndex = -1;
    s.dataset['fokus'] = 'status';
    teile.push(s);
  }
  teile.push(...hinweise(z));
  const a = z.aktiv;
  if (!z.nurLesen && a) {
    const leiste = el('div', `${P}__aktionen`);
    leiste.setAttribute('role', 'group');
    leiste.setAttribute('aria-label', t.bearbeiten(a.knoten.titel));
    const ziel = el('span', `${P}__ziel`, a.knoten.titel);
    ziel.setAttribute('aria-hidden', 'true');
    // Review U2, Befund 10/14: der Fokus bleibt am Knopf; die Tasten gelten im Baum (Hinweis unten).
    leiste.append(ziel, knopf(t.unterpunkt, 'kind'), knopf(t.danach, 'danach'), knopf(t.hoch, 'hoch'),
      knopf(t.runter, 'runter'), knopf(t.ein, 'ein'), knopf(t.aus, 'aus'), knopf(t.loeschen, 'loeschen'),
      knopf(t.rueckgaengig, 'rueckgaengig'));
    teile.push(leiste);
  } else if (!z.nurLesen) {
    const leiste = el('div', `${P}__aktionen`);
    const erster = knopf(t.ersterPunkt, 'erster');
    erster.id = k('erster');
    leiste.append(erster);
    teile.push(leiste);
  } else if (a) {
    const lesen = el('div', `${P}__details ${P}__details--lesen`);
    lesen.append(el('p', `${P}__ziel`, a.knoten.titel), el('p', '', a.knoten.beschreibung || t.keineBeschreibung));
    if (a.knoten.keywords?.length) lesen.append(el('p', `${P}__neben`, `${t.schlagworte}: ${a.knoten.keywords.join(', ')}`));
    teile.push(lesen);
  }
  return teile;
}

function feld(beschriftung: string, eingabe: HTMLInputElement | HTMLTextAreaElement, ...mehr: Node[]): HTMLLabelElement {
  const l = el('label', `${P}__feld`);
  l.append(el('span', '', beschriftung), eingabe, ...mehr);
  return l;
}

/** Das Detailfeld des aktiven Punkts (Titel, Beschreibung, Schlagworte) — nur bearbeitbar. */
export function details(z: EntwurfZustand, k: Kennung): Node[] {
  const a = z.aktiv;
  if (z.nurLesen || !a) return [];
  const t = z.texte;
  const box = el('div', `${P}__details`);
  box.setAttribute('role', 'group');
  box.setAttribute('aria-label', t.details(a.knoten.titel));
  const titel = el('input');
  titel.type = 'text';
  titel.id = k('titel');
  titel.value = a.knoten.titel;
  titel.maxLength = TITEL_ZEICHEN;
  titel.dataset['feld'] = 'titel';
  const beschreibung = el('textarea');
  beschreibung.rows = 2;
  beschreibung.value = a.knoten.beschreibung ?? '';
  beschreibung.maxLength = BESCHREIBUNG_ZEICHEN;
  beschreibung.dataset['feld'] = 'beschreibung';
  beschreibung.dataset['fokus'] = 'beschreibung';
  const kw = el('input');
  kw.type = 'text';
  kw.value = z.kwText ?? (a.knoten.keywords ?? []).join(', ');
  kw.setAttribute('aria-describedby', k('kw-hinweis'));
  kw.dataset['feld'] = 'keywords';
  kw.dataset['fokus'] = 'keywords';
  const hinweis = el('span', `${P}__neben`, t.kwHinweis);
  hinweis.id = k('kw-hinweis');
  box.append(feld(t.titel, titel), feld(t.beschreibung, beschreibung), feld(t.keywords, kw, hinweis));
  return [box];
}

/** Bedienhinweis und Abschluss (Übernehmen, Herunterladen). */
export function abschluss(z: EntwurfZustand, beschaeftigt: boolean): Node[] {
  const t = z.texte;
  const teile: Node[] = [];
  if (!z.nurLesen) teile.push(el('p', `${P}__hinweis`, t.hinweis));
  const ende = el('div', `${P}__abschluss`);
  if (!z.nurLesen) {
    const haupt = knopf(t.uebernehmen, 'uebernehmen', `${P}__knopf ${P}__knopf--haupt`);
    if (beschaeftigt) haupt.setAttribute('aria-disabled', 'true');
    ende.append(haupt);
  }
  ende.append(knopf(t.json, 'json'), knopf(t.markdown, 'md'));
  teile.push(ende);
  return teile;
}

/** Gleicht den Baum mit der Ansicht ab: Einträge bleiben dieselben Elemente je Punkt. */
export class BaumZeichner {
  private readonly eintraege = new Map<string, HTMLLIElement>();

  constructor(readonly wurzel: HTMLUListElement) {}

  zeichne(z: EntwurfZustand, k: Kennung): void {
    const aktiv = z.aktiv?.knoten.id ?? null;
    const gesehen = new Set<string>();
    this.liste(this.wurzel, z.baum, z, k, aktiv, gesehen);
    for (const id of [...this.eintraege.keys()]) if (!gesehen.has(id)) this.eintraege.delete(id);
  }

  /** Nur den aktiven Eintrag umsetzen (beim Fokus): nichts wird ersetzt. */
  markiere(aktiv: string | null): void {
    for (const [id, li] of this.eintraege) {
      li.tabIndex = id === aktiv ? 0 : -1;
      li.setAttribute('aria-selected', String(id === aktiv));
    }
  }

  private liste(ul: HTMLUListElement, liste: readonly EntwurfEintrag[], z: EntwurfZustand, k: Kennung,
                aktiv: string | null, gesehen: Set<string>): void {
    liste.forEach((e, i) => {
      gesehen.add(e.knoten.id);
      const li = this.eintrag(e, z, k, aktiv, gesehen);
      const jetzt = ul.children[i] ?? null;
      if (jetzt !== li) ul.insertBefore(li, jetzt);
    });
    while (ul.children.length > liste.length) ul.lastElementChild?.remove();
  }

  private eintrag(e: EntwurfEintrag, z: EntwurfZustand, k: Kennung, aktiv: string | null,
                  gesehen: Set<string>): HTMLLIElement {
    const id = e.knoten.id;
    let li = this.eintraege.get(id);
    if (!li) {
      li = el('li', `${P}__eintrag`);
      li.setAttribute('role', 'treeitem');
      li.dataset['id'] = id;
      this.eintraege.set(id, li);
    }
    li.id = k(`k-${id}`);
    li.setAttribute('aria-labelledby', k(`n-${id}`));
    if (e.knoten.ausstehend) li.setAttribute('aria-describedby', k(`a-${id}`));
    else li.removeAttribute('aria-describedby');
    li.setAttribute('aria-level', String(e.ebene));
    li.setAttribute('aria-setsize', String(e.setsize));
    li.setAttribute('aria-posinset', String(e.posinset));
    const offen = e.aufklappbar && z.istOffen(e);
    if (e.aufklappbar) li.setAttribute('aria-expanded', String(offen));
    else li.removeAttribute('aria-expanded');
    li.tabIndex = id === aktiv ? 0 : -1;
    li.setAttribute('aria-selected', String(id === aktiv));

    const zeile = el('span', `${P}__zeile`);
    const pfeil = el('span', `${P}__pfeil${offen ? ` ${P}__pfeil--offen` : ''}`);
    pfeil.setAttribute('aria-hidden', 'true');
    if (e.aufklappbar) pfeil.append(symbol(PFEIL));
    const titel = el('span', `${P}__titel`, e.knoten.titel);
    titel.id = k(`n-${id}`);
    zeile.append(pfeil, titel);
    if (e.knoten.ausstehend) {
      const aus = el('span', `${P}__neben ${P}__ausstehend`, z.texte.ausstehend);
      aus.id = k(`a-${id}`);
      zeile.append(aus);
    }
    const alt = li.firstElementChild;
    if (alt) li.replaceChild(zeile, alt);
    else li.append(zeile);

    // Direkt unter dem Eintrag (nicht per `:scope`-Selektor — den werten nicht alle Umgebungen aus).
    let gruppe = [...li.children].find((c): c is HTMLUListElement => c.tagName === 'UL');
    if (e.kinder.length) {
      if (!gruppe) {
        gruppe = el('ul', `${P}__gruppe`);
        gruppe.setAttribute('role', 'group');
        li.append(gruppe);
      }
      this.liste(gruppe, e.kinder, z, k, aktiv, gesehen);
    } else {
      gruppe?.remove();
    }
    return li;
  }
}
