/**
 * Darstellung von `<boerdi-ui-upload>` (aus dem Element gelöst, Querschnitts-Review 2026-11-06, Q4):
 * aus einer Sicht auf den Zustand (`UploadSicht`; Werte, dazu die beiden Abläufe als lebende Objekte)
 * die Knoten des Moduls — Wahl, Befund, „Wo sollen sie verarbeitet werden?“, „Hier im Chat“,
 * Übertragen nach WLO, „nur lesen“. Das Element behält Zustand, Ereignisse und Fokus. Fremdtext
 * (Ordner- und Dateinamen) nur als `textContent`.
 *
 * Plan 2026-11-17, Paket U4: ein Weg — nach der Auswahl die Frage nach dem Ort (Chips), ein
 * Hauptknopf, daneben „Nur die Dateinamen senden“ und „Andere Auswahl“. Läuft „Hier im Chat“ oder die
 * Übertragung, steht statt der Frage deren Fortschritt. Plan 2026-11-20, P2: der Hauptknopf heißt je Ort
 * „Hier lesen“ bzw. „Weiter zur Vorschau“ (er legt noch nichts ab — ablegen tut erst der Knopf der
 * Vorschau, „In WLO ablegen und erschließen“ / „In WLO ablegen“).
 */
import type { ModulKontext } from '../_vertrag/ui-block';
import { antwortDaten, type UploadAntwort } from './upload-antwort';
import { baueBaum } from './upload-baum';
import type { ChatAblauf } from './upload-chat-ablauf';
import { chatTeile } from './upload-chat-ansicht';
import { type Erfassung, GRENZEN, type Grenzen } from './upload-erfassen';
import {
  chatOhneAnmeldung, erschliessenVorgabe, flowDa, gewaehlt, hakenVorgesehen, lokaleAuswahl, lokaleGrenzen, type Ort, type Orte,
  orteFuer,
} from './upload-orte';
import { datenschutzSatz, orteTeile } from './upload-orte-ansicht';
import type { Sprache, UploadTexte } from './upload-texte';
import { auswahl, maxBytesAblage, zaehlung } from './upload-uebertragen';
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
  /** Rollen und „Ignorieren“ ruhen (es wird hochgeladen, oder eine Freigabe besteht). */
  readonly auswahlFest: boolean;
  /** Der Ort, den die Person angeklickt hat (`null`: die Vorauswahl gilt). */
  readonly ort: Ort | null;
  /** P2: das Häkchen „Metadaten von WLO erzeugen lassen“, wie die Person es gestellt hat (`null`: die Vorgabe). */
  readonly erschliessen: boolean | null;
  readonly chat: ChatAblauf;
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

/** Der Ort, den „Hochladen“ für diese Sicht nimmt — `null`, wenn nur die Namen gehen. */
export function wahlFuer(s: Pick<UploadSicht, 'daten' | 'erfassung' | 'ort'>): 'chat' | 'wlo' | null {
  return s.erfassung ? gewaehlt(orteFuer(s.daten, s.erfassung), s.ort) : null;
}

/** P2: ist das Häkchen gesetzt — die Wahl der Person, sonst die Vorgabe des Blocks (`erschliessen`)? */
export function hakenGesetzt(s: Pick<UploadSicht, 'daten' | 'erschliessen'>): boolean {
  return s.erschliessen ?? erschliessenVorgabe(s.daten);
}

/** P2: was `vorbereiten` als `erschliessen` schickt — nur mit Metadaten-Flow und gesetztem Häkchen; Review P2,
 *  Befund 1: nur, wenn der Schritt das Häkchen vorsieht (sonst `false`: nur ablegen). */
export function erschliessenFuer(s: Pick<UploadSicht, 'daten' | 'erschliessen'>, orte: Orte): boolean {
  return hakenVorgesehen(s.daten) && flowDa(orte.wlo) && hakenGesetzt(s);
}

/** Läuft gerade ein Weg (oder steht sein Ergebnis da)? Dann zeigt das Modul ihn statt der Frage.
 *  Ein Fehler der Übertragung (vor dem Senden) bringt die Frage zurück — „Hochladen“ versucht neu. */
export function wegAktiv(s: Pick<UploadSicht, 'chat' | 'uebertragen'>): boolean {
  return !!s.chat.lauf || (!!s.uebertragen.lauf && s.uebertragen.lauf.phase !== 'fehler');
}

