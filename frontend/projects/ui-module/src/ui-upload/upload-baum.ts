/**
 * Der Ordnerbaum von `<boerdi-ui-upload>` (Paket U3-1a) als DOM — Disclosure-Muster: Ordner sind Knöpfe
 * mit `aria-expanded`, darunter verschachtelte Listen; jede Datei hat ein beschriftetes Auswahlfeld für
 * ihre Rolle. Bewusst kein ARIA-„tree“: dessen Einträge dürfen keine Bedienelemente enthalten, hier
 * braucht jede Datei eins; so geht alles mit Tab, Enter und Leertaste. Fremdtext (Namen) nur als
 * `textContent`. Systemdateien stehen nicht im Baum (sie zählen bei „ignoriert“).
 *
 * `data-fokus` trägt einen stabilen Schlüssel je Bedienelement: das Element zeichnet bei jeder
 * Änderung neu und setzt den Fokus danach wieder auf denselben Schlüssel.
 */
import type { Erfassung, OrdnerKnoten } from './upload-erfassen';
import { kannStrukturSein } from './upload-rollen';
import { groesse, type Sprache, type UploadTexte } from './upload-texte';

export interface BaumSicht<T> {
  readonly erfassung: Erfassung<T>;
  readonly offen: ReadonlySet<string>;
  readonly t: UploadTexte;
  readonly sprache: Sprache;
  /** Rollen und „ignorieren“ gesperrt — solange das Strukturdokument gelesen wird (Review U3-2, 3). */
  readonly gesperrt?: boolean;
}

function el<K extends keyof HTMLElementTagNameMap>(
  dok: Document, tag: K, klasse?: string, text?: string,
): HTMLElementTagNameMap[K] {
  const e = dok.createElement(tag);
  if (klasse) e.className = klasse;
  if (text !== undefined) e.textContent = text;
  return e;
}

function zaehle<T>(e: Erfassung<T>, k: OrdnerKnoten): number {
  return k.dateien.filter((i) => e.dateien[i].rolle !== 'ignorieren').length
    + k.ordner.reduce((s, o) => s + zaehle(e, o), 0);
}

function alleIgnoriert<T>(e: Erfassung<T>, k: OrdnerKnoten): boolean {
  return zaehle(e, k) === 0;
}

function dateiZeile<T>(dok: Document, sicht: BaumSicht<T>, index: number): HTMLLIElement | null {
  const d = sicht.erfassung.dateien[index];
  if (d.grund === 'system') return null;
  const li = el(dok, 'li', d.rolle === 'ignorieren' ? 'u__datei u__datei--ignoriert' : 'u__datei');
  li.append(el(dok, 'span', 'u__name', d.name), el(dok, 'span', 'u__zahl', groesse(sicht.sprache, d.groesse)));
  const auswahl = el(dok, 'select');
  auswahl.setAttribute('aria-label', sicht.t.rolleVon(d.name));
  auswahl.dataset['datei'] = String(index);
  auswahl.dataset['fokus'] = `d:${index}`;
  for (const rolle of ['inhalt', 'struktur', 'ignorieren'] as const) {
    const o = el(dok, 'option', undefined, sicht.t.rolle[rolle]);
    o.value = rolle;
    o.disabled = rolle === 'struktur' && !kannStrukturSein(d);
    o.selected = d.rolle === rolle;
    auswahl.append(o);
  }
  // Leere und zu große Dateien bleiben ignoriert — das Feld sagt es, statt still nichts zu tun.
  auswahl.disabled = !!d.grund || !!sicht.gesperrt;
  li.append(auswahl);
  return li;
}

function ordnerZeile<T>(dok: Document, sicht: BaumSicht<T>, k: OrdnerKnoten): HTMLLIElement {
  const offen = sicht.offen.has(k.pfad);
  const li = el(dok, 'li');
  const kopf = el(dok, 'div', 'u__ordner');
  const auf = el(dok, 'button', 'u__auf');
  auf.type = 'button';
  auf.setAttribute('aria-expanded', String(offen));
  auf.dataset['ordner'] = k.pfad;
  auf.dataset['fokus'] = `o:${k.pfad}`;
  const pfeil = el(dok, 'span', undefined, offen ? '▾ ' : '▸ ');
  pfeil.setAttribute('aria-hidden', 'true');
  auf.append(pfeil, dok.createTextNode(k.name || sicht.t.auswahl));
  kopf.append(auf, el(dok, 'span', 'u__zahl', sicht.t.dateien(zaehle(sicht.erfassung, k))));
  const ignoriert = alleIgnoriert(sicht.erfassung, k);
  const schalter = el(dok, 'button', 'u__leise', ignoriert ? sicht.t.wiederEinschliessen : sicht.t.alleIgnorieren);
  schalter.type = 'button';
  schalter.dataset['ignorieren'] = k.pfad;
  schalter.dataset['an'] = String(!ignoriert);
  schalter.dataset['fokus'] = `i:${k.pfad}`;
  schalter.disabled = !!sicht.gesperrt;
  // Sichtbar kurz, für Screenreader mit Ordner — sonst hießen alle Knöpfe gleich.
  const ordnerName = k.name || sicht.t.auswahl;
  schalter.setAttribute('aria-label', ignoriert ? sicht.t.wiederEinschliessenIn(ordnerName) : sicht.t.alleIgnorierenIn(ordnerName));
  kopf.append(schalter);
  li.append(kopf);
  if (offen) {
    const gruppe = el(dok, 'ul', 'u__gruppe');
    for (const o of k.ordner) gruppe.append(ordnerZeile(dok, sicht, o));
    for (const i of k.dateien) {
      const zeile = dateiZeile(dok, sicht, i);
      if (zeile) gruppe.append(zeile);
    }
    li.append(gruppe);
  }
  return li;
}

export function baueBaum<T>(dok: Document, sicht: BaumSicht<T>): HTMLUListElement {
  const ul = el(dok, 'ul', 'u__baum');
  ul.append(ordnerZeile(dok, sicht, sicht.erfassung.wurzel));
  return ul;
}
