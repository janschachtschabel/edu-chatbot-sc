/**
 * Darstellung von `<boerdi-ui-upload>` (aus dem Element gelöst, Querschnitts-Review 2026-11-06, Q4):
 * aus einer Sicht auf den Zustand (`UploadSicht`; Werte, dazu die beiden Abläufe als lebende Objekte) die Knoten des Moduls — Wahl, Befund, Strukturdokument,
 * Übertragen, „nur lesen“. Das Element behält Zustand, Ereignisse und Fokus. Fremdtext (Ordner- und
 * Dateinamen) nur als `textContent`.
 */
import type { ModulKontext } from '../_vertrag/ui-block';
import { antwortDaten, type UploadAntwort } from './upload-antwort';
import { baueBaum } from './upload-baum';
import { dokumentErlaubt } from './upload-dokument';
import type { DokumentAblauf } from './upload-dokument-ablauf';
import { dokumentTeile } from './upload-dokument-ansicht';
import { type Erfassung, GRENZEN, type Grenzen } from './upload-erfassen';
import type { Sprache, UploadTexte } from './upload-texte';
import { ablageErlaubt, auswahl, maxBytesAblage } from './upload-uebertragen';
import type { UebertragenAblauf } from './upload-uebertragen-ablauf';
import { uebertragenTeile } from './upload-uebertragen-ansicht';
import { uebertragenTexte } from './upload-uebertragen-texte';

export interface UploadSicht {
  readonly t: UploadTexte;
  readonly sprache: Sprache;
  readonly daten: Record<string, unknown>;
  readonly kontext: ModulKontext | null;
  readonly zustand: Zustand;
  readonly erfassung: Erfassung<File> | null;
  readonly offen: Set<string>;
  readonly beschaeftigt: boolean;
  /** Rollen und „Ignorieren“ ruhen (Dokument wird gelesen oder eine Freigabe besteht). */
  readonly auswahlFest: boolean;
  readonly dokument: DokumentAblauf;
  readonly uebertragen: UebertragenAblauf;
  link(url: string): { href: string; hinweis: string };
}

export type Zustand = 'leer' | 'liest' | 'erfasst' | 'fehler';

export function grenzenAus(daten: Record<string, unknown>): Grenzen {
  const g = (daten['grenzen'] ?? {}) as Record<string, unknown>;
  const n = (v: unknown, vorgabe: number) => (typeof v === 'number' && v > 0 ? v : vorgabe);
  return {
    maxDateien: n(g['max_dateien'], GRENZEN.maxDateien),
    maxTiefe: n(g['max_tiefe'], GRENZEN.maxTiefe),
    maxBytesDatei: n(g['max_mb_datei'], GRENZEN.maxBytesDatei / 1024 / 1024) * 1024 * 1024,
  };
}

export function zusammenfassung(t: UploadTexte, a: UploadAntwort): string {
  return `${t.ordner(a.zahlen.ordner)}, ${t.dateien(a.zahlen.inhalte + a.zahlen.strukturdokumente)}`
    + (a.zahlen.ignoriert ? `, ${t.ignoriert(a.zahlen.ignoriert)}` : '');
}

export function ansichtTeile(s: UploadSicht): Node[] {
  const t = s.t;
  const titel = knoten('h3', 'u__titel', t.titel);
  if (s.kontext?.nurLesen) {
    // Querschnitts-Review M1/M2: ein Zug mitten im Übertragen schließt den Block, der Stapel läuft weiter
    // und bleibt sichtbar (Anhalten, Ergebnis) — nur ohne Antwortknopf.
    if (!nurLesenOhneStapel(s) && s.erfassung) return [titel, ablageTeil(s, s.erfassung, true)];
    return [titel, nurLesenZeile(s, t)];
  }
  const teile: Node[] = [titel];
  if (s.zustand !== 'erfasst' || !s.erfassung) {
    const zone = knoten('div', 'u__ablage');
    zone.dataset['ablage'] = '';
    zone.append(knoten('p', 'u__hinweis', s.zustand === 'liest' ? t.liest : t.ablage));
    const hinweis = typeof s.daten['hinweis'] === 'string' && s.daten['hinweis'].trim()
      ? s.daten['hinweis'] : t.hinweisLeer;
    teile.push(knoten('p', 'u__hinweis', hinweis), zone, waehler(s));
    if (s.zustand === 'fehler') {
      const meldung = knoten('p', 'u__hinweis', s.erfassung ? t.nichtsGefunden : t.leseFehler);
      meldung.tabIndex = -1;
      meldung.dataset['fokus'] = 's:fehler';
      teile.push(meldung);
    }
  } else {
    teile.push(...befund(s, s.erfassung));
  }
  teile.push(knoten('p', 'u__hinweis', datenschutz(s, t)));
  return teile;
}

/** Der Satz zur Datenweitergabe — er nennt, was das System gerade anbietet (Querschnitts-Review FE-3). */
function datenschutz(s: UploadSicht, t: UploadTexte): string {
  const dokument = dokumentErlaubt(s.daten);
  if (ablageErlaubt(s.daten)) return dokument ? t.datenschutzBeides : t.datenschutzAblage;
  return dokument ? t.datenschutzDokument : t.datenschutz;
}

/** Nur lesen ohne Übertragung in diesem Modul (dann gibt es nur die Zusammenfassung). */
export function nurLesenOhneStapel(s: UploadSicht): boolean {
  const phase = s.uebertragen.lauf?.phase;
  return !!s.kontext?.nurLesen && phase !== 'sendet' && phase !== 'fertig';
}