export function ansichtTeile(s: UploadSicht): Node[] {
  const t = s.t;
  const titel = knoten('h3', 'u__titel', t.titel);
  if (s.kontext?.nurLesen) {
    // Querschnitts-Review M1/M2: ein Zug mitten im Übertragen schließt den Block, der Stapel läuft weiter
    // und bleibt sichtbar (Anhalten, Ergebnis) — nur ohne Antwortknopf.
    if (!nurLesenOhneStapel(s) && s.erfassung) return [titel, ablageTeil(s, true)];
    return [titel, nurLesenZeile(s, t)];
  }
  const teile: Node[] = [titel];
  if (s.zustand !== 'erfasst' || !s.erfassung) {
    const zone = knoten('div', 'u__ablage');
    zone.dataset['ablage'] = '';
    zone.append(knoten('p', 'u__hinweis', s.zustand === 'liest' ? t.liest : t.ablage));
    const hinweis = typeof s.daten['hinweis'] === 'string' && s.daten['hinweis'].trim()
      ? s.daten['hinweis'] : t.hinweisLeer;
    teile.push(knoten('p', 'u__hinweis', hinweis));
    // R3-b und Rückmeldung 16.11.: der Hinweis der KI kann Lesen oder Ablegen versprechen, das erst nach
    // der Anmeldung geht — vor der Auswahl als Satz, danach sagt es der Chip („braucht eine WLO-Anmeldung“)
    const schalter = s.daten['schalter'] as Record<string, unknown> | undefined;
    if (schalter?.['lesen_nach_anmeldung'] === true) teile.push(knoten('p', 'u__hinweis', t.lesenNachAnmeldung));
    if (schalter?.['ablage_nach_anmeldung'] === true) {
      teile.push(knoten('p', 'u__hinweis', t.ablageNachAnmeldung(hakenVorgesehen(s.daten))));
    }
    teile.push(zone, waehler(s));
    if (s.zustand === 'fehler') {
      const meldung = knoten('p', 'u__hinweis', s.erfassung ? t.nichtsGefunden : t.leseFehler);
      meldung.tabIndex = -1;
      meldung.dataset['fokus'] = 's:fehler';
      teile.push(meldung);
    }
    teile.push(knoten('p', 'u__hinweis', t.datenschutzLeer));
    return teile;
  }
  return [...teile, ...befund(s, s.erfassung)];
}

/** Nur lesen ohne Übertragung in diesem Modul (dann gibt es nur die Zusammenfassung). */
export function nurLesenOhneStapel(s: Pick<UploadSicht, 'kontext' | 'uebertragen'>): boolean {
  const phase = s.uebertragen.lauf?.phase;
  return !!s.kontext?.nurLesen && phase !== 'sendet' && phase !== 'fertig';
}