function nurLesenZeile(s: UploadSicht, t: UploadTexte): HTMLElement {
  const a = s.kontext?.antwort as UploadAntwort | null;
  const z = a?.zahlen;
  const text = a?.dokument ? t.nurLesenDokument(a.dokument.name, t.abschnitte(a.dokument.befund.abschnitte))
    : a?.ablage ? uebertragenTexte(s.sprache).nurLesen(a.ablage.abgelegt, a.ablage.gesamt)
      : z ? t.nurLesen(t.ordner(z.ordner), t.dateien(z.inhalte + z.strukturdokumente)) : t.nichtVerwendet;
  const zeile = knoten('p', 'u__hinweis', text);
  // Ziel des Fokus, wenn ein fokussierter Knopf mit dem Wechsel auf „nur lesen“ verschwindet.
  zeile.tabIndex = -1;
  zeile.dataset['fokus'] = 's:nurlesen';
  return zeile;
}

function waehler(s: UploadSicht): Node {
  const leiste = knoten('div', 'u__knoepfe');
  for (const [quelle, text] of [['ordner', s.t.ordnerWaehlen], ['dateien', s.t.dateienWaehlen]] as const) {
    leiste.append(knopf(text, { waehle: quelle }, quelle === 'ordner', s.zustand === 'liest'));
  }
  return leiste;
}

function befund(s: UploadSicht, e: Erfassung<File>): Node[] {
  const t = s.t;
  const a = antwortDaten(e, 'erfasst');
  const kopf = knoten('p', 'u__befund', zusammenfassung(s.t, a));
  kopf.tabIndex = -1;
  kopf.dataset['fokus'] = 's:befund';
  const teile: Node[] = [kopf];
  if (a.warnungen.length) {
    const g = grenzenAus(s.daten);
    const liste = knoten('ul', 'u__warnungen');
    for (const w of a.warnungen) {
      const wert = w === 'zu_viele' ? g.maxDateien : w === 'zu_tief' ? g.maxTiefe : Math.round(g.maxBytesDatei / 1024 / 1024);
      liste.append(knoten('li', undefined, t.warnung[w](wert)));
    }
    teile.push(liste);
  }
  teile.push(baueBaum(document, { erfassung: e, offen: s.offen, t, sprache: s.sprache, gesperrt: s.auswahlFest }));
  const gesperrt = s.beschaeftigt || s.dokument.laeuft() || s.uebertragen.laeuft();
  if (a.strukturdokument) {
    teile.push(...dokumentTeile({
      t, erlaubt: dokumentErlaubt(s.daten), lauf: s.dokument.lauf, gesperrt, beschaeftigt: s.beschaeftigt,
      knoten: (tag, klasse, text) => knoten(tag, klasse, text),
      knopf: (text, daten, haupt, aus) => knopf(text, daten, haupt, aus),
    }, a.strukturdokument.name));
  }
  if (ablageErlaubt(s.daten)) teile.push(ablageTeil(s, e));
  const leiste = knoten('div', 'u__knoepfe');
  // Ohne Unterordner gäbe es keinen Entwurf (das Backend antwortete nur „keine Unterordner“).
  if (e.wurzel.ordner.length) leiste.append(knopf(t.alsEntwurf, { antwort: 'ordner_als_entwurf' }, true, gesperrt));
  leiste.append(
    knopf(t.befundSenden, { antwort: 'erfasst' }, !e.wurzel.ordner.length, gesperrt),
    knopf(t.andereAuswahl, { zurueck: '1' }, false, s.dokument.laeuft() || s.uebertragen.laeuft()),
  );
  teile.push(leiste);
  if (gesperrt) teile.push(knoten('p', 'u__hinweis', t.beschaeftigt));
  return teile;
}

/** U3-3b: der Abschnitt „In deinen persönlichen Bereich in WLO übertragen“. */
function ablageTeil(s: UploadSicht, e: Erfassung<File>, nurLesen = false): HTMLElement {
  const max = maxBytesAblage(s.daten);
  const u = s.uebertragen;
  const teil = knoten('div', 'u__wlo');
  teil.append(...uebertragenTeile({
    t: uebertragenTexte(s.sprache), auswahl: auswahl(e, max), maxMb: Math.round(max / 1024 / 1024),
    lauf: u.lauf, ergebnisse: u.ergebnisse, anhalten: u.anhalten, ordnerVerweigert: u.ordnerVerweigert,
    vorgangFehlt: u.vorgang === 'fehlt', weiterLaeuft: u.weiterLaeuft, gesperrt: s.beschaeftigt || s.dokument.laeuft(),
    beschaeftigt: s.beschaeftigt, nurLesen, link: (url) => s.link(url),
    knoten: (tag, klasse, text) => knoten(tag, klasse, text),
    knopf: (text, daten, haupt, aus) => knopf(text, daten, haupt, aus),
  }, (n) => s.t.dateien(n)));
  return teil;
}

function knopf(text: string, daten: Record<string, string>, haupt = false, gesperrt = false): HTMLButtonElement {
  const b = knoten('button', haupt ? 'u__haupt' : undefined, text);
  b.type = 'button';
  b.disabled = gesperrt;
  for (const [k, v] of Object.entries(daten)) b.dataset[k] = v;
  b.dataset['fokus'] = `k:${Object.entries(daten).map(([k, v]) => `${k}=${v}`).join(',')}`;
  return b;
}

function knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (text !== undefined) e.textContent = text;
  return e;
}