function nurLesenZeile(s: UploadSicht, t: UploadTexte): HTMLElement {
  const a = s.kontext?.antwort as UploadAntwort | null;
  const z = a?.zahlen;
  const namen = z ? [t.ordner(z.ordner), t.dateien(z.inhalte + z.strukturdokumente)] as const : null;
  // Ältere Antworten (`dokument`, TG-3e) zeigt das Modul weiter, wie sie damals hießen.
  const dokumente = a?.dokumente ?? (a?.dokument ? [a.dokument] : []);
  const abschnitte = t.abschnitte(dokumente.reduce((n, d) => n + d.befund.abschnitte, 0));
  const text = a?.ablage ? uebertragenTexte(s.sprache).nurLesen(a.ablage.abgelegt, a.ablage.gesamt)
    : a?.ort === 'chat' ? t.nurLesenChat(t.dateien(a.dateien?.length ?? 0))
      : a?.ort === 'namen' && namen ? t.nurLesenNamen(...namen)
        : dokumente.length > 1 ? t.nurLesenDokumente(dokumente.length, abschnitte)
          : a?.dokument ? t.nurLesenDokument(a.dokument.name, abschnitte)
            : namen ? t.nurLesen(...namen) : t.nichtVerwendet;
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
  const a = antwortDaten(e, 'erfasst', t.dateiOhneName);
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
  teile.push(...baueBaum(document, { erfassung: e, offen: s.offen, t, sprache: s.sprache, gesperrt: s.auswahlFest }));
  const laeuft = s.chat.laeuft() || s.uebertragen.laeuft();
  const aktiv = wegAktiv(s);
  if (s.uebertragen.lauf) teile.push(ablageTeil(s));
  if (s.chat.lauf) {
    const bereich = knoten('div', 'u__wlo');
    bereich.append(...chatTeile({ t, lauf: s.chat.lauf, anhalten: s.chat.anhalten, aufbewahrungH: lokaleGrenzen(s.daten).aufbewahrungH,
      beschaeftigt: s.beschaeftigt, knoten, knopf }));
    teile.push(bereich);
  }
  const wahl = wahlFuer(s);
  if (!aktiv) teile.push(...frage(s, e, wahl));
  else {
    // Review P2, Befund 2: steht eine Vorschau, gilt der Wert des Servers — wie am Knopf, der ablegt
    const lauf = s.uebertragen.lauf;
    const orte = orteFuer(s.daten, e);
    const erschliessen = lauf && 'plan' in lauf ? lauf.plan.erschliessen : erschliessenFuer(s, orte);
    teile.push(knoten('p', 'u__hinweis', datenschutzSatz(t, orte, wahl, lokaleGrenzen(s.daten), erschliessen)));
  }
  const leiste = knoten('div', 'u__knoepfe');
  if (!aktiv) {
    // Ein Hauptknopf je Ort (P2) — gehen nur die Namen, ist „Nur die Dateinamen senden“ der Hauptknopf.
    if (wahl) leiste.append(knopf(wahl === 'chat' ? t.hierLesen : t.zurVorschau, { hochladen: wahl }, true, s.beschaeftigt));
    leiste.append(knopf(t.nurNamen, { namen: '1' }, !wahl, s.beschaeftigt));
  }
  // Zweites Review P4–P6, MINOR 1: liegen Dateien dieses Blocks in WLO, gilt die Ablage — eine
  // andere Auswahl mit „Nur hier im Chat lesen“ ließe sonst den Ablauf den WLO-Weg nehmen
  const schonInWlo = abgelegtInWlo(s.uebertragen);
  const zurueck = knopf(t.andereAuswahl, { zurueck: '1' }, false, laeuft || schonInWlo);
  leiste.append(zurueck);
  teile.push(leiste);
  if (schonInWlo) {
    const grund = knoten('p', 'u__hinweis', t.schonInWlo);
    grund.id = SCHON_IN_WLO;
    zurueck.setAttribute('aria-describedby', SCHON_IN_WLO);
    teile.push(grund);
  }
  if (s.beschaeftigt && !aktiv) teile.push(knoten('p', 'u__hinweis', t.beschaeftigt));
  return teile;
}

/** Die Kennung des Grunds am gesperrten „Andere Auswahl“ (`aria-describedby`). */
const SCHON_IN_WLO = 'u-schon-in-wlo';

/** Liegt mindestens eine Datei dieses Blocks in WLO? Dann bleibt nur „Im Chat weitermachen“. */
export function abgelegtInWlo(u: Pick<UebertragenAblauf, 'ergebnisse'>): boolean {
  return zaehlung(u.ergebnisse).abgelegt > 0;
}

/** Die Frage „Wo sollen sie verarbeitet werden?“ für diese Auswahl. */
function frage(s: UploadSicht, e: Erfassung<File>, wahl: 'chat' | 'wlo' | null): Node[] {
  const max = maxBytesAblage(s.daten);
  const aus = auswahl(e, max);
  const grenzen = lokaleGrenzen(s.daten);
  const lokal = lokaleAuswahl(e, grenzen);
  return orteTeile({
    t: s.t, orte: orteFuer(s.daten, e), wahl, grenzen, nichtLesbar: lokal.nichtLesbar, zuGross: lokal.zuGross,
    ohneAnmeldung: chatOhneAnmeldung(s.daten),
    ausgelassenWlo: uebertragenTexte(s.sprache).ausgelassen(aus.ohneArt, aus.zuGross, Math.round(max / 1024 / 1024)),
    gesperrt: s.beschaeftigt, erschliessen: hakenGesetzt(s), hakenVorgesehen: hakenVorgesehen(s.daten), knoten,
  });
}

/** U3-3b: der Abschnitt „In deinen persönlichen Bereich in WLO übertragen“ (seit Paket U4 erst, wenn
 *  „Hochladen“ mit Ort wlo begonnen hat). */
function ablageTeil(s: UploadSicht, nurLesen = false): HTMLElement {
  const u = s.uebertragen;
  const teil = knoten('div', 'u__wlo');
  if (!u.lauf) return teil;
  teil.append(...uebertragenTeile({
    t: uebertragenTexte(s.sprache), lauf: u.lauf, ergebnisse: u.ergebnisse, letzte: u.letzte, letzteOffen: u.letzteOffen,
    letzteUmschalten: (offen) => { u.letzteOffen = offen; }, anhalten: u.anhalten, ordnerVerweigert: u.ordnerVerweigert,
    vorgangFehlt: u.vorgang === 'fehlt', weiterLaeuft: u.weiterLaeuft, gesperrt: s.beschaeftigt || s.chat.laeuft(),
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
